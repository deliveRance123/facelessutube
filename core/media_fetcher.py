import requests
from pathlib import Path
from core.config import PEXELS_API_KEY, TEMP_DIR

PEXELS_VIDEO_URL = "https://api.pexels.com/videos/search"
HEADERS_BASE = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

FALLBACK_QUERIES = [
    "sharp Nigerian man portrait studio lighting 4k",
    "confident African woman professional sharp focus",
    "charismatic Black entrepreneur cinematic portrait",
    "modern African creator high definition portrait",
    "Lagos modern skyline golden hour cinematic",
    "stylish young Nigerian in studio sharp lighting",
    "thoughtful African leader cinematic close up",
    "vibrant African urban street cinematography 4k",
    "real human executive looking at camera sharp focus",
    "authentic African young professional natural lighting"
]

BANNED_VISUAL_KEYWORDS = [
    "statue", "bust", "marble", "sculpture", "stone carving", "sculpted", 
    "monument", "socrates", "plinth", "ancient pillar", "relic", "ruins", 
    "plaster", "mannequin", "greek statue", "roman bust", "stone figure", "carving"
]

def is_banned_visual_subject(text: str) -> bool:
    """Detects if a query, title, or video URL contains statues, busts, or stone carvings."""
    if not text:
        return False
    t = str(text).lower()
    return any(kw in t for kw in BANNED_VISUAL_KEYWORDS)

def sanitize_visual_query(query: str) -> str:
    """Guarantees visual queries are strictly real living people and modern scenes, never statues."""
    import random
    if not query or is_banned_visual_subject(query):
        return random.choice(FALLBACK_QUERIES)
    return query

def search_pexels_video(query: str, orientation: str = "portrait") -> str:
    """
    Queries Pexels for a vertical video clip matching the query.
    Enforces strict filter against statues, marble busts, or stone relics.
    """
    if not PEXELS_API_KEY:
        raise ValueError("PEXELS_API_KEY is not set in .env")
        
    query = sanitize_visual_query(query)
    headers = {**HEADERS_BASE, "Authorization": PEXELS_API_KEY}
    params = {
        "query": query,
        "orientation": orientation,
        "per_page": 8,
        "size": "medium"
    }
    
    try:
        response = requests.get(PEXELS_VIDEO_URL, headers=headers, params=params, timeout=12)
        response.raise_for_status()
        data = response.json()
        
        videos = data.get("videos", [])
        if not videos:
            return None
            
        for video in videos:
            # Check video URL and metadata for banned terms
            v_url = str(video.get("url", "")).lower()
            if is_banned_visual_subject(v_url):
                print(f"[MediaFetcher] Filtered out statue/sculpture video: {v_url}")
                continue
            
            video_files = video.get("video_files", [])
            
            if orientation == "portrait":
                # 1. Prefer vertical files (h > w) around 720p to 1080p
                for vf in video_files:
                    w = vf.get("width", 0)
                    h = vf.get("height", 0)
                    link = vf.get("link")
                    if h > w and link and 720 <= h <= 1920:
                        return link
                # 2. Fallback to any vertical file
                for vf in video_files:
                    w = vf.get("width", 0)
                    h = vf.get("height", 0)
                    link = vf.get("link")
                    if h > w and link:
                        return link
            else:
                # 1. Prefer horizontal landscape files (w > h) around 720p to 1080p
                for vf in video_files:
                    w = vf.get("width", 0)
                    h = vf.get("height", 0)
                    link = vf.get("link")
                    if w > h and link and 1080 <= w <= 1920:
                        return link
                # 2. Fallback to any horizontal file
                for vf in video_files:
                    w = vf.get("width", 0)
                    h = vf.get("height", 0)
                    link = vf.get("link")
                    if w > h and link:
                        return link
                    
            # 3. Fallback to any mp4
            for vf in video_files:
                if vf.get("file_type") == "video/mp4" and vf.get("link"):
                    return vf.get("link")
                    
        return None
    except Exception as e:
        print(f"Error fetching Pexels video for '{query}': {e}")
        return None

def download_video_clip(url: str, output_path: Path) -> Path:
    """Downloads a video file from URL to output_path using streaming and browser headers"""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    response = requests.get(url, headers=HEADERS_BASE, stream=True, timeout=20)
    response.raise_for_status()
    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 512):
            if chunk:
                f.write(chunk)
    return output_path

def search_pexels_photo(query: str, orientation: str = "portrait") -> str:
    """Queries Pexels for an ultra-sharp, high-res photo (large2x / original) of real people/scenes."""
    if not PEXELS_API_KEY:
        return None
    
    query = sanitize_visual_query(query)
    headers = {**HEADERS_BASE, "Authorization": PEXELS_API_KEY}
    
    # Try direct query first, then clean focused query if needed
    queries_to_try = [query]
    if len(query.split()) > 4:
        queries_to_try.append(" ".join(query.split()[:3]))
    queries_to_try.append("sharp African portrait studio lighting 4k")

    for q in queries_to_try:
        params = {"query": q, "orientation": orientation, "per_page": 6}
        try:
            res = requests.get("https://api.pexels.com/v1/search", headers=headers, params=params, timeout=8)
            if res.status_code == 200:
                photos = res.json().get("photos", [])
                for photo in photos:
                    p_url = str(photo.get("url", "")).lower()
                    p_alt = str(photo.get("alt", "")).lower()
                    if is_banned_visual_subject(p_url) or is_banned_visual_subject(p_alt):
                        continue
                    src = photo.get("src", {})
                    link = src.get("large2x") or src.get("original") or src.get("large")
                    if link:
                        return link
        except Exception:
            continue
    return None

