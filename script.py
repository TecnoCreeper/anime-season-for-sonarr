import os
import time
from dataclasses import dataclass

import arrapi
import configargparse
import questionary
import requests


@dataclass
class Show:
    """Show dataclass."""

    english_title: str
    romaji_title: str
    anilist_id: int
    air_year: int
    tmdb_id: int | None = None
    tvdb_id: int | None = None


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

    genre_id: int = get_TMDB_genre_id("Animation")

    shows: list[Show] = get_season_list(year, season)

    shows_success: list[Show] = []  # contains shows that are found successfully
    shows_error: list[Show] = []  # contains shows that encountered an error

    for show in shows:  # try to add the tmdb_id and the tvdb_id to each show
        try:
            # <show> is a class, so it's passed by reference.
            # The show is updated inside the function, so it doesn't need to return anything.
            search_TMDB_for_show(show, genre_id)
            tvdb_id: int = get_TVDB_id_from_TMDB_id(show.tmdb_id)
            show.tvdb_id = tvdb_id
            shows_success.append(show)
        except SystemExit as e:
            print(e)
            exit(1)
        except Exception as e:
            print(e)
            shows_error.append(show)

    # log error titles to file if there are any
    if shows_error:
        try:
            file = open("log_search_errors.txt", "a", encoding="utf-8")
        except FileNotFoundError:
            file = open("log_search_errors.txt", "w", encoding="utf-8")
            file.close()
            file = open("log_search_errors.txt", "a", encoding="utf-8")

        file.write(f"Year: {year} - Season: {season.capitalize()}\n")
        for show in shows_error:
            file.write(f"{show}\n")
        file.write("-----\n")
        file.close()

    try:
        sonarr: arrapi.SonarrAPI = arrapi.SonarrAPI(SONARR_BASE_URL, SONARR_API_KEY)
    except Exception as e:
        print(e)
        exit(1)

    shows_exist_sonarr: list[int] = get_shows_in_sonarr(sonarr)

    select_all = options.select_all

    # if select_all is not enabled, ask the user which series they want to add
    if not select_all:
        selected_shows: list[int] = interactive_selection(
            shows_success, shows_exist_sonarr
        )
    else:  # if select all is enabled, add all shows
        print("Select all enabled. Adding all shows...")
        selected_shows: list[int] = [show.tvdb_id for show in shows_success]

    try:
        # Add series to Sonarr
        added, exists, not_found, excluded = add_series_to_sonarr(
            selected_shows, sonarr
        )
    except Exception as e:
        print(e)
        exit(1)

    print(
        f"Added: {added}\nExists: {exists}\nNot Found: {not_found}\nExcluded: {excluded}"
    )


def interactive_selection(
    all_shows: list[Show], existing_tvdb_ids: list[int]
) -> list[int]:
    """Interactive selection screen. Return a list of TVDB IDs of the selected shows."""

    romaji: bool = options.romaji

    # fmt: off
    choices = [
        questionary.Choice(
            # prefer the title specified in the option, fallback to the other if it's None
            title=show.romaji_title if (romaji and show.romaji_title) else show.english_title if show.english_title else show.romaji_title,
            value=show.tvdb_id,
            disabled="Anime already exists in Sonarr" if show.tvdb_id in existing_tvdb_ids else None,
        )
        for show in all_shows
    ]
    # fmt: on

    selected_shows: list[int] | None = questionary.checkbox(
        "Select anime to add to Sonarr:", choices=choices
    ).ask()

    if selected_shows is None:
        raise TypeError("[ERROR] No shows selected.")

    return selected_shows


def get_shows_in_sonarr(sonarr: arrapi.SonarrAPI) -> list[int]:
    """Return the TVDB IDs of the shows in Sonarr."""

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

    while (page == 1) or has_next_page:
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


def get_TMDB_genre_id(genre_to_find: str) -> int:
    """Get the TMDB genre ID for anime."""

    genre_dict = build_TMDB_genre_dict()
    for genre_name, genre_id in genre_dict.items():
        if genre_name == genre_to_find:
            return genre_id
    raise Exception(f"[ERROR] Genre '{genre_to_find}' not found.")


