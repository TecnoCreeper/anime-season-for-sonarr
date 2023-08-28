# anime-season-for-sonarr
Choose an anime season (year + season) to automatically add it to Sonarr.

# Usage
- Clone/download the repository
- `cd anime-season-for-sonarr`
- `pip install -r requirements.txt`
- Edit `config.ini` to your liking (some configuration edits are **required**)
- Run the script: `python ./script.py <year> <season>` (year = integer; season = winter, spring, summer or fall)
- Run `python ./script.py -h` to show advanced usage.

# Info
- A log file will be crated inside the working directory in case some series couldn't be found.

# Credits
This product uses the TMDB API but is not endorsed or certified by TMDB.
