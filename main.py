import os
import urllib.parse
import webbrowser
from difflib import SequenceMatcher
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import googleapiclient.discovery
from typing import Optional
import requests
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow
import time
import re

load_dotenv()
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
SPOTIFY_SCOPE = os.getenv("SPOTIFY_SCOPE")
GOOGLE_SCOPE = os.getenv("GOOGLE_SCOPE")

spotify_access_token = None

class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global spotify_access_token
        parsed_path = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed_path.query)
        code = query.get('code', [None])[0]
        if code:
            token_url = "https://accounts.spotify.com/api/token"
            payload = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": SPOTIFY_REDIRECT_URI,
                "client_id": SPOTIFY_CLIENT_ID,
                "client_secret": SPOTIFY_CLIENT_SECRET
            }
            response = requests.post(token_url, data=payload)
            data = response.json()
            spotify_access_token = data.get("access_token")
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"Authentication successful! You can close this window.")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing code parameter.")

def spotify_authenticate() -> Optional[str]:
    global spotify_access_token
    spotify_access_token = None
    auth_url = (
        "https://accounts.spotify.com/authorize"
        f"?response_type=code&client_id={SPOTIFY_CLIENT_ID}"
        f"&scope={SPOTIFY_SCOPE}&redirect_uri={SPOTIFY_REDIRECT_URI}"
    )
    webbrowser.open(auth_url)
    port = int(urllib.parse.urlparse(SPOTIFY_REDIRECT_URI).port)
    server = HTTPServer(("localhost", port), CallbackHandler)
    print("waiting for spotify auth")
    server.handle_request()
    return spotify_access_token

def google_authenticate(scopes):
    client_secret_file = Path(__file__).parent / "client_secret.json"

    flow = InstalledAppFlow.from_client_secrets_file(
        "client_secret.json",
        scopes=scopes
    )

    credentials = flow.run_local_server(
        port = 8080,
        prompt='consent',
        access_type='offline'
    )

    return credentials

def get_youtube_playlists(yt_credentials):
    youtube = googleapiclient.discovery.build(
        "youtube", "v3", credentials=yt_credentials
    )
    request = youtube.playlists().list(
        part="snippet",
        mine=True,
        maxResults=50
    )
    response = request.execute()
    playlists = response.get("items", [])
    for playlist in playlists:
        print(playlist["snippet"]["title"])

def get_spotify_playlists(access_token):
    url = "https://api.spotify.com/v1/me/playlists"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    params = {
        "limit": 50
    }
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    playlists = response.json().get("items", [])
    for playlist in playlists:
        print(f"Name: {playlist['name']}, ID: {playlist['id']}")
    return playlists

def get_song_names_spotify(playlist, access_token):
    playlist_id = playlist["id"]
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    params = {
        "limit": 100,
        "offset": 0
    }
    song_names = []
    while True:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        for item in data["items"]:
            track = item.get("track")
            if track:
                song_names.append(track.get("name"))
        if data["next"]:
            url = data["next"]
            params = {}
        else:
            break
        return song_names

def get_song_names_youtube(playlist, yt_credentials):
    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=yt_credentials)
    playlist_id = playlist["id"]
    song_names = []
    next_page_token = None

    while True:
        request = youtube.playlistItems().list(
            part="snippet",
            playlistId=playlist_id,
            maxResults=50,
            pageToken=next_page_token
        )
        response = request.execute()
        for item in response.get("items", []):
            title = item["snippet"]["title"]
            song_names.append(title)
        next_page_token = response.get("nextPageToken")
        if not next_page_token:
            break
    return song_names

def select_playlist(playlists, platform_name):
    print(f"Select a {platform_name} playlist:")
    for idx, playlist in enumerate(playlists):
        print(f"{idx + 1}: {playlist['name'] if 'name' in playlist else playlist['snippet']['title']}")
    choice = int(input("Enter number: ")) - 1
    return playlists[choice]

def search_youtube_video(youtube, query):
    request = youtube.search().list(
        part="id",
        q=query,
        maxResults=1,
        type="video"
    )
    response = request.execute()
    items = response.get("items", [])
    if items:
        return items[0]["id"]["videoId"]
    return None

