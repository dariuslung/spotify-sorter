import musicbrainzngs
from datetime import datetime

# Initialize MusicBrainz with your application details
# MusicBrainz requires a descriptive user agent to prevent rate limiting blocks
musicbrainzngs.set_useragent(
    "SpotifyReleaseDateSorter",
    "1.0",
    "contact@yourdomain.com"
)


def parse_release_date(date_str):
    """
    Parses flexible date strings into a standardized datetime object.
    Handles MusicBrainz and Spotify formats (YYYY, YYYY-MM, YYYY-MM-DD).
    """
    if not date_str:
        return datetime.max
        
    try:
        date_str = date_str.strip()
        
        if len(date_str) == 4:
            return datetime.strptime(date_str, "%Y")
        elif len(date_str) == 7:
            return datetime.strptime(date_str, "%Y-%m")
        else:
            return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return datetime.max


def fetch_dates_by_isrc_batch(isrc_list, progress_callback=None, total_tracks=0, check_cancelled=None):
    """
    Fetches first-release-date for a list of ISRCs in batches of 50
    using a single Lucene query per batch to bypass rate limit bottlenecks.
    """
    isrc_to_date = {}
    batch_size = 50
    
    # Remove empty/None ISRCs
    valid_isrcs = [isrc for isrc in isrc_list if isrc]
    
    for i in range(0, len(valid_isrcs), batch_size):
        if check_cancelled and check_cancelled():
            return {}
            
        if progress_callback:
            # Report progress during the batching phase
            progress_callback(min(i, total_tracks), total_tracks)
            
        chunk = valid_isrcs[i : i + batch_size]
        
        # Build Lucene query: isrc:ID1 OR isrc:ID2 OR ...
        query = " OR ".join([f"isrc:{isrc}" for isrc in chunk])
        
        try:
            # Limit 100 to ensure we capture all hits for our 50 ISRCs
            result = musicbrainzngs.search_recordings(query=query, limit=100)
            recordings = result.get("recording-list", [])
            
            for recording in recordings:
                # A recording might be tied to multiple ISRCs in the search results
                # musicbrainzngs sometimes returns strings instead of dicts for ISRCs
                rec_isrcs = [ext_isrc.get("id") if isinstance(ext_isrc, dict) else ext_isrc for ext_isrc in recording.get("isrc-list", [])]
                release_date = recording.get("first-release-date")
                
                if release_date:
                    for rec_isrc in rec_isrcs:
                        if rec_isrc in chunk and rec_isrc not in isrc_to_date:
                            isrc_to_date[rec_isrc] = release_date
                            
        except musicbrainzngs.MusicBrainzError:
            pass
            
    return isrc_to_date


def fetch_dates_by_search_batch(track_artist_pairs, check_cancelled=None):
    """
    Batches text-based searches for tracks missing ISRCs.
    Uses smaller chunks (15) to prevent Lucene URI length limits.
    """
    search_date_map = {}
    batch_size = 15
    
    valid_pairs = [(a, t) for a, t in track_artist_pairs if a and t]
    
    for i in range(0, len(valid_pairs), batch_size):
        if check_cancelled and check_cancelled():
            return {}
            
        chunk = valid_pairs[i : i + batch_size]
        
        query_parts = []
        for artist, track in chunk:
            # Clean strings of symbols to prevent breaking the Lucene syntax
            safe_track = "".join(c for c in track if c.isalnum() or c.isspace())
            safe_artist = "".join(c for c in artist if c.isalnum() or c.isspace())
            query_parts.append(f'(recording:"{safe_track}" AND artist:"{safe_artist}")')
            
        query = " OR ".join(query_parts)
        
        try:
            result = musicbrainzngs.search_recordings(query=query, limit=100)
            recordings = result.get("recording-list", [])
            
            for recording in recordings:
                rec_title = recording.get("title", "").lower()
                
                # Safely extract the artist from the recording
                artist_credit = recording.get("artist-credit", [])
                rec_artist = ""
                if artist_credit and isinstance(artist_credit[0], dict):
                    rec_artist = artist_credit[0].get("artist", {}).get("name", "").lower()
                elif artist_credit and isinstance(artist_credit[0], str):
                    rec_artist = artist_credit[0].lower()
                    
                release_date = recording.get("first-release-date")
                
                if release_date:
                    # Fuzzy mapping to link the batched result back to the original pair
                    for artist, track in chunk:
                        if track.lower() in rec_title and artist.lower() in rec_artist:
                            key = f"{artist}|||{track}"
                            if key not in search_date_map:
                                search_date_map[key] = release_date
                                
        except musicbrainzngs.MusicBrainzError:
            pass
            
    return search_date_map


