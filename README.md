# anime-season-for-sonarr

Easily bulk add seasonal anime (by year and season) to Sonarr.

## Features

- Choose how to display titles during selection (english/romaji)
- Filter results by genres and tags (based on [Anilist](https://anilist.co))
- Configure Sonarr settings (quality profile, tags, etc.)
- Allows all results to be added automatically without manual selection

## Setup and Configuration

```bash
git clone https://github.com/TecnoCreeper/anime-season-for-sonarr.git
cd anime-season-for-sonarr
```

Copy `config.example.toml` to `config.toml` and edit the file.

You **must** edit at least the following options:

- `base_url`
- `sonarr_api_key`
- `root_folder`
- `quality_profile`
- `language_profile` (Sonarr v3 only)

Script specific options:

| option           | description                                                              | value                                                                        |
| ---------------- | ------------------------------------------------------------------------ | ---------------------------------------------------------------------------- |
| select-all       | automatically add all anime found to Sonarr                              | bool                                                                         |
| romaji           | show romaji titles instead of english titles                             | bool                                                                         |
| log              | generate a file in the current directory to log anime not found          | bool                                                                         |
| target-countries | country codes the anime must originate from (according to TMDB)          | list from https://developer.themoviedb.org/reference/configuration-countries |
| tmdb-api-key     | replace with yours if you want (https://www.themoviedb.org/settings/api) | api key                                                                      |

Genres/tags filtering is supported. Filters are applied with "AND" logic (i.e. all conditions must be met).

Sonarr specific options are documented in the config file.

## Usage

> [!IMPORTANT]  
> Anilist API randomly responds with a 500 Bad Request. I have not figured out the cause. If it happens to you try re-running the search and/or wait a bit.

### uv

To run a search:

```bash
uv run anime_season_for_sonarr.py <year> <season>
```

To see all options:

```bash
uv run anime_season_for_sonarr.py --help
```

### Docker

```bash
docker compose run --rm anime_season_for_sonarr <year> <season>
```

Note: if the Dockerfile changes you will need to run the command with the `--build` option once to force rebuild the image.

### pip

> [!WARNING]  
> Tested with Python 3.13

```bash
# Optional but strongly recommended:
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
# ---

pip install -r requirements.txt
```

To run the script:

```bash
python anime_season_for_sonarr.py <year> <season>
```

## Credits

This tool uses the TMDB API but is not endorsed or certified by TMDB.
