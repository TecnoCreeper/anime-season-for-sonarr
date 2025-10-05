import sys
import unittest
from pathlib import Path

import httpx

sys.path.append(str(Path(__file__).parent.parent))

# now we can import the module in the parent directory.
import anime_season_for_sonarr as script


class TestScript(unittest.TestCase):
    def setUp(self):
        script.TMDB_API_KEY = "ac395b50e4cb14bd5712fa08b936a447"
        script.TARGET_COUNTRIES = {"JP", "CN", "KR", "TW", "HK"}
        script.client = httpx.Client()

    def tearDown(self):
        script.client.close()

    def test_get_season_list_no_filters(self):
        shows = script.get_season_list(2021, "spring")

        expected_output = (
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

        # just test the first and last items in response
        self.assertTupleEqual((shows[0], shows[-1]), expected_output)
        # and that the number of items is correct
        self.assertEqual(len(shows), 47)

    def test_get_TMDB_genre_id(self):
        self.assertEqual(script.get_TMDB_genre_id("Animation"), 16)

    def test_search_TMDB_for_show(self):
        test_input = script.Show(
            english_title="BOCCHI THE ROCK!",
            romaji_title="Bocchi the Rock!",
            anilist_id=130003,
            air_year=2022,
        )

        expected_output = script.Show(
            english_title="BOCCHI THE ROCK!",
            romaji_title="Bocchi the Rock!",
            anilist_id=130003,
            air_year=2022,
            tmdb_id=119100,
        )

        test_input.tmdb_id = script.search_TMDB_for_show(test_input, 16)

        self.assertEqual(test_input, expected_output)

    def test_search_previous_season(self):
        test_input = script.Show(
            english_title="Kaguya-sama: Love is War -Ultra Romantic-",
            romaji_title="Kaguya-sama wa Kokurasetai: Ultra Romantic",
            anilist_id=125367,
            air_year=2022,
        )

        expected_output = script.Show(
            english_title="Kaguya-sama: Love is War?",
            romaji_title="Kaguya-sama wa Kokurasetai?: Tensaitachi no Renai Zunousen",
            anilist_id=112641,
            air_year=2020,
        )

        self.assertEqual(script.search_previous_season(test_input), expected_output)

    def test_get_TVDB_id_from_TMDB_id(self):
        self.assertEqual(script.get_TVDB_id_from_TMDB_id(65844), 303867)

    def test_anilist_rate_limiter(self):
        """Test the ratelimiting functionality."""

        from unittest.mock import Mock  # noqa: PLC0415

        mock_response_429 = Mock(spec=httpx.Response)
        mock_response_429.status_code = 429
        mock_response_429.headers = {
            "Retry-After": "1",  # 1 second for testing
            "X-RateLimit-Remaining": "0",
        }

        import time  # noqa: PLC0415

        start_time = time.time()
        script.AnilistRequestHandler._handle_outcome(mock_response_429)
        elapsed_time = time.time() - start_time

        # Should have waited at least 1 second
        self.assertGreaterEqual(elapsed_time, 1.0)

    def test_filtering(self):
        shows = script.get_season_list(
            2025,
            "fall",
            genres_include=["comedy", "slice of life"],
            genres_exclude=["romance"],
            tags_include=["work"],
            tags_exclude=["Parody"],
        )

        expected_output = script.Show(
            english_title="A Mangaka's Weirdly Wonderful Workplace",
            romaji_title="Egao no Taenai Shokuba desu.",
            anilist_id=173523,
            air_year=2025,
            tmdb_id=None,
            tvdb_id=None,
        )

        self.assertEqual(shows[0], expected_output)


if __name__ == "__main__":
    unittest.main()
