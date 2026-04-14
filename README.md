# Spotify Playlist Sorter

A lightweight, robust web application that sorts your Spotify playlists by the **true original release date** of each track.

Unlike Spotify's native sorting—which often relies on the release date of a remaster, compilation, or "Best Of" album—this application cross-references track ISRCs (International Standard Recording Codes) with the open **MusicBrainz** database to find the actual debut date of a recording.

## Features

- **True Chronological Sorting**: Utilizes MusicBrainz to bypass inaccurate Spotify remaster/compilation dates.
- **Smart Fallback Mechanism**: Uses batched ISRC queries, falling back to batched text searches, and finally defaulting to Spotify's album date if a track is extremely obscure or new.
- **Alternative Sorting**: Also supports sorting by Track Name, Artist Name, and Duration (Ascending/Descending).

## Prerequisites

- Python 3.7+
- A Spotify Developer Account (to obtain a Client ID and Client Secret)

## Installation & Setup

1. **Clone or download the repository:** Ensure `app.py` and `spotify_sorter.py` are in the same directory.
2. **Install the required Python packages:**
	```
	pip install fastapi uvicorn spotipy itsdangerous python-multipart musicbrainzngs
	```
3. **Create a Spotify Developer App:**
	- Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard "null").
	- Log in and create a new application.
	- Go to your App's Settings and add `http://127.0.0.1:8000/callback` to the **Redirect URIs**.
	- Note your **Client ID** and **Client Secret**.

## Usage

1. **Start the local server:** Navigate to the directory containing your files and run:
    ```
    uvicorn app:app --reload
    ```
2. **Open the application:** Visit `http://127.0.0.1:8000` in your web browser.
3. **Configure & Login:** On your first run, the app will prompt you to enter your Spotify Client ID and Client Secret. These are saved locally to a `config.json` file (which should be ignored in version control). The app will then redirect you to securely log in with your Spotify account.
4. **Sort your playlists:** Select any playlist you own or collaborate on, choose your sorting criteria, and watch the progress bar as the app organizes your music!

## Sorting Logic

To ensure accuracy and speed, the sorting logic follows a strict cascade:
1. **ISRC Batch Fetching**: Extracts ISRCs from the Spotify playlist and queries MusicBrainz in batches of 50. This resolves the majority of tracks in seconds.
2. **Text Search Batching**: If ISRCs are missing or fail to return a match, the script batches Artist/Track Name pairs into groups of 15 for a secondary MusicBrainz Lucene text search.
3. **Spotify Fallback**: If a track simply does not exist in the MusicBrainz database, the script safely falls back to the original `album.release_date` provided by Spotify.