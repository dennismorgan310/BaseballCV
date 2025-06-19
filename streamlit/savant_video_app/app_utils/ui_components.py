import streamlit as st
import datetime

PITCH_TYPES = {
    "Four-Seam Fastball": "FF",
    "Sinker": "SI",
    "Cutter": "FC",
    "Changeup": "CH",
    "Split-Finger": "FS",
    "Forkball": "FO",
    "Screwball": "SC",
    "Curveball": "CU",
    "Knuckle Curve": "KC",
    "Slow Curve": "CS",
    "Slider": "SL",
    "Sweeper": "ST",
    "Slurve": "SV",
    "Knuckleball": "KN",
    "Eephus": "EP",
    "Fastball": "FA",
    "Intentional Ball": "IN",
    "Pitchout": "PO",
}

PA_RESULTS = {
    "Single": "single",
    "Double": "double",
    "Triple": "triple",
    "Home Run": "home_run",
    "Field Out": "field_out",
    "Strikeout": "strikeout",
    "Strikeout Double Play": "strikeout_double_play",
    "Walk": "walk",
    "Double Play": "double_play",
    "Field Error": "field_error",
    "Grounded Into Double Play": "grounded_into_double_play",
    "Fielder's Choice": "fielders_choice",
    "Fielder's Choice Out": "fielders_choice_out",
    "Batter Interference": "batter_interference",
    "Catcher Interference": "catcher_interf",
    "Caught Stealing 2B": "caught_stealing_2b",
    "Caught Stealing 3B": "caught_stealing_3b",
    "Caught Stealing Home": "caught_stealing_home",
    "Force Out": "force_out",
    "Hit By Pitch": "hit_by_pitch",
    "Intentional Walk": "intent_walk",
    "Sac Bunt": "sac_bunt",
    "Sac Bunt Double Play": "sac_bunt_double_play",
    "Sac Fly": "sac_fly",
    "Sac Fly Double Play": "sac_fly_double_play",
    "Triple Play": "triple_play",
}

PITCH_RESULTS = {
    "Ball": "ball",
    "Blocked Ball": "blocked_ball",
    "Called Strike": "called_strike",
    "Foul": "foul",
    "Foul Bunt": "foul_bunt",
    "Bunt Foul Tip": "bunt_foul_tip",
    "Foul Pitchout": "foul_pitchout",
    "Pitchout": "pitchout",
    "Hit by Pitch": "hit_by_pitch",
    "Intentional Ball": "intent_ball",
    "Hit into Play": "hit_into_play",
    "Missed Bunt": "missed_bunt",
    "Foul Tip": "foul_tip",
    "Swinging Pitchout": "swinging_pitchout",
    "Swinging Strike": "swinging_strike",
    "Swinging Strike Blocked": "swinging_strike_blocked",
}

# New filter categories from the URL
COUNT_SITUATIONS = {
    "0-0": "00",
    "0-1": "01", 
    "0-2": "02",
    "1-0": "10",
    "1-1": "11",
    "1-2": "12", 
    "2-0": "20",
    "2-1": "21",
    "2-2": "22",
    "3-0": "30",
    "3-1": "31",
    "3-2": "32",
    "Ahead in Count": "ahead",
    "Even Count": "even", 
    "Behind in Count": "behind",
    "Two Strikes": "2strikes",
    "Three Balls": "3balls"
}

OUTS = {
    "0 Outs": "0",
    "1 Out": "1", 
    "2 Outs": "2"
}

BATTED_BALL_DIRECTION = {
    "Pull": "Pull",
    "Straightaway": "Straightaway",
    "Opposite Field": "Opposite"
}

# Handedness options
PITCHER_HANDEDNESS = {
    "Left": "L",
    "Right": "R"
}

BATTER_HANDEDNESS = {
    "Left": "L", 
    "Right": "R"
}

