import os
import json
from fastapi import FastAPI, Request, BackgroundTasks, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware
import spotipy
from spotipy.oauth2 import SpotifyOAuth

# Import the unified sorting logic
from spotify_sorter import sort_playlist

# --- Configuration ---
SPOTIPY_REDIRECT_URI = "http://127.0.0.1:8000/callback"
CONFIG_FILE = "config.json"

# Initialize FastAPI
app = FastAPI(title="Spotify Sorter")

# Add session middleware
app.add_middleware(
    SessionMiddleware, 
    secret_key="replace_this_with_a_long_random_string_in_production"
)

# In-memory dictionary to store sorting progress
sorting_status = {}

def load_config():
    """Loads Spotify credentials from the local config file or environment variables."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
            
    # Fallback to environment variables if the file doesn't exist
    return {
        "CLIENT_ID": os.environ.get("SPOTIPY_CLIENT_ID", ""),
        "CLIENT_SECRET": os.environ.get("SPOTIPY_CLIENT_SECRET", "")
    }

def save_config(client_id: str, client_secret: str):
    """Saves Spotify credentials to a local JSON file."""
    with open(CONFIG_FILE, "w") as f:
        json.dump({
            "CLIENT_ID": client_id,
            "CLIENT_SECRET": client_secret
        }, f, indent=4)

def get_spotify_oauth():
    """Configures the Spotify authentication flow."""
    config = load_config()
    client_id = config.get("CLIENT_ID")
    client_secret = config.get("CLIENT_SECRET")
    
    if not client_id or not client_secret:
        return None
        
    return SpotifyOAuth(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=SPOTIPY_REDIRECT_URI,
        scope="playlist-read-private playlist-modify-private playlist-modify-public"
    )

base_style = """
<style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #121212; color: #ffffff; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; margin: 0; padding: 20px; }
    .hero { text-align: center; max-width: 600px; width: 100%; padding: 40px; background: #181818; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.5); box-sizing: border-box; }
    h1 { font-size: 2.5rem; margin-bottom: 16px; color: #1DB954; margin-top: 0; }
    p { font-size: 1.1rem; color: #b3b3b3; line-height: 1.5; margin-bottom: 30px; }
    .btn { background-color: #1DB954; color: white; text-decoration: none; border: none; border-radius: 500px; padding: 14px 32px; font-size: 16px; font-weight: bold; cursor: pointer; transition: transform 0.2s, background-color 0.2s; display: inline-block; margin: 5px; }
    .btn:hover { transform: scale(1.04); background-color: #1ed760; }
    .btn-outline { background-color: transparent; border: 2px solid #555; color: #b3b3b3; }
    .btn-outline:hover { background-color: #333; border-color: #fff; color: #fff; transform: scale(1.04); }
    .input-group { text-align: left; margin-bottom: 20px; }
    label { display: block; margin-bottom: 8px; color: #fff; font-weight: bold; }
    input[type="text"], input[type="password"] { width: 100%; padding: 12px; border-radius: 4px; border: 1px solid #333; background-color: #282828; color: white; font-size: 16px; box-sizing: border-box; outline: none; }
    input[type="text"]:focus, input[type="password"]:focus { border-color: #1DB954; }
</style>
"""

@app.get("/login", response_class=HTMLResponse)
def login_page():
    """Displays the form to confirm Spotify credentials and start login."""
    config = load_config()
    client_id = config.get("CLIENT_ID", "")
    client_secret = config.get("CLIENT_SECRET", "")
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>{base_style}</head>
    <body>
        <div class="hero">
            <h1>Spotify Login</h1>
            <p>Confirm your Spotify Developer credentials to proceed. They are saved locally to <code>config.json</code>.</p>
            <form action="/login" method="POST">
                <div class="input-group">
                    <label for="client_id">Client ID</label>
                    <input type="text" id="client_id" name="client_id" value="{client_id}" required placeholder="Enter your Client ID">
                </div>
                <div class="input-group">
                    <label for="client_secret">Client Secret</label>
                    <input type="password" id="client_secret" name="client_secret" value="{client_secret}" required placeholder="Enter your Client Secret">
                </div>
                <button type="submit" class="btn" style="width: 100%; margin-top: 10px;">Login with Spotify</button>
            </form>
        </div>
    </body>
    </html>
    """

@app.post("/login")
def login_post(client_id: str = Form(...), client_secret: str = Form(...)):
    """Handles the form submission, saves credentials, and redirects to Spotify Auth."""
    save_config(client_id.strip(), client_secret.strip())
    
    sp_oauth = get_spotify_oauth()
    if not sp_oauth:
        # Fallback in case of a highly unusual setup failure
        return RedirectResponse("/login")
        
    auth_url = sp_oauth.get_authorize_url()
    return RedirectResponse(auth_url, status_code=303)

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    """The landing page. Checks if the user is already logged in."""
    token_info = request.session.get("token_info")
    
    if not token_info:
        return f"""
        <!DOCTYPE html>
        <html>
        <head>{base_style}</head>
        <body>
            <div class="hero">
                <h1>Chronological Sorter</h1>
                <p>Sort your Spotify playlists by the true original release date of each track using open metadata from MusicBrainz.</p>
                <a href="/login" class="btn">Login with Spotify</a>
            </div>
        </body>
        </html>
        """
        
    return f"""
    <!DOCTYPE html>
    <html>
    <head>{base_style}</head>
    <body>
        <div class="hero">
            <h1>Welcome Back!</h1>
            <p>You are successfully logged in and ready to organize your music.</p>
            <div>
                <a href="/playlists" class="btn">View My Playlists</a>
            </div>
            <div style="margin-top: 15px;">
                <a href="/logout" class="btn btn-outline">Log Out</a>
            </div>
        </div>
    </body>
    </html>
    """

@app.get("/logout")
def logout(request: Request):
    """Clears the user session and redirects to home."""
    # Clears the session token but explicitly preserves config.json
    request.session.pop("token_info", None)
    return RedirectResponse("/")

@app.get("/callback")
def callback(request: Request, code: str):
    """Spotify redirects here after a successful login."""
    sp_oauth = get_spotify_oauth()
    if not sp_oauth:
        return RedirectResponse("/login")
        
    token_info = sp_oauth.get_access_token(code)
    request.session["token_info"] = token_info
    return RedirectResponse("/playlists")

@app.get("/playlists", response_class=HTMLResponse)
def get_playlists(request: Request):
    """Displays a list of the user's playlists."""
    token_info = request.session.get("token_info")
    if not token_info:
        return RedirectResponse("/")
        
    sp = spotipy.Spotify(auth=token_info["access_token"])
    playlists = sp.current_user_playlists()
    
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #121212; color: #fff; margin: 0; padding: 40px 20px; display: flex; justify-content: center; }
            .container { max-width: 800px; width: 100%; background: #181818; padding: 30px; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.5); }
            .header-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
            h2 { margin: 0; font-size: 28px; }
            .logout-btn { color: #b3b3b3; text-decoration: none; font-size: 14px; font-weight: bold; border: 1px solid #444; padding: 8px 16px; border-radius: 500px; transition: all 0.2s; }
            .logout-btn:hover { background: #333; color: #fff; border-color: #fff; }
            .playlist-item { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; background: #282828; padding: 16px 20px; border-radius: 8px; margin-bottom: 12px; transition: background 0.2s; }
            .playlist-item:hover { background: #333; }
            .playlist-info { font-size: 16px; font-weight: bold; margin-bottom: 8px; }
            .playlist-meta { color: #b3b3b3; font-size: 14px; font-weight: normal; margin-left: 6px; }
            .sort-form { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
            select { background: #3e3e3e; color: white; border: none; border-radius: 4px; padding: 8px 12px; outline: none; cursor: pointer; font-size: 14px; }
            button { background-color: #1DB954; color: white; border: none; border-radius: 500px; padding: 8px 20px; font-weight: bold; cursor: pointer; transition: transform 0.2s; font-size: 14px; }
            button:hover { transform: scale(1.04); background-color: #1ed760; }
            .back-link { display: inline-block; margin-top: 20px; color: #b3b3b3; text-decoration: none; font-weight: bold; }
            .back-link:hover { color: #fff; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header-bar">
                <h2>Select a Playlist to Sort</h2>
                <a href="/logout" class="logout-btn">Log Out</a>
            </div>
            <div>
    """
    
    for pl in playlists.get("items", []):
        html_content += f"""
                <div class="playlist-item">
                    <div class="playlist-info">
                        {pl['name']} <span class="playlist-meta">({pl['tracks']['total']} tracks)</span>
                    </div>
                    <form action="/sort/{pl['id']}" method="GET" class="sort-form">
                        <select name="sort_by">
                            <option value="date">Release Date</option>
                            <option value="name">Track Name</option>
                            <option value="artist">Artist Name</option>
                            <option value="duration">Duration</option>
                        </select>
                        <select name="order">
                            <option value="asc">Ascending</option>
                            <option value="desc">Descending</option>
                        </select>
                        <button type="submit">Sort</button>
                    </form>
                </div>
        """
        
    html_content += """
            </div>
            <a href='/' class="back-link">&larr; Go Back</a>
        </div>
    </body>
    </html>
    """
    return html_content

def background_sort_task(token_info: dict, playlist_id: str, sort_by: str, order: str):
    """
    This function runs in the background. It fetches all tracks,
    processes them via MusicBrainz, and updates the playlist.
    """
    sorting_status[playlist_id] = {"status": "Fetching tracks from Spotify...", "progress": 0, "total": 0, "cancelled": False}
    sp = spotipy.Spotify(auth=token_info["access_token"])
    
    # 1. Fetch all tracks from the playlist (handling pagination)
    results = sp.playlist_tracks(playlist_id)
    tracks = results["items"]
    
    while results["next"]:
        if sorting_status[playlist_id].get("cancelled"):
            return
        results = sp.next(results)
        tracks.extend(results["items"])
        
    # 2. Process and sort the tracks using our logic
    def update_progress(current, total):
        sorting_status[playlist_id] = {
            "status": f"Processing ({current}/{total})...", 
            "progress": current, 
            "total": total,
            "cancelled": sorting_status[playlist_id].get("cancelled", False)
        }
        
    def check_cancelled():
        return sorting_status[playlist_id].get("cancelled", False)
        
    sorted_tracks = sort_playlist(
        tracks, 
        sort_by=sort_by, 
        order=order, 
        progress_callback=update_progress, 
        check_cancelled=check_cancelled
    )
    
    if check_cancelled():
        return
        
    sorting_status[playlist_id]["status"] = "Updating playlist on Spotify..."
    
    # 3. Extract the raw Spotify track IDs (ignoring local tracks that don't have IDs)
    sorted_uris = [
        track["spotify_id"] for track in sorted_tracks if track.get("spotify_id")
    ]
    
    if not sorted_uris:
        sorting_status[playlist_id] = {"status": "Completed (No tracks found).", "progress": len(tracks), "total": len(tracks)}
        return
        
    # 4. Update the playlist in blocks of 100 (Spotify API limit)
    sp.playlist_replace_items(playlist_id, sorted_uris[:100])
    
    for i in range(100, len(sorted_uris), 100):
        sp.playlist_add_items(playlist_id, sorted_uris[i:i+100])
        
    sorting_status[playlist_id] = {"status": "Completed!", "progress": len(tracks), "total": len(tracks)}

@app.get("/status/{playlist_id}")
def get_sort_status(playlist_id: str):
    """Returns the current progress of the sorting task."""
    status = sorting_status.get(playlist_id, {"status": "Initializing...", "progress": 0, "total": 0})
    return JSONResponse(content=status)

@app.post("/cancel/{playlist_id}")
def cancel_sort(playlist_id: str):
    """Cancels an ongoing sort operation."""
    if playlist_id in sorting_status:
        sorting_status[playlist_id]["cancelled"] = True
        sorting_status[playlist_id]["status"] = "Cancelled by user."
    return JSONResponse(content={"status": "cancelled"})

@app.get("/sort/{playlist_id}", response_class=HTMLResponse)
def trigger_sort(request: Request, playlist_id: str, background_tasks: BackgroundTasks, sort_by: str = "date", order: str = "asc"):
    """Endpoint that triggers the sorting background task."""
    token_info = request.session.get("token_info")
    if not token_info:
        return RedirectResponse("/")
        
    background_tasks.add_task(background_sort_task, token_info, playlist_id, sort_by, order)
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background-color: #121212; color: #ffffff; display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 100vh; margin: 0; padding: 20px; }}
            .container {{ text-align: center; max-width: 500px; width: 100%; padding: 40px; background: #181818; border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.5); }}
            h1 {{ margin-top: 0; color: #1DB954; font-size: 32px; }}
            .meta-info {{ color: #b3b3b3; margin-bottom: 30px; font-size: 15px; }}
            strong {{ color: #fff; }}
            .progress-wrapper {{ width: 100%; background-color: #333; border-radius: 500px; height: 16px; overflow: hidden; margin: 24px 0; }}
            #progress-bar {{ width: 0%; height: 100%; background-color: #1DB954; transition: width 0.4s ease, background-color 0.4s ease; }}
            #status-text {{ font-weight: bold; font-size: 18px; margin-bottom: 8px; color: #fff; }}
            .subtext {{ color: #b3b3b3; font-size: 14px; margin-bottom: 0; }}
            .btn {{ background-color: #1DB954; color: white; border: none; border-radius: 500px; padding: 12px 28px; font-size: 16px; font-weight: bold; cursor: pointer; transition: transform 0.2s; text-decoration: none; display: inline-block; }}
            .btn:hover {{ transform: scale(1.04); background-color: #1ed760; }}
            .btn-danger {{ background-color: #e74c3c; margin-top: 10px; }}
            .btn-danger:hover {{ background-color: #ff5e4d; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Sorting in Progress 🎵</h1>
            
            <p class="meta-info">Sorting by: <strong>{sort_by.capitalize()}</strong> ({order.upper()})</p>
            
            <div class="progress-wrapper">
                <div id="progress-bar"></div>
            </div>
            
            <p id="status-text">Starting...</p>
            <p class="subtext">This might take a few minutes depending on the playlist size.</p>
            
            <div id="cancel-section" style="margin-top: 30px;">
                <button class="btn btn-danger" onclick="cancelSort()">Cancel Sort</button>
            </div>
            
            <div id="done-section" style="display: none; margin-top: 30px;">
                <h2 id="final-message" style="color: #1DB954; margin-bottom: 24px;">All done! Check your Spotify app.</h2>
                <a href="/playlists" class="btn">Back to Playlists</a>
            </div>
        </div>

        <script>
            const playlistId = "{playlist_id}";
            let isCancelled = false;
            
            async function cancelSort() {{
                isCancelled = true;
                await fetch('/cancel/' + playlistId, {{ method: 'POST' }});
                document.getElementById('cancel-section').style.display = 'none';
                document.getElementById('progress-bar').style.backgroundColor = '#e74c3c';
                document.getElementById('final-message').innerText = "Sorting Cancelled.";
                document.getElementById('final-message').style.color = '#e74c3c';
                document.getElementById('done-section').style.display = 'block';
                document.getElementById('status-text').innerText = "Cancelled";
            }}
            
            async function pollStatus() {{
                if (isCancelled) return;
                
                try {{
                    const response = await fetch('/status/' + playlistId);
                    const data = await response.json();
                    
                    document.getElementById('status-text').innerText = data.status;
                    
                    if (data.total > 0) {{
                        const percent = Math.round((data.progress / data.total) * 100);
                        document.getElementById('progress-bar').style.width = percent + '%';
                    }}
                    
                    if (data.status.includes("Completed") || data.status.includes("Cancelled")) {{
                        document.getElementById('progress-bar').style.width = '100%';
                        document.getElementById('cancel-section').style.display = 'none';
                        
                        if (data.status.includes("Cancelled")) {{
                            document.getElementById('progress-bar').style.backgroundColor = '#e74c3c';
                            document.getElementById('final-message').innerText = "Sorting Cancelled.";
                            document.getElementById('final-message').style.color = '#e74c3c';
                        }}
                        
                        document.getElementById('done-section').style.display = 'block';
                        return; 
                    }}
                }} catch (error) {{
                    console.error("Error fetching status:", error);
                }}
                
                setTimeout(pollStatus, 1000);
            }}
            
            pollStatus();
        </script>
    </body>
    </html>
    """