import os
import shutil
import asyncio
import aiohttp
import random
import pyarrow as pq
import pandas as pd
import requests
import re
from dataclasses import dataclass, field
from typing import Tuple, Union, Any, Literal, Callable
from baseballcv.utilities import BaseballCVLogger, ProgressBar

cpu_threads = min(32, os.cpu_count() + 4)

@dataclass
class BaseballCVAPI:
    token: str = field(default='')
    url: str = "https://api.baseballcv.com"

@dataclass
class HuggingFaceAPI:
    token: str = field(default='')
    url: str = "https://huggingface.co"

def create_requests_params(base_url: str, endpoint: str, token: str) -> Tuple[str, dict]:
    """
    Creates the proper url with headers for the API.

    Args:
        base_url (str): The base url based on the API dataclass.
        endpoint (str): The returned API endpoint.
        token (str): The access token.

    Raises:
        ValueError: If a token is not provided or no endpoint was returned.

    Returns:
        Tuple[str, dict]: A string of the formatted url: https://example.com/api/models/{} and the headers
            with the token initialized.
    """
    
    if endpoint is None or token is None:
        raise ValueError('Invalid query. Your token is None or query alias is inavlid.')
    
    headers = {'Authorization': f'Bearer {token}'}
    return (base_url + endpoint, headers)

