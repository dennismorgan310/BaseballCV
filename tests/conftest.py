import pytest
import os
import sys
from typing import Dict
from unittest.mock import Mock
import requests
import multiprocessing as mp
from baseballcv.utilities import BaseballCVLogger

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@pytest.fixture(scope="session", autouse=True)
def setup_multiprocessing() -> None:
    """
    Ensures that the multiprocessing start method is set to 'spawn' for tests.
    
    This fixture runs automatically once per test session and configures the
    multiprocessing start method to 'spawn' which is more compatible with
    pytest and avoids potential issues with forking processes during testing.
    
    Returns:
        None: This fixture doesn't return any value.
    """
    if mp.get_start_method(allow_none=True) != 'spawn':
        mp.set_start_method('spawn', force=True)
    
    return None

@pytest.fixture(scope='session')
def mock_responses() -> tuple:
    """
    Provides mock HTTP responses for testing network requests.
    
    Creates and returns two mock response objects:
    1. A success response (200) with mock file content and headers
    2. An error response (404) that raises an HTTPError when raise_for_status is called
    
    These mock responses can be used to test functions that make HTTP requests
    without actually connecting to external services.

    Returns:
        tuple: A tuple containing (success_response, error_response) mock objects.
    """
    success = Mock()
    success.status_code = 200
    success.content = b"mock file content"
    success.headers = {"Content-Disposition": "attachment; filename=model.pt"}
    success.raise_for_status.return_value = None  

    # Create error response
    error = Mock()
    error.status_code = 404
    error.json.return_value = {"error": "File not found"}
    http_error = requests.exceptions.HTTPError("404 Client Error: Not Found")
    http_error.response = error  
    error.raise_for_status.side_effect = http_error  

    return success, error

@pytest.fixture(scope='session') # Only run once
def load_dataset() -> Dict[str, str]:
    """
    Returns the respective dataset path for each tested dataset type. 
    Use this for any tests on datasets, not datasets in the API due to 
    their size, which can slow down testing speed.

    Returns:
        Dict[str, str]: An iterable of each dataset stored in a dictionary.
    """
    return {
        'coco': 'tests/data/test_datasets/coco_stuff',
        'jsonl': 'tests/data/test_datasets/jsonl_stuff',
        'pascal': 'tests/data/test_datasets/pascal_stuff',
        'yolo': 'tests/data/test_datasets/yolo_stuff'
    }

@pytest.fixture(scope='session') # Only run once
def logger() -> BaseballCVLogger:
    """
    Creates and returns a BaseballCVLogger instance that can be used in tests
    to verify the functionality of logging and logging messages.

    Returns:
        BaseballCVLogger: An instance of BaseballCVLogger.
    """
    return BaseballCVLogger.get_logger("TestLogger")

@pytest.fixture
def reset_logger_registry():
    """
    Reset the BaseballCVLogger registry before and after each test.
    
    This fixture ensures that each test starts with a clean logger registry
    and restores the original registry after the test completes.
    
    Yields:
        None
    """
    original_loggers = BaseballCVLogger._loggers.copy()
    BaseballCVLogger._loggers = {}
    yield
    BaseballCVLogger._loggers = original_loggers


# Network testing configurations
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "network: mark test as requiring network access"
    )

def pytest_runtest_setup(item):
    if "network" in item.keywords and os.environ.get("SKIP_NETWORK_TESTS", "0") == "1":
        pytest.skip("Network tests disabled")