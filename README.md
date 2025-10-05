# anime-season-for-sonarr

Easily bulk add seasonal anime (by year and season) to Sonarr.

## Features

-   Choose the language in which titles are shown during selection (english/romaji)
-   Filter results by genres and tags
-   Configure Sonarr settings (quality profile, tags, etc.)
-   Supports adding all results without manual selection.

---

## 🚀 Quick Start

> [!IMPORTANT]  
> Anilist API randomly responds with a 500 Bad Request. I have not figured out the cause. If it happens to you try re-running the search and/or wait a bit.

Clone the repo and choose your setup method

```bash
git clone https://github.com/TecnoCreeper/anime-season-for-sonarr.git
cd anime-season-for-sonarr
```

### Docker

```bash
docker compose run --rm anime_season_for_sonarr <year> <season>
```

### uv

```bash
uv run anime_season_for_sonarr.py <year> <season>
```

### pip

> ⚠️ Tested with Python 3.13

```bash
# Optional but recommended:
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
# ---

pip install -r requirements.txt
```

To run the script:

```bash
python anime_season_for_sonarr.py <year> <season>
```

---

## ⚙️ Configuration

Before running, rename `config.toml.example` to `config.toml` and **edit** the following settings:

-   `base_url`
-   `sonarr_api_key`
-   `root_folder`
-   `quality_profile`
-   `language_profile` (Sonarr v3 only)

You can also configure the other settings to customize behavior.

Script specific options:

| option           | description                                                              | value                                                                        |
| ---------------- | ------------------------------------------------------------------------ | ---------------------------------------------------------------------------- |
| select-all       | automatically add to sonarr all anime found                              | bool                                                                         |
| romaji           | show romaji titles instead of english titles.                            | bool                                                                         |
| log              | generate a log file in the current directory. It list anime not found.   | bool                                                                         |
| target-countries | country codes the anime must originate from (according to TMDB)          | list from https://developer.themoviedb.org/reference/configuration-countries |
| tmdb-api-key     | replace with yours if you want (https://www.themoviedb.org/settings/api) | api key                                                                      |

Genres/tags filtering is supported. Filters are applied as "AND".

Sonarr specific options are documented in the config file.

---

## Credits

This tool uses the TMDB API but is not endorsed or certified by TMDB.

Thanks to:

-   [ArrAPI](https://github.com/meisnate12/ArrAPI)
-   [questionary](https://github.com/tmbo/questionary)
