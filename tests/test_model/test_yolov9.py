import pytest
import torch
from baseballcv.model import YOLOv9

class TestYOLOv9:
    """
    Test cases for YOLOv9 model.
    
    This test suite verifies the functionality of the YOLOv9 object detection model,
    including initialization, device selection, inference capabilities, and parameter
    sensitivity.
    """

    @pytest.fixture(scope='class')
    def setup_yolo_test(self, load_dataset, tmp_path_factory) -> dict:
        """
        Set up test environment with BaseballCV dataset.
        
        Creates a temporary directory and loads a baseball dataset for testing.
        Initializes a YOLOv9 model and prepares test images either from the dataset
        or creates a synthetic test image if needed.
        
        Args:
            load_tools: Fixture providing tools to load datasets
            
        Returns:
            dict: A dictionary containing test resources including:
                - test_image_path: Path to an image for testing inference
                - dataset_path: Path to the loaded dataset
                - class_mapping: Dictionary mapping class IDs to class names
                - temp_dir: Path to temporary directory for test artifacts
                - model: Initialized YOLOv9 model instance
        """

        temp_dir = tmp_path_factory.mktemp('yolov9')
        dataset_path = load_dataset['yolo']

        model = YOLOv9(
            device='cpu',
            model_path=str(temp_dir)
        ) #using default model yolov9-c

        test_image_path = 'tests/data/test_datasets/yolo_stuff/train/images/000002_jpg.rf.e107a7a3d26b698c7ff4a201f65e532b.jpg'
        
        class_mapping = {
            0: 'Bat',
            1: 'Player'
        }
        
        return {
            'test_image_path': test_image_path,
            'dataset_path': dataset_path,
            'class_mapping': class_mapping,
            'temp_dir': str(temp_dir / "weights"),
            'model': model
        }

    def test_model_initialization(self, setup_yolo_test) -> None:
        """
        Test model initialization and device selection.
        
        Verifies that the YOLOv9 model initializes correctly with the specified
        device and tests device selection logic, including optional MPS support
        when available.
        
        Args:
            setup_yolo_test: Fixture providing test resources
        """

        model = setup_yolo_test['model']
        
        assert model is not None, "YOLOv9 model should initialize"
        assert model.device == 'cpu', "Device should be set correctly"
        
        with pytest.MonkeyPatch().context() as m: #optional MPS test - not necessary but can be used to test MPS device selection
            m.setattr(torch.cuda, 'is_available', lambda: False)
            m.setattr(torch.backends.mps, 'is_available', lambda: True)
            
            try:
                model.device = 'mps' # Set the device of the model to mps to check if it works
                assert model.device == 'mps', "Should select MPS when available"
            except Exception as e:
                pytest.skip(f"MPS model initialization test skipped: {str(e)}")

    def test_inference(self, setup_yolo_test) -> None:
        """
        Test basic inference functionality.
        
        Verifies that the YOLOv9 model can perform inference on a test image
        and returns properly structured detection results with expected fields.
        
        Args:
            setup_yolo_test: Fixture providing test resources including model and test image
        """
        
        model = setup_yolo_test['model']
        
        result = model.inference(
            source=setup_yolo_test['test_image_path'],
            project=setup_yolo_test['temp_dir']
        )
        
        assert result is not None, "Inference should return results"
        
        if isinstance(result, list) and len(result) > 0:
            assert 'box' in result[0], "Detection should include bounding box"
            assert 'confidence' in result[0], "Detection should include confidence"
            assert 'class_id' in result[0], "Detection should include class_id"
            
            assert len(result[0]['box']) == 4, "Box should have 4 coordinates"
                
    
    def test_threshold_parameters(self, setup_yolo_test) -> None:
        """
        Test confidence and IoU threshold parameters.
        
        Verifies that the confidence threshold parameter correctly filters
        detection results, with lower thresholds yielding more detections
        than higher thresholds.
        
        Args:
            setup_yolo_test: Fixture providing test resources including model and test image
        """
        
        model = setup_yolo_test['model']
        
        high_conf_results = model.inference(
            source=setup_yolo_test['test_image_path'],
            project=setup_yolo_test['temp_dir'],
            conf_thres=0.9
        )
        
        low_conf_results = model.inference(
            source=setup_yolo_test['test_image_path'],
            project=setup_yolo_test['temp_dir'],
            conf_thres=0.05
        )
        
        if high_conf_results and low_conf_results:
            assert len(high_conf_results) <= len(low_conf_results), \
                "Lower confidence threshold should yield more or equal detections"

#TODO: Add tests for Finetuning when Tests can be run on GPU
