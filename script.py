import os
import time

import arrapi
import configargparse
import questionary
import requests


class Show:
    def __init__(
        self, english_title: str, romaji_title: str, anilist_id: int, air_year: int
    ) -> None:
        self.english_title: str = english_title
        self.romaji_title: str = romaji_title
        self.anilist_id: int = anilist_id
        self.air_year: int = air_year
        self.tmdb_id: int | None = None
        self.tvdb_id: int | None = None

    def __str__(self) -> str:
        return f"English title: {self.english_title} - Romaji title {self.romaji_title} - Anilist ID: {self.anilist_id} - TMDB ID: {self.tmdb_id} - TVDB ID: {self.tvdb_id}"

    def __repr__(self) -> str:
        return str(self)

    def get_english_title(self) -> str:
        return self.english_title

    def get_romaji_title(self) -> str:
        return self.romaji_title

    def get_anilist_id(self) -> int:
        return self.anilist_id

    def get_air_year(self) -> int:
        return self.air_year

    def get_tmdb_id(self) -> int:
        if type(self.tmdb_id) is int:
            return self.tmdb_id
        raise TypeError(
            f"[ERROR] TMDB ID for <{self}> is not an int, type: {type(self.tmdb_id)}."
        )

    def get_tvdb_id(self) -> int:
        if type(self.tvdb_id) is int:
            return self.tvdb_id
        raise TypeError(
            f"[ERROR] TVDB ID for <{self}> is not an int, type: {type(self.tvdb_id)}."
        )

    def set_tmdb_id(self, tmdb_id: int) -> None:
        self.tmdb_id = tmdb_id

    def set_tvdb_id(self, tvdb_id: int) -> None:
        self.tvdb_id = tvdb_id


ANILIST_API_COOLDOWN = 0.8  # seconds
ANILIST_API_URL = "https://graphql.anilist.co"


def main() -> None:
    """Main function."""

    year = options.year[0]
    season = options.season[0]

    clear_screen()
    print(
        f"===== Anime Season For Sonarr =====\nYear: {year}\nSeason: {season.capitalize()}\n\nSearching...\n(The search can take a while)\n(The search will continue even after encountering [ERROR]s.)\n"
    )

    genre_id: int = get_TMDB_genre_id()

    shows: list[Show] = get_season_list(year, season)

    # whether to automatically select all or not
    select_all = options.select_all
    if (
        type(select_all) is str
    ):  # workaround for how configargparse handles bools in config files
        select_all: bool = True if select_all.capitalize() == "True" else False

    # contains shows that are found successfully
    shows_success: list[Show] = []
    shows_error: list[Show] = []  # contains shows that encountered an error

    for show in shows:
        try:
            show: Show = search_TMDB_for_show(show, genre_id)
            tvdb_id: int = get_TVDB_id_from_TMDB_id(show.get_tmdb_id())
            show.set_tvdb_id(tvdb_id)
            shows_success.append(show)
        except Exception as e:
            print(e)
            shows_error.append(show)

    sonarr: arrapi.SonarrAPI = arrapi.SonarrAPI(SONARR_BASE_URL, SONARR_API_KEY)
    shows_exist_sonarr: list[int] = get_shows_in_sonarr(sonarr)

    # if select_all is not enabled, ask the user which series they want to add
    if select_all is False:
        selected_shows: list[int] = interactive_selection(
            shows_success, shows_exist_sonarr
        )
    else:
        print("Select all enabled. Adding all shows...")
        selected_shows: list[int] = [show.get_tvdb_id() for show in shows_success]

    # log error titles if there are any
    if shows_error:
        try:
            file = open("log_error_titles.txt", "a", encoding="utf-8")
        except FileNotFoundError:
            file = open("log_error_titles.txt", "w", encoding="utf-8")
            file.close()
            file = open("log_error_titles.txt", "a", encoding="utf-8")
        file.write(f"Year: {year} - Season: {season.capitalize()}\n")
        for show in shows_error:
            file.write(f"{show}\n")
        file.write("-----\n")
        file.close()

    # Add series to Sonarr
    added, exists, not_found, excluded = add_series_to_sonarr(selected_shows, sonarr)
    print(
        f"Added: {added} - Exists: {exists} - Not Found: {not_found} - Excluded: {excluded}"
    )


