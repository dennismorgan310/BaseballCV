# Functions

This directory contains the functions used in the project.

## Main Scripts

- `load_tools.py`: Contains a class LoadTools containing functions for both loading the raw and annotated datasets as well as the available models.
- `dataset_tools.py`: Contains a class DataTools to generate and manipulate datasets.
- `savant_scraper.py`: Contains a class BaseballSavVideoScraper to scrape baseball videos from Savant.
- `baseball_tools.py`: Contains a class BaseballTools to analyze baseball data and create data from video.
- `function_utils/utils.py`: Contains utility functions used across the project.

### load_tools.py

#### `LoadTools` class

Key function(s):
- `load_dataset(dataset_alias: str, use_bdl_api: Optional[bool] = True, file_txt_path: Optional[str] = None) -> str`: 
  Loads a zipped dataset and extracts it to a folder. It can use either a dataset alias or a file path to a text file containing the download link.

- `load_model(model_alias: str, model_type: str = 'YOLO', use_bdl_api: Optional[bool] = True, model_txt_path: Optional[str] = None) -> str`: 
  Loads a given baseball computer vision model into the repository. It can use either a model alias or a file path to a text file containing the download link.

### baseball_tools.py

#### `BaseballTools` class

Key function(s):
- `distance_to_zone(start_date: str = "2024-05-01", end_date: str = "2024-05-01", team_abbr: str = None, pitch_type: str = None, player: int = None, max_videos: int = None, max_videos_per_game: int = None, create_video: bool = True, catcher_model: str = 'phc_detector', glove_model: str = 'glove_tracking', ball_model: str = 'ball_trackingv4', zone_vertical_adjustment: float = 0.5, save_csv: bool = True, csv_path: str = None) -> list`: The DistanceToZone function calculates the distance of a pitch to the strike zone in a video, as well as other information about the Play ID including the frame where the ball crosses, and the distance between the target and the estimated strike zone.

### dataset_tools.py

#### `DataTools` class

Key function(s):
- `generate_photo_dataset(max_plays=5000, max_num_frames=10000, max_videos_per_game=10, start_date="2024-05-01", end_date="2024-07-31", delete_savant_videos=True)`: Generates a photo dataset from a diverse set of baseball videos from Savant.

- `automated_annotation(model_alias: str = None, model_type: str = 'detection', image_dir: str = "cv_dataset", output_dir: str = "labeled_dataset", conf: float = .80, device: str = 'cpu', mode: str = 'autodistill', ontology: dict = None, extension: str = '.jpg', batch_size: int = 100) -> str`: Automatically annotates images using pre-trained YOLO model from BaseballCV repo or Autodistill library depending on the mode specified. The annotated output consists of image files in the output directory, and label files in the subfolder "annotations" to work with annotation tools.

### savant_scraper.py

#### `BaseballSavVideoScraper` class

Key functions:
- `from_date_range(start_dt: str, end_dt: str = None, 
  team_abbr: str = None, player: int = None, 
  pitch_type: str = None,
  download_folder: str = 'savant_videos', 
  max_return_videos: int = 10, 
  max_videos_per_game: int = None)`: Extracts PBP data via a specified date range. It helps instantiate the `BaseballSavVideoScraper` class.

- `from_game_pks(game_pks: List[Dict[int, Dict[str, str]]], 
  player: int = None, pitch_type: str = None,
  download_folder: str = 'savant_videos',
  max_return_videos: int = 10, 
  max_videos_per_game: int = None)`: Extracts PBP data
  via a specified game_pk input, which is a list of dictionaries. i.e. {game_pk: {'home_team': home_team, 'away_team': away_team}}. It helps instantiate the `BaseballSavVideoScraper` class.

- `run_executor()`: Runs the multi-threaded script, extracting videos from baseball savant and saving it to your local directory.

- `cleanup_savant_videos()` : Removes the download folder directory.
  

Example Use Cases:
1. Adding in an extra filter with the dataframe
```python
scraper = BaseballSavVideoScraper.from_date_range('2024-05-12')
df = scraper.play_ids_df
df = df[df['release_speed'] >= 100] # Additional filter for 100 mph pitches
scraper.play_ids_df = df
scraper.run_executor() # Downloads the videos.
```
2. Querying a player (Jose Ramirez in this example)
```python
scraper = BaseballSavVideoScraper.from_date_range('2024-04-12', player = 60870, team_abbr = 'CLE')
```
3. Query all videos
```python
scraper = BaseballSavVideoScraper.from_date_range('2024-04-12', max_return_videos = None)
```
4. Query your own custom games
```python
game = [{777019: {'home_team': 'CLE', 'away_team': 'BAL'}}]
scraper = BaseballSavVideoScraper.from_game_pks(game)
```


## Usage

To use these functions, please consult the main README.md, the individual files docstrings, or the notebooks in the notebooks directory. These references should allow the user to understand the use-cases for each of these scripts.
