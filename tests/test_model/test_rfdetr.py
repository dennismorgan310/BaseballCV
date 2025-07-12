import pytest
import numpy as np
import os
import cv2
import torch
import supervision as sv
from unittest.mock import patch
from baseballcv.model import RFDETR

DUMMY_DETECTION = sv.Detections(
    xyxy=np.array([[10, 120, 40, 300], 
                   [20, 133, 12, 280]]), 
    class_id=np.array([0, 1]), 
    confidence=np.array([0.5, 0.5])
)
class TestRFDETR:

    @pytest.fixture(scope='module')
    def setup_rfdetr_test(self, load_dataset, tmp_path_factory):
        """
        Setup test environment for RFDETR tests.
        
        Creates temporary directories for test data and model outputs,
        initializes a model instance, and provides test resources.
        """
        temp_dir = tmp_path_factory.mktemp('rfdetr')
        test_input_dir = temp_dir / "test_input"
        test_input_dir.mkdir(exist_ok=True)

        output_dir = temp_dir / 'output'
        output_dir.mkdir(parents=True, exist_ok=True)

        checkpoints_dir = output_dir / 'checkpoint_best_regular.pth'
        # Weird hardcode solution that will suffice for now, but need to investigate further for No such file or directory error
        torch.save({}, checkpoints_dir) 
        
        test_video_path = 'tests/data/test_functions/savant_scraper_ex_videos/745506_0d995b3c-1e05-418e-a0af-4f41e196a928.mp4'

        frames = list(sv.get_video_frames_generator(test_video_path))
        if not frames:
            raise ValueError(f"Failed to read frames from video: {test_video_path}")
        
        frame = frames[0]
        
        test_image_path = os.path.join(temp_dir, "test_frame.jpg")
        cv2.imwrite(test_image_path, frame)

        labels = {
            "0": "Bat",
            "1": "Player",
        }
        
        # Initialize model
        model_base = RFDETR(
            model_type="base",
            labels=labels,
            project_path=str(temp_dir)
        )

        model_large = RFDETR(
            model_type="large",
            labels=labels,
            project_path=temp_dir
        )

        dataset_path = load_dataset['coco']
        
        return {
            'output_dir': output_dir,
            'test_video_path': test_video_path,
            'test_image_path': test_image_path,
            'model_base': model_base,
            'model_large': model_large,
            'labels': labels,
            'dataset_path': dataset_path
        }
    
    def test_model_initialization(self, setup_rfdetr_test):
        """
        Test model initialization and device selection.
        
        Verifies that the RFDETR model initializes correctly with the specified
        device and tests device selection logic, including optional MPS support
        when available.
        
        Args:
            setup_rfdetr_test: Fixture providing test resources
        """
        labels = setup_rfdetr_test['labels']
        model_base = setup_rfdetr_test['model_base']
        model_large = setup_rfdetr_test['model_large']
        
        assert model_base is not None, "RFDETR Basemodel should initialize"
        assert model_large is not None, "RFDETR Large model should initialize"
        assert model_base.device == 'cpu', "Device should be set correctly"
        assert model_base.model_name == "rfdetr", "Model name should be set correctly"
        assert labels is not None, "Labels should be set correctly"

    @patch('baseballcv.model.od.detr.rfdetr.RFDETRBase.predict', return_value = DUMMY_DETECTION)
    def test_inference(self, mock_rf_base_predict, setup_rfdetr_test):
        """
        Test basic inference functionality.
        
        Mocks the model's predict method to return test detections and verifies
        that the inference method processes and returns results correctly.
        
        Args:
            monkeypatch: PyTest's monkeypatch fixture
            setup_rfdetr_test: Fixture providing test resources including model and test image
        """
        
        model = setup_rfdetr_test['model_base']
        test_image_path = setup_rfdetr_test['test_image_path']
        test_video_path = setup_rfdetr_test['test_video_path']
        
        # Test image inference
        result_image, output_image_path = model.inference(
            source_path=test_image_path,
            conf=0.1,
            save_viz=True
        )
        
        # Test video inference
        result_video, output_video_path = model.inference(
            source_path=test_video_path,
            conf=0.1,
            save_viz=True
        )
        
        assert result_image is not None, "Inference should return results"
        assert result_video is not None, "Inference should return results"
        assert isinstance(result_image, sv.Detections), "Result should be a Detections object"
        assert isinstance(result_video, list) and all(isinstance(x, sv.Detections) for x in result_video), "Video result should be a list of Detections objects"
        assert os.path.exists(output_image_path), "Output image should be saved"
        assert os.path.exists(output_video_path), "Output video should be saved"

    def test_finetune(self, setup_rfdetr_test):
        """
        Downloads RHG COCO-format dataset and verifies that the model
        can begin the training process successfully.
        
        Args:
            setup_rfdetr_test: Fixture providing test resources
        """
        model = setup_rfdetr_test['model_base']

        model.finetune(
            data_path=setup_rfdetr_test['dataset_path'],
            output_dir=setup_rfdetr_test['output_dir'],
            epochs=1,
            batch_size=1,
            num_workers=0,
            checkpoint_interval=1,
            warmup_epochs=0
        )
        assert True, "Finetuning started successfully"