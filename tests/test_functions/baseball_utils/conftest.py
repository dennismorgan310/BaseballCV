import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
from typing import Generator, Any

@pytest.fixture(scope='module')
def mock_savant_scraper() -> Generator[MagicMock, Any, None]:
    """
    Mocks the `BaseballSavVideoScraper` class to reduce network calls to the internet.
    What this does it mock the return values as the function works, but want to make sure hidden
    functionality works consistently.

    Yields:
        Generator[MagicMock, Any, None]: The MagickMock instance of the scraper class
    """
    with patch('baseballcv.functions.savant_scraper.BaseballSavVideoScraper') as MockScraper:

        mock_instance = MockScraper.return_value
        mock_instance.download_folder = 'tests/data/test_functions/savant_scraper_ex_videos'

        mock_instance.run_executor.return_value = None

        mock_instance.get_play_ids_df.return_value = pd.read_csv('tests/data/test_functions/savant_df_ex/mock_df.csv')

        mock_instance.cleanup_savant_videos = None

        yield mock_instance

# TODO: Add mock implementation for load tools that mocks the loading in of the model ONCE