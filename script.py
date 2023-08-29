import os
import time

import arrapi
import configargparse
import pick
import requests


class Show:
    def __init__(self, title: str, air_year: int, mal_id: int) -> None:
        self.title = title
        self.mal_id = mal_id
        self.air_year = air_year
        self.tmdb_id = None
        self.tvdb_id = None
    
    def __str__(self) -> str:
        return f"Title: {self.title} - Air Year: {self.air_year} - MAL ID: {self.mal_id} - TMDB ID: {self.tmdb_id} - TVDB ID: {self.tvdb_id}"
    
    def __repr__(self) -> str:
        return str(self)
    
    def get_title(self) -> str:
        return self.title
    
    def get_mal_id(self) -> int:
        return self.mal_id
    
    def get_air_year(self) -> int:
        return self.air_year
    
    def get_tmdb_id(self) -> int:
        return self.tmdb_id

    def set_tmdb_id(self, tmdb_id: int) -> None:
        self.tmdb_id = tmdb_id

    def get_tvdb_id(self) -> int:
        return self.tvdb_id
    
    def set_tvdb_id(self, tvdb_id: int) -> None:
        self.tvdb_id = tvdb_id


JIKAN_API_BASE_URL = "https://api.jikan.moe/v4"
JIKAN_API_COOLDOWN = 1  # seconds


def main() -> None:
    """Main function."""

    year = options.year[0]
    season = options.season[0]

    clear_screen()
    print(
        f"===== Anime Season For Sonarr =====\nYear: {year}\nSeason: {season.capitalize()}\n\nSearching...\n(The search can take a while)\n(The search will continue even after encountering errors.)\n")

    genre_id = get_TMDB_genre_id()

    shows = get_season_list(year, season)

    # whether to automatically select all or not
    select_all = options.select_all
    if type(select_all) is str:  # workaround for how configargparse handles bools in config files
        select_all = True if select_all.capitalize() == "True" else False
    
    # if select_all is not enabled, ask the user which series they want to add
    if not select_all:
        prompt = "Select series to add to Sonarr.\nControls: j/down_arrow = down, k/up_arrow = up, space/right_arrow = select/unselect, enter = confirm"
        choices = [show.get_title() for show in shows]
        selected_shows: list[tuple[str, int]] = pick.pick(title=prompt, options=choices, multiselect=True)
    
        if selected_shows == []:
            print("No shows selected. Exiting...")
            exit()

        shows_to_search: list[Show] = [show for show in shows if show.get_title() in [selected_show[0] for selected_show in selected_shows]]

    else:
        print("Select all enabled. Adding all shows...")
        shows_to_search = shows

    shows_success: list[Show] = []  # contains shows that were found successfully
    shows_error: list[Show] = []  # contains shows that were not found/encountered an error

    for show in shows_to_search:
        try:
            show = get_TMDB_id_from_title(show, genre_id)
            show = get_TVDB_id_from_TMDB_id(show)
            shows_success.append(show)
        except Exception as e:
            print(e)
            shows_error.append(show)

    # log missing titles
    if shows_error:
        try:
            f = open("log_missing_titles.txt", "a")
        except FileNotFoundError:
            f = open("log_missing_titles.txt", "w")
            f.close()
            f = open("log_missing_titles.txt", "a")
        f.write(f"Year: {year} - Season: {season.capitalize()}\n")
        for show in shows_error:
            f.write(f"{show}\n")
        f.write("-----\n")
        f.close()

    # Add series to Sonarr
    added, exists, not_found, excluded = add_series_to_sonarr(shows_success)
    print(
        f"Added: {added} - Exists: {exists} - Not Found: {not_found} - Excluded: {excluded}")


