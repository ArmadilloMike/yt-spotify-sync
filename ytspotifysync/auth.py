import urllib
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional

import requests
from google_auth_oauthlib.flow import InstalledAppFlow
from .utils import SPOTIFY_SCOPE, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI


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
        str(client_secret_file),
        scopes=scopes
    )

    credentials = flow.run_local_server(
        port = 8080,
        prompt='consent',
        access_type='offline'
    )

    return credentials