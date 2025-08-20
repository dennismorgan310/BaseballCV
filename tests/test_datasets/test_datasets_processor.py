import pytest
import os
from typing import Tuple
from baseballcv.datasets import DatasetProcessor

class TestDataProcessor:
    """
    Test suite for the `DatasetProcessor` class.
    Simple implementation for now due to other dependencies taking care of 
    the data preprocessing steps.
    """
    
    @pytest.fixture(scope='class')
    def setup(self) -> Tuple[DatasetProcessor]:
        """Set up a DataProcessor instance
        
        This fixture initializes a DataProcessor instance. There is only one function to test
        for now until new ideas and strategies for implementation come about.
        
        Args:
            load_tools: Fixture providing tools to load datasets
            
        Returns:
            tuple: A tuple containing:
                - processor (DataProcessor): Initialized DataProcessor instance
                
        """
        processor = DatasetProcessor()
        
        return processor

    def test_generate_photo_dataset(self, setup, tmp_path_factory):
        """
        Makes sure that frames are generated with the correct number.

        Args:
            setup: Fixture of the dataset processor instance
            tmp_path_factory: Fixture of the output frames directory.
        """
        processor = setup
        videos_folder = 'tests/data/test_functions/savant_scraper_ex_videos'
        output_folder = tmp_path_factory.mktemp('processor')

        processor.generate_photo_dataset(video_folder=videos_folder, output_frames_folder=str(output_folder),
                                         max_num_frames=100, frame_stride=5)
        
        frames = os.listdir(output_folder)
        assert len(frames) == 100, 'There should be 100 frames generated'
