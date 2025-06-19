import requests
import pandas as pd
from io import StringIO

class SavantScraper:
    """
    Scrapes data from Baseball Savant. It uses the Statcast Search CSV endpoint
    and enriches the data with calls to the MLB Gumbo API to find video playIds.
    """
    def __init__(self):
        self.search_api_url = "https://baseballsavant.mlb.com/statcast_search/csv"
        self.gumbo_api_url = "https://statsapi.mlb.com/api/v1.1/game/{}/feed/live"
        self.gumbo_cache = {}

    def _fetch_gumbo_data(self, game_pk: int):
        """
        Fetches and caches the Gumbo live feed data for a given game_pk.
        """
        if game_pk in self.gumbo_cache:
            return self.gumbo_cache[game_pk]
        
        try:
            url = self.gumbo_api_url.format(game_pk)
            response = requests.get(url, timeout=20)
            response.raise_for_status()
            data = response.json()
            self.gumbo_cache[game_pk] = data
            return data
        except requests.exceptions.RequestException as e:
            print(f"DEBUG: Failed to fetch Gumbo data for game_pk {game_pk}: {e}")
            self.gumbo_cache[game_pk] = None # Cache failure to avoid retries
            return None

    def _find_play_id_from_gumbo(self, statcast_row: pd.Series, all_gumbo_plays: list):
        """
        Matches a row from a Statcast search with its corresponding Gumbo play event
        to find the video playId UUID.
        """
        try:
            # Statcast at_bat_number is 1-indexed, Gumbo's atBatIndex is 0-indexed.
            target_at_bat_index = statcast_row['at_bat_number'] - 1
            target_pitch_number = statcast_row['pitch_number']

            for play in all_gumbo_plays:
                if play.get('about', {}).get('atBatIndex') == target_at_bat_index:
                    for event in play.get('playEvents', []):
                        # Match the specific pitch within the at-bat
                        if event.get('isPitch') and event.get('pitchNumber') == target_pitch_number:
                            # The 'playId' field in this event is the UUID we need.
                            play_id = event.get('playId')
                            if play_id:
                                return play_id
        except (KeyError, IndexError, TypeError) as e:
            print(f"DEBUG: Error processing Gumbo data for a row: {e}")
            return None
        return None

    def _construct_video_url(self, play_id: str) -> str:
        """Constructs the video URL from a playId."""
        if not play_id or pd.isna(play_id):
            return "NO_PLAY_ID_FOUND"
        return f"https://baseballsavant.mlb.com/sporty-videos?playId={play_id}"

    def _format_savant_payload(self, search_params: dict, max_results: int) -> dict:
        """
        Formats parameters to match Baseball Savant's expected format.
        Based on analysis of working Baseball Savant URLs.
        """
        # Start with all the standard empty parameters that Baseball Savant expects
        payload = {
            'hfPT': '',
            'hfAB': '',
            'hfGT': '',  # Season type - will be populated from search params
            'hfPR': '',
            'hfZ': '',
            'hfStadium': '',
            'hfBBL': '',
            'hfNewZones': '',
            'hfPull': '',
            'hfC': '',
            'hfSea': '2025|',  # Current season with pipe
            'hfSit': '',
            'player_type': 'pitcher',
            'hfOuts': '',
            'hfOpponent': '',
            'pitcher_throws': '',
            'batter_stands': '',
            'hfSA': '',
            'hfMo': '',
            'hfTeam': '',
            'home_road': '',
            'hfRO': '',
            'position': '',
            'hfInfield': '',
            'hfOutfield': '',
            'hfInn': '',
            'hfBBT': '',
            'hfFlag': '',
            'group_by': 'name',
            'min_pitches': '0',
            'min_results': '0', 
            'min_pas': '0',
            'sort_col': 'pitches',
            'player_event_sort': 'api_p_release_speed',
            'sort_order': 'desc',
            'all': 'true',
            'type': 'details'
        }
        
        # Now override with our specific search parameters
        for key, values in search_params.items():
            if not values:  # Skip empty values
                continue
                
            if key == 'game_date_gt':
                payload['game_date_gt'] = values[0]
            elif key == 'game_date_lt':
                payload['game_date_lt'] = values[0]
            elif key == 'hfGT':  # Season types
                payload['hfGT'] = '|'.join(values) + '|'
            elif key == 'hfPT':  # Pitch types
                payload['hfPT'] = '|'.join(values) + '|'
            elif key == 'hfAB':  # PA results
                payload['hfAB'] = '|'.join(values) + '|'
            elif key == 'hfPR':  # Pitch results
                payload['hfPR'] = '|'.join(values) + '|'
            elif key == 'hfC':  # Count situations
                payload['hfC'] = '|'.join(values) + '|'
            elif key == 'hfOuts':  # Outs
                payload['hfOuts'] = '|'.join(values) + '|'
            elif key == 'hfPull':  # Batted ball direction
                payload['hfPull'] = '|'.join(values) + '|'
            elif key == 'hfStadium':  # Venues/Stadiums
                payload['hfStadium'] = '|'.join(values) + '|'
            elif key == 'hfSit':  # Situations
                payload['hfSit'] = '|'.join(values) + '|'
            elif key == 'pitcher_throws':  # Pitcher handedness
                payload['pitcher_throws'] = values[0]
            elif key == 'batter_stands':  # Batter handedness
                payload['batter_stands'] = values[0]
            elif key == 'hfTeam':  # Teams
                payload['hfTeam'] = '|'.join(values) + '|'
            elif key == 'pitchers_lookup[]':
                payload['pitchers_lookup[]'] = '|'.join(map(str, values))
            elif key == 'batters_lookup[]':
                payload['batters_lookup[]'] = '|'.join(map(str, values))
            elif key == 'player_type':
                payload['player_type'] = values[0]
            elif key.startswith('metric_'):
                # Handle metric parameters directly
                payload[key] = values[0] if len(values) == 1 else '|'.join(map(str, values))
        
        # Set max results
        payload['h_max'] = str(max_results)
        
        return payload

    def get_data_by_filters(self, search_params: dict, max_results: int = 50) -> pd.DataFrame:
        """
        Fetches and processes Statcast data for a set of search filters.
        """
        # Format payload to match Baseball Savant's expected format
        payload = self._format_savant_payload(search_params, max_results)
        
        # Debug output for metric parameters
        metric_params = {k: v for k, v in payload.items() if k.startswith('metric_')}
        if metric_params:
            print("--- DEBUG: Metric Parameters ---")
            for k, v in metric_params.items():
                print(f"{k}: {v}")
        
        print(f"--- DEBUG: Sending Request to Statcast ---")
        print(f"URL: {self.search_api_url}")
        print(f"Key parameters: hfPT={payload.get('hfPT')}, hfAB={payload.get('hfAB')}, hfPR={payload.get('hfPR')}")
        print(f"Game filters: hfGT={payload.get('hfGT')}, hfSea={payload.get('hfSea')}")
        print(f"Game situation: hfC={payload.get('hfC')}, hfOuts={payload.get('hfOuts')}, hfPull={payload.get('hfPull')}")
        print(f"Venue & Situation: hfStadium={payload.get('hfStadium')}, hfSit={payload.get('hfSit')}")
        print(f"Handedness: pitcher_throws={payload.get('pitcher_throws')}, batter_stands={payload.get('batter_stands')}")
        print(f"Player type: player_type={payload.get('player_type')}")
        print(f"Date range: game_date_gt={payload.get('game_date_gt')}, game_date_lt={payload.get('game_date_lt')}")
        print(f"Player filters: pitchers_lookup[]={payload.get('pitchers_lookup[]')}")
        
        try:
            response = requests.get(self.search_api_url, params=payload, timeout=90)
            response.raise_for_status()
            
            csv_content = response.text.strip()
            
            if not csv_content:
                print("DEBUG: Statcast search returned no data.")
                return pd.DataFrame()

            # Debug: Show first few lines of response
            lines = csv_content.split('\n')
            print(f"DEBUG: Response contains {len(lines)} lines")
            print("DEBUG: First line (headers):", lines[0] if lines else "No lines")
            
            # Check if response is an error
            if lines[0].strip().lower() == '"error"':
                print("DEBUG: Baseball Savant returned an error response")
                if len(lines) > 1:
                    print(f"DEBUG: Error details: {lines[1]}")
                return pd.DataFrame()
            
            df = pd.read_csv(StringIO(csv_content))
            print(f"DEBUG: Initial Statcast search returned {len(df)} rows.")
            
            if df.empty:
                print("DEBUG: DataFrame is empty after parsing CSV")
                return df

            # Check if we have the required columns
            required_cols = ['game_pk', 'at_bat_number', 'pitch_number']
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                print(f"DEBUG: Missing required columns: {missing_cols}")
                print(f"DEBUG: Available columns: {list(df.columns)}")
                # If we're missing core columns, there might be a different issue
                # Let's see what we actually got
                if len(df.columns) < 10:  # Probably an error response
                    print("DEBUG: Too few columns returned, likely an API error")
                    print(f"DEBUG: Full response preview:\n{csv_content[:500]}")
                return pd.DataFrame()

            # --- Gumbo Enrichment Step ---
            print("DEBUG: Enriching with Gumbo data to find playIds...")
            df['play_id'] = None # Initialize column
            
            for game_pk in df['game_pk'].unique():
                gumbo_data = self._fetch_gumbo_data(game_pk)
                if not gumbo_data:
                    continue
                
                all_gumbo_plays = gumbo_data.get('liveData', {}).get('plays', {}).get('allPlays', [])
                if not all_gumbo_plays:
                    continue
                
                # Get indices for all rows corresponding to the current game
                game_indices = df[df['game_pk'] == game_pk].index
                
                def find_id_for_row(row):
                    return self._find_play_id_from_gumbo(row, all_gumbo_plays)

                # Apply the finder function to this game's subset of the DataFrame
                found_ids = df.loc[game_indices].apply(find_id_for_row, axis=1)
                df.loc[game_indices, 'play_id'] = found_ids

            # --- Final Processing ---
            initial_count = len(df)
            df.dropna(subset=['play_id'], inplace=True)
            final_count = len(df)
            
            print(f"DEBUG: Found {final_count} rows with valid 'play_id' from Gumbo out of {initial_count} total rows.")
            
            if not df.empty:
                df['video_url'] = df['play_id'].apply(self._construct_video_url)
                print(f"DEBUG: Successfully created video URLs for {len(df)} plays.")

            return df
            
        except requests.exceptions.RequestException as e:
            print(f"--- DEBUG: Request Failed ---\nError: {e}")
            return pd.DataFrame()
        except Exception as e:
            print(f"--- DEBUG: An unexpected error occurred ---\nError: {e}")
            import traceback
            print(f"DEBUG: Full traceback:\n{traceback.format_exc()}")
            return pd.DataFrame()

    def get_data_by_play_id(self, game_pk: int, at_bat_number: int, pitch_number: int) -> pd.DataFrame:
        """
        Fetch data for a specific play by its identifiers.
        """
        params = {'game_pk': [game_pk]}
        df = self.get_data_by_filters(params, max_results=500)
        
        if not df.empty:
            df['at_bat_number'] = pd.to_numeric(df['at_bat_number'], errors='coerce')
            df['pitch_number'] = pd.to_numeric(df['pitch_number'], errors='coerce')
            play_df = df[
                (df['at_bat_number'] == at_bat_number) &
                (df['pitch_number'] == pitch_number)
            ].copy()
            print(f"DEBUG: Found {len(play_df)} matches for game_pk={game_pk}, at_bat={at_bat_number}, pitch={pitch_number}")
            return play_df
        return pd.DataFrame()