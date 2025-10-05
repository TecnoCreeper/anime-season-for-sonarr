import argparse
import datetime
import os
import sys
import time
import tomllib
from dataclasses import dataclass

import arrapi
import httpx
import questionary

ANILIST_API_URL = "https://graphql.anilist.co"


@dataclass
class Show:
    """Show dataclass."""

    english_title: str
    romaji_title: str
    anilist_id: int
    air_year: int
    tmdb_id: int | None = None
    tvdb_id: int | None = None


class AnilistRequestHandler:
    @staticmethod
    def send_request(query: str, variables: dict | None = None) -> dict:
        while True:
            response = client.post(
                ANILIST_API_URL, json={"query": query, "variables": variables}
            )
            retry = AnilistRequestHandler._handle_outcome(response)

            # Parse response and check for GraphQL errors
            response_data = response.json()
            if response_data.get("errors"):
                error_messages = [
                    error.get("message", "Unknown error")
                    for error in response_data["errors"]
                ]
                raise Exception(f"AniList GraphQL errors: {', '.join(error_messages)}")

            if not retry:
                return response_data

    @staticmethod
    def _handle_outcome(response: httpx.Response) -> bool:
        if response.status_code == 429:
            if "Retry-After" in response.headers:
                retry_after = int(response.headers["Retry-After"])
                print(f"Rate limited. Waiting {retry_after} seconds...")
                time.sleep(retry_after)
            else:
                # Fallback: wait 60 seconds
                print("Rate limited. Waiting 60 seconds... (fallback)")
                time.sleep(60)
            return True

        # Check for other errors
        if response.status_code != 200:
            raise Exception(
                f"AniList API error: {response.status_code=} - {response.text=}"
            )

        return False


def main() -> None:  # noqa: PLR0915
    """Main function."""

    year: int = options.year
    season: str = options.season
    genres_include: list[str] = config["ANILIST"]["includes-genres"]
    genres_exclude: list[str] = config["ANILIST"]["excludes-genres"]
    tags_include: list[str] = config["ANILIST"]["includes-tags"]
    tags_exclude: list[str] = config["ANILIST"]["excludes-tags"]

    clear_screen()
    print(
        f"===== Anime Season For Sonarr =====\nYear: {year}\nSeason: {season.capitalize()}\n\nSearching...\n"
    )

    genre_id: int = get_TMDB_genre_id("Animation")

    shows: list[Show] = get_season_list(
        year, season, genres_include, genres_exclude, tags_include, tags_exclude
    )

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
            sys.exit(1)
        except Exception as e:
            print(e)
            shows_error.append(show)

    # log error titles to file if there are any
    if shows_error and config["SCRIPT"]["log"]:
        with open("log_search_errors.txt", "a", encoding="utf-8") as file:
            file.write(
                f"{datetime.datetime.now()} - Year: {year} - Season: {season.capitalize()}\n"
            )
            for show in shows_error:
                file.write(f"{show}\n")
            file.write("-----\n")

    if not shows_success:
        print(
            "The search concluded with no anime that has a TVDB ID, so nothing can get added to Sonarr."
        )
        sys.exit(1)

    try:
        sonarr: arrapi.SonarrAPI = arrapi.SonarrAPI(SONARR_BASE_URL, SONARR_API_KEY)
    except Exception as e:
        print(
            f"-----\n{e}\nCan't connect to Sonarr. Possible fix: check the URL and API key."
        )
        sys.exit(1)

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
        sys.exit(1)

    print(
        f"Added: {added}\nExists: {exists}\nNot Found: {not_found}\nExcluded: {excluded}"
    )


def clear_screen() -> None:
    """Clear the screen."""
    os.system("cls" if os.name == "nt" else "clear")  # noqa: S605


def get_genre_and_tag_list() -> tuple[list, list]:
    """
    Returns the list of genres and tags.

    Adult tags are excluded.
    """

    query = """
    query {
        genres: GenreCollection
        tags: MediaTagCollection {
            name
            description
            category
            isAdult
        }
    }
    """

    response_data = AnilistRequestHandler.send_request(query)

    genres: list = response_data["data"]["genres"]

    tags: list = list(
        filter(lambda tag: tag["isAdult"] is False, response_data["data"]["tags"])
    )
    for tag in tags:
        del tag["isAdult"]

    return genres, tags


