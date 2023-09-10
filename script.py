import os
import time

import arrapi
import configargparse
import pick
import requests

class Show:
    def __init__(self, english_title: str, romaji_title: str, anilist_id: int, air_year: int) -> None:
        self.english_title = english_title
        self.romaji_title = romaji_title
        self.anilist_id = anilist_id
        self.air_year = air_year
        self.tmdb_id = None
        self.tvdb_id = None
    
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
        if type(self.tmdb_id) is not int:
            raise Exception(f"[ERROR] TMDB ID for <{self}> is not an int, type: {type(self.tmdb_id)}.")
        return self.tmdb_id

    def get_tvdb_id(self) -> int:
        if type(self.tvdb_id) is not int:
            raise Exception(f"[ERROR] TVDB ID for <{self}> is not an int, type: {type(self.tvdb_id)}.")
        return self.tvdb_id
    
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
        f"===== Anime Season For Sonarr =====\nYear: {year}\nSeason: {season.capitalize()}\n\nSearching...\n(The search can take a while)\n(The search will continue even after encountering [ERROR]s.)\n")

    genre_id = get_TMDB_genre_id()

    shows = get_season_list(year, season)

    # whether to automatically select all or not
    select_all = options.select_all
    if type(select_all) is str:  # workaround for how configargparse handles bools in config files
        select_all = True if select_all.capitalize() == "True" else False
    
    # if select_all is not enabled, ask the user which series they want to add
    if not select_all:
        prompt = "Select series to add to Sonarr.\nControls: j/down_arrow = down, k/up_arrow = up, space/right_arrow = select/unselect, enter = confirm"
        romaji = options.romaji
        if romaji is True:
            choices = [show.get_romaji_title() for show in shows]
        else:
            choices = [show.get_english_title() for show in shows]
        selected_shows: list[tuple[str, int]] = pick.pick(title=prompt, options=choices, multiselect=True)
    
        if selected_shows == []:
            print("No shows selected. Exiting...")
            exit()

        shows_to_search: list[Show] = [show for show in shows if show.get_english_title() in [selected_show[0] for selected_show in selected_shows]]

    else:
        print("Select all enabled. Adding all shows...")
        shows_to_search = shows

    shows_success: list[Show] = []  # contains shows that were found successfully
    shows_error: list[Show] = []  # contains shows that were not found/encountered an error

    for show in shows_to_search:
        try:
            show = search_TMDB_for_show(show, genre_id)
            tvdb_id = get_TVDB_id_from_TMDB_id(show.get_tmdb_id())
            show.set_tvdb_id(tvdb_id)
            shows_success.append(show)
        except Exception as e:
            print(e)
            shows_error.append(show)

    # log missing titles
    if shows_error:
        try:
            f = open("log_error_titles.txt", "a")
        except FileNotFoundError:
            f = open("log_error_titles.txt", "w")
            f.close()
            f = open("log_error_titles.txt", "a")
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

        variables = {
            "page": page,
            "season": season.upper(),
            "seasonYear": year
        }

        response = requests.post(ANILIST_API_URL, json={"query": query, "variables": variables}).json()
        time.sleep(ANILIST_API_COOLDOWN)  # Avoid rate limiting
        
        has_next_page = response["data"]["Page"]["pageInfo"]["hasNextPage"]
        page += 1

        for entry in response["data"]["Page"]["media"]:
            shows.append(
                Show(english_title=entry["title"]["english"], romaji_title=entry["title"]["romaji"], anilist_id=entry["id"], air_year=entry["seasonYear"])
            )
    
    if not shows:
        raise Exception(
            f"[ERROR] No titles found from Anilist API. Series for <year: {year} season: {season}> don't exist.")
    
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


def search_TMDB_for_show(show: Show, genre_id: int) -> Show:
    """Search for a show on TMDB."""

    query = show.get_english_title().replace(" ", "+")
    url = f"https://api.themoviedb.org/3/search/tv?api_key={TMDB_API_KEY}&query={query}&first_air_date_year={show.get_air_year()}&page=1"
    response = requests.get(url).json()

    if response["total_results"] == 0:
        # try using the romaji title
        query = show.get_romaji_title().replace(" ", "+")
        url = f"https://api.themoviedb.org/3/search/tv?api_key={TMDB_API_KEY}&query={query}&first_air_date_year={show.get_air_year()}&page=1"
        response = requests.get(url).json()
        
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
                if (genre_id in result["genre_ids"]) and (result["origin_country"][0] in ("JP", "CN", "KR", "TW", "HK")):
                    show.set_tmdb_id(int(result["id"]))
                    return show

            current_page += 1
            url = f"https://api.themoviedb.org/3/search/tv?api_key={TMDB_API_KEY}&first_air_date_year={show.get_air_year()}&query={query}&page={current_page}"
            time.sleep(ANILIST_API_COOLDOWN)  # Avoid rate limiting
            response = requests.get(url).json()

        raise Exception(
            f"[ERROR] No result(s) with <genre id: {genre_id}> found for <{show}> on TMDB.")


