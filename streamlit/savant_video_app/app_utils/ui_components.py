import streamlit as st
import datetime

PITCH_TYPES = {
    "Four-Seam Fastball": "FF", "Sinker": "SI", "Cutter": "FC", "Curveball": "CU", 
    "Slider": "SL", "Changeup": "CH", "Split-Finger": "FS", "Knuckleball": "KN"
}
PA_RESULTS = {
    "Single": "single", "Double": "double", "Triple": "triple", "Home Run": "home_run",
    "Walk": "walk", "Strikeout": "strikeout", "Field Out": "field_out", 
    "Hit By Pitch": "hit_by_pitch", "Sac Fly": "sac_fly", "Sac Bunt": "sac_bunt",
    "Fielders Choice": "fielders_choice", "Double Play": "double_play"
}
TEAMS = {
    'Angels': '108', 'Astros': '117', 'Athletics': '133', 'Blue Jays': '141',
    'Braves': '144', 'Brewers': '158', 'Cardinals': '138', 'Cubs': '112',
    'Diamondbacks': '109', 'Dodgers': '119', 'Giants': '137', 'Guardians': '114',
    'Mariners': '136', 'Marlins': '146', 'Mets': '121', 'Nationals': '120',
    'Orioles': '110', 'Padres': '135', 'Phillies': '143', 'Pirates': '134',
    'Rangers': '140', 'Rays': '139', 'Red Sox': '111', 'Reds': '113',
    'Rockies': '115', 'Royals': '118', 'Tigers': '116', 'Twins': '142',
    'White Sox': '145', 'Yankees': '147'
}

# Fixed metric filters with correct Baseball Savant parameter names
METRIC_FILTERS = {
    "Pitch Velocity (mph)": {"param": "api_p_release_speed", "min": 0, "max": 120},
    "Exit Velocity (mph)": {"param": "api_h_launch_speed", "min": 0, "max": 125},
    "Launch Angle (°)": {"param": "api_h_launch_angle", "min": -90, "max": 90},
    "Distance Projected (ft)": {"param": "api_h_distance_projected", "min": 0, "max": 550},
    "IVB - Induced Vertical Break (in)": {"param": "api_break_z_induced", "min": -30, "max": 30},
    "HB - Horizontal Break (in)": {"param": "api_break_x_batter_out", "min": -30, "max": 30},
    "Spin Rate (rpm)": {"param": "api_p_release_spin_rate", "min": 0, "max": 4000},
    "Bat Speed (mph)": {"param": "sweetspot_speed_mph", "min": 0, "max": 100},
}

def display_search_interface(player_df):
    st.sidebar.header("Search Options")
    query_mode = st.sidebar.radio("Query Mode", ('Search by Filters', 'Search by Specific Play ID'))
    if query_mode == 'Search by Filters':
        return 'filters', display_search_filters(player_df)
    else:
        return 'play_id', display_play_id_search()

def display_search_filters(player_df):
    params = {}
    player_names = sorted(player_df['name'].unique()) if not player_df.empty else []

    st.sidebar.markdown("##### Date Range")
    today = datetime.date.today()
    default_start = today - datetime.timedelta(days=2)
    start_date = st.sidebar.date_input("Start Date", default_start)
    end_date = st.sidebar.date_input("End Date", today)
    params['game_date_gt'] = [start_date.strftime('%Y-%m-%d')]
    params['game_date_lt'] = [end_date.strftime('%Y-%m-%d')]
    
    st.sidebar.markdown("##### Player & Team")
    selected_pitchers = st.sidebar.multiselect("Pitcher(s)", player_names)
    selected_batters = st.sidebar.multiselect("Batter(s)", player_names)
    pitcher_ids = [int(player_df[player_df['name'] == name].iloc[0]['id']) for name in selected_pitchers]
    batter_ids = [int(player_df[player_df['name'] == name].iloc[0]['id']) for name in selected_batters]
    if pitcher_ids:
        params['pitchers_lookup[]'] = pitcher_ids
    if batter_ids:
        params['batters_lookup[]'] = batter_ids

    st.sidebar.markdown("##### Pitch, PA & Team")
    params['hfPT'] = [PITCH_TYPES[p] for p in st.sidebar.multiselect("Pitch Type(s)", list(PITCH_TYPES.keys()))]
    params['hfAB'] = [PA_RESULTS[p] for p in st.sidebar.multiselect("PA Result(s)", list(PA_RESULTS.keys()))]
    params['hfTeam'] = [TEAMS[t] for t in st.sidebar.multiselect("Team(s)", list(TEAMS.keys()))]
    
    st.sidebar.markdown("##### Advanced Metric Filters")
    st.sidebar.caption("Select up to 6 metrics to filter by specific ranges")
    selected_metrics = st.sidebar.multiselect(
        "Select metrics", 
        options=list(METRIC_FILTERS.keys()), 
        max_selections=6,
        help="Choose up to 6 metrics to apply range filters. These correspond to Baseball Savant's advanced search options."
    )
    
    metric_counter = 1
    for metric_name in selected_metrics:
        metric_info = METRIC_FILTERS[metric_name]
        min_val, max_val = metric_info["min"], metric_info["max"]
        
        st.sidebar.markdown(f"**{metric_name}**")
        
        # Create columns for min/max inputs
        col1, col2 = st.sidebar.columns(2)
        
        with col1:
            lower_bound = st.number_input(
                "Min", 
                min_value=float(min_val), 
                max_value=float(max_val), 
                value=float(min_val),
                step=0.1 if 'Angle' in metric_name or 'Break' in metric_name else 1.0,
                key=f"num_min_{metric_info['param']}"
            )
        with col2:
            upper_bound = st.number_input(
                "Max", 
                min_value=float(min_val), 
                max_value=float(max_val), 
                value=float(max_val),
                step=0.1 if 'Angle' in metric_name or 'Break' in metric_name else 1.0,
                key=f"num_max_{metric_info['param']}"
            )

        # Ensure lower_bound <= upper_bound
        if lower_bound > upper_bound:
            st.sidebar.error(f"Min value cannot be greater than max value for {metric_name}")
            continue

        # Add to params if the range is not the default full range
        if lower_bound > min_val or upper_bound < max_val:
            params[f'metric_{metric_counter}'] = [metric_info['param']]
            params[f'metric_{metric_counter}_gt'] = [lower_bound]
            params[f'metric_{metric_counter}_lt'] = [upper_bound]
            metric_counter += 1

    st.sidebar.markdown("##### Other Options")
    params['player_type'] = [st.sidebar.selectbox("Primary Player Type", ["pitcher", "batter"], index=0)]
    max_results = st.sidebar.slider("Max Results to Fetch", 1, 500, 50)

    # Add season filter (usually helpful for Baseball Savant)
    current_year = datetime.datetime.now().year
    params['hfSea'] = [str(current_year)]

    return params, max_results, start_date, end_date

def display_play_id_search():
    st.sidebar.markdown("##### Enter Play Identifiers")
    game_pk = st.sidebar.number_input("Game PK", step=1, value=None)
    at_bat_number = st.sidebar.number_input("At Bat Number", step=1, value=None)
    pitch_number = st.sidebar.number_input("Pitch Number", step=1, value=None)
    return game_pk, at_bat_number, pitch_number, None, None