def interactive_selection(
    all_shows: list[Show], existing_tvdb_ids: list[int]
) -> list[int]:
    """Interactive selection screen. Return a list of TVDB IDs of the selected shows."""

    romaji: bool = config["SCRIPT"]["romaji"]

    # fmt: off
    choices = [
        questionary.Choice(
            # prefer the title specified in the config; fallback to the romaji if the english one is None
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


def get_season_list(  # noqa: PLR0913
    year: int,
    season: str,
    genres_include: list[str] | None = None,
    genres_exclude: list[str] | None = None,
    tags_include: list[str] | None = None,
    tags_exclude: list[str] | None = None,
) -> list[Show]:
    """Get the list of anime from Anilist API for the given season."""

    page = 1
    has_next_page = None
    shows: list[Show] = []

    while (page == 1) or has_next_page:
        variables = {
            "page": page,
            "season": season.upper(),
            "seasonYear": year,
        }

        # Ugly string manipulation because of how graphql variables work
        query1 = """
        query (
        $page: Int,
        $season: MediaSeason,
        $seasonYear: Int,
        """

        query2 = """
        ) {
            Page (page: $page, perPage: 30) {
                pageInfo {
                    hasNextPage
                    currentPage
                    lastPage
                }
                media (
                    season: $season,
                    seasonYear: $seasonYear,
                    type: ANIME,
                    format: TV,
        """

        if genres_include:
            query1 += "$genres_include: [String],"
            query2 += "genre_in: $genres_include,"
            variables.update({"genres_include": genres_include})
        if genres_exclude:
            query1 += "$genres_exclude: [String],"
            query2 += "genre_not_in: $genres_exclude,"
            variables.update({"genres_exclude": genres_exclude})
        if tags_include:
            query1 += "$tags_include: [String],"
            query2 += "tag_in: $tags_include,"
            variables.update({"tags_include": tags_include})
        if tags_exclude:
            query1 += "$tags_exclude: [String],"
            query2 += "tag_not_in: $tags_exclude,"
            variables.update({"tags_exclude": tags_exclude})

        query2 += """
                ) {
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

        query = query1 + query2

        response_data = AnilistRequestHandler.send_request(query, variables)

        has_next_page = response_data["data"]["Page"]["pageInfo"]["hasNextPage"]
        page += 1

        shows.extend(
            Show(
                english_title=entry["title"]["english"],
                romaji_title=entry["title"]["romaji"],
                anilist_id=entry["id"],
                air_year=entry["seasonYear"],
            )
            for entry in response_data["data"]["Page"]["media"]
        )

    if not shows:  # if no shows are found (the list is empty)
        raise Exception(
            f"[ERROR] No anime in {year=}, {season=} with the configured genres/tags."
        )

    return shows


def build_TMDB_genre_dict() -> dict[str, int]:
    """Build a list of TMDB genres."""

    url = f"https://api.themoviedb.org/3/genre/movie/list?api_key={TMDB_API_KEY}"
    response = client.get(url).json()
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
                response = client.get(url).json()
            except AttributeError:  # thrown by .replace()
                # if title is None mock a response with 0 results
                response = {"total_results": 0}
            except Exception as e:
                print(e)
                sys.exit(1)

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
        response = client.get(url).json()

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

    response_data = AnilistRequestHandler.send_request(query, variables)

    parent_story = None
    prequel = None

    for entry in response_data["data"]["Media"]["relations"]["edges"]:
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
    response = client.get(url).json()

    if "tvdb_id" not in response:
        raise Exception(f"[ERROR] No TVDB ID field for <TMDB ID: {tmdb_id}>.")

    if response["tvdb_id"] is None:
        raise Exception(f"[ERROR] TVDB ID is None for <TMDB ID: {tmdb_id}>.")

    return int(response["tvdb_id"])


def get_shows_in_sonarr(sonarr: arrapi.SonarrAPI) -> list[int]:
    """Return the TVDB IDs of the shows in Sonarr."""

    series = sonarr.all_series()
    return [int(entry.tvdbId) for entry in series]


def add_series_to_sonarr(tvdb_ids: list[int], sonarr: arrapi.SonarrAPI):  # noqa: ANN201
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
        description="Script to bulk add seasonal anime to Sonarr.",
        epilog="Configure the script with config.toml.",
    )

    parser.add_argument("year", nargs="?", type=int, help="year of the anime season.")
    parser.add_argument(
        "season",
        nargs="?",
        choices=["winter", "spring", "summer", "fall"],
        help="season of the anime season. Lowercase.",
    )
    parser.add_argument(
        "--tag-list",
        nargs="?",
        choices=["simple", "fancy"],
        const="fancy",
        help="Print genres and tags.",
    )

    options = parser.parse_args()

    if options.tag_list:
        with httpx.Client() as client:
            genres, tags = get_genre_and_tag_list()

        if options.tag_list == "fancy":
            from tabulate import tabulate

            print(
                tabulate(
                    ([x] for x in genres), headers=["Genres"], tablefmt="mixed_grid"
                )
            )

            print(
                "\nTag list\n"
                + tabulate(
                    tags,
                    headers="keys",
                    maxcolwidths=[None, 50, None, None],
                    tablefmt="mixed_grid",
                )
            )

        elif options.tag_list == "simple":
            print("== Genres ==\n" + "\n".join(genres))
            print("\n== Tags ==\n" + "\n".join([tag["name"] for tag in tags]))

        sys.exit(0)

    elif (not options.year) or (not options.season):
        print("Error: use --help to see usage.")
        sys.exit(1)

    with open("config.toml", "rb") as file:
        config = tomllib.load(file)

    TMDB_API_KEY = config["TMDB"]["tmdb-api-key"]
    SONARR_BASE_URL = config["SONARR"]["base-url"]
    SONARR_API_KEY = config["SONARR"]["sonarr-api-key"]
    TARGET_COUNTRIES = set(config["SCRIPT"]["target-countries"])
    with httpx.Client() as client:
        main()
