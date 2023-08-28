import os
import time

import arrapi
import configargparse
import requests

JIKAN_API_BASE_URL = "https://api.jikan.moe/v4"
JIKAN_API_COOLDOWN = 1  # seconds


configargp = configargparse.ArgParser(default_config_files=["config.ini"])

configargp.add_argument("year", nargs=1, type=int, help="year of the anime season")
configargp.add_argument("season", nargs=1, choices=["winter", "spring", "summer", "fall"], help="season of the anime season")
configargp.add_argument("-c", "--config", is_config_file=True, help="config file path")
configargp.add_argument("-t", "--tmdb_api_key", help="TMDB API key")
configargp.add_argument("-u", "--base_url", help="Sonarr base URL")
configargp.add_argument("-a", "--sonarr_api_key", help="Sonarr API key")
configargp.add_argument("-r", "--root_folder", help="Sonarr root folder")
configargp.add_argument("-q", "--quality_profile", help="Sonarr quality profile")
configargp.add_argument("-l", "--language_profile", help="Sonarr language profile")
configargp.add_argument("-m", "--monitor", choices=["all", "future", "missing", "existing", "pilot", "firstSeason", "latestSeason", "none"], help="Sonarr monitor mode")
configargp.add_argument("-f", "--season_folder", help="Sonarr season folder")
configargp.add_argument("-s", "--search", help="Sonarr search on add")
configargp.add_argument("-n", "--unmet_search", help="Sonarr unmet search on add")
configargp.add_argument("-p", "--series_type", choices=["standard", "daily", "anime"], help="Sonarr series type")
configargp.add_argument("-g", "--tags", action="append", help="Sonarr tags")

options = configargp.parse_args()


TMDB_API_KEY = options.tmdb_api_key


def main() -> None:
    """Main function."""

    year = options.year[0]
    season = options.season[0]

    clear_screen()
    print(
        f"===== Anime Season Downloader =====\nYear: {year}\nSeason: {season.capitalize()}\n\nSearching...\n(The search takes a while, it's not stuck.)\n(It will continue even after encountering errors.)\n")

    genre_id = get_TMDB_genre_id()

    # Get titles from MAL via Jikan API for that season
    titles = get_season_list(year, season)

    tvdb_ids = []
    failed_titles = []

    for title in titles:
        try:
            TMDB_id = get_TMDB_id_from_title(title, genre_id)
            TVDB_id = get_TVDB_id_from_TMDB_id(TMDB_id)
            tvdb_ids.append(TVDB_id)
        except Exception as e:
            print(e)
            failed_titles.append(title)

    print(
        f"\nFound {len(tvdb_ids)}/{len(titles)} series. Add to Sonarr? (y/n)")
    if input() != "y":
        print("Exiting...")
        exit()

    # log missing titles
    if failed_titles:
        try:
            f = open("log_missing_titles.txt", "a")
        except FileNotFoundError:
            f = open("log_missing_titles.txt", "w")
            f.close()
            f = open("log_missing_titles.txt", "a")

        for title in failed_titles:
            f.write(f"{title['title']} - {title['mal_id']}\n")
        f.close()

    # Add series to Sonarr
    added, exists, not_found, excluded = add_series_to_sonarr(tvdb_ids)
    print(
        f"Added: {added} - Exists: {exists} - Not Found: {not_found} - Excluded: {excluded}")


