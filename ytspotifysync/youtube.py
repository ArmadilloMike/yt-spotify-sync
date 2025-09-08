import googleapiclient

from .utils import clean_song_title, string_similarity, select_playlist
from .spotify import get_spotify_playlists, search_spotify_track, add_tracks_to_spotify_playlist

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

def sync_youtube_to_spotify(yt_credentials, spotify_token):
    # Get YouTube playlists and select one
    youtube = googleapiclient.discovery.build("youtube", "v3", credentials=yt_credentials)
    yt_playlists = youtube.playlists().list(part="snippet", mine=True, maxResults=50).execute().get("items", [])
    selected_yt = select_playlist(yt_playlists, "YouTube")
    yt_song_names = get_song_names_youtube(selected_yt, yt_credentials)

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