import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

# now we can import the module in the parent directory.
import anime_season_for_sonarr as script


class TestScript(unittest.TestCase):
    def setUp(self):
        script.TMDB_API_KEY = "ac395b50e4cb14bd5712fa08b936a447"
        script.TARGET_COUNTRIES = {"JP", "CN", "KR", "TW", "HK"}

    def test_get_season_list(self):
        expected_output_shows = (
            script.Show(
                english_title="ZOMBIE LAND SAGA REVENGE",
                romaji_title="Zombie Land Saga: Revenge",
                anilist_id=110733,
                air_year=2021,
                tmdb_id=None,
                tvdb_id=None,
            ),  # first expected item in response
            script.Show(
                english_title=None,
                romaji_title="Oshiri Tantei 5",
                anilist_id=132697,
                air_year=2021,
                tmdb_id=None,
                tvdb_id=None,
            ),  # last expected item in response
        )

        shows = script.get_season_list(2021, "spring")

        # just test the first and last items in response
        self.assertTupleEqual((shows[0], shows[-1]), expected_output_shows)
        # and that the number of items is correct
        self.assertEqual(len(shows), 47)

    def test_build_TMDB_genre_dict(self):
        expected_output = {
            "Action": 28,
            "Adventure": 12,
            "Animation": 16,
            "Comedy": 35,
            "Crime": 80,
            "Documentary": 99,
            "Drama": 18,
            "Family": 10751,
            "Fantasy": 14,
            "History": 36,
            "Horror": 27,
            "Music": 10402,
            "Mystery": 9648,
            "Romance": 10749,
            "Science Fiction": 878,
            "TV Movie": 10770,
            "Thriller": 53,
            "War": 10752,
            "Western": 37,
        }

        self.assertEqual(script.build_TMDB_genre_dict(), expected_output)

    def test_get_TMDB_genre_id(self):
        self.assertEqual(script.get_TMDB_genre_id("Animation"), 16)

    def test_search_TMDB_for_show(self):
        input_show = script.Show(
            english_title="BOCCHI THE ROCK!",
            romaji_title="Bocchi the Rock!",
            anilist_id=130003,
            air_year=2022,
        )

        expected_output_show = script.Show(
            english_title="BOCCHI THE ROCK!",
            romaji_title="Bocchi the Rock!",
            anilist_id=130003,
            air_year=2022,
            tmdb_id=119100,
        )

        input_show.tmdb_id = script.search_TMDB_for_show(input_show, 16)

        self.assertEqual(input_show, expected_output_show)

    def test_search_previous_season(self):
        input_show = script.Show(
            english_title="Kaguya-sama: Love is War -Ultra Romantic-",
            romaji_title="Kaguya-sama wa Kokurasetai: Ultra Romantic",
            anilist_id=125367,
            air_year=2022,
        )

        expected_output_show = script.Show(
            english_title="Kaguya-sama: Love is War?",
            romaji_title="Kaguya-sama wa Kokurasetai?: Tensaitachi no Renai Zunousen",
            anilist_id=112641,
            air_year=2020,
        )

        self.assertEqual(
            script.search_previous_season(input_show), expected_output_show
        )

    def test_get_TVDB_id_from_TMDB_id(self):
        self.assertEqual(script.get_TVDB_id_from_TMDB_id(65844), 303867)

    def test_anilist_rate_limiter(self):
        """Test the AniListRateLimiter class functionality."""
        from unittest.mock import Mock  # noqa: PLC0415

        import httpx  # noqa: PLC0415

        # Test rate limiter initialization
        rate_limiter = script.AniListRateLimiter()
        self.assertEqual(rate_limiter.remaining_requests, 90)
        self.assertEqual(rate_limiter.limit, 90)

        # Test handling of rate limit headers
        mock_response = Mock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.headers = {
            "X-RateLimit-Limit": "90",
            "X-RateLimit-Remaining": "45",
        }

        rate_limiter.handle_response(mock_response)
        self.assertEqual(rate_limiter.remaining_requests, 45)
        self.assertEqual(rate_limiter.limit, 90)

        # Test 429 status code handling
        mock_response_429 = Mock(spec=httpx.Response)
        mock_response_429.status_code = 429
        mock_response_429.headers = {
            "Retry-After": "1",  # 1 second for testing
            "X-RateLimit-Remaining": "0",
        }

        import time  # noqa: PLC0415

        start_time = time.time()
        rate_limiter.handle_response(mock_response_429)
        elapsed_time = time.time() - start_time

        # Should have waited at least 1 second
        self.assertGreaterEqual(elapsed_time, 1.0)
        self.assertEqual(rate_limiter.remaining_requests, 0)


if __name__ == "__main__":
    unittest.main()
