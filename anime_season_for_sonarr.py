import argparse
import datetime
import os
import time
from dataclasses import dataclass

import arrapi
import questionary
import requests
import tomllib


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
            show.tmdb_id = search_TMDB_for_show(show, genre_id)
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
    if shows_error and config["SCRIPT"]["log"]:
        try:
            file = open("log_search_errors.txt", "a", encoding="utf-8")
        except FileNotFoundError:
            file = open("log_search_errors.txt", "w", encoding="utf-8")
            file.close()
            file = open("log_search_errors.txt", "a", encoding="utf-8")

        file.write(
            f"{datetime.datetime.now()} - Year: {year} - Season: {season.capitalize()}\n"
        )
        for show in shows_error:
            file.write(f"{show}\n")
        file.write("-----\n")
        file.close()

    try:
        sonarr: arrapi.SonarrAPI = arrapi.SonarrAPI(SONARR_BASE_URL, SONARR_API_KEY)
    except Exception as e:
        print(
            f"-----\n{e}\nCan't connect to Sonarr. Possible fix: check the URL and API key."
        )
        exit(1)

    shows_exist_sonarr: list[int] = get_shows_in_sonarr(sonarr)

    select_all = config["SCRIPT"]["select-all"]

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

    romaji: bool = config["SCRIPT"]["romaji"]

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


def search_TMDB_for_show(show: Show, target_genre_id: int) -> int:
    """Search for a show on TMDB, if it's found return the TMDB ID."""

    COMMON_START_URL = f"https://api.themoviedb.org/3/search/tv?api_key={TMDB_API_KEY}"

    titles = (show.english_title, show.romaji_title)
    include_air_year = (True, False)

    # search in this order:
    # 1 - english + air year
    # 2 - romaji + air year
    # 3 - english
    # 4 - romaji

    # ends search when the first result is found

    response = None

    for option in include_air_year:
        for title in titles:
            try:
                query = title.replace(" ", "+")
                url = f"{COMMON_START_URL}&query={query}&page=1"
                if option:
                    url += f"&first_air_date_year={show.air_year}"
                response = requests.get(url, timeout=60).json()
            except AttributeError:  # thrown by .replace()
                # if title is None mock a response with 0 results
                response = {"total_results": 0}
            except Exception as e:
                print(e)
                exit(1)

            if response["total_results"] != 0:
                break
        else:  # else block is executed only if the loop ends without breaks
            response = None
            continue
        break  # so if we break in the inner loop we also break out of the outer

    # if there are no results, search recursively for parent story / prequel
    if not response:
        next_show = search_previous_season(show)
        return search_TMDB_for_show(next_show, target_genre_id)

    # Iterate through all the results and return the first one with the correct genre and country
    current_page = response["page"]
    last_page = response["total_pages"]

    while current_page <= last_page:
        for result in response["results"]:
            if (target_genre_id in result["genre_ids"]) and (result["origin_country"][0] in TARGET_COUNTRIES):  # fmt: skip
                return int(result["id"])

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

    root_folder = config["SONARR"]["root-folder"]
    quality_profile = config["SONARR"]["quality-profile"]

    language_profile = config["SONARR"]["language-profile"]
    if language_profile == "NULL":
        language_profile = None

    monitor = config["SONARR"]["monitor"]
    season_folder = config["SONARR"]["season-folder"]
    search = config["SONARR"]["search"]
    unmet_search = config["SONARR"]["unmet-search"]
    series_type = config["SONARR"]["series-type"].lower()

    tags = config["SONARR"]["tags"]
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
    parser = argparse.ArgumentParser(
        prog="anime-season-for-sonarr",
        description="Automate bulk adding anime seasons to Sonarr.",
        epilog="Configuration must be set from the config.toml file.",
    )

    parser.add_argument("year", nargs=1, type=int, help="year of the anime season.")
    parser.add_argument(
        "season",
        nargs=1,
        choices=["winter", "spring", "summer", "fall"],
        help="season of the anime season. Lowercase.",
    )

    options = parser.parse_args()
    with open("config.toml", "rb") as file:
        config = tomllib.load(file)

    TMDB_API_KEY = config["TMDB"]["tmdb-api-key"]
    SONARR_BASE_URL = config["SONARR"]["base-url"]
    SONARR_API_KEY = config["SONARR"]["sonarr-api-key"]
    TARGET_COUNTRIES = set(config["SCRIPT"]["target-countries"])
    main()
