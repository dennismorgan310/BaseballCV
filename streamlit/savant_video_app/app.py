import streamlit as st
import pandas as pd
from app_utils.ui_components import display_search_interface
from app_utils.savant_scraper import SavantScraper
from app_utils.player_lookup import load_player_id_map
from app_utils.downloader import create_zip_in_memory, create_concatenated_video, create_simple_ordered_videos
import os
from datetime import datetime, timedelta

def display_header():
    """
    Display the BaseballCV branded header with logo and motto.
    """
    # Create columns for logo and title
    col1, col2 = st.columns([1, 4])
    
    # Logo and motto column
    with col1:
        # Use logo from i.ibb.co hotlink
        logo_url = "https://i.ibb.co/jP339csq/logo-old.jpg"
        
        try:
            # Create clickable logo using the direct image URL
            st.markdown(f"""
            <a href="https://github.com/BaseballCV" target="_blank">
                <img src="{logo_url}" width="120" style="cursor: pointer; border-radius: 8px;">
            </a>
            """, unsafe_allow_html=True)
        except Exception as e:
            # Fallback with clickable emoji if logo fails to load
            st.markdown("""
            <a href="https://github.com/BaseballCV" target="_blank" style="text-decoration: none; font-size: 48px;">
            Baseball/CV
            </a>
            """, unsafe_allow_html=True)
        
        # Add motto under logo in small text
        st.markdown("""
        <small style="color: #666; font-size: 11px;">
        <em>A collection of tools and models designed to aid in the use of Computer Vision in baseball.</em>
        </small>
        """, unsafe_allow_html=True)
    
    # Title column
    with col2:
        st.markdown("""
        # <a href="https://github.com/BaseballCV" target="_blank" style="text-decoration: none; color: inherit;">BaseballCV</a> Savant Video & Data Tool
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Tool description
    st.markdown("""
    **Search and download Baseball Savant pitch-by-pitch data with videos**
    
    Use the sidebar to search for plays by various filters (date, pitch type, player, advanced metrics) 
    or look up specific plays by their identifiers. Selected plays can be downloaded as video files.
    """)

def find_batter_highlights(scraper, search_params, max_results, selected_players):
    """
    Find top 10 batter highlight plays using stepping algorithm for exit velocity.
    Steps down from 110+ mph in 5 mph increments until finding 10 plays.
    Prioritizes: Home Runs > Triples > Doubles > Singles, sorted by distance projected.
    """
    target_plays = 10
    min_exit_velo = 110
    step_size = 5
    current_velo = min_exit_velo
    min_acceptable_velo = 95  # Don't go below 95 mph
    
    st.write("**Searching for batter highlights with smart exit velocity filtering...**")
    
    all_plays = []
    attempts = []
    
    # Define PA result priorities (Home Runs > Triples > Doubles > Singles only)
    allowed_pa_results = ['home_run', 'triple', 'double', 'single']
    pa_priority = {'home_run': 4, 'triple': 3, 'double': 2, 'single': 1}
    
    while len(all_plays) < target_plays and current_velo >= min_acceptable_velo:
        # Create parameters with current exit velocity filter
        velo_params = search_params.copy()
        
        # Add exit velocity filter using the metric system
        velo_params['metric_1'] = ['api_h_launch_speed']
        velo_params['metric_1_gt'] = [current_velo]
        velo_params['metric_1_lt'] = [130]  # Max reasonable exit velocity
        
        st.write(f"Searching for plays with exit velocity >= {current_velo} mph...")
        
        try:
            df = scraper.get_data_by_filters(velo_params, max_results)
            
            if not df.empty:
                # Filter for plays with launch_speed data and valid PA results
                df_filtered = df[
                    df['launch_speed'].notna() & 
                    (df['launch_speed'] >= current_velo) &
                    df['events'].isin(allowed_pa_results)
                ].copy()
                
                if not df_filtered.empty:
                    attempts.append({
                        'min_velo': current_velo,
                        'plays_found': len(df_filtered),
                        'avg_velo': df_filtered['launch_speed'].mean()
                    })
                    
                    # Add new plays to our collection (avoid duplicates)
                    for _, play in df_filtered.iterrows():
                        if len(all_plays) < target_plays:
                            # Avoid duplicates by checking play_id
                            if not any(p.get('play_id') == play.get('play_id') for p in all_plays):
                                all_plays.append(play.to_dict())
                    
                    st.write(f"Found {len(df_filtered)} plays at {current_velo}+ mph (total: {len(all_plays)}/{target_plays})")
                    
                    if len(all_plays) >= target_plays:
                        break
                else:
                    st.write(f"No qualifying plays found at {current_velo}+ mph")
            else:
                st.write(f"No plays found at {current_velo}+ mph")
                
        except Exception as e:
            st.write(f"Error searching at {current_velo}+ mph: {str(e)}")
        
        # Step down velocity
        current_velo -= step_size
    
    if all_plays:
        # Convert back to DataFrame
        highlights_df = pd.DataFrame(all_plays)
        
        # Create priority score and sort by: PA priority first, then by distance projected (ascending)
        highlights_df['pa_priority'] = highlights_df['events'].map(pa_priority).fillna(0)
        
        # For distance, we want ascending order (shortest distances first as they are typically more impressive line drives)
        # But we need to handle NaN values in distance
        highlights_df['distance_score'] = highlights_df.get('hit_distance_sc', 0).fillna(0)
        
        # Sort by: PA priority (descending), then distance (ascending for line drives), then exit velocity (descending)
        highlights_df = highlights_df.sort_values([
            'pa_priority', 
            'distance_score', 
            'launch_speed'
        ], ascending=[False, True, False]).head(target_plays)
        
        # Remove scoring columns for display
        highlights_df = highlights_df.drop(['pa_priority', 'distance_score'], axis=1, errors='ignore')
        
        # Display search summary with PA result breakdown
        pa_counts = highlights_df['events'].value_counts()
        pa_summary = []
        for pa_result in ['home_run', 'triple', 'double', 'single']:
            if pa_result in pa_counts:
                count = pa_counts[pa_result]
                pa_name = pa_result.replace('_', ' ').title()
                pa_summary.append(f"{count} {pa_name}{'s' if count != 1 else ''}")
        
        st.success(f"**Found {len(highlights_df)} batter highlight plays for {', '.join(selected_players)}** ({', '.join(pa_summary)})")
        
        if attempts:
            st.info(f"**Search Summary:** Found plays with exit velocity from {max(attempts[-1]['min_velo'], min_acceptable_velo)}+ to {attempts[0]['min_velo']}+ mph")
            
            # Show velocity breakdown
            for attempt in attempts[:3]:  # Show top 3 velocity ranges
                st.write(f"• {attempt['plays_found']} plays at {attempt['min_velo']}+ mph (avg: {attempt['avg_velo']:.1f} mph)")
        
        return highlights_df
    else:
        st.warning(f"No batter highlight plays found for {', '.join(selected_players)} in the selected date range.")
        st.info("Try expanding the date range or selecting different batters. Only Home Runs, Triples, Doubles, and Singles with 95+ mph exit velocity qualify as highlights.")
        return pd.DataFrame()

def find_pitcher_highlights(scraper, search_params, max_results, selected_players):
    """
    Find top 10 pitcher highlight plays - strikeouts with 2 strikes in the count.
    Baseball Savant does the filtering server-side, so we just need to sort and limit results.
    """
    target_plays = 10
    
    st.write("**Searching for pitcher highlights - strikeouts with 2 strikes...**")
    
    try:
        df = scraper.get_data_by_filters(search_params, max_results)
        
        if not df.empty:
            st.write(f"Found {len(df)} strikeout pitches with 2 strikes")
            
            # Since Baseball Savant already filtered correctly, we just need to sort by most recent and limit
            sort_columns = ['game_date', 'game_pk', 'inning', 'at_bat_number', 'pitch_number']
            existing_sort_cols = [col for col in sort_columns if col in df.columns]
            
            if existing_sort_cols:
                df = df.sort_values(by=existing_sort_cols, ascending=False)
            
            # Take the most recent target_plays
            highlights_df = df.head(target_plays)
            
            # Create pitch type summary
            if 'pitch_type' in highlights_df.columns:
                pitch_types = highlights_df['pitch_type'].value_counts()
                pitch_summary = []
                for pitch_type, count in pitch_types.items():
                    pitch_summary.append(f"{count} {pitch_type}")
            else:
                pitch_summary = []
            
            # Create description summary (swinging vs called)
            if 'description' in highlights_df.columns:
                description_counts = highlights_df['description'].value_counts()
                desc_summary = []
                for desc, count in description_counts.items():
                    desc_name = desc.replace('_', ' ').title()
                    desc_summary.append(f"{count} {desc_name}{'s' if count != 1 else ''}")
            else:
                desc_summary = ["strikeout pitches"]
            
            st.success(f"**Found {len(highlights_df)} pitcher highlight plays for {', '.join(selected_players)}** ({', '.join(desc_summary)})")
            
            if pitch_summary:
                st.info(f"**Pitch Types:** {', '.join(pitch_summary)}")
            
            return highlights_df
        else:
            st.warning(f"No strikeout pitches with 2 strikes found for {', '.join(selected_players)} in the selected date range.")
            st.info("Try expanding the date range or selecting different pitchers.")
            return pd.DataFrame()
            
    except Exception as e:
        st.error(f"Error searching for pitcher highlights: {str(e)}")
        return pd.DataFrame()

def main():
    """
    Main function to run the Streamlit app.
    """
    st.set_page_config(
        page_title="BaseballCV Savant Video & Data Tool", 
        layout="wide",
        page_icon="⚾",
        initial_sidebar_state="expanded"
    )
    
    # Display branded header
    display_header()

    player_id_map_df = load_player_id_map()
    query_mode, params = display_search_interface(player_id_map_df)

    # Initialize all session state variables at the start
    if 'results_df' not in st.session_state:
        st.session_state.results_df = pd.DataFrame()
    if 'zip_buffers' not in st.session_state:
        st.session_state.zip_buffers = []
    if 'concatenated_video' not in st.session_state:
        st.session_state.concatenated_video = None
    if 'last_download_format' not in st.session_state:
        st.session_state.last_download_format = None

    # --- Search Logic ---
    search_pressed = st.sidebar.button("Search", type="primary", use_container_width=True)
    perform_search = False

    if search_pressed:
        # Clear previous search results and download states on new search
        st.session_state.results_df = pd.DataFrame()
        st.session_state.zip_buffers = []
        st.session_state.concatenated_video = None
        
        if query_mode == 'filters':
            # filters mode: params, max_results, start_date, end_date
            if params and len(params) >= 4:
                search_params, max_results, start_date, end_date = params[0], params[1], params[2], params[3]
                if (end_date - start_date) > timedelta(days=5):
                    st.session_state.show_date_warning = True
                else:
                    perform_search = True
            else:
                st.sidebar.error("Invalid filter parameters")
        elif query_mode == 'highlights':
            # highlights mode: params, max_results, start_date, end_date, selected_players, highlights_type
            if params and len(params) >= 6 and params[4]:  # Check if selected_players exists
                perform_search = True
            else:
                st.sidebar.error("Please select at least one player for highlights mode")
        elif query_mode == 'play_id':
            # play_id mode: game_pk, at_bat_number, pitch_number, None, None
            if params and len(params) >= 5 and all(params[:3]):
                perform_search = True
            else:
                st.sidebar.error("Please provide all three Play ID values")

    if st.session_state.get('show_date_warning'):
        st.sidebar.warning("Large date range selected. This may be slow.")
        if st.sidebar.button("Proceed Anyway", use_container_width=True):
            st.session_state.show_date_warning = False
            perform_search = True

    if perform_search:
        with st.spinner("Fetching data from Baseball Savant... (This may take a moment)"):
            scraper = SavantScraper()
            try:
                if query_mode == 'filters':
                    search_params, max_results = params[0], params[1]
                    st.session_state.results_df = scraper.get_data_by_filters(search_params, max_results)
                elif query_mode == 'highlights':
                    # Extract each value explicitly from the 6-value tuple
                    search_params = params[0]
                    max_results = params[1] 
                    selected_players = params[4]
                    highlights_type = params[5]
                    
                    if search_params and selected_players:
                        if highlights_type == "Batter Highlights":
                            st.session_state.results_df = find_batter_highlights(scraper, search_params, max_results, selected_players)
                        else:  # Pitcher Highlights
                            st.session_state.results_df = find_pitcher_highlights(scraper, search_params, max_results, selected_players)
                    else:
                        st.warning("Please select at least one player for highlights mode.")
                elif query_mode == 'play_id':
                    game_pk, at_bat, pitch = params[0], params[1], params[2]
                    if all([game_pk, at_bat, pitch]):
                        st.session_state.results_df = scraper.get_data_by_play_id(int(game_pk), int(at_bat), int(pitch))
                    else:
                        st.warning("Please provide all three Play ID values.")
            except Exception as e:
                st.error(f"An error occurred during search: {e}")

    # --- Display and Download Logic ---
    if not st.session_state.get('results_df', pd.DataFrame()).empty:
        # Check if this was a highlights search
        if query_mode == 'highlights':
            st.subheader("Highlights Results")
            if params and len(params) >= 6 and params[4] and params[5]:  # Check if selected_players and highlights_type exist
                selected_players = params[4]
                highlights_type = params[5]
                st.info(f"**{highlights_type} for:** {', '.join(selected_players)} • **{len(st.session_state.results_df)} plays found**")
        else:
            st.subheader("Search Results")
        
        results_df = st.session_state.results_df.copy()

        # Data Prep
        id_to_name_map = player_id_map_df.set_index('id')['name'].to_dict()
        if 'pitcher' in results_df.columns:
            results_df['pitcher_name'] = results_df['pitcher'].map(id_to_name_map).fillna(results_df['pitcher'])
        if 'batter' in results_df.columns:
            results_df['batter_name'] = results_df['batter'].map(id_to_name_map).fillna(results_df['batter'])
        if 'balls' in results_df.columns and 'strikes' in results_df.columns:
            results_df['count'] = results_df['balls'].astype(str) + '-' + results_df['strikes'].astype(str)
        
        sort_columns = ['game_date', 'game_pk', 'inning', 'at_bat_number', 'pitch_number']
        existing_sort_cols = [col for col in sort_columns if col in results_df.columns]
        if existing_sort_cols:
            results_df.sort_values(by=existing_sort_cols, inplace=True, ascending=True)

        display_columns = [
            'game_date', 'pitcher_name', 'batter_name', 'pitch_type', 'release_speed', 
            'zone', 'count', 'events', 'description', 'launch_angle', 'launch_speed', 
            'pitch_name', 'bat_speed', 'play_id', 'video_url'
        ]
        existing_display_cols = [col for col in display_columns if col in results_df.columns]
        df_for_display = results_df[existing_display_cols].copy()
        
        # Results summary - special handling for highlights mode
        if query_mode == 'highlights':
            if params and len(params) >= 6 and params[5]:  # Check if highlights_type exists
                highlights_type = params[5]
                if highlights_type == "Batter Highlights" and 'launch_speed' in results_df.columns:
                    avg_exit_velo = results_df['launch_speed'].mean()
                    max_exit_velo = results_df['launch_speed'].max()
                    st.success(f"Found **{len(df_for_display)} batter highlight plays** • Avg Exit Velocity: **{avg_exit_velo:.1f} mph** • Max: **{max_exit_velo:.1f} mph**")
                elif highlights_type == "Pitcher Highlights":
                    # Show pitch velocity stats for pitcher highlights
                    if 'release_speed' in results_df.columns:
                        avg_pitch_speed = results_df['release_speed'].mean()
                        max_pitch_speed = results_df['release_speed'].max()
                        st.success(f"Found **{len(df_for_display)} pitcher highlight plays** • Avg Pitch Speed: **{avg_pitch_speed:.1f} mph** • Max: **{max_pitch_speed:.1f} mph**")
                    else:
                        st.success(f"Found **{len(df_for_display)} pitcher highlight plays**")
                else:
                    st.success(f"Found **{len(df_for_display)} highlight plays**")
            else:
                st.success(f"Found **{len(df_for_display)} highlight plays**")
        else:
            st.info(f"Found **{len(df_for_display)}** plays matching your search criteria")
        
        st.checkbox("Select All / Deselect All", key="select_all")
        df_for_display.insert(0, "Select", st.session_state.select_all)
        edited_df = st.data_editor(
            df_for_display, 
            hide_index=True, 
            column_config={"Select": st.column_config.CheckboxColumn(required=True)}, 
            disabled=df_for_display.columns.drop("Select"), 
            key="data_editor",
            use_container_width=True
        )
        
        selected_rows = edited_df[edited_df.Select]
        
        st.subheader("Download Options")
        
        if not selected_rows.empty:
            st.success(f"**{len(selected_rows)} play(s)** selected for download")
            
            # Download format selection
            download_format = st.radio(
                "Choose download format:",
                options=[
                    "Individual videos in zip file", 
                    "Single concatenated video file",
                    "Ordered videos for manual concatenation"
                ],
                index=0,
                help="Individual videos: Each play as a separate MP4 file. Concatenated: All plays joined into one video (fast with FFmpeg). Ordered: Sequential numbered files for easy manual concatenation."
            )
            
            # Clear previous downloads if format changed
            if st.session_state.get('last_download_format') != download_format:
                st.session_state.zip_buffers = []
                st.session_state.concatenated_video = None
                st.session_state.last_download_format = download_format
            
            # Check if concatenation is available
            if download_format == "Single concatenated video file":
                try:
                    import imageio_ffmpeg
                    concatenation_available = True
                except ImportError:
                    concatenation_available = False
                    st.warning("Video concatenation requires imageio-ffmpeg. Install it to enable this feature:")
                    st.code("pip install imageio-ffmpeg", language="bash")
                    st.info("After installation, restart your Streamlit app.")
            else:
                concatenation_available = True
            
            if download_format == "Individual videos in zip file":
                button_text = "Prepare Individual Videos for Download"
                if st.button(button_text, type="primary", use_container_width=True):
                    st.session_state.zip_buffers = []
                    BATCH_SIZE = 50
                    if len(selected_rows) > BATCH_SIZE:
                        st.warning(f"Preparing {len(selected_rows)} videos in batches of {BATCH_SIZE}. Please download each zip file as it becomes available.")
                    rows_to_download = results_df.loc[selected_rows.index]
                    list_df = [rows_to_download.iloc[i:i+BATCH_SIZE] for i in range(0, len(rows_to_download), BATCH_SIZE)]
                    
                    for i, batch_df in enumerate(list_df):
                        with st.spinner(f"Preparing zip file for batch {i+1}/{len(list_df)}..."):
                            zip_buffer = create_zip_in_memory(batch_df)
                            st.session_state.zip_buffers.append(zip_buffer)
            
            elif download_format == "Ordered videos for manual concatenation":
                button_text = "Create Ordered Video Collection"
                if st.button(button_text, type="primary", use_container_width=True):
                    st.session_state.zip_buffers = []
                    rows_to_download = results_df.loc[selected_rows.index]
                    with st.spinner("Creating ordered video collection..."):
                        ordered_buffer = create_simple_ordered_videos(rows_to_download)
                        st.session_state.zip_buffers.append(ordered_buffer)
            
            elif concatenation_available:  # Single concatenated video and imageio-ffmpeg is available
                button_text = "Create Concatenated Video"
                if st.button(button_text, type="primary", use_container_width=True):
                    if len(selected_rows) > 25:
                        st.error("Too many videos selected for concatenation. Please select 25 or fewer videos.")
                        st.info("Use 'Individual videos' or 'Ordered videos' option for larger collections.")
                    elif len(selected_rows) > 15:
                        st.warning("Concatenating many videos may take 2-3 minutes.")
                        st.info("FFmpeg concatenation is much faster than before!")
                    
                    if len(selected_rows) <= 25:
                        rows_to_download = results_df.loc[selected_rows.index]
                        with st.spinner("Creating concatenated video with FFmpeg..."):
                            try:
                                concatenated_buffer = create_concatenated_video(rows_to_download)
                                st.session_state.concatenated_video = concatenated_buffer
                                st.success("Concatenated video is ready for download!")
                            except Exception as e:
                                st.error(f"Error creating concatenated video: {e}")
                                if "imageio-ffmpeg is required" in str(e):
                                    st.code("pip install imageio-ffmpeg", language="bash")
                                    st.info("After installing imageio-ffmpeg, restart your Streamlit app to enable video concatenation.")
                                else:
                                    st.info("Try using 'Individual videos' or 'Ordered videos' option instead, or select fewer plays.")


        # Initialize session state for concatenated video
        if 'concatenated_video' not in st.session_state:
            st.session_state.concatenated_video = None

        # Download buttons section
        if st.session_state.zip_buffers:
            if len(st.session_state.zip_buffers) == 1 and download_format == "Ordered videos for manual concatenation":
                st.success("Ordered video collection is ready for download!")
                st.download_button(
                    label="Download Ordered Videos as .zip File",
                    data=st.session_state.zip_buffers[0],
                    file_name=f"baseballcv_ordered_videos_{datetime.now().strftime('%Y%m%d')}.zip",
                    mime="application/zip",
                    key="dl_ordered_videos",
                    use_container_width=True
                )
            else:
                st.success("Individual video batches are ready for download!")
                for i, zip_buffer in enumerate(st.session_state.zip_buffers):
                    st.download_button(
                        label=f"Download Batch {i+1} as .zip File",
                        data=zip_buffer,
                        file_name=f"baseballcv_savant_videos_batch_{i+1}_{datetime.now().strftime('%Y%m%d')}.zip",
                        mime="application/zip",
                        key=f"dl_button_{i}",
                        use_container_width=True
                    )
        elif st.session_state.concatenated_video:
            st.download_button(
                label="Download Concatenated Video",
                data=st.session_state.concatenated_video,
                file_name=f"baseballcv_concatenated_plays_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4",
                mime="video/mp4",
                key="dl_concatenated_video",
                use_container_width=True
            )
        elif not selected_rows.empty:
             st.info("Choose your download format and click the button to begin.")
        else:
            st.info("Select one or more plays to prepare for download.")

        # CSV download with branding
        st.markdown("---")
        st.subheader("Export Data")
        st.download_button(
            "Download Full Search Results as CSV", 
            results_df.to_csv(index=False).encode('utf-8'), 
            f"baseballcv_savant_search_results_{datetime.now().strftime('%Y%m%d')}.csv", 
            "text/csv", 
            key='download-full-csv',
            use_container_width=True
        )

    else:
        st.info("Use the sidebar to search for Baseball Savant data and see results here.")
    
    # Footer with BaseballCV info
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; padding: 20px;'>
        <small>
        <strong><a href="https://github.com/BaseballCV" target="_blank" style="text-decoration: none; color: inherit;">BaseballCV</a></strong> - A collection of tools and models designed to aid in the use of Computer Vision in baseball.<br>
        Built with Streamlit • Data from Baseball Savant • Videos from MLB
        </small>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()