def search_TMDB_for_show(show: Show, target_genre_id: int) -> None:
    """Search for a show on TMDB, if it's found add the TMDB ID to it."""

    COMMON_START_URL = f"https://api.themoviedb.org/3/search/tv?api_key={TMDB_API_KEY}"

    try:
        query = show.english_title.replace(" ", "+")
        url = f"{COMMON_START_URL}&query={query}&first_air_date_year={show.air_year}&page=1"  # fmt: skip
        response = requests.get(url, timeout=60).json()
    except AttributeError:
        # if the show has no english title mock a response with 0 results
        response = {"total_results": 0}
    except Exception as e:
        print(e)
        exit(1)

    # if there are no results with the english title try using the romaji one
    if response["total_results"] == 0:
        try:
            query = show.romaji_title.replace(" ", "+")
            url = f"{COMMON_START_URL}&query={query}&first_air_date_year={show.air_year}&page=1"
            response = requests.get(url, timeout=60).json()
        except AttributeError:
            # if the show has no romaji title mock a response with 0 results
            response = {"total_results": 0}
        except Exception as e:
            print(e)
            exit(1)

        # if there are still no results, search recursively for parent story / prequel
        if response["total_results"] == 0:
            next_show = search_previous_season(show)
            return search_TMDB_for_show(next_show, target_genre_id)

    # Iterate through all the results and return the first one with the correct genre and country
    TARGET_COUNTRIES = ("JP", "CN", "KR", "TW", "HK")
    current_page = response["page"]
    last_page = response["total_pages"]

    while current_page <= last_page:
        for result in response["results"]:
            if (target_genre_id in result["genre_ids"]) and (result["origin_country"][0] in TARGET_COUNTRIES):  # fmt: skip
                show.tmdb_id = int(result["id"])
                return

        current_page += 1
        url = f"{COMMON_START_URL}&first_air_date_year={show.air_year}&query={query}&page={current_page}"
        time.sleep(ANILIST_API_COOLDOWN)  # Avoid rate limiting
        response = requests.get(url, timeout=60).json()

    raise Exception(
        f"[ERROR] No result with <genre id: {target_genre_id}> and <target countries: {TARGET_COUNTRIES}> found for <{show}> on TMDB."
    )


def search_previous_season(show: Show) -> Show:
    """Search for the previous season of a show via Anilist API. Return the previous season."""

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

    variables = {"id": show.anilist_id}

    response = requests.post(
        ANILIST_API_URL, json={"query": query, "variables": variables}, timeout=60
    ).json()
    time.sleep(ANILIST_API_COOLDOWN)  # Avoid rate limiting

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
        if entry["relationType"] == "PREQUEL":
            prequel = Show(
                english_title=entry["node"]["title"]["english"],
                romaji_title=entry["node"]["title"]["romaji"],
                anilist_id=entry["node"]["id"],
                air_year=entry["node"]["seasonYear"],
            )

    if (parent_story is None) and (prequel is None):
        raise Exception(f"[ERROR] No valid relations found for <{show}>.")

    show_to_search: Show = parent_story if parent_story else prequel

    return show_to_search


def get_TVDB_id_from_TMDB_id(tmdb_id: int) -> int:
    """Get the TVDB ID from a TMDB ID."""

    url = f"https://api.themoviedb.org/3/tv/{tmdb_id}/external_ids?api_key={TMDB_API_KEY}"  # fmt:skip
    response = requests.get(url, timeout=60).json()

    if "tvdb_id" not in response:
        raise Exception(f"[ERROR] No TVDB ID field for <TMDB ID: {tmdb_id}>.")

    if response["tvdb_id"] is None:
        raise Exception(f"[ERROR] TVDB ID is None for <TMDB ID: {tmdb_id}>.")

    tvdb_id = int(response["tvdb_id"])
    return tvdb_id


