
import os
from datetime import date, datetime
from typing import Union, List, overload
from baseballcv.utilities import BaseballCVLogger
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

def _get_team(team: str, player: int, season: int) -> str:
    
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

@rate_limiter
def _parse_game_dates(start_dt: date, end_dt: date) -> List[int]:
    start_dt, end_dt = datetime.strftime(start_dt, "%Y-%m-%d"), datetime.strftime(end_dt, "%Y-%m-%d")
    response = requests_with_retry(GAMEDAY_DATE_RANGE_URL.format(start_dt, end_dt))

    game_pk_list = []


def get_game_pks_from_date_range(): ...


# This one only extracts from a date range
@overload
def get_pbp_data(
    start_dt: str,
    end_dt: str = None,
    team_abbr: str = None,
    player: int = None, # player ID
    pitch_type: str = None,
    max_return_videos: int = 10,
    max_videos_per_game: int = None
):
    start_dt_date, end_dt_date = sanitize_date_range(start_dt, end_dt)

    team = _get_team(team_abbr, player, end_dt_date.year)



# THis one extracts where the game and play IDs Are known
@overload
def get_pbp_data(
    game_pk: Union[int, List[int]],
    play_id: Union[str, List[str]],
    *,
    max_return_videos: int = 10, # Optional args in case the user wants to sample it
    max_videos_per_game: int = None
): ...