# anime-season-for-sonarr

Easily add seasonal anime (by year and season) to Sonarr.

---

## 🚀 Quick Start

Choose your setup method:

### 🐳 Docker

```bash
git clone https://github.com/TecnoCreeper/anime-season-for-sonarr.git
cd anime-season-for-sonarr
```

Then, to run the script:

```bash
docker compose run --rm anime_season_for_sonarr
```

To specify a year and season (and other args if you want):

```bash
docker compose run --rm anime_season_for_sonarr 2025 spring
```

You can also modify the `command` in `docker-compose.yml` if needed.

---

### uv

```bash
git clone https://github.com/TecnoCreeper/anime-season-for-sonarr.git
cd anime-season-for-sonarr
uv run anime_season_for_sonarr.py <year> <season>
```

---

### pip

> ⚠️ Tested with Python 3.13 using the package versions in `requirements.txt`.

```bash
git clone https://github.com/TecnoCreeper/anime-season-for-sonarr.git
cd anime-season-for-sonarr

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

Before running, rename `config.toml.example` to `config.toml` and **edit** it with the following required settings:

-   `base_url`
-   `sonarr_api_key`
-   `root_folder`
-   `quality_profile`
-   `language_profile` (Sonarr v3 only)

You can also configure the other settings to customize behavior.

Script specific options:

| option           | description                                                                       | value                                                                        |
| ---------------- | --------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| select-all       | add automatically to sonarr all anime found without asking                        | bool                                                                         |
| romaji           | show Romaji titles instead of English titles.                                     | bool                                                                         |
| log              | generate a log file in the current directory. This will list any anime not found. | bool                                                                         |
| target-countries | country codes the anime must originate from (according to TMDB)                   | list from https://developer.themoviedb.org/reference/configuration-countries |
| tmdb-api-key     | replace with yours if you want (https://www.themoviedb.org/settings/api)          | api key                                                                      |

Sonarr specific options are documented in the config file.

---

## Credits

This tool uses the TMDB API but is not endorsed or certified by TMDB.

Thanks to:

-   [ArrAPI](https://github.com/meisnate12/ArrAPI)
-   [questionary](https://github.com/tmbo/questionary)
