import os
import io
import zipfile
import streamlit as st
import pandas as pd
import yt_dlp
import tempfile
import shutil

def create_zip_in_memory(selected_rows: pd.DataFrame):
    """
    Fetches videos using yt-dlp and stores them in a zip file in memory.
    """
    zip_buffer = io.BytesIO()
    total_videos = len(selected_rows)
    progress_bar = st.progress(0, text="Initializing download...")
    
    # Placeholder for warnings to show them all at the end
    warnings = []

    with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
        for i, row in enumerate(selected_rows.itertuples()):
            temp_filename = "" # Initialize to prevent reference before assignment error
            try:
                progress_text = f"Downloading video {i+1}/{total_videos}: {row.batter_name} vs {row.pitcher_name}"
                progress_bar.progress((i + 1) / total_videos, text=progress_text)
                
                film_room_url = row.video_url
                batter_str = str(row.batter_name).replace(' ', '_')
                pitcher_str = str(row.pitcher_name).replace(' ', '_')
                filename = f"{row.game_date}_{batter_str}_vs_{pitcher_str}_{row.play_id[:8]}.mp4"
                
                temp_filename = f"temp_{row.play_id}.mp4"
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'outtmpl': temp_filename,
                    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([film_room_url])

                if os.path.exists(temp_filename):
                    with open(temp_filename, 'rb') as f:
                        zip_file.writestr(filename, f.read())
                    print(f"DEBUG: Successfully added {filename} to zip.")
                else:
                    # This case can happen if yt-dlp fails silently.
                    warnings.append(f"Could not retrieve video for playId {row.play_id}. It might be unavailable.")

            # FIX: Specifically catch the DownloadError from yt-dlp
            except yt_dlp.utils.DownloadError as e:
                if "Unsupported URL" in str(e):
                    warnings.append(f"Video for playId `{row.play_id}` is unavailable (Unsupported URL).")
                else:
                    warnings.append(f"A download error occurred for playId `{row.play_id}`.")
                print(f"DEBUG: yt-dlp download error for {row.play_id}: {e}")
            
            except Exception as e:
                warnings.append(f"An unexpected error occurred for playId `{row.play_id}`.")
                print(f"DEBUG: General error for {row.play_id}: {e}")

            finally:
                # Always clean up the temp file if it exists
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)

    progress_bar.empty()
    
    # Display all collected warnings at the end
    for warning_text in warnings:
        st.warning(warning_text, icon="⚠️")

    return zip_buffer

