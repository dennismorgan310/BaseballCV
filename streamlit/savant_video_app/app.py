import streamlit as st
import pandas as pd
from app_utils.ui_components import display_search_interface
from app_utils.savant_scraper import SavantScraper
from app_utils.player_lookup import load_player_id_map
from app_utils.downloader import create_zip_in_memory
import os
import base64
from datetime import datetime, timedelta
from PIL import Image

def display_header():
    """
    Display the BaseballCV branded header with logo and motto.
    """
    # Create columns for logo and title
    col1, col2 = st.columns([1, 4])
    
    # Logo and motto column
    with col1:
        logo_path = "assets/logo.png"
        if os.path.exists(logo_path):
            try:
                # Create clickable logo using HTML
                with open(logo_path, "rb") as img_file:
                    img_base64 = base64.b64encode(img_file.read()).decode()
                
                st.markdown(f"""
                <a href="https://github.com/BaseballCV" target="_blank">
                    <img src="data:image/png;base64,{img_base64}" width="120" style="cursor: pointer;">
                </a>
                """, unsafe_allow_html=True)
            except Exception as e:
                # Fallback with clickable emoji if logo fails to load
                st.markdown("""
                <a href="https://github.com/BaseballCV" target="_blank" style="text-decoration: none; font-size: 48px;">
                🏀⚾
                </a>
                """, unsafe_allow_html=True)
        else:
            # Fallback with clickable emoji if logo file not found
            st.markdown("""
            <a href="https://github.com/BaseballCV" target="_blank" style="text-decoration: none; font-size: 48px;">
            🏀⚾
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
        # ⚾ <a href="https://github.com/BaseballCV" target="_blank" style="text-decoration: none; color: inherit;">BaseballCV</a> Savant Video & Data Tool
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Tool description
    st.markdown("""
    **Search and download Baseball Savant pitch-by-pitch data with videos**
    
    Use the sidebar to search for plays by various filters (date, pitch type, player, advanced metrics) 
    or look up specific plays by their identifiers. Selected plays can be downloaded as video files.
    """)

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

    # --- Search Logic ---
    search_pressed = st.sidebar.button("🔍 Search", type="primary", use_container_width=True)
    perform_search = False

    if search_pressed:
        # Clear previous search results and download states on new search
        st.session_state.results_df = pd.DataFrame()
        st.session_state.zip_buffers = []
        if query_mode == 'filters':
            _, _, start_date, end_date = params
            if (end_date - start_date) > timedelta(days=5):
                st.session_state.show_date_warning = True
            else:
                perform_search = True
        else: # For play_id search, no warning needed
            perform_search = True

    if st.session_state.get('show_date_warning'):
        st.sidebar.warning("⚠️ Large date range selected. This may be slow.")
        if st.sidebar.button("Proceed Anyway", use_container_width=True):
            st.session_state.show_date_warning = False
            perform_search = True

    if perform_search:
        with st.spinner("🔍 Fetching data from Baseball Savant... (This may take a moment)"):
            scraper = SavantScraper()
            try:
                if query_mode == 'filters':
                    search_params, max_results, _, _ = params
                    st.session_state.results_df = scraper.get_data_by_filters(search_params, max_results)
                elif query_mode == 'play_id':
                    game_pk, at_bat, pitch, _, _ = params
                    if all([game_pk, at_bat, pitch]):
                        st.session_state.results_df = scraper.get_data_by_play_id(int(game_pk), int(at_bat), int(pitch))
                    else:
                        st.warning("Please provide all three Play ID values.")
            except Exception as e:
                st.error(f"An error occurred during search: {e}")

    # --- Display and Download Logic ---
    if not st.session_state.get('results_df', pd.DataFrame()).empty:
        st.subheader("📊 Search Results")
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
        
        # Results summary
        st.info(f"📈 Found **{len(df_for_display)}** plays matching your search criteria")
        
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
        
        st.subheader("📥 Download Options")
        
        if not selected_rows.empty:
            st.success(f"✅ **{len(selected_rows)} play(s)** selected for download")
            if st.button("🎥 Prepare Videos for Download", type="primary", use_container_width=True):
                st.session_state.zip_buffers = []
                BATCH_SIZE = 50
                if len(selected_rows) > BATCH_SIZE:
                    st.warning(f"📦 Preparing {len(selected_rows)} videos in batches of {BATCH_SIZE}. Please download each zip file as it becomes available.")
                rows_to_download = results_df.loc[selected_rows.index]
                list_df = [rows_to_download.iloc[i:i+BATCH_SIZE] for i in range(0, len(rows_to_download), BATCH_SIZE)]
                
                for i, batch_df in enumerate(list_df):
                    with st.spinner(f"📦 Preparing zip file for batch {i+1}/{len(list_df)}..."):
                        zip_buffer = create_zip_in_memory(batch_df)
                        st.session_state.zip_buffers.append(zip_buffer)

        if st.session_state.zip_buffers:
            st.success("🎉 All batches are ready for download!")
            for i, zip_buffer in enumerate(st.session_state.zip_buffers):
                st.download_button(
                    label=f"📁 Download Batch {i+1} as .zip File",
                    data=zip_buffer,
                    file_name=f"baseballcv_savant_videos_batch_{i+1}_{datetime.now().strftime('%Y%m%d')}.zip",
                    mime="application/zip",
                    key=f"dl_button_{i}",
                    use_container_width=True
                )
        elif not selected_rows.empty:
             st.info("👆 Click 'Prepare Videos' to begin downloading.")
        else:
            st.info("☝️ Select one or more plays to prepare for download.")

        # CSV download with branding
        st.markdown("---")
        st.subheader("📊 Export Data")
        st.download_button(
            "📄 Download Full Search Results as CSV", 
            results_df.to_csv(index=False).encode('utf-8'), 
            f"baseballcv_savant_search_results_{datetime.now().strftime('%Y%m%d')}.csv", 
            "text/csv", 
            key='download-full-csv',
            use_container_width=True
        )

    else:
        st.info("👈 Use the sidebar to search for Baseball Savant data and see results here.")
    
    # Footer with BaseballCV info
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; padding: 20px;'>
        <small>
        🏀⚾ <strong><a href="https://github.com/BaseballCV" target="_blank" style="text-decoration: none; color: inherit;">BaseballCV</a></strong> - A collection of tools and models designed to aid in the use of Computer Vision in baseball.<br>
        Built with Streamlit • Data from Baseball Savant • Videos from MLB
        </small>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()