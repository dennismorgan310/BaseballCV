from supervision import DetectionDataset, Detections
from supervision.detection.utils import polygon_to_mask
from supervision.dataset.utils import save_dataset_images, approximate_mask_with_polygons
import os
from pathlib import Path
import cv2
import numpy as np
import json
import re
import glob
from baseballcv.utilities import BaseballCVLogger
from typing import Tuple, List, Optional, Dict

# What's left to do:
# 1. Fix dumb bug for the masking
# 2. Write unit tests + check for edge cases

def jsonl_to_detections(image_annotations: str, 
                        resolution_wh: Tuple[int, int], with_masks: bool,
                        classes: Dict[str, int]) -> Detections:
        
        if not image_annotations:
            return Detections.empty()
        
        w, h = resolution_wh

        if w <= 0 and h <=0:
            raise ValueError(f'Both dimensions must be positive. Got width {w} and height {h}')

        pattern = re.compile(r"(?<!<loc\d{4}>)<loc(\d{4})><loc(\d{4})><loc(\d{4})><loc(\d{4})> ([\w\s\-]+)")
        matches = pattern.findall(image_annotations)

        matches = np.array(matches) if matches else np.empty((0, 5))

        xyxy, class_name = matches[:, [1, 0, 3, 2]], matches[:, 4]
        xyxy = xyxy.astype(int) / 1024 * np.array([w, h, w, h])
        class_name = np.char.strip(class_name.astype(str))

        filter = np.array([name in classes for name in class_name], dtype=bool)
        xyxy = xyxy[filter]
        class_name = class_name[filter]
        class_id = np.array([classes.get(name) for name in class_name])

        relative_polygons = [np.array([[x1, y1], [x2, y1], [x2, y2], [x1, y2]]) for (x1, y1, x2, y2) in xyxy]

        if with_masks:
            polygons = [
                    (polygon * np.array(resolution_wh)).astype(int) for polygon in relative_polygons
                ]
            mask = np.array(
                [
                    polygon_to_mask(polygon=polygon, resolution_wh=resolution_wh)
                    for polygon in polygons
                ],
                dtype=bool,
            )
            
            if not np.any(mask):
                # This is some weird bug that's caused by the whol array being False. Need to figure out why.
                return Detections.empty()

            return Detections(xyxy=xyxy, class_id=class_id, mask=mask)

        return Detections(xyxy=xyxy, class_id=class_id)

def read_jsonl(path: str) -> List[dict]:
        data = []
        with open(str(path), 'r') as f:
            json_lines = list(f)

        for json_line in json_lines:
            result = json.loads(json_line)
            data.append(result)
        
        return data

def detections_to_jsonl_annotations(
        detections: Detections, image_shape: Tuple[int, int, int],
        image_name: str, class_labels: List[str],
        min_image_area_percentage: float, max_image_area_percentage: float,
        approximation_percentage: float
        ) -> Dict[str, str]:

    classes_dict = {identifier: name for identifier, name in enumerate(class_labels)}

    prefix = 'detect ' + ' ; '.join(class_labels)
    
    h, w, _ = image_shape
    suffixes = []
    
    for xyxy, mask, _, class_id, _, _ in detections:
        label = classes_dict.get(class_id)

        if mask is not None:
            polygons = approximate_mask_with_polygons(
                mask=mask,
                min_image_area_percentage=min_image_area_percentage,
                max_image_area_percentage=max_image_area_percentage,
                approximation_percentage=approximation_percentage
            )

            for polygon in polygons:
                scaled_polygon = (polygon * 1024 / np.array([w, h])).astype(int)
                suffix = ''.join(f"<loc{coord:04d}>" for point in scaled_polygon for coord in point)
                suffix += f" {label}"
                suffixes.append(suffix)

        else:
            yxyx = xyxy[[1, 0, 3, 2]]
            yxyx = (yxyx * 1024 / np.array([w, h, w, h])).astype(int)

            suffix = ''.join(f"<loc{num:04d}>" for num in yxyx) + f" {label}"

            suffixes.append(suffix)
    
    suffixes = ' ; '.join(suffixes)

    return {
        'image_path': image_name,
        'prefix': prefix,
        'suffix': suffixes
    }

def save_jsonl_file(lines: list, file_path: str) -> None:
    with open(file_path, 'w', encoding='utf-8') as f:
        for line in lines:
            f.write(json.dumps(line) + '\n')