def clear_screen() -> None:
    """Clear the screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def get_season_list(year: int, season: str) -> list[Show]:
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

    shows = []

    # Iterate through all pages
    while current_page <= last_visible_page:
        time.sleep(JIKAN_API_COOLDOWN)  # Avoid rate limiting

        # Extract the titles from the response
        for entry in response["data"]:
            shows.append(Show(title=entry["title"], air_year=entry["aired"]["prop"]["from"]["year"], mal_id=entry["mal_id"]))

        # URL for the next page
        url = f"{JIKAN_API_BASE_URL}/seasons/{year}/{season}?filter=tv&page={current_page+1}"
        response = requests.get(url).json()
        time.sleep(JIKAN_API_COOLDOWN)  # Avoid rate limiting

        # Update current page number
        current_page = response["pagination"]["current_page"]

    if not shows:
        raise Exception(
            f"[ERROR] No titles found from Jikan API. Series for <year: {year} season: {season}> don't exist.")

    return shows


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


def get_TMDB_id_from_title(show: Show, genre_id: int) -> Show:
    """Search for a title on TMDB."""

    query = show.get_title().replace(" ", "+")  # type: ignore
    url = f"https://api.themoviedb.org/3/search/tv?api_key={TMDB_API_KEY}&query={query}&first_air_date_year={show.get_air_year()}&page=1"
    response = requests.get(url).json()

    if response["total_results"] == 0:
        # Search recursively for parent story
        show = search_firest_released(show)
        return get_TMDB_id_from_title(show, genre_id)

    # Iterate through all results and return the one with the correct genre
    else:
        current_page = response["page"]
        last_page = response["total_pages"]

        while current_page <= last_page:
            for result in response["results"]:
                if (genre_id in result["genre_ids"]) and (result["origin_country"][0] in ("JP", "CN", "KR", "TW", "HK")):
                    show.set_tmdb_id(result["id"])
                    return show

            current_page += 1
            url = f"https://api.themoviedb.org/3/search/tv?api_key={TMDB_API_KEY}&first_air_date_year={show.get_air_year()}&query={query}&page={current_page}"
            time.sleep(JIKAN_API_COOLDOWN)  # Avoid rate limiting
            response = requests.get(url).json()

    raise Exception(
        f"[ERROR] No result(s) with <genre id: {genre_id}> found for <{show}> on TMDB.")


def search_firest_released(show: Show) -> Show:
    """Search for the first released related on MAL."""

    url = f"{JIKAN_API_BASE_URL}/anime/{show.get_mal_id()}/full"
    response = requests.get(url).json()
    time.sleep(JIKAN_API_COOLDOWN)  # Avoid rate limiting

    relations: list[Show] = []

    for entry in response["data"]["relations"]:
        if entry["relation"] != "Adaptation":
            entry_url = f"{JIKAN_API_BASE_URL}/anime/{entry['entry'][0]['mal_id']}/full"
            time.sleep(JIKAN_API_COOLDOWN)  # Avoid rate limiting
            entry_response = requests.get(entry_url).json()

            relations.append(Show(title=entry["entry"][0]["name"], air_year=entry_response["data"]["aired"]["prop"]["from"]["year"], mal_id=entry["entry"][0]["mal_id"]))

    if relations:
        first_release_order = min(relations, key=lambda x: x.get_air_year())

        if first_release_order.get_air_year() > show.get_air_year():
            raise Exception(
                f"[ERROR] Searched the first released title for <{show}> but it wasn't found on TMDB. Request URL: {url}")

        return first_release_order

    raise Exception(f"[ERROR] No relations found for <{show}>.")


def get_TVDB_id_from_TMDB_id(show: Show) -> Show:
    """Get the TVDB ID for a TMDB ID."""

    url = f"https://api.themoviedb.org/3/tv/{show.get_tmdb_id()}/external_ids?api_key={TMDB_API_KEY}"
    response = requests.get(url).json()

    if "tvdb_id" not in response:
        raise Exception(f"[ERROR] No TVDB ID field for <{show}>.")

    if response["tvdb_id"] is None:
        raise Exception(f"[ERROR] TVDB ID is None ({show}).")

    show.set_tvdb_id(response["tvdb_id"])
    return show


def add_series_to_sonarr(shows: list[Show]) -> any:
    """Add given shows to Sonarr."""

    # Get config
    base_url = options.base_url
    api_key = options.sonarr_api_key
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

    tvdb_ids = [show.get_tvdb_id() for show in shows]

    sonarr = arrapi.SonarrAPI(base_url, api_key)

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
        tags=tags
    )

    return added, exists, not_found, excluded


if __name__ == "__main__":

    configargp = configargparse.ArgParser(prog="anime-season-for-sonarr", description="Automate adding entire anime seasons to Sonarr.", epilog="All options can be set in the config file (apart from <year> and <season>).", default_config_files=["config.ini"])

    configargp.add_argument("year", nargs=1, type=int, help="year of the anime season.")
    configargp.add_argument("season", nargs=1, choices=["winter", "spring", "summer", "fall"], help="season of the anime season.")
    configargp.add_argument("-c", "--config", is_config_file=True, help="set config file path (default: ./config.ini). Note: you MUST use this option if the config file is not inside the direcotry you are running the script from.")
    configargp.add_argument("-k", "--tmdb_api_key", help="Set [TMDB] API key.")
    configargp.add_argument("-u", "--base_url", help="Set [Sonarr] base URL.")
    configargp.add_argument("-a", "--sonarr_api_key", help="Set [Sonarr] API key.")
    configargp.add_argument("-r", "--root_folder", help="Set [Sonarr] series root folder.")
    configargp.add_argument("-q", "--quality_profile", help="Set [Sonarr] quality profile.")
    configargp.add_argument("-l", "--language_profile", help="Set [Sonarr] language profile (Sonarr v3 only).")
    configargp.add_argument("-m", "--monitor", choices=["all", "future", "missing", "existing", "pilot", "firstSeason", "latestSeason", "none"], help="Set [Sonarr] series monitor mode.")
    # season_folder_group = configargp.add_mutually_exclusive_group(required=False)
    configargp.add_argument("--season_folder", dest="season_folder", action="store_true", help="[Sonarr] use season folder.")
    configargp.add_argument("--no_season_folder", dest="season_folder", action="store_false", help="[Sonarr] don't use season folder.")
    # search_group = configargp.add_mutually_exclusive_group(required=False)
    configargp.add_argument("--search", dest="search", action="store_true", help="[Sonarr] start searching for missing episodes on add.")
    configargp.add_argument("--no_search", dest="search", action="store_false", help="[Sonarr] don't start searching for missing episodes on add.")
    # unmet_search_group = configargp.add_mutually_exclusive_group(required=False)
    configargp.add_argument("--unmet_search", dest="unmet_search", action="store_true", help="[Sonarr] start search for cutoff unmet episodes on add.")
    configargp.add_argument("--no_unmet_search", dest="unmet_search", action="store_false", help="[Sonarr] don't start search for cutoff unmet episodes on add.")
    configargp.add_argument("-p", "--series_type", choices=["standard", "daily", "anime"], help="Set [Sonarr] series type.")
    configargp.add_argument("-t", "--tags", action="append", help="[Sonarr] tag(s) to add, can be used multiple times to add multiple tags. Example: -t anime -t seasonal -t qBit")
    # select_all_group = configargp.add_mutually_exclusive_group(required=False)
    configargp.add_argument("--select_all", dest="select_all", action="store_true", help="Add to [Sonarr] automatically without asking.")
    configargp.add_argument("--no_select_all", dest="select_all", action="store_false", help="Ask whether or not to add to [Sonarr].")

    options = configargp.parse_args()
    TMDB_API_KEY = options.tmdb_api_key  # probably should handle the key better
    main()