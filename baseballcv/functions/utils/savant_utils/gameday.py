import os
import concurrent.futures
import polars as pl
from datetime import date, datetime
from typing import Union, List, Dict, overload
from baseballcv.utilities import BaseballCVLogger, ProgressBar
from .crawler import sanitize_date_range, generate_date_range, requests_with_retry, rate_limiter

# Final goal: Return a polars dataframe of the filtered results
logger = BaseballCVLogger.get_logger(os.path.basename(__file__))

GAMEDAY_DATE_RANGE_URL = 'https://statsapi.mlb.com/api/v1/schedule?sportId=1&startDate={}&endDate={}&timeZone=America/New_York&gameType=E&&gameType=S&&gameType=R&&gameType=F&&gameType=D&&gameType=L&&gameType=W&&gameType=A&&gameType=C&language=en&leagueId=103&&leagueId=104&hydrate=team,flags,broadcasts(all),venue(location)&sortBy=gameDate,gameStatus,gameType'
GAMEDAY_PBP_URL = 'https://statsapi.mlb.com/api/v1/game/{}/playByPlay'

mlb_teams = {'ATH': 133, 'PIT': 134, 'SD': 135, 'SEA': 136,
        'SF': 137, 'STL': 138, 'TB': 139, 'TEX': 140, 'TOR': 141,
        'MIN': 142, 'PHI': 143, 'ATL': 144, 'CWS': 145, 'MIA': 146,
        'NYY': 147, 'MIL': 158, 'LAA': 108, 'AZ': 109, 'BAL': 110, 
        'BOS': 111, 'CHC': 112, 'CIN': 113, 'CLE': 114, 'COL': 115, 
        'DET': 116, 'HOU': 117, 'KC': 118, 'LAD': 119, 'WSH': 120,
        'NYM': 121
        }

corrected_teams = {'CHW': 'CWS', 'OAK': 'ATH', 'ARI': 'AZ' } # Incorrect -> Correct

# Renames normalized json columns
rename_map = {
    'count_balls': 'balls', 'count_strikes': 'strikes', 'count_outs': 'outs',
    'playId': 'play_id', 'pitchNumber': 'pitch_number_ab',
    'details_type_code': 'pitch_type', 'details_type_description': 'pitch_name',
    'pitchData_startSpeed': 'release_speed',  'pitchData_strikeZoneTop': 'sz_top',
    'pitchData_strikeZoneBottom': 'sz_bot', 'pitchData_coordinates_aX': 'ax',
    'pitchData_coordinates_aY': 'ay', 'pitchData_coordinates_aZ': 'az',
    'pitchData_coordinates_pfxX': 'pfx_x', 'pitchData_coordinates_pfxZ': 'pfx_z',
    'pitchData_coordinates_pX': 'plate_x', 'pitchData_coordinates_pZ': 'plate_z',
    'pitchData_coordinates_vX0': 'vx0', 'pitchData_coordinates_vY0': 'vy0',
    'pitchData_coordinates_vZ0': 'vz0', 'pitchData_coordinates_x0': 'x0',
    'pitchData_coordinates_y0': 'y0', 'pitchData_coordinates_z0': 'z0',
    'pitchData_breaks_breakAngle': 'break_angle', 'pitchData_breaks_breakLength': 'break_length',
    'pitchData_breaks_breakY': 'break_y', 'pitchData_breaks_breakHorizontal': 'horizontal_break',
    'pitchData_breaks_breakVertical': 'vertical_break', 'pitchData_breaks_breakVerticalInduced': 'induced_vertical_break',
    'pitchData_breaks_spinRate': 'spin_rate', 'pitchData_breaks_spinDirection': 'spin_direction',
    'pitchData_zone': 'zone', 'pitchData_typeConfidence': 'pitchtype_confidence',
    'pitchData_plateTime': 'plate_time', 'pitchData_extension': 'extension',
    'hitData_launchSpeed': 'launch_speed', 'hitData_launchAngle': 'launch_angle',
    'hitData_totalDistance': 'hit_distance', 'hitData_trajectory': 'hit_trajectory',
    'hitData_coordinates_coordX': 'hit_coord_x', 'hitData_coordinates_coordY': 'hit_coord_y'
}

columns_of_interest = list(rename_map.values())

# Use a third of the CPU threads
cpu_threads = os.cpu_count() / 3 if os.cpu_count() else None