# Complete venue list from Baseball Savant (in order from URL)
VENUES = {
    "[ATH] Sutter Health Park": "2529",
    "[ATH-2024] Oakland Coliseum": "10", 
    "[ATL] Truist Park": "4705",
    "[ATL-2016] Turner Field": "16",
    "[AZ] Chase Field": "15",
    "[BAL] Oriole Park": "2",
    "[BOS] Fenway Park": "3",
    "[CHC] Wrigley Field": "17",
    "[CIN] Great American Ball Park": "2602",
    "[CLE] Progressive Field": "5",
    "[COL] Coors Field": "19",
    "[CWS] Rate Field": "4",
    "[DET] Comerica Park": "2394",
    "[HOU] Daikin Park": "2392",
    "[KC] Kauffman Stadium": "7",
    "[LAA] Angel Stadium": "1",
    "[LAD] Dodger Stadium": "22",
    "[MIA] loanDepot Park": "4169",
    "[MIA-2011] Hard Rock Stadium": "20",
    "[MIL] American Family Field": "32",
    "[MIN] Target Field": "3312",
    "[MIN-2009] Metrodome": "8",
    "[NYM] Citi Field": "3289",
    "[NYM-2008] Shea Stadium": "25",
    "[NYY] Yankee Stadium": "3313",
    "[NYY-2008] Yankee Stadium": "9",
    "[PHI] Citizens Bank Park": "2681",
    "[PIT] PNC Park": "31",
    "[SD] Petco Park": "2680",
    "[SEA] T-Mobile Park": "680",
    "[SF] Oracle Park": "2395",
    "[STL] Busch Stadium": "2889",
    "[TB] Steinbrenner Field": "2523",
    "[TB-2024] Tropicana Field": "12",
    "[TEX] Globe Life Field": "5325",
    "[TEX-2019] Globe Life Park": "13",
    "[TOR] Rogers Centre": "14",
    "[WSH] Nationals Park": "3309"
}

# Game situations (simplified as per user's improvement)
SITUATIONS = {
    "Go-Ahead Run at Plate": "Go\\.\\.\\.Ahead\\.run\\.at\\.plate",
    "Go-Ahead Run on Base": "Go\\.\\.\\.Ahead\\.run\\.on\\.base",
    "Tying Run at Plate": "Tying\\.run\\.at\\.plate", 
    "Tying Run on Base": "Tying\\.run\\.on\\.base",
    "Tying Run on Deck": "Tying\\.run\\.on\\.deck"
}

# Season Type options (hfGT parameter)
SEASON_TYPES = {
    "Regular Season": "R",
    "Postseason": "PO",
    "Wildcard": "F", 
    "Division Series": "D",
    "League Championship": "L",
    "World Series": "W",
    "Spring Training": "S",
    "All Star": "A"
}