def interactive_selection(
    all_shows: list[Show], existing_tvdb_ids: list[int]
) -> list[int]:
    """Interactive selection screen. Returns a list of TVDB IDs of the selected shows."""

    romaji = options.romaji
    if romaji is True:
        choices = [
            questionary.Choice(
                title=show.get_romaji_title(),
                value=show.get_tvdb_id(),
                disabled="Anime already exists in Sonarr"
                if show.get_tvdb_id() in existing_tvdb_ids
                else None,
            )
            for show in all_shows
        ]
    else:
        choices = [
            questionary.Choice(
                title=show.get_english_title(),
                value=show.get_tvdb_id(),
                disabled="Anime already exists in Sonarr"
                if show.get_tvdb_id() in existing_tvdb_ids
                else None,
            )
            for show in all_shows
        ]

    selected_shows = questionary.checkbox(
        "Select anime to add to Sonarr:", choices=choices
    ).ask()

    if selected_shows is None:
        raise TypeError("[ERROR] No shows selected.")

    return selected_shows


def get_shows_in_sonarr(sonarr: arrapi.SonarrAPI) -> list[int]:
    """Returns the TVDB IDs of the shows in Sonarr."""

    series = sonarr.all_series()
    tvdb_ids = [int(entry.tvdbId) for entry in series]
    return tvdb_ids


def clear_screen() -> None:
    """Clear the screen."""
    os.system("cls" if os.name == "nt" else "clear")


def get_season_list(year: int, season: str) -> list[Show]:
    """Get the list of anime from Anilist API for the given season."""

    shows: list[Show] = []
    page = 1
    has_next_page = None

    while (page == 1) or (has_next_page is True):
        query = """
        query ($page: Int, $season: MediaSeason, $seasonYear: Int) {
            Page(page: $page, perPage: 30) {
                pageInfo {
                    hasNextPage
                    currentPage
                    lastPage
                }
                media(season: $season, seasonYear: $seasonYear, type: ANIME, format: TV) {
                    id
                    title {
                        romaji
                        english
                    }
                    seasonYear
                }
            }
        }
        """

        variables = {"page": page, "season": season.upper(), "seasonYear": year}

        response = requests.post(
            ANILIST_API_URL, json={"query": query, "variables": variables}, timeout=60
        ).json()
        time.sleep(ANILIST_API_COOLDOWN)  # Avoid rate limiting

        has_next_page = response["data"]["Page"]["pageInfo"]["hasNextPage"]
        page += 1

        for entry in response["data"]["Page"]["media"]:
            shows.append(
                Show(
                    english_title=entry["title"]["english"],
                    romaji_title=entry["title"]["romaji"],
                    anilist_id=entry["id"],
                    air_year=entry["seasonYear"],
                )
            )

    if not shows:  # if no shows are found (the list is empty)
        raise Exception(
            f"[ERROR] No titles found from Anilist API. Series for <year: {year} season: {season}> don't exist."
        )

    return shows


def build_TMDB_genre_dict() -> dict[str, int]:
    """Build a list of TMDB genres."""

    url = f"https://api.themoviedb.org/3/genre/movie/list?api_key={TMDB_API_KEY}"
    response = requests.get(url, timeout=60).json()
    genre_dict = {}
    for genre in response["genres"]:
        genre_dict.update({genre["name"]: genre["id"]})
    return genre_dict


def get_TMDB_genre_id(genre_to_find: str = "Animation") -> int:
    """Get the TMDB genre ID for anime."""

    genre_dict = build_TMDB_genre_dict()
    for genre_name, genre_id in genre_dict.items():
        if genre_name == genre_to_find:
            return genre_id
    raise Exception(f"[ERROR] Genre '{genre_to_find}' not found.")