def search_previous_season(show: Show) -> Show:
    """Search for the previous season of a show via Anilist API."""

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

    variables = {
        "id": show.get_anilist_id()
    }

    response = requests.post(ANILIST_API_URL, json={"query": query, "variables": variables}).json()
    time.sleep(ANILIST_API_COOLDOWN)  # Avoid rate limiting

    found = False
    parent_story = None
    prequel = None

    for entry in response["data"]["Media"]["relations"]["edges"]:
        if entry["relationType"] == "PARENT":
            parent_story = Show(english_title=entry["node"]["title"]["english"], romaji_title=entry["node"]["title"]["romaji"], anilist_id=entry["node"]["id"], air_year=entry["node"]["seasonYear"])
            found = True
        if entry["relationType"] == "PREQUEL":
            prequel = Show(english_title=entry["node"]["title"]["english"], romaji_title=entry["node"]["title"]["romaji"], anilist_id=entry["node"]["id"], air_year=entry["node"]["seasonYear"])
            found = True
        
    if found is False:
        raise Exception(f"[ERROR] No relations found for <{show}>.")
    
    show_to_search = parent_story if parent_story is not None else prequel
    
    return show_to_search


def get_TVDB_id_from_TMDB_id(tmdb_id: int) -> int:
    """Get the TVDB ID from a TMDB ID."""

    url = f"https://api.themoviedb.org/3/tv/{tmdb_id}/external_ids?api_key={TMDB_API_KEY}"
    response = requests.get(url).json()

    if "tvdb_id" not in response:
        raise Exception(f"[ERROR] No TVDB ID field for <TMDB ID: {tmdb_id}>.")

    if response["tvdb_id"] is None:
        raise Exception(f"[ERROR] TVDB ID is None <TMDB ID: {tmdb_id}>.")

    tvdb_id = int(response["tvdb_id"])
    return tvdb_id


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

    configargp = configargparse.ArgParser(prog="anime-season-for-sonarr", description="Automate bulk adding anime seasons to Sonarr.", epilog="Most options can be set in the config file.", default_config_files=["config.ini"])

    configargp.add_argument("year", nargs=1, type=int, help="year of the anime season.")
    configargp.add_argument("season", nargs=1, choices=["winter", "spring", "summer", "fall"], help="season of the anime season. Lowercase.")
    configargp.add_argument("-c", "--config", is_config_file=True, help="set config file path (default: ./config.ini). Note: you MUST use this option if the config file is not inside the direcotry you are running the script from.")
    configargp.add_argument("-k", "--tmdb_api_key", help="Set [TMDB] API key.")
    configargp.add_argument("-u", "--base_url", help="Set [Sonarr] base URL.")
    configargp.add_argument("-a", "--sonarr_api_key", help="Set [Sonarr] API key.")
    configargp.add_argument("-r", "--root_folder", help="Set [Sonarr] series root folder.")
    configargp.add_argument("-q", "--quality_profile", help="Set [Sonarr] quality profile.")
    configargp.add_argument("-l", "--language_profile", help="Set [Sonarr] language profile (Sonarr v3 only).")
    configargp.add_argument("-m", "--monitor", choices=["all", "future", "missing", "existing", "pilot", "firstSeason", "latestSeason", "none"], help="Set [Sonarr] series monitor mode.")
    configargp.add_argument("--season_folder", dest="season_folder", action="store_true", help="[Sonarr] use season folder.")
    configargp.add_argument("--no_season_folder", dest="season_folder", action="store_false", help="[Sonarr] don't use season folder.")
    configargp.add_argument("--search", dest="search", action="store_true", help="[Sonarr] start searching for missing episodes on add.")
    configargp.add_argument("--no_search", dest="search", action="store_false", help="[Sonarr] don't start searching for missing episodes on add.")
    configargp.add_argument("--unmet_search", dest="unmet_search", action="store_true", help="[Sonarr] start search for cutoff unmet episodes on add.")
    configargp.add_argument("--no_unmet_search", dest="unmet_search", action="store_false", help="[Sonarr] don't start search for cutoff unmet episodes on add.")
    configargp.add_argument("-p", "--series_type", choices=["standard", "daily", "anime"], help="Set [Sonarr] series type.")
    configargp.add_argument("-t", "--tags", action="append", help="[Sonarr] tag(s) to add, can be used multiple times to add multiple tags. Example: -t anime -t seasonal -t qBit")
    configargp.add_argument("--select_all", dest="select_all", action="store_true", help="Add to [Sonarr] automatically without asking.")
    configargp.add_argument("--no_select_all", dest="select_all", action="store_false", help="Ask whether or not to add to [Sonarr].")
    configargp.add_argument("--romaji", help="Show Romaji titles instead of English titles.", action="store_true")

    options = configargp.parse_args()
    TMDB_API_KEY = options.tmdb_api_key  # probably should handle the key better
    main()