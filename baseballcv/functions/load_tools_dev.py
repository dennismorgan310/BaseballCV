import os
from dataclasses import dataclass, field
import requests
import re
from typing import Tuple, Union, Any
from baseballcv.utilities import BaseballCVLogger, ProgressBar

@dataclass
class BaseballCVAPI:
    token: str = field(default='')
    url: str = "https://api.baseballcv.com"

@dataclass
class HuggingFaceAPI:
    token: str = field(default='')
    url: str = "https://huggingface.co"

def create_requests_params(base_url, endpoint, token) -> Tuple[str, str]:
    if endpoint is None or token is None:
        raise ValueError('Invalid query. Your token is None or query alias is inavlid.')
    
    headers = {'Authorization': f'Bearer {token}'}
    return (base_url + endpoint, headers)

# This function is niched for baseballcv api
def get_file_name_from_request(content: requests.Response):
    h = dict(content.headers).get('Content-Disposition', None)
    if not h:
        return
    exp = re.compile(r'filename="?([^";]+)"?')
    name = re.findall(exp, h)
    return name[0]

# TODO: Add in implementation for downloading multiple models, datasets
class LoadTools:

    def __init__(self, *, baseballcv_api_token: str = None, hf_api_token: str = None) -> None:
        if baseballcv_api_token is None and hf_api_token is None:
            raise ValueError('Please specify a BaseballCV token and/or HuggingFace token.')

        self.baseballcv_api = BaseballCVAPI(token=baseballcv_api_token)
        self.hf_api = HuggingFaceAPI(token=hf_api_token)

        self.endpoints = {
                "health": "/health",
                "list_datasets": "/api/datasets",
                "list_models": "/api/models",
                "load_model": "/api/models/{}",
                "load_dataset": "/api/datasets/{}"
            }

        self.logger = BaseballCVLogger.get_logger(self.__class__.__name__)

    def _download_file(self, url: str, dest: str) -> None:
        response = requests.get(url, stream=True)

        if response.status_code == 200:
            total_size = int(response.headers.get('content-length', 0))
            p_bar = ProgressBar(total=total_size, unit='iB', desc=f"Downloading {os.path.basename(dest)}")

            
        else:
            raise ValueError(f'Could not download. Returned with {response.status_code} status code')

    def load_from_baseballcv(
            self, 
            query: str, 
            *, 
            alias: Union[str, list, None] = None, 
            output_dir: str = 'downloads'
        ) -> Union[Any, dict]:
        """

        Args:
            query (str): _description_
            alias (Union[str, list, None], optional): _description_. Defaults to None.
            output_dir (str, optional): _description_. Defaults to None.

        Returns:
            Union[Any, dict]: A report of the returned output, whether it's a summary of the 
            API features or if the download was successful.
        """
        url, headers = create_requests_params(
            self.baseballcv_api.url, 
            self.endpoints.get(query), 
            self.baseballcv_api.token
        )

        response = requests.get(url.format(alias), headers=headers)
        response.raise_for_status()

        filename = get_file_name_from_request(response)

        if not filename:
            return response.json() # It's a link to an endpoint

        is_success = False
        if response.status_code == 302: # This does not work for some reason with 302 status code
            is_success = self._download_file(response.url, output_dir)

        return {query: filename, 'success': is_success}
    
    def load_from_huggingface(
            self, 
            query: str, 
            *, 
            repo_id: Union[str, list, None] = None, 
            ourput_dir: str = 'downloads', 
            **kwargs
        ) -> Union[Any, dict]:
        """

        Args:
            query (str): _description_
            repo_id (Union[str, list, None], optional): _description_. Defaults to None.
            ourput_dir (str, optional): _description_. Defaults to 'downloads'.
            **kwargs (Any): Any additional keyword arguments tailored to making a request to the HuggingFace API examples below.

        Example Payload from HuggingFace (https://huggingface.co/docs/hub/en/api):
        ```
        params = {
            "search":"str",
            "author":"str",
            "filter":"str",
            "sort":"str",
            "direction":"int", [1, -1]
            "limit":"int",
            "full":"bool",
            "config":"bool"
        }
        ```
        Returns:
            Union[Any, dict]: A report of the returned output, whether it's a summary of the 
            API features or if the download was successful.
        """

        assert query != 'health', 'There is no Health Check for HuggingFace'

        url, headers = create_requests_params(
            self.hf_api.url,
            self.endpoints.get(query),
            self.hf_api.token
        )

        response = requests.get(url.format(repo_id), params=dict(**kwargs), headers=headers)
        

if __name__ == '__main__':
    from dotenv import load_dotenv

    load_dotenv('.env')

    tools = LoadTools(hf_api_token=os.environ.get("HF_TOKEN"))

    p = tools.load_from_huggingface(query='load_model', repo_id='dyland222/detr-coco-baseball_v2')