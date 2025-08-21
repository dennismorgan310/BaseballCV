import os
import shutil
import concurrent.futures
import requests
from bs4 import BeautifulSoup
import polars as pl
from typing import Dict, List
from baseballcv.utilities import BaseballCVLogger, ProgressBar
from baseballcv.functions.utils import rate_limiter, requests_with_retry, get_pbp_data

cpu_threads = min(32, os.cpu_count() + 4)

class BaseballSavVideoScraper:
    """
    Class that scrapes Video Data off Baseball Savant. It also provides pandas DataFrames of the pitch-level data,
    similar to `pybaseball` statcast function.
    """

    SAVANT_VIDEO_URL = 'https://baseballsavant.mlb.com/sporty-videos?playId={}'

    def __init__(self, play_ids_df: pl.DataFrame,
                 download_folder: str = 'savant_videos') -> None:

        self.logger = BaseballCVLogger().get_logger(self.__class__.__name__)
        
        self.play_ids_df = play_ids_df.to_pandas() # Can use this for further queries
        self.download_folder = download_folder
        os.makedirs(self.download_folder, exist_ok=True)

    @classmethod
    def from_date_range(cls, start_dt: str, end_dt: str = None, 
                 team_abbr: str = None, player: int = None, pitch_type: str = None,
                 download_folder: str = 'savant_videos', 
                 max_return_videos: int = 10, 
                 max_videos_per_game: int = None) -> "BaseballSavVideoScraper":
        """
        Extracts PBP data via a specified date range.

        Args:
            start_dt (str): The start date of the query.
            end_dt (str, optional): The end date of the query. Defaults to None.
            team_abbr (str, optional): A team abbreviation (i.e. CLE) if filtering for a team. Defaults to None.
            player (int, optional): A player ID (i.e. 12345) if filtering for a player. Defaults to None.
            pitch_type (str, optional): A specified pitch type (i.e. FF) if filtering for a particular pitch. Defaults to None.
            download_folder (str, optional): The folder to save the videos. Defaults to 'savant_videos'.
            max_return_videos (int, optional): The max videos to be returned. Defaults to 10.
            max_videos_per_game (int, optional): The max videos to be extracted per game. Defaults to None.

        Returns:
            BaseballSavVideoScraper: An instantiation of the `BaseballSavVideoScraper` class with inputs 
            download_folder and play_ids_df
        """
        
        play_ids_df = get_pbp_data(start_dt, end_dt, team_abbr=team_abbr, 
                                   player= player, pitch_type=pitch_type,
                                   max_return_videos=max_return_videos, 
                                   max_videos_per_game=max_videos_per_game)
        
        return cls(play_ids_df=play_ids_df, download_folder=download_folder)
    
    @classmethod
    def from_game_pks(cls, game_pks: List[Dict[int, Dict[str, str]]], 
                     player: int = None, pitch_type: str = None,
                     download_folder: str = 'savant_videos',
                     max_return_videos: int = 10, 
                     max_videos_per_game: int = None) -> "BaseballSavVideoScraper":
        """
        Extracts PBP data via a specified game selection.

        Args:
            game_pks (List[Dict[int, Dict[str, str]]]): The queried games. Should be a list of dictionaries formatted as 
            `{game_pk: {'home_team': home_team, 'away_team': away_team}}`
            player (int, optional):  A player ID (i.e. 12345) if filtering for a player. Defaults to None.
            pitch_type (str, optional): A specified pitch type (i.e. FF) if filtering for a particular pitch. Defaults to None.
            download_folder (str, optional): The folder to save the videos. Defaults to 'savant_videos'.
            max_return_videos (int, optional): The max videos to be returned. Defaults to 10.
            max_videos_per_game (int, optional): The max videos to be extracted per game. Defaults to None.

        Returns:
            BaseballSavVideoScraper: An instantiation of the `BaseballSavVideoScraper` class with inputs 
            download_folder and play_ids_df
        """
        
        play_ids_df = get_pbp_data(game_pks, player=player, pitch_type=pitch_type, 
                                   max_return_videos=max_return_videos, 
                                   max_videos_per_game=max_videos_per_game)

        return cls(play_ids_df=play_ids_df, download_folder=download_folder)
        

    def run_executor(self) -> None:
        """
        Multi-threaded function that concurrently downloads videos to local directory.
        """
        with concurrent.futures.ThreadPoolExecutor(max_workers=cpu_threads) as executor:
            for _ in ProgressBar(executor.map(self._download_video, self.play_ids_df['game_pk'], self.play_ids_df['play_id']), 
                                 desc="Downloading Videos", total=len(self.play_ids_df)): ...

    @rate_limiter
    def _download_video(self, game_pk: int, play_id: str) -> None:
        """
        Function that downloads each video query and writes it to the `download_folder`
        using the `_write_content` function.

        Args:
            game_pk (int): The game id of the game. Used as the video file name.
            play_id (str): The play id of the game. Used to query the url and part of the video file name.
        """
        video_response = requests_with_retry(self.SAVANT_VIDEO_URL.format(play_id))

        if video_response is None:
            self.logger.info('Could not download video %s', play_id)
            return # Skip the remaining code since the download was unsuccessful

        soup = BeautifulSoup(video_response.content, 'html.parser')

        video_container = soup.find('div', class_='video-box')
        if video_container:
            video_url = video_container.find('video').find('source', type='video/mp4')['src']

            if video_url:
                video_container_response = requests_with_retry(video_url, stream=True)
                self._write_content(game_pk, play_id, video_container_response)
                self.logger.info('Successfully downloaded video %s', play_id)
    
    def _write_content(self, game_pk: int, play_id: str, response: requests.Response) -> None:
        """
        Function that writes the requested video content to the `download_folder`.

        Args:
            game_pk (int): The game id of the game. Used as the video file name.
            play_id (str): The play id of the game. Used to query the url and part of the video file name.
            response (Response): The successful response connection that was used on the url. 
        """
        content_file = os.path.join(self.download_folder, f'{game_pk}_{play_id}.mp4')
        with open(content_file, 'wb') as f:
            for chunk in response.iter_content(chunk_size = 8192):
                f.write(chunk)

    def cleanup_savant_videos(self) -> None:
        """
        Function that deletes the `download_folder` directory.
        """
        if os.path.exists(self.download_folder):
            try:
                shutil.rmtree(self.download_folder)
                self.logger.info("Deleted %s", self.download_folder)
            except Exception as e:
                self.logger.error("Error deleting %s: %s", self.download_folder, e)