def search_TMDB_for_show(show: Show, genre_id: int) -> Show:
    """Search for a show on TMDB. Return updated Show."""

    query = show.get_english_title().replace(" ", "+")
    url = f"https://api.themoviedb.org/3/search/tv?api_key={TMDB_API_KEY}&query={query}&first_air_date_year={show.get_air_year()}&page=1"
    response = requests.get(url, timeout=60).json()

    if response["total_results"] == 0:
        # try using the romaji title
        query = show.get_romaji_title().replace(" ", "+")
        url = f"https://api.themoviedb.org/3/search/tv?api_key={TMDB_API_KEY}&query={query}&first_air_date_year={show.get_air_year()}&page=1"
        response = requests.get(url, timeout=60).json()

        if response["total_results"] == 0:
            # Search recursively for parent story
            show = search_previous_season(show)
            return search_TMDB_for_show(show, genre_id)

    # Iterate through all results and return the one with the correct genre
    if response["total_results"] != 0:
        current_page = response["page"]
        last_page = response["total_pages"]

        while current_page <= last_page:
            for result in response["results"]:
                if (genre_id in result["genre_ids"]) and (
                    result["origin_country"][0] in ("JP", "CN", "KR", "TW", "HK")
                ):
                    show.set_tmdb_id(int(result["id"]))
                    return show

            current_page += 1
            url = f"https://api.themoviedb.org/3/search/tv?api_key={TMDB_API_KEY}&first_air_date_year={show.get_air_year()}&query={query}&page={current_page}"
            time.sleep(ANILIST_API_COOLDOWN)  # Avoid rate limiting
            response = requests.get(url, timeout=60).json()

        raise Exception(
            f"[ERROR] No result(s) with <genre id: {genre_id}> found for <{show}> on TMDB."
        )

    raise Exception("-- this shouldn't happen, please report --")


def search_previous_season(show: Show) -> Show:
    """Search for the previous season of a show via Anilist API. Returns the previous season (Show object)"""

    query = """
    query ($id: Int) {
        Media(id: $id, type: ANIME) {
            relations {
                edges {
                    relationType
                    node {
                        id
                        title {
                            romaji
                            english
                        }
                        seasonYear
                    }
                }
            }
        }
    }
    """

    variables = {"id": show.get_anilist_id()}

    response = requests.post(
        ANILIST_API_URL, json={"query": query, "variables": variables}, timeout=60
    ).json()
    time.sleep(ANILIST_API_COOLDOWN)  # Avoid rate limiting

    found = False
    parent_story = None
    prequel = None

    for entry in response["data"]["Media"]["relations"]["edges"]:
        if entry["relationType"] == "PARENT":
            parent_story = Show(
                english_title=entry["node"]["title"]["english"],
                romaji_title=entry["node"]["title"]["romaji"],
                anilist_id=entry["node"]["id"],
                air_year=entry["node"]["seasonYear"],
            )
            found = True
        if entry["relationType"] == "PREQUEL":
            prequel = Show(
                english_title=entry["node"]["title"]["english"],
                romaji_title=entry["node"]["title"]["romaji"],
                anilist_id=entry["node"]["id"],
                air_year=entry["node"]["seasonYear"],
            )
            found = True

    if found is False:
        raise Exception(f"[ERROR] No relations found for <{show}>.")

    show_to_search = parent_story if parent_story is not None else prequel

    return show_to_search


def get_TVDB_id_from_TMDB_id(tmdb_id: int) -> int:
    """Get the TVDB ID from a TMDB ID."""

    url = (
        f"https://api.themoviedb.org/3/tv/{tmdb_id}/external_ids?api_key={TMDB_API_KEY}"
    )
    response = requests.get(url, timeout=60).json()

    if "tvdb_id" not in response:
        raise Exception(f"[ERROR] No TVDB ID field for <TMDB ID: {tmdb_id}>.")

    if response["tvdb_id"] is None:
        raise Exception(f"[ERROR] TVDB ID is None for <TMDB ID: {tmdb_id}>.")

    tvdb_id = int(response["tvdb_id"])
    return tvdb_id


def add_series_to_sonarr(tvdb_ids: list[int], sonarr: arrapi.SonarrAPI):
    """Add given shows to Sonarr."""

    # Get config
    root_folder = options.root_folder
    quality_profile = options.quality_profile

    language_profile = options.language_profile
    if language_profile == "NULL":
        language_profile = None

    monitor = options.monitor

    season_folder = options.season_folder
    if type(season_folder) is str:
        season_folder = True if season_folder.capitalize() == "True" else False

    search = options.search
    if type(search) is str:
        search = True if search.capitalize() == "True" else False

    unmet_search = options.unmet_search
    if type(unmet_search) is str:
        unmet_search = True if unmet_search.capitalize() == "True" else False

    series_type = options.series_type.lower()

    tags = options.tags
    if tags == []:
        tags = None

    added, exists, not_found, excluded = sonarr.add_multiple_series(
        ids=tvdb_ids,
        root_folder=root_folder,
        quality_profile=quality_profile,
        language_profile=language_profile,
        monitor=monitor,
        season_folder=season_folder,
        search=search,
        unmet_search=unmet_search,
        series_type=series_type,
        tags=tags,
    )

    return added, exists, not_found, excluded