def create_concatenated_video(selected_rows: pd.DataFrame):
    """
    Downloads videos and concatenates them into a single video file using MoviePy.
    Returns the concatenated video as bytes for download.
    """
    # Check if moviepy is available
    try:
        from moviepy.editor import VideoFileClip, concatenate_videoclips
    except ImportError:
        raise Exception(
            "MoviePy is required for video concatenation. Please install it by running:\n"
            "pip install moviepy\n\n"
            "Then restart your Streamlit app."
        )
    
    total_videos = len(selected_rows)
    progress_bar = st.progress(0, text="Initializing video concatenation...")
    
    # Create a temporary directory for processing
    temp_dir = tempfile.mkdtemp(prefix="baseballcv_concat_")
    video_clips = []
    downloaded_files = []
    warnings = []
    
    try:
        # Step 1: Download all videos
        for i, row in enumerate(selected_rows.itertuples()):
            progress_text = f"Downloading video {i+1}/{total_videos}: {row.batter_name} vs {row.pitcher_name}"
            progress_bar.progress((i + 1) / (total_videos * 2), text=progress_text)
            
            temp_filename = os.path.join(temp_dir, f"video_{i}_{row.play_id[:8]}.mp4")
            
            try:
                film_room_url = row.video_url
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'outtmpl': temp_filename,
                    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([film_room_url])

                if os.path.exists(temp_filename):
                    downloaded_files.append(temp_filename)
                    print(f"DEBUG: Downloaded video {i+1} for concatenation")
                else:
                    warnings.append(f"Could not download video for play {i+1} ({row.play_id[:8]})")

            except Exception as e:
                warnings.append(f"Error downloading video {i+1}: {str(e)}")
                print(f"DEBUG: Error downloading video {i+1}: {e}")

        if not downloaded_files:
            raise Exception("No videos were successfully downloaded for concatenation")

        # Step 2: Load video clips with moviepy
        progress_bar.progress(0.5, text="Loading videos for concatenation...")
        
        for i, video_file in enumerate(downloaded_files):
            try:
                clip = VideoFileClip(video_file)
                video_clips.append(clip)
                print(f"DEBUG: Loaded video clip {i+1} for concatenation")
            except Exception as e:
                warnings.append(f"Error loading video {i+1} for concatenation: {str(e)}")
                print(f"DEBUG: Error loading video {i+1}: {e}")

        if not video_clips:
            raise Exception("No video clips could be loaded for concatenation")

        # Step 3: Concatenate videos
        progress_bar.progress(0.75, text="Concatenating videos... This may take a few minutes")
        
        final_video = concatenate_videoclips(video_clips, method="compose")
        
        # Step 4: Write concatenated video to buffer
        progress_bar.progress(0.9, text="Preparing final video file...")
        
        output_path = os.path.join(temp_dir, "concatenated_output.mp4")
        final_video.write_videofile(
            output_path,
            codec='libx264',
            audio_codec='aac',
            temp_audiofile='temp-audio.m4a',
            remove_temp=True,
            verbose=False,
            logger=None  # Suppress moviepy logs
        )
        
        # Read the final video into memory
        with open(output_path, 'rb') as f:
            video_buffer = f.read()
        
        progress_bar.progress(1.0, text="Video concatenation complete!")
        
        # Clean up video clips
        for clip in video_clips:
            clip.close()
        final_video.close()
        
        progress_bar.empty()
        
        # Display warnings if any
        for warning_text in warnings:
            st.warning(warning_text, icon="⚠️")
        
        if warnings:
            st.info(f"✅ Successfully concatenated {len(video_clips)} out of {total_videos} videos")
        else:
            st.success(f"✅ Successfully concatenated all {len(video_clips)} videos!")
        
        return io.BytesIO(video_buffer)
        
    except Exception as e:
        progress_bar.empty()
        # Clean up video clips if they were created
        for clip in video_clips:
            try:
                clip.close()
            except:
                pass
        raise e
        
    finally:
        # Clean up temporary directory
        try:
            shutil.rmtree(temp_dir)
            print("DEBUG: Cleaned up temporary directory")
        except Exception as e:
            print(f"DEBUG: Error cleaning up temp directory: {e}")

def create_simple_concatenated_video(selected_rows: pd.DataFrame):
    """
    Simple fallback that creates a zip with renamed files in order.
    Use this if MoviePy is not available.
    """
    st.warning("⚠️ Video concatenation requires MoviePy. Creating ordered zip file instead.")
    
    zip_buffer = io.BytesIO()
    total_videos = len(selected_rows)
    progress_bar = st.progress(0, text="Creating ordered video collection...")
    
    warnings = []

    with zipfile.ZipFile(zip_buffer, 'a', zipfile.ZIP_DEFLATED, False) as zip_file:
        for i, row in enumerate(selected_rows.itertuples()):
            temp_filename = ""
            try:
                progress_text = f"Downloading video {i+1}/{total_videos}: {row.batter_name} vs {row.pitcher_name}"
                progress_bar.progress((i + 1) / total_videos, text=progress_text)
                
                film_room_url = row.video_url
                batter_str = str(row.batter_name).replace(' ', '_')
                pitcher_str = str(row.pitcher_name).replace(' ', '_')
                
                # Create ordered filename
                filename = f"{i+1:03d}_{row.game_date}_{batter_str}_vs_{pitcher_str}_{row.play_id[:8]}.mp4"
                
                temp_filename = f"temp_{row.play_id}.mp4"
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'outtmpl': temp_filename,
                    'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([film_room_url])

                if os.path.exists(temp_filename):
                    with open(temp_filename, 'rb') as f:
                        zip_file.writestr(filename, f.read())
                    print(f"DEBUG: Successfully added {filename} to ordered collection.")
                else:
                    warnings.append(f"Could not retrieve video for play {i+1}")

            except Exception as e:
                warnings.append(f"Error downloading video {i+1}: {str(e)}")

            finally:
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)

    progress_bar.empty()
    
    for warning_text in warnings:
        st.warning(warning_text, icon="⚠️")
    
    st.info("📁 Created ordered video collection. Videos are numbered in sequence for manual concatenation.")
    
    return zip_buffer