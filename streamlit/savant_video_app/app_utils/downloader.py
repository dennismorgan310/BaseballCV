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
    Downloads videos and concatenates them using imageio-ffmpeg (much faster than MoviePy).
    Returns the concatenated video as bytes for download.
    """
    # Check if imageio-ffmpeg is available
    try:
        import imageio_ffmpeg as ffmpeg
    except ImportError:
        raise Exception(
            "imageio-ffmpeg is required for video concatenation. Please install it by running:\n"
            "pip install imageio-ffmpeg\n\n"
            "Then restart your Streamlit app."
        )
    
    total_videos = len(selected_rows)
    
    # Reasonable limit for concatenation
    if total_videos > 25:
        raise Exception(
            f"Too many videos selected ({total_videos}). "
            f"Please select 25 or fewer videos for concatenation. "
            f"Use 'Individual videos' or 'Ordered videos' option for larger collections."
        )
    
    progress_bar = st.progress(0, text="Initializing video concatenation...")
    
    # Create a temporary directory for processing
    temp_dir = tempfile.mkdtemp(prefix="baseballcv_concat_")
    downloaded_files = []
    warnings = []
    
    try:
        # Step 1: Download all videos
        st.write("📥 **Step 1/3**: Downloading videos...")
        for i, row in enumerate(selected_rows.itertuples()):
            progress_text = f"Downloading video {i+1}/{total_videos}: {row.batter_name} vs {row.pitcher_name}"
            progress_bar.progress((i + 1) / (total_videos * 3), text=progress_text)
            
            temp_filename = os.path.join(temp_dir, f"video_{i:03d}_{row.play_id[:8]}.mp4")
            
            try:
                film_room_url = row.video_url
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'outtmpl': temp_filename,
                    'format': 'best[height<=720][ext=mp4]/best[ext=mp4]',  # Limit quality for faster processing
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

        # Step 2: Create file list for ffmpeg concat
        st.write("🔗 **Step 2/3**: Preparing for concatenation...")
        progress_bar.progress(0.66, text="Creating file list for concatenation...")
        
        file_list_path = os.path.join(temp_dir, "filelist.txt")
        with open(file_list_path, 'w', encoding='utf-8') as f:
            for video_file in downloaded_files:
                # Escape path for ffmpeg (handle Windows paths and special characters)
                escaped_path = video_file.replace('\\', '/').replace("'", "'\"'\"'")
                f.write(f"file '{escaped_path}'\n")
        
        # Step 3: Use ffmpeg to concatenate (this is the fast part!)
        st.write("⚡ **Step 3/3**: Concatenating with FFmpeg (fast!)...")
        progress_bar.progress(0.8, text=f"FFmpeg concatenating {len(downloaded_files)} videos...")
        
        output_path = os.path.join(temp_dir, "concatenated_output.mp4")
        
        # Get ffmpeg executable from imageio-ffmpeg
        ffmpeg_exe = ffmpeg.get_ffmpeg_exe()
        
        # Build ffmpeg command for concatenation
        ffmpeg_cmd = [
            ffmpeg_exe,
            '-f', 'concat',
            '-safe', '0',
            '-i', file_list_path,
            '-c', 'copy',  # Copy streams without re-encoding (much faster)
            '-y',  # Overwrite output file
            output_path
        ]
        
        try:
            # Run ffmpeg concatenation
            import subprocess
            result = subprocess.run(
                ffmpeg_cmd, 
                capture_output=True, 
                text=True, 
                check=True,
                timeout=300  # 5 minute timeout
            )
            print("DEBUG: FFmpeg concatenation completed successfully")
        except subprocess.CalledProcessError as e:
            print(f"DEBUG: FFmpeg copy failed, trying re-encoding: {e}")
            # If copy fails, try re-encoding (slower but more compatible)
            ffmpeg_cmd = [
                ffmpeg_exe,
                '-f', 'concat',
                '-safe', '0',
                '-i', file_list_path,
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-preset', 'fast',  # Fast encoding preset
                '-crf', '23',       # Good quality/speed balance
                '-y',
                output_path
            ]
            subprocess.run(ffmpeg_cmd, capture_output=True, check=True, timeout=600)
            print("DEBUG: FFmpeg re-encoding completed")
        except subprocess.TimeoutExpired:
            raise Exception("Video concatenation timed out. Try selecting fewer videos.")
        
        # Step 4: Read the final video into memory
        progress_bar.progress(0.95, text="Reading final video...")
        
        if not os.path.exists(output_path):
            raise Exception("FFmpeg failed to create output file")
            
        with open(output_path, 'rb') as f:
            video_buffer = f.read()
        
        progress_bar.progress(1.0, text="Video concatenation complete!")
        progress_bar.empty()
        
        # Display warnings if any
        for warning_text in warnings:
            st.warning(warning_text, icon="⚠️")
        
        if warnings:
            st.info(f"✅ Successfully concatenated {len(downloaded_files)} out of {total_videos} videos")
        else:
            st.success(f"✅ Successfully concatenated all {len(downloaded_files)} videos!")
        
        # Show file size info
        file_size_mb = len(video_buffer) / (1024 * 1024)
        st.info(f"📁 Final video size: {file_size_mb:.1f} MB")
        
        return io.BytesIO(video_buffer)
        
    except Exception as e:
        progress_bar.empty()
        raise e
        
    finally:
        # Clean up temporary directory
        try:
            shutil.rmtree(temp_dir)
            print("DEBUG: Cleaned up temporary directory")
        except Exception as e:
            print(f"DEBUG: Error cleaning up temp directory: {e}")

def create_simple_ordered_videos(selected_rows: pd.DataFrame):
    """
    Alternative to concatenation: creates a zip with sequentially named files
    that can be easily concatenated manually or with simple tools.
    """
    st.info("📁 Creating ordered video collection instead of concatenation...")
    
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
                
                # Create ordered filename for easy manual concatenation
                filename = f"{i+1:03d}_{row.game_date}_{batter_str}_vs_{pitcher_str}_{row.play_id[:8]}.mp4"
                
                temp_filename = f"temp_{row.play_id}.mp4"
                ydl_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'outtmpl': temp_filename,
                    'format': 'best[height<=720][ext=mp4]/best[ext=mp4]',
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
    
    st.success("📁 Created ordered video collection!")
    st.info("💡 Videos are numbered in sequence (001_, 002_, etc.) for easy manual concatenation with tools like ffmpeg or video editors.")
    
    return zip_buffer