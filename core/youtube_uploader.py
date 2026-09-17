import os
import pickle
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow, Flow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from core.config import CLIENT_SECRET_FILE, TOKEN_PICKLE_FILE

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly"
]

def is_youtube_authenticated() -> bool:
    """Checks whether YouTube token file exists on disk without making network calls."""
    if not TOKEN_PICKLE_FILE.exists():
        return False
    try:
        with open(TOKEN_PICKLE_FILE, "rb") as token:
            creds = pickle.load(token)
            return creds is not None and (creds.valid or getattr(creds, "refresh_token", None) is not None)
    except Exception:
        return False

def get_credentials_or_none():
    """Loads and returns valid credentials, refreshing if needed. Used only when uploading."""
    if not TOKEN_PICKLE_FILE.exists():
        return None
    try:
        with open(TOKEN_PICKLE_FILE, "rb") as token:
            creds = pickle.load(token)
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(TOKEN_PICKLE_FILE, "wb") as token:
                pickle.dump(creds, token)
        if creds and creds.valid:
            return creds
    except Exception as e:
        print(f"Credentials load/refresh error: {e}")
    return None

def create_oauth_flow(redirect_uri: str) -> Flow:
    """Creates a Google OAuth flow configured for the specified redirect URI."""
    if not CLIENT_SECRET_FILE.exists():
        raise FileNotFoundError(f"client_secret.json not found at {CLIENT_SECRET_FILE}")
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
    return Flow.from_client_secrets_file(
        str(CLIENT_SECRET_FILE),
        scopes=SCOPES,
        redirect_uri=redirect_uri
    )

def get_oauth_authorization_url(redirect_uri: str) -> str:
    """Generates the Google OAuth authorization URL to redirect the user directly."""
    flow = create_oauth_flow(redirect_uri)
    auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")
    return auth_url

def exchange_code_for_token(code: str, redirect_uri: str):
    """Exchanges an authorization code from Google redirect for persistent credentials."""
    flow = create_oauth_flow(redirect_uri)
    flow.fetch_token(code=code)
    creds = flow.credentials
    TOKEN_PICKLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TOKEN_PICKLE_FILE, "wb") as token:
        pickle.dump(creds, token)
    return creds

def start_oauth_flow():
    """Fallback interactive OAuth in user browser using local port."""
    if not CLIENT_SECRET_FILE.exists():
        raise FileNotFoundError(f"client_secret.json not found at {CLIENT_SECRET_FILE}")
    
    flow = InstalledAppFlow.from_client_secrets_file(
        str(CLIENT_SECRET_FILE), SCOPES
    )
    try:
        creds = flow.run_local_server(port=8080, prompt="consent", access_type="offline")
    except Exception:
        creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

    TOKEN_PICKLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TOKEN_PICKLE_FILE, "wb") as token:
        pickle.dump(creds, token)
    return creds

def get_authenticated_youtube_service():
    """Returns YouTube service using existing credentials, or raises error if not authenticated."""
    creds = get_credentials_or_none()
    if not creds:
        raise RuntimeError("YouTube account is not connected yet. Please click 'Connect YouTube Channel'.")
    return build("youtube", "v3", credentials=creds)

_CHANNEL_INFO_CACHE = {"data": None, "timestamp": 0}

def get_connected_channel_info() -> dict:
    """Returns basic profile of connected YouTube channel if authenticated, cached for 10 minutes."""
    import time
    now = time.time()
    if _CHANNEL_INFO_CACHE["data"] and (now - _CHANNEL_INFO_CACHE["timestamp"]) < 600:
        return _CHANNEL_INFO_CACHE["data"]

    creds = get_credentials_or_none()
    if not creds:
        return None
    try:
        youtube = build("youtube", "v3", credentials=creds)
        response = youtube.channels().list(
            part="snippet,statistics",
            mine=True
        ).execute()
        items = response.get("items", [])
        if items:
            item = items[0]
            snippet = item.get("snippet", {})
            stats = item.get("statistics", {})
            data = {
                "title": snippet.get("title", "YouTube Channel"),
                "description": snippet.get("description", ""),
                "custom_url": snippet.get("customUrl", ""),
                "thumbnail": snippet.get("thumbnails", {}).get("default", {}).get("url", ""),
                "subscribers": stats.get("subscriberCount", "0"),
                "video_count": stats.get("videoCount", "0"),
                "view_count": stats.get("viewCount", "0")
            }
            _CHANNEL_INFO_CACHE["data"] = data
            _CHANNEL_INFO_CACHE["timestamp"] = now
            return data
    except Exception as e:
        print(f"Error fetching channel info: {e}")
    return None

def upload_video_to_youtube(
    video_path: Path,
    title: str,
    description: str,
    tags: list = None,
    privacy_status: str = "public",
    publish_at: str = None,
    thumbnail_path: Path = None
) -> dict:
    """
    Uploads video to YouTube with full metadata and optional custom thumbnail.
    Returns: {"status": "success", "video_id": ..., "video_url": ...}
    """
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video file {video_path} does not exist")

    youtube = get_authenticated_youtube_service()

    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags or ["shorts", "psychology", "stoicism"],
            "categoryId": "27"  # Education / Mindset
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False
        }
    }

    if publish_at and privacy_status == "private":
        body["status"]["publishAt"] = publish_at

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        resumable=True,
        chunksize=1024 * 1024 * 2
    )

    print(f"Uploading '{title}' to YouTube...")
    response = None
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploaded {int(status.progress() * 100)}%")

    video_id = response.get("id")
    video_url = f"https://youtube.com/shorts/{video_id}"
    print(f"Upload complete! Live at: {video_url}")

    # Set custom thumbnail if provided
    if thumbnail_path and Path(thumbnail_path).exists():
        try:
            print(f"Uploading thumbnail {thumbnail_path}...")
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(str(thumbnail_path), mimetype="image/jpeg")
            ).execute()
            print("Thumbnail uploaded successfully!")
        except Exception as e:
            print(f"Notice: Could not set thumbnail: {e}")

    return {
        "status": "success",
        "video_id": video_id,
        "video_url": video_url,
        "title": title
    }

if __name__ == "__main__":
    print("Testing YouTube service configuration...")
    print("Client secret exists:", CLIENT_SECRET_FILE.exists())
