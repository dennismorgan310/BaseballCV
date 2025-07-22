from pathlib import Path
from sys import call_tracing
import requests
import os
from tqdm import tqdm
import zipfile
import io
from typing import Union
import shutil
from huggingface_hub import snapshot_download, hf_hub_download
from baseballcv.utilities import BaseballCVLogger, ProgressBar
import datasets
import textwrap

class LoadTools:

    def __init__(self, secret_token: str) -> None:
        self.BASE_URL = "https://api.baseballcv.com"
        headers = {'Authorization': 'Bearer {}'.format(secret_token)}
        self.session = requests.Session()
        self.session.headers.update(headers)

        self.logger = BaseballCVLogger.get_logger(self.__class__.__name__)

    def check_health(self) -> dict:
        response = self.session.get(f'{self.BASE_URL}/health')
        response.raise_for_status()
        return response.json()
    
    def get_available_datasets(self) -> str:
        response = self.session.get(f'{self.BASE_URL}/api/datasets')
        response.raise_for_status()
        datasets =  response.json()['datasets']
        return f"Number of Available Datasets: {len(datasets)}\n" + "\n-".join([""] + datasets)
    
    def get_available_models(self) -> str:
        response = self.session.get(f'{self.BASE_URL}/api/models')
        response.raise_for_status()
        models =  response.json()['models']
        return f"Number of Available Models: {len(models)}\n" + "\n-".join([""] + models)

    def load_model(self, aliases: Union[str, list], output_dir: str = 'models'):
        pass

    def load_dataset(self, aliases: Union[str, list], output_dir: str = 'datasets'):
        pass