if __name__ == "__main__":
    configargp = configargparse.ArgParser(
        prog="anime-season-for-sonarr",
        description="Automate bulk adding anime seasons to Sonarr.",
        epilog="Most options can be set in the config file.",
        default_config_files=["config.ini"],
    )

    configargp.add_argument("year", nargs=1, type=int, help="year of the anime season.")
    configargp.add_argument(
        "season",
        nargs=1,
        choices=["winter", "spring", "summer", "fall"],
        help="season of the anime season. Lowercase.",
    )
    configargp.add_argument(
        "-c",
        "--config",
        is_config_file=True,
        help="set config file path (default: ./config.ini). Note: you MUST use this option if the config file is not inside the direcotry you are running the script from.",
    )
    configargp.add_argument("-k", "--tmdb_api_key", help="Set [TMDB] API key.")
    configargp.add_argument("-u", "--base_url", help="Set [Sonarr] base URL.")
    configargp.add_argument("-a", "--sonarr_api_key", help="Set [Sonarr] API key.")
    configargp.add_argument(
        "-r", "--root_folder", help="Set [Sonarr] series root folder."
    )
    configargp.add_argument(
        "-q", "--quality_profile", help="Set [Sonarr] quality profile."
    )
    configargp.add_argument(
        "-l",
        "--language_profile",
        help="Set [Sonarr] language profile (Sonarr v3 only).",
    )
    configargp.add_argument(
        "-m",
        "--monitor",
        choices=[
            "all",
            "future",
            "missing",
            "existing",
            "pilot",
            "firstSeason",
            "latestSeason",
            "none",
        ],
        help="Set [Sonarr] series monitor mode.",
    )
    configargp.add_argument(
        "--season_folder",
        dest="season_folder",
        action="store_true",
        help="[Sonarr] use season folder.",
    )
    configargp.add_argument(
        "--no_season_folder",
        dest="season_folder",
        action="store_false",
        help="[Sonarr] don't use season folder.",
    )
    configargp.add_argument(
        "--search",
        dest="search",
        action="store_true",
        help="[Sonarr] start searching for missing episodes on add.",
    )
    configargp.add_argument(
        "--no_search",
        dest="search",
        action="store_false",
        help="[Sonarr] don't start searching for missing episodes on add.",
    )
    configargp.add_argument(
        "--unmet_search",
        dest="unmet_search",
        action="store_true",
        help="[Sonarr] start search for cutoff unmet episodes on add.",
    )
    configargp.add_argument(
        "--no_unmet_search",
        dest="unmet_search",
        action="store_false",
        help="[Sonarr] don't start search for cutoff unmet episodes on add.",
    )
    configargp.add_argument(
        "-p",
        "--series_type",
        choices=["standard", "daily", "anime"],
        help="Set [Sonarr] series type.",
    )
    configargp.add_argument(
        "-t",
        "--tags",
        action="append",
        help="[Sonarr] tag(s) to add, can be used multiple times to add multiple tags. Example: -t anime -t seasonal -t qBit",
    )
    configargp.add_argument(
        "--select_all",
        dest="select_all",
        action="store_true",
        help="Add to [Sonarr] automatically without asking.",
    )
    configargp.add_argument(
        "--no_select_all",
        dest="select_all",
        action="store_false",
        help="Ask whether or not to add to [Sonarr].",
    )
    configargp.add_argument(
        "--romaji",
        help="Show Romaji titles instead of English titles.",
        action="store_true",
    )

    options = configargp.parse_args()
    TMDB_API_KEY = options.tmdb_api_key
    SONARR_BASE_URL = options.base_url
    SONARR_API_KEY = options.sonarr_api_key
    main()
