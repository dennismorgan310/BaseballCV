import os
from collections import defaultdict
import supervision as sv
from baseballcv.utilities import BaseballCVLogger, ProgressBar

class DatasetProcessor:
    def __init__(self):
        self.logger = BaseballCVLogger.get_logger(self.__class__.__name__)

    def generate_photo_dataset(
            self,
            video_folder: str,
            output_frames_folder: str = "cv_dataset",
            max_num_frames: int = 6000,
            frame_stride: int = 30
        ) -> None:
        """
        Generates a photo dataset with N frames for the user.

        Args:
            video_folder (str): The input folder containing the videos.
            output_frames_folder (str, optional): The output folder name for saving the frames. Defaults to "cv_dataset".
            max_num_frames (int, optional): The number of frames to extract. Defaults to 6000.
            frame_stride (int, optional): The stride resembling n frames in between. Defaults to 30.

        Raises:
            NotADirectoryError: If the input video folder is empty with no videos.
        """

        os.makedirs(output_frames_folder, exist_ok=True)

        video_files = [f for f in os.listdir(video_folder) if f.endswith(('.mp4', '.mov', '.mts'))]

        if not video_files:
            raise NotADirectoryError(f'No videos found in folder {video_folder}')
        
        games = defaultdict(list)
        for video_file in video_files:
            game_id = os.path.splitext(video_file)[0][:6]
            games[game_id].append(video_file)
        
        frames_per_game = max_num_frames // len(games)
        remaining_frames = max_num_frames % len(games)

        for game_id, game_videos in games.items():
            frames_for_game = frames_per_game + (1 if remaining_frames > 0 else 0)
            remaining_frames = max(0, remaining_frames - 1)
            
            frames_per_video = frames_for_game // len(game_videos)
            extra_frames = frames_for_game % len(game_videos)
            
            for i, video_file in enumerate(game_videos):
                frames_to_extract = frames_per_video + (1 if i < extra_frames else 0)
                video_path = os.path.join(video_folder, video_file)
                
                video_name = os.path.splitext(video_file)[0]
                image_name_pattern = f"{video_name}-{{:05d}}.png"
                
                frame_count = 0
                with sv.ImageSink(target_dir_path=output_frames_folder, image_name_pattern=image_name_pattern) as sink:
                    for image in sv.get_video_frames_generator(source_path=str(video_path), stride=frame_stride):
                        sink.save_image(image=image)
                        frame_count += 1

                        if frame_count >= frames_to_extract:
                            break
        