def _get_team(team: Union[str, None], player: Union[int, None], season: int) -> Union[str, None]:
    if not team:
        return # Skip the function as no team was queried
    
    if player and not team: # If player is specified, but not team, query latest team for faster queries
        player_universe_url = f'https://statsapi.mlb.com/api/v1/sports/1/players?season={season}'
        response = requests_with_retry(player_universe_url)
        people = response.json()['people']
        team_id = None

        for player in people:
            if player.get('id') == player:
                team_id = player.get('currentTeam')['id']
                break

        if not team_id:
            raise ValueError(f"Cannot find player ID {player}. Maybe a typo?")
        
        team_abbr = {v: k for k,v in mlb_teams.items()}.get(team_id)
        return team_abbr

    team_abbr = corrected_teams.get(team.upper(), team.upper())

    if team_abbr not in mlb_teams:
        raise ValueError(
            f"ERROR: Team Abbreviation '{team_abbr}' was not recognized.\n"
            "Please use proper team abbreviations. These conversions are supported:\n"
            "* ARI -> AZ\n"
            "* OAK -> ATH\n"
            "* CHW -> CWS"
        )
    return team_abbr

def _check_game_pks(game_pks: dict) -> None:
    if not game_pks:
        raise ValueError(
            "Game IDs should not be None.\n"
            "If you specified a player, please check to make sure you put in the correct team.\n"
            "Another issue could be that there were no games in the queried date range."
        )
    if not isinstance(game_pks, dict):
        raise ValueError('Game Pks must be a large dictionary')

    for game, game_info in game_pks.items():
        if not isinstance(game_info, dict):
            raise ValueError(f"Game entry '{game}' is not a dictionary.")
        if not all(key in game_info for key in ['home_team', 'away_team']):
            raise ValueError(f"Game entry '{game}' must contain both 'home_team' and 'away_team' keys.")

@rate_limiter
def _parse_game_dates(start_dt: date, end_dt: date, team_abbr: str = None) -> Dict[int, Dict[str, str]]:
    start_dt, end_dt = datetime.strftime(start_dt, "%Y-%m-%d"), datetime.strftime(end_dt, "%Y-%m-%d")
    response = requests_with_retry(GAMEDAY_DATE_RANGE_URL.format(start_dt, end_dt))

    game_pk_dict: Dict[int, Dict[str, str]] = {}

    for games in response.json()['dates']:
        for game in games['games']:
            home_team = game['teams']['home']['team'].get('abbreviation', 'Unknown')
            away_team = game['teams']['away']['team'].get('abbreviation', 'Unknown')
            game_pk = game.get('gamePk', None)

            if team_abbr is None or home_team == team_abbr or away_team == team_abbr:
                game_pk_dict[game_pk] = {'home_team': home_team, 'away_team': away_team}

    # Should be unique games, if for some reason the API doesn't update delayed games, troubleshoot here
    return game_pk_dict

@rate_limiter(20) # ~20 calls per second
def _parse_game_data(
    game_pk: int, 
    home_team: str, 
    away_team: str, 
    player: int = None,
    pitch_type: str = None, 
    max_videos_per_game: int = None
    ) -> pl.DataFrame:

    response = requests_with_retry(GAMEDAY_PBP_URL.format(game_pk))

    df = pl.DataFrame()
    inning_list = []
    inning_top_bot_list = []
    batter_list = []
    pitcher_list = []
    p_throws_list = []

    for play in response.json()['allPlays']:
        inning = play['about']['inning']
        inning_top_bot = play['about']['halfInning']
        batter = play['matchup']['batter']['id']
        pitcher = play['matchup']['pitcher']['id']
        p_throws = play['matchup']['pitchHand']['code']

        for pitch in play.get('playEvents', {}):
            if not pitch.get('isPitch', None):
                continue # Skip non-pitch instances

            _df = pl.json_normalize(pitch, separator='_')

            # Since columns are created and filled with NA, remove strict requirement
            _df = _df.rename(rename_map, strict=False) 

            # Fill in missing columns with None
            for col in columns_of_interest:
                if col not in _df.columns:
                    _df = _df.with_columns(pl.lit(None).alias(col))
            _df = _df.select(columns_of_interest)

            df = pl.concat([df, _df], how='diagonal_relaxed')
            inning_list.append(inning)
            inning_top_bot_list.append(inning_top_bot)
            batter_list.append(batter)
            pitcher_list.append(pitcher)
            p_throws_list.append(p_throws)
    
    df = df.with_columns([
            pl.Series(name="batter", values = batter_list),
            pl.Series(name="pitcher", values = pitcher_list),
            pl.Series(name="p_throws", values = p_throws_list),
            pl.Series(name="inning", values = inning_list),
            pl.Series(name="inning_top_bot", values = inning_top_bot_list),
            pl.lit(game_pk).alias("game_pk"),
            pl.lit(home_team).alias("home_team"),
            pl.lit(away_team).alias("away_team")
        ])
    
    # Apply filters for player and pitch type
    if player:
        player_filter = (pl.col('batter') == player) | (pl.col('pitcher') == player)
        if pitch_type:
            df = df.filter(player_filter & (pl.col('pitch_type') == pitch_type))
        else:
            df = df.filter(player_filter)
    elif pitch_type:
        df = df.filter(pl.col('pitch_type') == pitch_type)
    
    if max_videos_per_game:
        return df.sample(min(max_videos_per_game, len(df)))
    
    return df
    

