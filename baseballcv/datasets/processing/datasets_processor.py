import logging
import os
import shutil
import random
from sklearn.model_selection import train_test_split
from collections import defaultdict
import supervision as sv
from typing import Dict, Tuple
from autodistill.detection import CaptionOntology
import json
from baseballcv.utilities import BaseballCVLogger, ProgressBar

class DatasetProcessor:
    def __init__(self):
        self.logger = BaseballCVLogger.get_logger(self.__class__.__name__)

    def generate_photo_dataset(
            self,
            video_folder: str,
            output_frames_folder: str = "cv_dataset",
            max_num_frames: int = 6000,
            frame_stride: int = 30
        ) -> None:

        os.makedirs(output_frames_folder, exist_ok=True)

        video_files = [f for f in os.listdir(video_folder) if f.endswith(('.mp4', '.mov', '.mts'))]

        if not video_files:
            raise NotADirectoryError(f'No videos found in folder {video_folder}')
        
        games = defaultdict(list)
        for video_file in video_files:
            game_id = os.path.splitext(video_file)[0][:6]
            games[game_id].append(video_file)
        
        frames_per_game = max_num_frames // len(games)
        remaining_frames = max_num_frames % len(games)

        extracted_frames = 0
        for game_id, game_videos in games.items():
            frames_for_game = frames_per_game + (1 if remaining_frames > 0 else 0)
            remaining_frames = max(0, remaining_frames - 1)
            
            frames_per_video = frames_for_game // len(game_videos)
            extra_frames = frames_for_game % len(game_videos)
            
            for i, video_file in enumerate(game_videos):
                frames_to_extract = frames_per_video + (1 if i < extra_frames else 0)
                video_path = os.path.join(video_folder, video_file)
                
                video_name = os.path.splitext(video_file)[0]
                image_name_pattern = f"{game_id}_{video_name}-{{:05d}}.png"
                
                frame_count = 0
                with sv.ImageSink(target_dir_path=output_frames_folder, image_name_pattern=image_name_pattern) as sink:
                    for image in sv.get_video_frames_generator(source_path=str(video_path), stride=frame_stride):
                        sink.save_image(image=image)
                        frame_count += 1
                        
                        extracted_frames += 1
                        if frame_count >= frames_to_extract:
                            break
        
        self.logger.info(f"Extracted {extracted_frames} frames from {len(video_files)} videos over {len(games)} games.")


# TODO: Fix implementation for this
    def automated_annotation(self, 
                             model_alias: str = None,
                             model_type: str = 'detection',
                             image_dir: str = "cv_dataset",
                             output_dir: str = "labeled_dataset", 
                             conf: float = .80, 
                             device: str = 'cpu',
                             mode: str = 'autodistill',
                             ontology: dict = None,
                             extension: str = '.jpg',
                             batch_size: int = 100) -> str:
        """
        Automatically annotates images using pre-trained YOLO model from BaseballCV repo. The annotated output
        consists of image files in the output directory, and label files in the subfolder "annotations" to 
        work with annotation tools.

        Note: The current implementation only supports YOLO detection models. 

        Args:
            model_alias (str): Alias of model to utilize for annotation.
            model_type (str): Type of CV model to utilize for annotation. Default is 'detection'.
            image_dir (str): Directory with images to annotate. Default is "cv_dataset".
            output_dir (str): Directory to save annotated images / labels. Default is "labeled_dataset".
            conf (float): Minimum confidence threshold for detections. Default is 0.80.
            device (str): Device to run model on ('cpu', 'mps', 'cuda'). Default is 'cpu'. MPS is not supported for AutoDistill.
            mode (str): Mode to use for annotation. Default is 'autodistill'.
            ontology (dict): Ontology to use for annotation. Default is None.
            extension (str): Extension of images to annotate. Default is '.jpg'.
            batch_size (int): Number of images to process in each batch. Default is 100.

        Returns:
            None: Saves annotated images and labels to the output directory.
        """
        os.makedirs(output_dir, exist_ok=True)
        annotations_dir = os.path.join(output_dir, "annotations")
        os.makedirs(annotations_dir, exist_ok=True)

        if mode == 'autodistill': #use RF Autodistill library
            if ontology is not None:
                self.logger.info(f"Using Autodistill mode with ontology: {ontology}")
                self.logger.info(f"This may take a while...")
                from autodistill_grounded_sam import GroundedSAM #lazy load to prevent GroundingDINO warning
                
                auto_model = GroundedSAM(ontology=CaptionOntology(ontology))
                all_images = [f for f in os.listdir(image_dir) if f.endswith(extension)]
                total_images = len(all_images)
                self.logger.info(f"Found {total_images} images to process")
                
                total_batches = (total_images + batch_size - 1) // batch_size
                with ProgressBar(total=total_batches, desc="Processing image batches") as pbar:
                    for i in range(0, total_images, batch_size):
                        batch_images = all_images[i:i+batch_size]
                        
                        temp_input_dir = os.path.join(image_dir, f"temp_batch_{i//batch_size}")
                        os.makedirs(temp_input_dir, exist_ok=True)                      
                        for img in batch_images: shutil.copy(os.path.join(image_dir, img), os.path.join(temp_input_dir, img))
                        
                        auto_model.label(
                            input_folder=str(temp_input_dir),
                            output_folder=str(output_dir),
                            extension=extension
                        )
                        
                        shutil.rmtree(temp_input_dir)
                        pbar.update(1)
                
                self.logger.info("Annotation process complete.")
                return output_dir
            else:
                raise ValueError("ontology must be provided when using autodistill mode")
        
        else: #Legacy Version for using models from YOLO repo
            if model_alias is not None:
                model = YOLO(self.LoadTools.load_model(model_alias))
                self.logger.info(f"Model loaded: {model}")
            else:
                raise ValueError("model_alias must be provided when using legacy mode")

            annotation_tasks = [image_file for image_file in os.listdir(image_dir)]

            with ProgressBar(total=len(annotation_tasks), desc="Annotating images") as pbar:
                for image_file in annotation_tasks:
                    image_path = os.path.join(image_dir, image_file)
                    annotations = []

                    results = model.predict(source=image_path, save=False, conf=conf, device=device, verbose=False)
                    
                    if model_type == 'detection':
                        for result in results:
                            for box in result.boxes:
                                cls = int(box.cls)
                                xywhn = box.xywhn[0].tolist()
                                if len(xywhn) == 4:
                                    x_center, y_center, width, height = xywhn
                                    annotations.append(f"{cls} {x_center} {y_center} {width} {height}")
                                else:
                                    self.logger.warning(f"Invalid bounding box for {image_file}: {xywhn}")

                    #TODO: Add annotation format for YOLO Keypoint, Segmentation, and Classification models

                    if annotations:
                        shutil.copy(image_path, output_dir)
                        output_file = os.path.join(annotations_dir, os.path.splitext(image_file)[0] + '.txt')
                        os.makedirs(os.path.dirname(output_file), exist_ok=True)
                        with open(output_file, 'w') as f:
                            f.write('\n'.join(annotations))
                    
                    pbar.update(1)
                    
                self.logger.info("Annotation process complete.")
                return output_dir
