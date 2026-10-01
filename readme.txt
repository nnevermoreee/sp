============================================================
 Spotify -> MP3
============================================================

Streamlit app that reads a public Spotify playlist and downloads
every track from YouTube as a 320 kbps MP3.


------------------------------------------------------------
 WHAT IT DOES
------------------------------------------------------------
  - Fetches the full track list of a public Spotify playlist
    (handles playlists larger than 100 songs).
  - Searches YouTube for each track as "{artist} - {title} audio".
  - Downloads the best audio stream and converts it to 320 kbps MP3.
  - Bundles everything into a ZIP you can download from the browser.


------------------------------------------------------------
 REQUIREMENTS
------------------------------------------------------------
  Python packages:
      pip install streamlit spotipy yt-dlp

  ffmpeg (must be on your PATH):
      macOS    : brew install ffmpeg
      Linux    : sudo apt install ffmpeg
      Windows  : winget install Gyan.FFmpeg


------------------------------------------------------------
 GET SPOTIFY CREDENTIALS
------------------------------------------------------------
  1. Go to https://developer.spotify.com/dashboard
  2. Log in and click "Create app".
  3. Give it any name and redirect URI (e.g. http://localhost).
  4. Copy the Client ID and Client Secret.


------------------------------------------------------------
 RUN
------------------------------------------------------------
  streamlit run app.py

  Then:
    1. Paste your Client ID and Client Secret in the sidebar.
       (Or set env vars SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET
        before launching.)
    2. Paste a public Spotify playlist URL.
    3. Click "Fetch playlist".
    4. Click "Download all as MP3".
    5. Click "Download playlist ZIP" when it finishes.


------------------------------------------------------------
 WARNING
------------------------------------------------------------
  Only download content you have the right to download
  (your own uploads, public-domain or CC-licensed material, etc).

  Downloading commercial music from YouTube generally violates
  YouTube's Terms of Service and copyright law in most countries.
  You are responsible for how you use this tool.
============================================================