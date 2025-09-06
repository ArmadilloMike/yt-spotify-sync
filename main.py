import os
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import googleapiclient.discovery

import requests
from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

load_dotenv()
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
SPOTIFY_SCOPE = os.getenv("SPOTIFY_SCOPE")
GOOGLE_SCOPE = os.getenv("GOOGLE_SCOPE")

class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed_path.query)
        code = query.get('code', [None]) [0]
        if code:
            token_url = "https://accounts.spotify.com/api/token"
            payload = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": SPOTIFY_REDIRECT_URI,
                "client_id": SPOTIFY_CLIENT_ID,
                "client_secret": SPOTIFY_CLIENT_SECRET
            }
            responce = requests.post(token_url, data=payload)
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b"Authentication successful! You can close this window.")
            print("Access token response:", responce.json())
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing code parameter.")

def spotify_authenticate():
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

if __name__ == "__main__":
    credentials = google_authenticate(GOOGLE_SCOPE)
    get_youtube_playlists(credentials)