class NewDetectionsDataset(DetectionDataset):
    """
    A Monkey Patch Class of Roboflow's `DetectionDataset` with a JSONL implementation in place
    """

    def __init__(self, classes, images, annotations) -> None:
        super().__init__(classes, images, annotations)

    @classmethod
    def from_yolo(cls, *args, **kwargs) -> "NewDetectionsDataset":
        base = DetectionDataset.from_yolo(*args, **kwargs)
        return cls._from_base(base)

    @classmethod
    def from_coco(cls, *args, **kwargs) -> "NewDetectionsDataset":
        base = DetectionDataset.from_coco(*args, **kwargs)
        return cls._from_base(base)
    
    @classmethod
    def from_pascal_voc(cls, *args, **kwargs) -> "NewDetectionsDataset":
        base = DetectionDataset.from_pascal_voc(*args, **kwargs)
        return cls._from_base(base)

    @classmethod
    def _from_base(cls, base: DetectionDataset):
        # Cast DetectionDataset → NewDetectionsDataset
        obj = cls.__new__(cls)
        obj.__dict__ = base.__dict__
        return obj

    @classmethod
    def from_jsonl(cls, images_directory_path: str, annotations_path: str, force_masks: bool) -> "NewDetectionsDataset":
        jsonl_data = read_jsonl(path=annotations_path)

        images = []
        annotations = {}

        # assume prefix is the same throughout JSONL
        classes_dict = None
        assigned_class = False

        for jsonl_image in jsonl_data:
            # Extract name, width, height from the name + suffix
            image_name = jsonl_image['image']

            image_path = os.path.join(images_directory_path, image_name)

            (image_height, image_width, _) = cv2.imread(image_path).shape

            pattern = re.compile(r'\b(?!detect\b)(\w+)')

            classes = pattern.findall(jsonl_image['prefix'])

            if assigned_class == False:
                classes_dict = {name: identifier for identifier, name in enumerate(classes)}
                assigned_class = True


            annotation = jsonl_to_detections(
                image_annotations=jsonl_image['suffix'],
                resolution_wh=(image_width, image_height),
                with_masks=force_masks,
                classes=classes_dict
            )

            if annotation.is_empty() and force_masks:
                continue
            
            images.append(image_path)
            annotations[image_path] = annotation

        return NewDetectionsDataset(classes=classes, images=images, annotations=annotations)
    
    def as_jsonl(self: "NewDetectionsDataset",
        images_directory_path: Optional[str] = None,
        annotations_path: Optional[str] = None,
        min_image_area_percentage: float = 0.0,
        max_image_area_percentage: float = 1.0,
        approximation_percentage: float = 0.0,
    ) -> None:
        """
        Exports the dataset to JSONL format. This method saves the images
        and their corresponding annotations in the Paligemma JSONL format.

        Args:
            images_directory_path (Optional[str], optional): The path where the images are saved. Defaults to None.
            annotations_path (Optional[str], optional): The path where the JSONL annotations are saved. Defaults to None.
            min_image_area_percentage (float, optional): The minimum percentage of
                detection area relative to
                the image area for a detection to be included.
                Argument is used only for segmentation datasets. Defaults to 0.0.
            max_image_area_percentage (float, optional): The maximum percentage
                of detection area relative to
                the image area for a detection to be included.
                Argument is used only for segmentation datasets. Defaults to 1.0.
            approximation_percentage (float, optional): The percentage of
                polygon points to be removed from the input polygon,
                in the range [0, 1). Argument is used only for segmentation datasets. Defaults to 0.0.
        """

        if images_directory_path:
            save_dataset_images(
                dataset=self, 
                images_directory_path=images_directory_path
            )
        
        if annotations_path:
            Path(annotations_path).parent.mkdir(parents=True, exist_ok=True)

            lines = []
            for image_path, image, annotation in self:
                image_name = Path(image_path).name

                line = detections_to_jsonl_annotations(
                    detections=annotation,
                    image_shape = image.shape,
                    image_name=image_name,
                    class_labels = self.classes,
                    min_image_area_percentage=min_image_area_percentage,
                    max_image_area_percentage=max_image_area_percentage,
                    approximation_percentage=approximation_percentage
                )

                lines.append(line)
            
            save_jsonl_file(lines=lines, file_path=annotations_path)
              
