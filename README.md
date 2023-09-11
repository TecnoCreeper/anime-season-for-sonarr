# anime-season-for-sonarr
Choose an anime season (year + season) and select which ones you want to add to Sonarr.

# Video and screenshot

https://github.com/TecnoCreeper/anime-season-for-sonarr/assets/110969133/b3934008-e74a-44dc-8816-6f4b930797b3

![screenshot1](https://github.com/TecnoCreeper/anime-season-for-sonarr/assets/110969133/86feda0d-78e1-44d8-bfdd-d5da2517acb9)

# Download
- Clone/download the repository  
`git clone https://github.com/TecnoCreeper/anime-season-for-sonarr.git`
- `cd anime-season-for-sonarr`
- (Optional) Create a python virtual environment and activate it
- `pip install -r requirements.txt`

# Configuration
- (REQUIRED) Edit `config.ini` and set the following options:  
`base_url, sonarr_api_key, root_folder, quality_profile, language_profile (Sonarr v3 only)`

- (OPTIONAL) Edit the other options to your liking

Note: every option in the config file can be overridden by command line arguments (so technically you don't need to edit the config file if you pass the required arguments every time).

# Usage
Run the script with `-h` or `--help` to view options.

If you configured `config.ini` you can run

`python ./script.py <year> <season>`

replacing \<year> with the wanted year and \<season> with the wanted season (winter, spring, summer or fall, lowercase).

By default the english titles are shown, this behaviour can be changed using the `--romaji` flag.

Note: if the config file is not inside the directory from which you are running the script from you MUST provide the path to the config file using `-c <path>` or `--config <path>`.

# Additional info
- A log file will be created inside the working directory in case the script encounters errors.

# Credits
This product uses the TMDB API but is not endorsed or certified by TMDB.

Dependencies:
- [ArrAPI](https://github.com/meisnate12/ArrAPI)
- [ConfigArgParse](https://github.com/bw2/ConfigArgParse)
- [questionary](https://github.com/tmbo/questionary)