def sort_playlist(spotify_tracks, sort_by="date", order="asc", progress_callback=None, check_cancelled=None):
    """
    Iterates through a list of Spotify track dictionaries, 
    fetches metadata if needed, and sorts them.
    """
    enriched_tracks = []
    total_tracks = len(spotify_tracks)
    
    isrc_date_map = {}
    if sort_by == "date":
        # 1. Extract all ISRCs for the batch fetch
        all_isrcs = []
        for item in spotify_tracks:
            track_data = item.get("track", item) 
            isrc = track_data.get("external_ids", {}).get("isrc")
            if isrc:
                all_isrcs.append(isrc)
                
        # 2. Perform the batched fetch (This drops a 500 track playlist from 500s to ~10s)
        isrc_date_map = fetch_dates_by_isrc_batch(
            all_isrcs, 
            progress_callback=progress_callback, 
            total_tracks=total_tracks,
            check_cancelled=check_cancelled
        )
        
        # 2.5 Identify tracks that STILL don't have a date and batch search them
        missing_date_pairs = []
        for item in spotify_tracks:
            track_data = item.get("track", item) 
            isrc = track_data.get("external_ids", {}).get("isrc")
            if not isrc or isrc not in isrc_date_map:
                track_name = track_data.get("name")
                artists = track_data.get("artists", [])
                artist_name = artists[0].get("name") if artists else ""
                if track_name and artist_name:
                    missing_date_pairs.append((artist_name, track_name))
        
        if missing_date_pairs:
            search_date_map = fetch_dates_by_search_batch(
                missing_date_pairs,
                check_cancelled=check_cancelled
            )

    # 3. Iterate through tracks and apply fallbacks
    for index, item in enumerate(spotify_tracks):
        if check_cancelled and check_cancelled():
            return []
            
        # Report progress during the final compilation/fallback phase
        if progress_callback:
            progress_callback(index, total_tracks)
            
        track_data = item.get("track", item) 
        isrc = track_data.get("external_ids", {}).get("isrc")
        track_name = track_data.get("name")
        artists = track_data.get("artists", [])
        artist_name = artists[0].get("name") if artists else ""
        spotify_date = track_data.get("album", {}).get("release_date")
        duration_ms = track_data.get("duration_ms", 0)
        
        release_date = None
        date_source = "None"
        
        if sort_by == "date":
            # Check the dictionary we built during the batch phase
            release_date = isrc_date_map.get(isrc)
            date_source = "MusicBrainz (Batched ISRC)"
            
            # Fallback 1: Batched Text Search
            if not release_date:
                key = f"{artist_name}|||{track_name}"
                release_date = search_date_map.get(key)
                if release_date:
                    date_source = "MusicBrainz (Batched Text Search)"
                
            # Fallback 2: Spotify Date
            if not release_date:
                release_date = spotify_date
                date_source = "Spotify (Album Fallback)"
            
        enriched_tracks.append({
            "spotify_id": track_data.get("id"),
            "track_name": track_name,
            "artist_name": artist_name,
            "duration": duration_ms,
            "display_date": release_date or "Unknown",
            "sortable_date": parse_release_date(release_date) if sort_by == "date" else None,
            "source_used": date_source
        })

    # Ensure progress hits 100% at the end
    if progress_callback:
        progress_callback(total_tracks, total_tracks)

    # 4. Sort the list in-place based on the chosen criteria
    reverse_sort = (order == "desc")
    
    if sort_by == "date":
        enriched_tracks.sort(key=lambda x: x["sortable_date"], reverse=reverse_sort)
    elif sort_by == "name":
        enriched_tracks.sort(key=lambda x: x["track_name"].lower() if x["track_name"] else "", reverse=reverse_sort)
    elif sort_by == "artist":
        enriched_tracks.sort(key=lambda x: x["artist_name"].lower() if x["artist_name"] else "", reverse=reverse_sort)
    elif sort_by == "duration":
        enriched_tracks.sort(key=lambda x: x["duration"], reverse=reverse_sort)
    
    return enriched_tracks


# --- Example Usage ---
if __name__ == "__main__":
    # Mock data representing the Spotify API response
    mock_spotify_response = [
        {
            "id": "1",
            "name": "Under Pressure - Remastered",
            "artists": [{"name": "Queen"}],
            "album": {"release_date": "2011-01-01"}, 
            "external_ids": {"isrc": "GBUM71029604"},
            "duration_ms": 248000
        },
        {
            "id": "2",
            "name": "A Track With No ISRC",
            "artists": [{"name": "The Beatles"}],
            "album": {"release_date": "2000-11-13"}, 
            "external_ids": {},
            "duration_ms": 185000
        },
        {
            "id": "3",
            "name": "Brand New Indie Song",
            "artists": [{"name": "Local Artist"}],
            "album": {"release_date": "2026-03-15"}, 
            "external_ids": {"isrc": "USXX92612345"},
            "duration_ms": 210000
        }
    ]

    print("Sorting playlist...")
    sorted_playlist = sort_playlist(mock_spotify_response, sort_by="date", order="asc")
    
    for rank, track in enumerate(sorted_playlist, start=1):
        print(f"{rank}. {track['track_name']} by {track['artist_name']}")
        print(f"    Date: {track['display_date']} (Source: {track['source_used']})")