def thread_game_dates(start_dt: date, end_dt: date, team_abbr: str) -> list:
    date_range = list(generate_date_range(start_dt, end_dt))

    game_pks = []
    with ProgressBar(total=len(date_range), desc='Extracting Game IDs') as progress:
        with concurrent.futures.ThreadPoolExecutor(max_workers=cpu_threads) as executor:
            futures = {executor.submit(_parse_game_dates, subsq_start, subsq_end, team_abbr) for subsq_start, subsq_end in date_range}
            for future in concurrent.futures.as_completed(futures):
                game_pks.append(future.result())
                progress.update(1)
    return game_pks

def thread_game_data(game_pks: dict, player: str, pitch_type: str, max_videos_per_game: int, max_return_videos: int) -> pl.DataFrame:
    play_ids_df = []
    with ProgressBar(game_pks.keys(), desc='Extracting Game Data', total=len(game_pks.keys())) as progress:
        with concurrent.futures.ThreadPoolExecutor(max_workers=cpu_threads) as executor:
            futures = {executor.submit(_parse_game_data, game_pk, teams_data['home_team'], teams_data['away_team'], 
                                       player, pitch_type, max_videos_per_game) for game_pk, teams_data in game_pks.items()}
            
            for future in concurrent.futures.as_completed(futures):
                play_ids_df.append(future.result())
                progress.update(1)

    play_ids_df = pl.concat(play_ids_df, how = 'diagonal_relaxed') # Hoping diagonal relaxed fixes the Null -> Ints, Floats columns

    if play_ids_df.is_empty():
        raise pl.exceptions.NoDataError("Cannot continue, no dataframe was returned.")
    
    if max_return_videos:
        return play_ids_df.sample(min(max_return_videos, len(play_ids_df)))
    return play_ids_df
    
@overload
def get_pbp_data(
    start_dt: str,
    end_dt: str = None,
    *, # To make parsing simpler, make the rest keyword arguments
    team_abbr: str = None,
    player: int = None, # player ID
    pitch_type: str = None,
    max_return_videos: int = 10,
    max_videos_per_game: int = None
) -> pl.DataFrame:  ...

@overload
def get_pbp_data(
    game_pks: List[Dict[int, Dict[str, str]]],
    *, # To make parsing simpler, make the rest keyword arguments
    player: int = None, # player ID
    pitch_type: str = None,
    max_return_videos: int = 10, # Optional args in case the user wants to sample it
    max_videos_per_game: int = None
) -> pl.DataFrame: ...


def get_pbp_data(
    *args,
    **kwargs
) -> pl.DataFrame:

    start_dt = kwargs.get('start_dt', args[0] if args and isinstance(args[0], str) else None)
    end_dt = kwargs.get('end_dt', args[1] if args and isinstance(args[1], str) else None)
    team_abbr = kwargs.get('team_abbr', None)
    player = kwargs.get('player', None)
    pitch_type = kwargs.get('pitch_type', None)
    max_videos_per_game = kwargs.get('max_videos_per_game', None)
    max_return_videos = kwargs.get('max_return_videos', 10)
    game_pks = kwargs.get('game_pks', None)

    if start_dt:
        start_dt_date, end_dt_date = sanitize_date_range(start_dt, end_dt)

        if (end_dt_date - start_dt_date).days >= 45:
            _OVERSIZE_WARN_STRING = """
            Woah, that's a hefty request you've got there. Please consider using arguments such as 
            `team_abbr` or `player` if you are only looking for a specific team or player to make
            queries faster. """
            logger.warning(_OVERSIZE_WARN_STRING)

        team = _get_team(team_abbr, player, end_dt_date.year)

        game_pks = thread_game_dates(start_dt_date, end_dt_date, team)
    
    game_pks = {k: v for d in game_pks for k, v in d.items()} # Flatten list into one large dictionary

    _check_game_pks(game_pks)

    return thread_game_data(game_pks, player, pitch_type, max_videos_per_game, max_return_videos)