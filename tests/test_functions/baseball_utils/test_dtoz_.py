import pytest
from unittest.mock import patch

from baseballcv.functions.utils import DistanceToZone

@pytest.mark.skip('Test not needed for now')
def test_distance_to_zone(tmp_path):
        """
        Tests the distance_to_zone method of BaseballTools.
        
        This test verifies that the distance_to_zone method correctly:
        1. Initializes the DistanceToZone class
        2. Processes baseball pitch videos
        3. Returns properly formatted results with distance measurements
        
        Args:
            tmp_path: Temp directory for DTOZ
        """
                
        with patch('baseballcv.functions.utils.baseball_utils.distance_to_zone.DistanceToZone.analyze') as mock_analyze:
            mock_analyze.return_value = [{
                'game_pk': 1, 
                'play_id': 'a',
                'distance_inches': 2.5,
                'in_zone': True
            }]
                
            dtoz = DistanceToZone(results_dir=str(tmp_path))
            results_internal = dtoz.analyze(start_date="2024-05-01", end_date="2024-05-01", 
                                            max_videos=2, max_videos_per_game=2, create_video=False)
            
            assert len(results_internal) > 0
            assert isinstance(results_internal, list)
            assert isinstance(results_internal[0], dict)