class _BaseFmt:

    def __init__(self, root_dir: str, force_masks: bool, is_obb: bool):

        self.root_dir = root_dir
        self.force_masks = force_masks
        self.is_obb = is_obb
        self.logger = BaseballCVLogger.get_logger(self.__class__.__name__)

        dir_list = os.listdir(self.root_dir)

        for item in dir_list:
            if item in ['train', 'test', 'valid', 'dataset']:
                full_path = os.path.join(self.root_dir, item)
                setattr(self, f"{item}_dir", full_path)
        
        if not all(hasattr(self, attr) for attr in ['train_dir', 'test_dir']):
            self.logger.warning('Please ensure you have a train AND test directory. ' \
            'Please refer to the README for details on convention. ' \
            'If you are using, JSONL, you just need a dataset directory.')

        self.new_dir = f"{self.root_dir}_conversion"
        os.makedirs(self.new_dir, exist_ok=True)

    @property
    def detections_data(self): raise NotImplementedError

    def to_coco(self, detections_data: tuple):
        train_det, test_det, val_det = detections_data

        train_det.as_coco(images_directory_path=os.path.join(self.new_dir, 'train'), 
                          annotations_path=os.path.join(self.new_dir, 'train', '_annotations.coco.json'))
        
        test_det.as_coco(images_directory_path=os.path.join(self.new_dir, 'test'), 
                          annotations_path=os.path.join(self.new_dir, 'test', '_annotations.coco.json'))
        
        if val_det:
            val_det.as_coco(images_directory_path=os.path.join(self.new_dir, 'val'), 
                          annotations_path=os.path.join(self.new_dir, 'valid', '_annotations.coco.json'))
            
    def to_yolo(self, detections_data: tuple):
        train_det, test_det, val_det = detections_data

        train_det.as_yolo(images_directory_path=os.path.join(self.new_dir, 'train', 'images'),
                          annotations_directory_path=os.path.join(self.new_dir, 'train', 'labels'),
                          data_yaml_path=os.path.join(self.new_dir, 'train_detections'))
        
        test_det.as_yolo(images_directory_path=os.path.join(self.new_dir, 'test', 'images'),
                          annotations_directory_path=os.path.join(self.new_dir, 'test', 'labels'),
                          data_yaml_path=os.path.join(self.new_dir, 'test_detections'))
        
        if val_det:
            val_det.as_yolo(images_directory_path=os.path.join(self.new_dir, 'valid', 'images'),
                          annotations_directory_path=os.path.join(self.new_dir, 'valid', 'labels'),
                          data_yaml_path=os.path.join(self.new_dir, 'valid_detections'))

    def to_pascal(self, detections_data: tuple): 
        train_det, test_det, val_det = detections_data

        train_det.as_pascal_voc(images_directory_path=os.path.join(self.new_dir, 'train'), 
                          annotations_directory_path=os.path.join(self.new_dir, 'train'))
        
        test_det.as_pascal_voc(images_directory_path=os.path.join(self.new_dir, 'test'), 
                          annotations_directory_path=os.path.join(self.new_dir, 'test'))
        
        if val_det:
            val_det.as_pascal_voc(images_directory_path=os.path.join(self.new_dir, 'valid'), 
                          annotations_directory_path=os.path.join(self.new_dir, 'valid'))

    def to_jsonl(self, detections_data: tuple):
        train_det, test_det, val_det = detections_data

        train_det.as_jsonl(images_directory_path=os.path.join(self.new_dir, 'dataset'), 
                          annotations_path=os.path.join(self.new_dir, 'dataset', '_annotations.train.jsonl'))
        
        test_det.as_jsonl(images_directory_path=os.path.join(self.new_dir, 'dataset'), 
                          annotations_path=os.path.join(self.new_dir, 'dataset', '_annotations.test.jsonl'))
        
        if val_det:
            val_det.as_jsonl(images_directory_path=os.path.join(self.new_dir, 'dataset'), 
                          annotations_path=os.path.join(self.new_dir, 'dataset', '_annotations_valid.jsonl'))

