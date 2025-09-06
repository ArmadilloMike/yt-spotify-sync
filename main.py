import os
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import googleapiclient.discovery
from typing import Optional
import requests
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

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

if __name__ == "__main__":
    yt_credentials = google_authenticate([GOOGLE_SCOPE])

    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=yt_credentials)
    playlists = youtube.playlists().list(part="snippet", mine=True, maxResults=50).execute().get("items", [])
    selected_playlist = playlists[0]

    song_names = get_song_names_youtube(selected_playlist, yt_credentials)
    print(song_names)