def add_series_to_sonarr(tvdb_ids: list[int], sonarr: arrapi.SonarrAPI):
    """Add given TVDB IDs to Sonarr."""

    root_folder = options.root_folder
    quality_profile = options.quality_profile

    language_profile = options.language_profile
    if language_profile == "NULL":
        language_profile = None

    monitor = options.monitor
    season_folder = options.season_folder
    search = options.search
    unmet_search = options.unmet_search
    series_type = options.series_type.lower()

    tags = options.tags
    if not tags:
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
    parser = configargparse.ArgParser(
        prog="anime-season-for-sonarr",
        description="Automate bulk adding anime seasons to Sonarr.",
        epilog="All options can be set from a config file.",
        default_config_files=["config.ini"],
        formatter_class=configargparse.ArgumentDefaultsRawHelpFormatter,
    )

    parser.add_argument("year", nargs=1, type=int, help="year of the anime season.")
    parser.add_argument(
        "season",
        nargs=1,
        choices=["winter", "spring", "summer", "fall"],
        help="season of the anime season. Lowercase.",
    )
    parser.add_argument(
        "-c",
        "--config",
        is_config_file=True,
        help="set config file path (default behaviour = search for ./config.ini).",
    )
    parser.add_argument(
        "--select-all",
        action="store_true",
        help="add automatically to sonarr all anime found without asking.",
    )
    parser.add_argument(
        "--no-select-all",
        dest="select-all",
        action="store_false",
        help="interactive selection of anime to add to sonarr.",
    )
    parser.add_argument(
        "--romaji",
        action="store_true",
        help="show Romaji titles instead of English titles.",
    )
    parser.add_argument(
        "--no-romaji",
        dest="romaji",
        action="store_false",
        help="show English titles.",
    )
    parser.add_argument("-k", "--tmdb-api-key", help="[TMDB] API key.")
    parser.add_argument("-u", "--base-url", help="[Sonarr] base URL.")
    parser.add_argument("-a", "--sonarr-api-key", help="[Sonarr] API key.")
    parser.add_argument("-r", "--root-folder", help="[Sonarr] series root folder.")
    parser.add_argument("-q", "--quality-profile", help="[Sonarr] quality profile.")
    parser.add_argument(
        "-l",
        "--language-profile",
        help="[Sonarr] language profile (Sonarr v3 only).",
    )
    parser.add_argument(
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
        help="[Sonarr] series monitor mode.",
    )
    parser.add_argument(
        "--season-folder",
        action="store_true",
        help="[Sonarr] use season folder.",
    )
    parser.add_argument(
        "--no-season-folder",
        dest="season-folder",
        action="store_false",
        help="[Sonarr] don't use season folder.",
    )
    parser.add_argument(
        "--search",
        action="store_true",
        help="[Sonarr] start searching for missing episodes on add.",
    )
    parser.add_argument(
        "--no-search",
        dest="search",
        action="store_false",
        help="[Sonarr] don't start searching for missing episodes on add.",
    )
    parser.add_argument(
        "--unmet-search",
        action="store_true",
        help="[Sonarr] start search for cutoff unmet episodes on add.",
    )
    parser.add_argument(
        "--no-unmet-search",
        dest="unmet-search",
        action="store_false",
        help="[Sonarr] don't start search for cutoff unmet episodes on add.",
    )
    parser.add_argument(
        "-s",
        "--series-type",
        choices=["standard", "daily", "anime"],
        help="[Sonarr] series type.",
    )
    parser.add_argument(
        "-t",
        "--tags",
        action="append",
        help="[Sonarr] tag(s) to add, can be used multiple times to add multiple tags. Example: -t anime -t seasonal -t qBit",
    )

    parser.set_defaults(
        select_all=False,
        no_select_all=True,
        romaji=False,
        no_romaji=True,
        tmdb_api_key="ac395b50e4cb14bd5712fa08b936a447",
        base_url=None,
        sonarr_api_key=None,
        root_folder=None,
        quality_profile=None,
        language=None,
        monitor="all",
        season_folder=True,
        no_season_folder=False,
        search=True,
        unmet_search=True,
        no_unmet_search=False,
        series_type="anime",
        tags=[],
    )
    options = parser.parse_args()
    TMDB_API_KEY = options.tmdb_api_key
    SONARR_BASE_URL = options.base_url
    SONARR_API_KEY = options.sonarr_api_key
    main()
