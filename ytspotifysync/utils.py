import os
import re
from difflib import SequenceMatcher

from dotenv import load_dotenv

load_dotenv()

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")
SPOTIFY_SCOPE = os.getenv("SPOTIFY_SCOPE")
GOOGLE_SCOPE = os.getenv("GOOGLE_SCOPE")

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

def select_playlist(playlists, platform_name):
    print(f"Select a {platform_name} playlist:")
    for idx, playlist in enumerate(playlists):
        print(f"{idx + 1}: {playlist['name'] if 'name' in playlist else playlist['snippet']['title']}")
    choice = int(input("Enter number: ")) - 1
    return playlists[choice]