def clean_song_title(title):
    # Remove common patterns and extras from YouTube titles
    patterns = [
        r'\(.*?\)',  # Anything in parentheses
        r'\[.*?\]',  # Anything in brackets
        r'Official.*?Video',  # "Official Video" and variants
        r'Official.*?Audio',  # "Official Audio" and variants
        r'ft\..*',  # Featured artists
        r'feat\..*',  # Featured artists alternative
        r'HD',  # HD quality marker
        r'HQ',  # HQ quality marker
        r'4K',  # 4K quality marker
        r'Lyrics',  # Lyrics indicator
        r'M/V',  # Music Video indicator
        r'MV',  # Music Video alternative
    ]

    cleaned = title
    for pattern in patterns:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

    # Split artist and title if possible
    if ' - ' in cleaned:
        artist, song = cleaned.split(' - ', 1)
    else:
        artist, song = '', cleaned

    return artist.strip(), song.strip()

def string_similarity(str1, str2):
    return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()

def search_spotify_track(song_name, access_token):
    artist, title = clean_song_title(song_name)

    url = "https://api.spotify.com/v1/search"
    headers = {"Authorization": f"Bearer {access_token}"}

    # Search with both artist and title if available
    if artist:
        query = f"{title} artist:{artist}"
    else:
        query = title

    params = {"q": query, "type": "track", "limit": 5}  # Increased limit to get more candidates
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()

    items = response.json().get("tracks", {}).get("items", [])
    if not items:
        return None

    # Score matches based on similarity
    best_match = None
    highest_score = 0

    for item in items:
        spotify_title = item['name']
        spotify_artist = item['artists'][0]['name']

        # Calculate similarity scores
        title_score = string_similarity(title, spotify_title)
        artist_score = string_similarity(artist, spotify_artist) if artist else 0.5

        # Combined score with more weight on title match
        total_score = (title_score * 0.6) + (artist_score * 0.4)

        if total_score > highest_score and total_score > 0.5:  # Minimum threshold
            highest_score = total_score
            best_match = item['id']

    return best_match

def add_video_to_youtube_playlist(youtube, playlist_id, video_id):
    youtube.playlistItems().insert(
        part="snippet",
        body={
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": video_id
                }
            }
        }
    ).execute()

def add_tracks_to_spotify_playlist(playlist_id, track_ids, access_token):
    url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    for i in range(0, len(track_ids), 100):
        batch = track_ids[i:i+100]
        data = {"uris": [f"spotify:track:{tid}" for tid in batch]}
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        time.sleep(0.2)  # avoid rate limits

def sync_spotify_to_youtube(spotify_token, yt_credentials):
    spotify_playlists = get_spotify_playlists(spotify_token)
    selected_spotify = select_playlist(spotify_playlists, "Spotify")
    song_names = get_song_names_spotify(selected_spotify, spotify_token)[:50]

    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=yt_credentials)
    yt_playlists = youtube.playlists().list(part="snippet", mine=True, maxResults=50).execute().get("items", [])
    selected_yt = select_playlist(yt_playlists, "YouTube")
    yt_playlist_id = selected_yt["id"]

    for song in song_names:
        video_id = search_youtube_video(youtube, song)
        if video_id:
            add_video_to_youtube_playlist(youtube, yt_playlist_id, video_id)
            print(f"Added '{song}' to YouTube playlist.")
        else:
            print(f"Could not find '{song}' on YouTube.")

def sync_youtube_to_spotify(yt_credentials, spotify_token):
    # Get YouTube playlists and select one
    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=yt_credentials)
    yt_playlists = youtube.playlists().list(part="snippet", mine=True, maxResults=50).execute().get("items", [])
    selected_yt = select_playlist(yt_playlists, "YouTube")
    yt_song_names = get_song_names_youtube(selected_yt, yt_credentials)[:50]

    # Get Spotify playlists and select one
    spotify_playlists = get_spotify_playlists(spotify_token)
    selected_spotify = select_playlist(spotify_playlists, "Spotify")
    spotify_playlist_id = selected_spotify["id"]

    # Search each YouTube song on Spotify and collect track IDs
    track_ids = []
    for song in yt_song_names:
        track_id = search_spotify_track(song, spotify_token)
        if track_id:
            track_ids.append(track_id)
            print(f"Found '{song}' on Spotify.")
        else:
            print(f"Could not find '{song}' on Spotify.")

    # Add found tracks to Spotify playlist
    if track_ids:
        add_tracks_to_spotify_playlist(spotify_playlist_id, track_ids, spotify_token)
        print("Added tracks to Spotify playlist.")

if __name__ == "__main__":
    yt_credentials = google_authenticate([GOOGLE_SCOPE])
    spotify_token = spotify_authenticate()
    sync_youtube_to_spotify(yt_credentials, spotify_token)
