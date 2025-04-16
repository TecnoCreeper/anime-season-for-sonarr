# anime-season-for-sonarr

Choose an anime season (year + season) and select which series you want to add to Sonarr.

# Download / Setup

## Docker

```
git clone https://github.com/TecnoCreeper/anime-season-for-sonarr.git
cd anime-season-for-sonarr
```

## Manual

**NOTE: tested only on python 3.12.1 with the versions of the packages specified in requirements.txt**

```
git clone https://github.com/TecnoCreeper/anime-season-for-sonarr.git
cd anime-season-for-sonarr
(optional but recommended) create and activate a python virtual environment
pip install -r requirements.txt
```

# Configuration

-   (REQUIRED) Edit `config.ini` and set the following options:  
    `base_url, sonarr_api_key, root_folder, quality_profile, language_profile (Sonarr v3 only)`

-   (OPTIONAL) Edit the other options to your preferences

Note: every option in the config file can be overridden by command line arguments (so technically you don't need to edit the config file if you pass the required options every time).

# Usage

Run the script with `-h` or `--help` to view the options.

If you configured `config.ini` you can run

## Docker

```
docker compose run --rm anime_season_for_sonarr
```

you can pass args to the script normally like this

```
docker compose run --rm anime_season_for_sonarr 2025 spring
```

or edit the docker-compose.yml command

## Manual

```
python anime_season_for_sonarr.py <year> <season>
```

Note: the config file is assumed to be located inside the directory you are running the script from (`./config.ini`), you can pass the path to the config file using the `-c` / `--config` option.

# Additional info

-   Use --log to create a log file inside the working directory. It will contain the anime failed to be found.

# Credits

This product uses the TMDB API but is not endorsed or certified by TMDB.

Thanks to:

-   [ArrAPI](https://github.com/meisnate12/ArrAPI)
-   [ConfigArgParse](https://github.com/bw2/ConfigArgParse)
-   [questionary](https://github.com/tmbo/questionary)