def run_tasks_in_loop(async_function: Callable[..., None], *args, **kwargs) -> None:
    """
    Runs tasks in the proper loop. This is mainly for if users are running the 
    function in Jupyter Notebook, where it's already running asynchronous tasks.

    Args:
        async_function (Callable[..., None]): The asynchronous function to run.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = None
    
    if loop and loop.is_running():
        asyncio.create_task(async_function(*args, **kwargs))
    else:
        asyncio.run(async_function(*args, **kwargs))

# We recommend downloading one repo model or dataset at a time due to the size
class LoadTools:

    FILE_REGEX = re.compile(r'filename="?([^";]+)"?')

    def __init__(self, *, baseballcv_api_token: str = None, hf_api_token: str = None, output_dir: str = 'downloads') -> None:
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
        
        self.output_dir = output_dir

        self.logger = BaseballCVLogger.get_logger(self.__class__.__name__)

    async def _download_file(self, session: aiohttp.ClientSession, url: str, headers: dict, dest: str, filename: str, limiter: asyncio.Semaphore) -> None:
        async with limiter:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    total_size = int(response.headers.get('content-length', 0))
                    p_bar = ProgressBar(total=total_size, unit='iB', desc=f"Downloading {filename}")

                    with open(os.path.join(dest, os.path.basename(filename)), 'wb') as f:
                        async for chunk in response.content.iter_chunked(4*1024*1024): # 4 MB
                            f.write(chunk)
                            p_bar.update(len(chunk))
                    
                else:
                    self.logger.warning(f'Could not download a link from the API. Returned with {response.status} status code')
        
    async def _download_files_in_concurrency(self, extracted_files: dict, headers: dict, dest: str):
        limiter = asyncio.Semaphore(5)
        async with aiohttp.ClientSession() as session:
            tasks = [
                self._download_file(session, url, headers, dest, filename, limiter)
                for filename, url in extracted_files.items()
            ]
            await asyncio.gather(*tasks)

    def load_from_baseballcv(
            self, 
            query: str, 
            alias: Union[str, list, None] = None, 
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

        filename = dict(response.headers).get('Content-Disposition', None)

        if not filename:
            return response.json() # It's a link to an endpoint

        filename = self.FILE_REGEX.search(filename)

        is_success = False
        # We return ZIP files
        if response.status_code == 302: # This does not work for some reason with 302 status code
            is_success = self._download_file(response.url, self.output_dir)

        return {query: filename, 'success': is_success, 'output_pth': self.output_dir}
    
    def load_from_huggingface(
            self, 
            repo_id: str, 
            query: Literal['list_datasets', 'list_models', 'load_model', 'load_dataset'], 
            *,
            ignore_patterns: Union[Tuple[str], str] = ('.md', '.gitattributes', '.gitignore'),
            limit: int = None,
            **kwargs
        ) -> None:
        """
        Function that loads in data and models from HuggingFace API. This function is best suited
        for BaseballCV datasets and models.


        Please note: This is a very **basic** implementation for extracting files from HuggingFace.
        We are mainly focused on downloads from repositories created by users + maintainers in the 
        BaseballCV space, not large SOTA models and datasets. If you want to properly install larger 
        scale models + datasets, it is recommended to use the `huggingface-hub` package. 

        Args:
            repo_id (str): The reposiory ID for the dataset or model
            query (Literal[&#39;list_datasets&#39;, &#39;list_models&#39;, &#39;load_model&#39;, &#39;load_dataset&#39;]): Which endpoint to query
            ignore_patterns (Union[Tuple[str], str], optional): Any file types to ignore. Defaults to ('.md', '.gitattributes', '.gitignore').
            limit (int, optional): A variable that limits the number of files to extract. Defaults to None.
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
        Raises:
            ValueError: If the query is for `health`, invalid for HuggingFace.
        """

        if query == 'health': 
            raise ValueError('There is no Health Check for HuggingFace')
        
        url, headers = create_requests_params(
            self.hf_api.url,
            self.endpoints.get(query),
            self.hf_api.token
        )

        response = requests.get(url.format(repo_id), params=dict(**kwargs), headers=headers)

        response_info = response.json()

        sha = response_info['sha'] # revision hash

        files = [name['rfilename'] for name in response_info['siblings'] 
                 if not name['rfilename'].endswith(ignore_patterns)]
        
        if limit:
            files = random.sample(files, limit)
        
        self.logger.info(f'Found {len(files)} files. Attempting to download...')
        
        hf_url_fmt = (self.hf_api.url + '/datasets' if query == 'load_dataset' else self.hf_api.url) + '/{}/resolve/{}/{}'

        extracted_files = {name: hf_url_fmt.format(repo_id, sha, name) for name in files}

        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

        run_tasks_in_loop(self._download_files_in_concurrency, extracted_files=extracted_files, headers=headers, dest=self.output_dir)

    def unzip_from_parquet(self, destination: str = None) -> None:
        """
        Takes extracted parquet content loaded in from HuggingFace and unzips to a 
        desired destination.

        Args:
            destination (str, optional): The output directory, if None, it will default to the initialized 
              `output_dir` in the constructor. Defaults to None.
        """
        destination = destination or self.output_dir

        if not os.path.exists(destination):
            os.makedirs(destination)

        parquet_files = os.listdir(self.output_dir)

        for file in parquet_files:
            file_pth = os.path.join(self.output_dir, file)

            try:
                table = pd.read_parquet(file_pth, engine='pyarrow')

                for filename, data in zip(table['filename'], table['image']):
                    with open(os.path.join(destination, filename), 'wb') as f:
                        f.write(data.get('bytes'))
            except pq.ArrowInvalid:
                self.logger.error(f'Issue retrieving content from {file}. Most likely does not have data. skipping...')
            
            finally:
                os.remove(file_pth)

        if len(os.listdir(self.output_dir)) == 0:
            shutil.rmtree(self.output_dir)

if __name__ == '__main__':
    from dotenv import load_dotenv

    load_dotenv('.env')

    tools = LoadTools(hf_api_token=os.environ.get("HF_TOKEN"), baseballcv_api_token=os.environ.get("BASEBALLCV_TOKEN"))

    # p = tools.load_from_huggingface(repo_id='dyland222/detr-coco-baseball_v2', query='load_model')
    # p = tools.load_from_huggingface(repo_id='dyland222/international_amateur_baseball_catcher_photos', query='load_dataset')

    tools.write_from_parquet('cool')