# Primary Player Type options (player_type parameter)
PLAYER_TYPES = {
    "Pitcher": "pitcher",
    "Batter": "batter", 
    "Catcher": "fielder_2",
    "1st Base": "fielder_3",
    "2nd Base": "fielder_4", 
    "3rd Base": "fielder_5",
    "Shortstop": "fielder_6",
    "Left Field": "fielder_7",
    "Center Field": "fielder_8",
    "Right Field": "fielder_9"
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
    
    # Initialize search mode in session state
    if 'search_mode' not in st.session_state:
        st.session_state.search_mode = 'filters'
    
    # Highlights mode - prominent button at top
    st.sidebar.markdown("### Quick Highlights")
    if st.sidebar.button("Find Highlights", type="primary", use_container_width=True, help="Automatically find the top 10 hardest hit balls (home runs prioritized) for selected batter(s). Steps down from 110+ mph exit velocity until finding 10 plays."):
        st.session_state.search_mode = 'highlights'
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### Advanced Search")
    
    # Mode selection buttons
    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("Filter Search", use_container_width=True, type="secondary" if st.session_state.search_mode != 'filters' else "primary"):
            st.session_state.search_mode = 'filters'
    with col2:
        if st.button("Play ID Search", use_container_width=True, type="secondary" if st.session_state.search_mode != 'play_id' else "primary"):
            st.session_state.search_mode = 'play_id'
    
    # Return appropriate interface based on mode
    if st.session_state.search_mode == 'highlights':
        return 'highlights', display_highlights_search(player_df)
    elif st.session_state.search_mode == 'filters':
        return 'filters', display_search_filters(player_df)
    else:
        return 'play_id', display_play_id_search()

def display_highlights_search(player_df):
    """Display simplified interface for highlights mode"""
    params = {}
    player_names = sorted(player_df['name'].unique()) if not player_df.empty else []

    st.sidebar.markdown("##### Date Range")
    today = datetime.date.today()
    default_start = today - datetime.timedelta(days=7)  # Default to last week for highlights
    start_date = st.sidebar.date_input("Start Date", default_start, key="highlights_start")
    end_date = st.sidebar.date_input("End Date", today, key="highlights_end")
    
    st.sidebar.markdown("##### Select Batter(s)")
    selected_batters = st.sidebar.multiselect("Batter(s) for Highlights", player_names, key="highlights_batters")
    
    # Add explanation of highlights mode
    st.sidebar.info("**Highlights Mode:** Finds the top 10 hardest hit balls (starting at 110+ mph exit velocity, stepping down by 5 mph until 10 plays are found). Home runs are prioritized.")
    
    if not selected_batters:
        st.sidebar.warning("Please select at least one batter to find highlights")
        return None, None, start_date, end_date, None
    
    batter_ids = [int(player_df[player_df['name'] == name].iloc[0]['id']) for name in selected_batters]
    
    # Auto-configure search parameters for highlights
    params['game_date_gt'] = [start_date.strftime('%Y-%m-%d')]
    params['game_date_lt'] = [end_date.strftime('%Y-%m-%d')]
    params['batters_lookup[]'] = batter_ids
    params['hfGT'] = ['R']  # Regular season only
    params['hfSea'] = [str(datetime.datetime.now().year)]
    params['player_type'] = ['batter']
    
    # Set pitch result for highlights (hit into play - this covers all batted balls including home runs)
    params['hfPR'] = ['hit_into_play']  # Pitch result: hit into play (covers all contact)
    
    max_results = 200  # Get more results to filter through
    
    return params, max_results, start_date, end_date, selected_batters

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
    
    st.sidebar.markdown("##### Season & Game Type")
    selected_season_types = st.sidebar.multiselect("Season Type(s)", list(SEASON_TYPES.keys()), default=["Regular Season"])
    params['hfGT'] = [SEASON_TYPES[st] for st in selected_season_types]
    
    st.sidebar.markdown("##### Player & Team")
    selected_pitchers = st.sidebar.multiselect("Pitcher(s)", player_names)
    selected_batters = st.sidebar.multiselect("Batter(s)", player_names)
    pitcher_ids = [int(player_df[player_df['name'] == name].iloc[0]['id']) for name in selected_pitchers]
    batter_ids = [int(player_df[player_df['name'] == name].iloc[0]['id']) for name in selected_batters]
    if pitcher_ids:
        params['pitchers_lookup[]'] = pitcher_ids
    if batter_ids:
        params['batters_lookup[]'] = batter_ids

    # Handedness filters
    st.sidebar.markdown("##### Player Handedness")
    pitcher_hand = st.sidebar.selectbox("Pitcher Throws", ["Both", "Left", "Right"], index=0)
    if pitcher_hand != "Both":
        params['pitcher_throws'] = [PITCHER_HANDEDNESS[pitcher_hand]]
    
    batter_hand = st.sidebar.selectbox("Batter Stands", ["Both", "Left", "Right"], index=0)
    if batter_hand != "Both":
        params['batter_stands'] = [BATTER_HANDEDNESS[batter_hand]]

    st.sidebar.markdown("##### Pitch, PA & Team")
    params['hfPT'] = [PITCH_TYPES[p] for p in st.sidebar.multiselect("Pitch Type(s)", list(PITCH_TYPES.keys()))]
    params['hfAB'] = [PA_RESULTS[p] for p in st.sidebar.multiselect("PA Result(s)", list(PA_RESULTS.keys()))]
    params['hfPR'] = [PITCH_RESULTS[p] for p in st.sidebar.multiselect("Pitch Result(s)", list(PITCH_RESULTS.keys()))]
    params['hfTeam'] = [TEAMS[t] for t in st.sidebar.multiselect("Team(s)", list(TEAMS.keys()))]
    
    st.sidebar.markdown("##### Game Situation")
    params['hfC'] = [COUNT_SITUATIONS[c] for c in st.sidebar.multiselect("Count(s)", list(COUNT_SITUATIONS.keys()))]
    params['hfOuts'] = [OUTS[o] for o in st.sidebar.multiselect("Outs", list(OUTS.keys()))]
    params['hfPull'] = [BATTED_BALL_DIRECTION[d] for d in st.sidebar.multiselect("Batted Ball Direction", list(BATTED_BALL_DIRECTION.keys()))]
    
    # Situations
    selected_situations = st.sidebar.multiselect("Specific Situations", list(SITUATIONS.keys()))
    params['hfSit'] = [SITUATIONS[s] for s in selected_situations]
    
    # Venue selection with search
    st.sidebar.markdown("##### Venue")
    selected_venues = st.sidebar.multiselect(
        "Stadium(s)", 
        options=list(VENUES.keys()),
        help="Search and select stadiums. Use Ctrl+Click to select multiple venues."
    )
    params['hfStadium'] = [VENUES[v] for v in selected_venues]
    
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
    selected_player_type = st.sidebar.selectbox("Primary Player Type", list(PLAYER_TYPES.keys()), index=0)
    params['player_type'] = [PLAYER_TYPES[selected_player_type]]
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