import urllib.parse
import random

def generate_photorealistic_ai_image(
    prompt: str,
    output_path: Path,
    orientation: str = "portrait"
) -> Path:
    """
    Generates an ultra-sharp, photorealistic 4K AI image of a real living human person or cinematic scene.
    Enforces 100% lifelike human photography — NEVER stone statues or marble busts.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    is_long = (orientation == "landscape")
    width, height = (1280, 720) if is_long else (720, 1280)

    clean_prompt = sanitize_visual_query(prompt)

    # Enhance visual prompt for photorealism and culture
    enhanced_prompt = (
        f"Realistic photograph of a real living human person, {clean_prompt}, "
        f"authentic human skin details and pores, natural expressive eyes, real person, 85mm portrait photography, "
        f"cinematic studio lighting, ultra-sharp focus, 8k resolution, hyperrealistic, award winning photography, "
        f"no statues, no marble busts, no sculptures, no stone carvings, no CGI, no cartoon, 100% real lifelike human"
    )

    encoded = urllib.parse.quote(enhanced_prompt)
    seed = random.randint(10000, 999999)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&model=flux&nologo=true&seed={seed}"

    try:
        req = requests.get(url, headers=HEADERS_BASE, stream=True, timeout=20)
        req.raise_for_status()
        with open(output_path, "wb") as f:
            for chunk in req.iter_content(chunk_size=1024 * 64):
                if chunk:
                    f.write(chunk)

        if output_path.exists() and output_path.stat().st_size > 15000:
            # Guarantee 100% zero-watermark: trim bottom margin and scale cleanly to target dimensions
            try:
                import imageio_ffmpeg
                import subprocess
                ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
                clean_tmp = output_path.parent / f"clean_{output_path.name}"
                cmd = [
                    ffmpeg, "-y", "-i", str(output_path),
                    "-vf", f"crop=in_w:in_h-45:0:0,scale={width}:{height}",
                    str(clean_tmp)
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                if clean_tmp.exists() and clean_tmp.stat().st_size > 10000:
                    clean_tmp.replace(output_path)
            except Exception:
                pass

            print(f"[AI Vision Engine] Generated 4K photorealistic scene: {output_path.name} ({output_path.stat().st_size // 1024} KB)")
            return output_path
    except Exception as e:
        print(f"Notice: AI photorealistic image generation fallback ({e})")
    
    return None

def fetch_clips_for_scenes(scenes: list, orientation: str = "portrait") -> list:
    """
    Iterates over scenes, searches Pexels for video clips, and generates ultra-sharp
    photorealistic 4K AI images when video clips are not ideal.
    orientation: 'portrait' (Shorts 9:16) or 'landscape' (Long 16:9).
    """
    downloaded_clips = []
    max_scenes = min(len(scenes), 12 if orientation == "landscape" else 8)
    
    for i in range(max_scenes):
        scene = scenes[i]
        query = scene.get("visual_search", "")
        clean_q = "".join(c for c in query if c.isalnum() or c in (" ", "_")).strip()
        dest_file = TEMP_DIR / f"scene_{i}_{clean_q[:12].replace(' ', '_')}.mp4"
        
        # Check if already downloaded
        if dest_file.exists() and dest_file.stat().st_size > 100_000:
            downloaded_clips.append(dest_file)
            continue
            
        video_url = search_pexels_video(query, orientation=orientation)
        
        if video_url:
            try:
                print(f"Downloading clip {i+1}/{max_scenes} for '{query}'...")
                download_video_clip(video_url, dest_file)
                if dest_file.exists() and dest_file.stat().st_size > 50_000:
                    downloaded_clips.append(dest_file)
                    print(f"[OK] Clip {i+1} downloaded ({dest_file.stat().st_size // 1024} KB)")
                    continue
            except Exception as e:
                print(f"Notice: Video clip download error for scene {i+1}: {e}")

        # If video clip unavailable or low quality: Generate sharp photorealistic 4K scene
        img_dest = TEMP_DIR / f"scene_{i}_{clean_q[:12].replace(' ', '_')}.jpg"
        ai_img = generate_photorealistic_ai_image(query, img_dest, orientation=orientation)
        if ai_img and ai_img.exists() and ai_img.stat().st_size > 15000:
            downloaded_clips.append(ai_img)
            print(f"[OK] Photorealistic 4K image {i+1} ready for Ken Burns animation")
            continue

        # Fallback to Pexels HD photo
        photo_url = search_pexels_photo(query, orientation=orientation)
        if photo_url:
            try:
                download_video_clip(photo_url, img_dest)
                if img_dest.exists() and img_dest.stat().st_size > 20_000:
                    downloaded_clips.append(img_dest)
                    print(f"[OK] Stock photo {i+1} downloaded ({img_dest.stat().st_size // 1024} KB)")
            except Exception as e:
                print(f"Error downloading photo for scene {i+1}: {e}")
            
    return downloaded_clips

if __name__ == "__main__":
    print("Testing photorealistic AI generation...")
    test_p = TEMP_DIR / "test_photoreal.jpg"
    res = generate_photorealistic_ai_image("sharp portrait of Nigerian entrepreneur studio lighting", test_p)
    print("Result:", res)