class YOLOFmt(_BaseFmt):
    @property
    def detections_data(self):

        train_detections, test_detections, val_detections = (None, None, None)
        try:
            yaml_pth = glob.glob(os.path.join(self.root_dir, '**', '*.y?ml'), recursive=True)[0]
        except IndexError:
            self.logger.error('Make sure you have a specified yaml file in your directory.')

        train_detections = NewDetectionsDataset.from_yolo(
            images_directory_path=os.path.join(self.train_dir, 'images'),
            annotations_directory_path=os.path.join(self.train_dir, 'labels'),
            data_yaml_path=yaml_pth, force_masks=self.force_masks, is_obb=self.is_obb
            )
        
        test_detections = NewDetectionsDataset.from_yolo(
                images_directory_path=os.path.join(self.test_dir, 'images'),
                annotations_directory_path=os.path.join(self.test_dir, 'labels'),
                data_yaml_path=yaml_pth, force_masks=self.force_masks, is_obb=self.is_obb
                )

        if hasattr(self, 'valid_dir'):
            val_detections = NewDetectionsDataset.from_yolo(
                images_directory_path=os.path.join(self.valid_dir, 'images'),
                annotations_directory_path=os.path.join(self.valid_dir, 'labels'),
                data_yaml_path=yaml_pth, force_masks=self.force_masks, is_obb=self.is_obb
                )
        
        return (train_detections, test_detections, val_detections)
        
    def to_coco(self):
        super().to_coco(detections_data=self.detections_data)

    def to_pascal(self):
        super().to_pascal(detections_data=self.detections_data)

    def to_jsonl(self):
        super().to_jsonl(detections_data=self.detections_data)
        
class COCOFmt(_BaseFmt):
    @property
    def detections_data(self):

        train_detections, test_detections, val_detections = (None, None, None)

        train_detections = NewDetectionsDataset.from_coco(
            images_directory_path=self.train_dir,
            annotations_path=glob.glob(os.path.join(self.train_dir, '*.json'))[0],
            force_masks=self.force_masks
            )
        
        test_detections = NewDetectionsDataset.from_coco(
                images_directory_path=self.test_dir,
                annotations_path=glob.glob(os.path.join(self.test_dir, '*.json'))[0],
                force_masks=self.force_masks
                )

        if hasattr(self, 'valid_dir'):
            val_detections = NewDetectionsDataset.from_coco(
                images_directory_path=self.valid_dir,
                annotations_path=glob.glob(os.path.join(self.valid_dir, '*.json'))[0],
                force_masks=self.force_masks
                )
            
        return (train_detections, test_detections, val_detections)
        
    def to_yolo(self):
        super().to_yolo(detections_data=self.detections_data)

    def to_pascal(self):
        super().to_pascal(detections_data=self.detections_data)

    def to_jsonl(self):
        super().to_jsonl(detections_data=self.detections_data)

class PascalFmt(_BaseFmt):
    @property
    def detections_data(self):

        train_detections, test_detections, val_detections = (None, None, None)

        train_detections = NewDetectionsDataset.from_pascal_voc(
            images_directory_path=self.train_dir,
            annotations_path=self.train_dir,
            force_masks=self.force_masks
            )
        
        test_detections = NewDetectionsDataset.from_pascal_voc(
                images_directory_path=self.test_dir,
                annotations_path=self.test_dir,
                force_masks=self.force_masks
                )

        if hasattr(self, 'valid_dir'):
            val_detections = NewDetectionsDataset.from_pascal_voc(
                images_directory_path=self.valid_dir,
                annotations_path=self.valid_dir,
                force_masks=self.force_masks
                )
            
        return (train_detections, test_detections, val_detections)

    def to_yolo(self):
        super().to_yolo(detections_data=self.detections_data)
    
    def to_coco(self):
        super().to_coco(detections_data=self.detections_data)
    
    def to_jsonl(self):
        super().to_jsonl(detections_data=self.detections_data)

class JsonLFmt(_BaseFmt):
    
    @property
    def detections_data(self):
        train_detections, test_detections, val_detections = (None, None, None)

        if not hasattr(self, 'dataset_dir'):
            self.logger.error('There needs to be a dataset directory containing the jsonl and image files')
            return (train_detections, test_detections, val_detections)

        train_detections = NewDetectionsDataset.from_jsonl(
            images_directory_path=self.dataset_dir,
            annotations_path=os.path.join(self.dataset_dir, '_annotations.train.jsonl'),
            force_masks=self.force_masks
            )

        test_detections = NewDetectionsDataset.from_jsonl(
                images_directory_path=self.dataset_dir,
                annotations_path=os.path.join(self.dataset_dir, '_annotations.test.jsonl'),
                force_masks=self.force_masks
                )

        if hasattr(self, 'valid_dir'):
            val_detections = NewDetectionsDataset.from_jsonl(
                images_directory_path=self.dataset_dir,
                annotations_path=os.path.join(self.dataset_dir, '_annotations.valid.jsonl'),
                force_masks=self.force_masks
                )
        
        return (train_detections, test_detections, val_detections)

    def to_coco(self):
        return super().to_coco(detections_data=self.detections_data)
    
    def to_pascal(self):
        return super().to_pascal(detections_data=self.detections_data)
    
    def to_yolo(self):
        return super().to_yolo(detections_data=self.detections_data)