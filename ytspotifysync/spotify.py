import time

import googleapiclient
import requests
from .utils import clean_song_title, string_similarity, select_playlist


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
    song_names = get_song_names_spotify(selected_spotify, spotify_token)

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