def clear_screen() -> None:
    """Clear the screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def get_season_list(year: int, season: str) -> list[dict[str, str | int]]:
    """Get the list of anime from Jikan API for the given season."""

    url = f"{JIKAN_API_BASE_URL}/seasons/{year}/{season}?filter=tv"
    response = requests.get(url)
    time.sleep(JIKAN_API_COOLDOWN)  # Avoid rate limiting

    # Check if the request was successful otherwise raise an exception
    if response.status_code != 200:
        raise Exception(
            f"[ERROR] Status code: {response.status_code} - Response Text: {response.text}")

    response = response.json()

    # Get current page number and last visible page number
    last_visible_page = response["pagination"]["last_visible_page"]
    current_page = response["pagination"]["current_page"]

    titles = []

    # Iterate through all pages
    while current_page <= last_visible_page:
        time.sleep(JIKAN_API_COOLDOWN)  # Avoid rate limiting

        # Extract the titles from the response
        for entry in response["data"]:
            titles.append(
                {"title": entry["title"], "mal_id": entry["mal_id"], "air_year": entry["aired"]["prop"]["from"]["year"]})

        # URL for the next page
        url = f"{JIKAN_API_BASE_URL}/seasons/{year}/{season}?filter=tv&page={current_page+1}"
        response = requests.get(url).json()
        time.sleep(JIKAN_API_COOLDOWN)  # Avoid rate limiting

        # Update current page number
        current_page = response["pagination"]["current_page"]

    if not titles:
        raise Exception(
            f"[ERROR] No titles found from Jikan API. Series for <year: {year} season: {season}> don't exist.")

    return titles


def build_TMDB_genre_dict() -> dict[str, int]:
    """Build a list of TMDB genres."""

    url = f"https://api.themoviedb.org/3/genre/movie/list?api_key={TMDB_API_KEY}"
    response = requests.get(url).json()
    genre_dict = {}
    for genre in response["genres"]:
        genre_dict.update({genre["name"]: genre["id"]})
    return genre_dict


def get_TMDB_genre_id(genre_to_find: str = "Animation") -> int:
    """Get the TMDB genre ID for anime."""

    genre_dict = build_TMDB_genre_dict()
    for genre, id in genre_dict.items():
        if genre == genre_to_find:
            return id
    raise Exception(f"[ERROR] Genre '{genre_to_find}' not found.")


def get_TMDB_id_from_title(title: dict[str, str | int], genre_id: int) -> int:
    """Search for a title on TMDB."""

    query = title["title"].replace(" ", "+")  # type: ignore
    url = f"https://api.themoviedb.org/3/search/tv?api_key={TMDB_API_KEY}&query={query}&first_air_date_year={title['air_year']}&page=1"
    response = requests.get(url).json()

    # print(f"[INFO] Searching for: {title} - url: {url}")

    if response["total_results"] == 0:
        # Search recursively for parent story
        title = search_firest_released(title)
        return get_TMDB_id_from_title(title, genre_id)

    # Iterate through all results and return the one with the correct genre
    else:
        current_page = response["page"]
        last_page = response["total_pages"]

        while current_page <= last_page:
            for result in response["results"]:
                if (genre_id in result["genre_ids"]) and (result["origin_country"][0] in ("JP", "CN", "KR", "TW", "HK")):
                    return result["id"]

            current_page += 1
            url = f"https://api.themoviedb.org/3/search/tv?api_key={TMDB_API_KEY}&first_air_date_year={title['air_year']}&query={query}&page={current_page}"
            time.sleep(JIKAN_API_COOLDOWN)  # Avoid rate limiting
            response = requests.get(url).json()

    raise Exception(
        f"[ERROR] No result(s) with <genre id: {genre_id}> found for '{title}' on TMDB.")


def search_firest_released(title: dict[str, str | int]) -> dict[str, str | int]:
    """Search for the first released related on MAL."""

    url = f"{JIKAN_API_BASE_URL}/anime/{title['mal_id']}/full"
    response = requests.get(url).json()
    time.sleep(JIKAN_API_COOLDOWN)  # Avoid rate limiting

    relations = []

    for entry in response["data"]["relations"]:
        if entry["relation"] != "Adaptation":
            entry_url = f"{JIKAN_API_BASE_URL}/anime/{entry['entry'][0]['mal_id']}/full"
            time.sleep(JIKAN_API_COOLDOWN)  # Avoid rate limiting
            entry_response = requests.get(entry_url).json()

            relations.append(
                {
                    "title": entry["entry"][0]["name"],
                    "mal_id": entry["entry"][0]["mal_id"],
                    "air_year": entry_response["data"]["aired"]["prop"]["from"]["year"]
                }
            )
    if relations:
        first_release_order = min(relations, key=lambda x: x["air_year"])

        if first_release_order["air_year"] > title["air_year"]:
            raise Exception(
                f"[ERROR] Searched the first released title for <{title}> but it wasn't found on TMDB. Request URL: {url}")

        # print(f"[INFO] Searching for parent story: {first_release_order}")
        return first_release_order

    raise Exception(f"[ERROR] No relations found for <{title}>.")


def get_TVDB_id_from_TMDB_id(TMDB_id: int) -> int:
    """Get the TVDB ID for a TMDB ID."""

    url = f"https://api.themoviedb.org/3/tv/{TMDB_id}/external_ids?api_key={TMDB_API_KEY}"
    response = requests.get(url).json()

    if "tvdb_id" not in response:
        raise Exception(f"[ERROR] No TVDB ID field for TMDB ID {TMDB_id}.")

    if response["tvdb_id"] is None:
        raise Exception(f"[ERROR] TVDB ID for TMDB ID {TMDB_id} is None.")

    return response["tvdb_id"]


def add_series_to_sonarr(series_tvdb_ids):
    """Add given tvdb_ids to Sonarr."""

    # Get config
    base_url = options.base_url
    api_key = options.sonarr_api_key
    root_folder = options.root_folder
    quality_profile = options.quality_profile
    language_profile = options.language_profile
    if language_profile == "NULL":
        language_profile = None
    monitor = options.monitor
    season_folder = options.season_folder.capitalize()
    season_folder = True if season_folder == "True" else False
    search = options.search.capitalize()
    search = True if search == "True" else False
    unmet_search = options.unmet_search.capitalize()
    unmet_search = True if unmet_search == "True" else False
    series_type = options.series_type.lower()
    tags = options.tags
    if tags == []:
        tags = None

    sonarr = arrapi.SonarrAPI(base_url, api_key)

    added, exists, not_found, excluded = sonarr.add_multiple_series(
        ids=series_tvdb_ids,
        root_folder=root_folder,
        quality_profile=quality_profile,
        language_profile=language_profile,
        monitor=monitor,
        season_folder=season_folder,
        search=search,
        unmet_search=unmet_search,
        series_type=series_type,
        tags=tags
    )

    return added, exists, not_found, excluded


if __name__ == "__main__":
    main()
