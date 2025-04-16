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
docker compose run --rm anime_season_for_sonarr 2025 spring --select-all --romaji
```

You can also modify the `command` in `docker-compose.yml` if needed.

---

### 🖥️ Manual (No Docker)

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

Use `-h` or `--help` for available options.

---

## ⚙️ Configuration

Before running, **edit `config.ini`** with the following required settings:

-   `base_url`
-   `sonarr_api_key`
-   `root_folder`
-   `quality_profile`
-   `language_profile` (Sonarr v3 only)

You can also configure the other settings to customize behavior.

> All settings can also be passed/overriden via command-line arguments.

> The script assumes `config.ini` is in the current directory unless specified with `-c` or `--config`.

---

## 📝 Logging

Use the `--log` flag to generate a log file in the current directory. This will list any anime that failed to be found.

---

## Credits

This tool uses the TMDB API but is not endorsed or certified by TMDB.

Special thanks to:

-   [ArrAPI](https://github.com/meisnate12/ArrAPI)
-   [ConfigArgParse](https://github.com/bw2/ConfigArgParse)
-   [questionary](https://github.com/tmbo/questionary)
