import time
import json
import sys
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
from pathlib import Path
from core.config import VIDEOS_DIR, TEMP_DIR, VOICE_SAMPLE_PATH, FACE_IMAGE_PATH

def generate_video_pipeline(
    custom_topic: str = None,
    format_type: str = "short",
    voice: str = None,
    niche: str = "psychology",
    include_avatar: bool = False,
    custom_audio_path: Path = None,
    caption_style: str = "classic",
    progress_cb=None
) -> dict:
    from core.script_gen import generate_video_script
    from core.voice_gen import generate_speech, transcribe_custom_audio
    from core.media_fetcher import fetch_clips_for_scenes
    from core.video_composer import compose_video
    from core.thumbnail_gen import create_video_thumbnail
    """
    Complete end-to-end automation runner:
    format_type: 'short' (9:16 vertical) or 'long' (16:9 horizontal documentary).
    voice: neural voice identifier (e.g. en-US-ChristopherNeural) or 'custom' for user recording.
    niche: 'psychology' (Dark Psychology / Stoic) or 'tech' (AI / Robotics / Future Tech).
    include_avatar: bool (whether to overlay face photo in video & thumbnail).
    custom_audio_path: optional path to user-uploaded voiceover file.
    """
    def log(msg):
        print(f"[Deliverace Engine] {msg}")
        if progress_cb:
            progress_cb(msg)

    prefix = "short" if format_type == "short" else "long"
    video_id = f"deliv_{prefix}_{int(time.time())}"
    
    from core.config import get_default_voice
    if not voice:
        voice = get_default_voice()
        
    # Check if user provided an explicit pre-recorded audio file to override script & TTS
    use_raw_audio = False
    raw_audio_file = None
    if custom_audio_path and Path(custom_audio_path).exists() and Path(custom_audio_path).stat().st_size > 1000:
        use_raw_audio = True
        raw_audio_file = Path(custom_audio_path)
    elif voice == "custom":
        if not (VOICE_SAMPLE_PATH.exists() and VOICE_SAMPLE_PATH.stat().st_size > 1000):
            raise ValueError(
                "Personal voice clone was selected, but no audio sample was found in voice.wav. "
                "Please record or upload your voice sample in the Voice Studio first or pick an AI neural voice."
            )

    if use_raw_audio:
        log(f"🎙️ Using direct uploaded voiceover track ({raw_audio_file.name})...")
        audio_info = transcribe_custom_audio(raw_audio_file, format_type=format_type, custom_topic=custom_topic)
        script_data = {
            "title": audio_info.get("title", "The Power of Master Strategy #shorts"),
            "description": audio_info.get("description", "Master human behavior and leadership #mindset #growth"),
            "tags": audio_info.get("tags", ["mindset", "psychology", "leadership"]),
            "hook": audio_info.get("full_narration", "")[:100],
            "full_narration": audio_info.get("full_narration", ""),
            "scenes": audio_info.get("scenes", [{"visual_search": "sharp African man portrait studio lighting 4k"}])
        }
        voice_res = {
            "audio_path": raw_audio_file,
            "words": audio_info.get("words", [])
        }
        log(f"✅ Direct voiceover processed: '{script_data['title']}' ({len(voice_res['words'])} words mapped)")
    else:
        # Gather recent titles in this niche to guarantee 100% fresh, non-repeating topics
        recent_titles = []
        for meta_path in sorted(VIDEOS_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:15]:
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    vdata = json.load(f)
                    if vdata.get("niche") == niche and vdata.get("title"):
                        recent_titles.append(vdata["title"])
            except Exception:
                pass

        # 1. Script
        type_label = "Cinema Widescreen (16:9)" if format_type == "long" else "Vertical Video (9:16)"
        niche_label = "Future Tech & AI" if niche == "tech" else "Dark Psychology & Stoic"
        log(f"🧠 Generating {type_label} narrative ({niche_label})...")
        script_data = generate_video_script(custom_topic, format_type=format_type, niche=niche, recent_titles=recent_titles)
        log(f"✅ Script generated: '{script_data.get('title')}'")

        # 2. Voice
        voice_desc = "Your Cloned Voice" if voice == "custom" else f"Selected AI Voice ({voice})"
        log(f"🎙️ Synthesizing voiceover with {voice_desc}...")
        audio_file = TEMP_DIR / f"{video_id}_audio.mp3"
        voice_res = generate_speech(script_data["full_narration"], audio_file, voice=voice)
        log(f"✅ Voiceover ready ({len(voice_res['words'])} words mapped)")

    # 3. B-Roll
    orientation = "landscape" if format_type == "long" else "portrait"
    log(f"🎬 Sourcing moody HD cinematic visuals ({orientation})...")
    clips = fetch_clips_for_scenes(script_data["scenes"], orientation=orientation)
    log(f"✅ Downloaded {len(clips)} matching clips")

    # 4. Compose
    output_filename = f"{video_id}.mp4"
    log("⚡ Assembling video with dynamic camera motion, gold captions, and soundtrack...")
    video_path = compose_video(
        clips=clips,
        voice_audio=voice_res["audio_path"],
        words=voice_res["words"],
        output_name=output_filename,
        format_type=format_type,
        include_avatar=include_avatar,
        caption_style=caption_style
    )
    log(f"🎉 Final Video Ready: {video_path.name}")

    # 5. Generate Click-Worthy AI Artwork Thumbnail
    thumbnail_filename = f"{video_id}_thumb.jpg"
    thumb_path = VIDEOS_DIR / thumbnail_filename
    log("🖼️ Generating custom AI artwork thumbnail with 3D typography...")
    try:
        create_video_thumbnail(
            title=script_data.get("title", "The Law of Silence"),
            output_path=thumb_path,
            format_type=format_type,
            include_avatar=include_avatar,
            niche=niche,
            video_path=video_path
        )
        log(f"✅ Thumbnail ready: {thumbnail_filename}")
    except Exception as e:
        print(f"Notice: Thumbnail creation failed: {e}")
        thumbnail_filename = None

    # 6. Save Metadata Record
    metadata = {
        "id": video_id,
        "format_type": format_type,  # 'short' | 'long'
        "niche": niche,  # 'psychology' | 'tech'
        "title": script_data.get("title"),
        "description": script_data.get("description"),
        "tags": script_data.get("tags", []),
        "hook": script_data.get("hook"),
        "full_narration": script_data.get("full_narration"),
        "scenes": script_data.get("scenes", []),
        "video_filename": output_filename,
        "video_path": str(video_path),
        "thumbnail_filename": thumbnail_filename,
        "status": "ready",  # ready | scheduled | published
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "youtube_url": None
    }

    meta_file = VIDEOS_DIR / f"{video_id}.json"
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    return metadata

def get_all_videos() -> list:
    """Returns all video records for the Deliverace dashboard, newest first"""
    videos = []
    for f in sorted(VIDEOS_DIR.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            with open(f, "r", encoding="utf-8") as jf:
                data = json.load(jf)
                if (VIDEOS_DIR / data.get("video_filename", "")).exists():
                    videos.append(data)
        except Exception:
            pass
    return videos

def get_video_by_id(video_id: str) -> dict:
    meta_file = VIDEOS_DIR / f"{video_id}.json"
    if meta_file.exists():
        with open(meta_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

def update_video_metadata(video_id: str, new_title: str, new_desc: str) -> dict:
    meta_file = VIDEOS_DIR / f"{video_id}.json"
    if meta_file.exists():
        with open(meta_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["title"] = new_title
        data["description"] = new_desc
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return data
    return None

def mark_video_published(video_id: str, youtube_url: str):
    meta_file = VIDEOS_DIR / f"{video_id}.json"
    if meta_file.exists():
        with open(meta_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["status"] = "published"
        data["youtube_url"] = youtube_url
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

def delete_video_by_id(video_id: str) -> bool:
    meta_file = VIDEOS_DIR / f"{video_id}.json"
    if not meta_file.exists():
        return False
    try:
        with open(meta_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        video_fn = data.get("video_filename")
        if video_fn:
            video_path = VIDEOS_DIR / video_fn
            if video_path.is_file():
                try:
                    video_path.unlink(missing_ok=True)
                except Exception as ve:
                    print(f"Notice: video file locked: {ve}")
                    
        thumb_fn = data.get("thumbnail_filename")
        if thumb_fn:
            thumb_path = VIDEOS_DIR / thumb_fn
            if thumb_path.is_file():
                try:
                    thumb_path.unlink(missing_ok=True)
                except Exception as te:
                    print(f"Notice: thumb file locked: {te}")
                    
        meta_file.unlink(missing_ok=True)
        return True
    except Exception as e:
        print(f"Error deleting video {video_id}: {e}")
        return False

def generate_story_video_pipeline(
    prompt: str = None,
    custom_script: str = None,
    images: list = None,
    format_type: str = "short",
    niche: str = "story",
    voice_provider: str = "edge-tts",
    voice_id: str = "en-US-ChristopherNeural",
    elevenlabs_key: str = None,
    caption_style: str = "gold",
    user_id: str = None,
    progress_cb = None
) -> dict:
    from core.script_gen import generate_multi_scene_story
    from core.voice_plugin import synthesize_voice
    from core.story_animator import animate_story_video
    from core.db import db
    import asyncio
    
    def log(msg):
        print(f"[Story Engine] {msg}")
        if progress_cb:
            progress_cb(msg)
            
    prefix = "short" if format_type == "short" else "long"
    project_id = f"story_{prefix}_{int(time.time())}"
    
    # 1. Resolve Images
    valid_images = []
    if images:
        for p in images:
            ip = Path(p)
            if ip.exists() and ip.stat().st_size > 1000:
                valid_images.append(ip)
                
    if not valid_images:
        if FACE_IMAGE_PATH.exists():
            valid_images.append(FACE_IMAGE_PATH)
        else:
            raise ValueError("Please provide at least 1 image to animate.")
            
    num_images = len(valid_images)
    
    # 2. Resolve Script
    is_pasted_script = False
    script_text = ""
    if custom_script and custom_script.strip():
        is_pasted_script = True
        script_text = custom_script.strip()
    elif prompt and (len(prompt.strip()) > 100 or "scene" in prompt.lower() or "\n" in prompt):
        is_pasted_script = True
        script_text = prompt.strip()

    if is_pasted_script:
        log("📝 Using provided story script...")
        first_line = script_text.splitlines()[0].strip()
        clean_title = first_line.replace("10-Scene Voiceover Script:", "").replace("Voiceover Script:", "").replace("Script:", "").replace('"', '').strip()
        if not clean_title or len(clean_title) > 60:
            clean_title = prompt.strip()[:60] if (prompt and len(prompt.strip()) <= 60 and "\n" not in prompt) else "Custom Story Animation"
        story_data = {
            "title": clean_title,
            "description": f"Custom animated story ({niche})",
            "tags": ["story", niche, "animation"],
            "hook": script_text[:100],
            "full_narration": script_text,
            "scenes": [{"scene_index": i, "narration": f"Scene {i+1}"} for i in range(num_images)]
        }
    else:
        log(f"Generating multi-scene {niche.title()} script for {num_images} scenes...")
        clean_prompt = prompt if (prompt and prompt.strip()) else f"A compelling viral {niche} story with twists and intense pacing"
        story_data = generate_multi_scene_story(
            clean_prompt,
            niche=niche,
            format_type=format_type,
            num_scenes=num_images
        )
        
    log(f"Story Title: '{story_data.get('title')}'")

    # 3. Voiceover Narration
    log(f"Synthesizing voiceover narration with {voice_provider.upper()} ({voice_id})...")
    def _run_sync(coro):
        try:
            return asyncio.run(coro)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()

    voice_audio, words = _run_sync(synthesize_voice(
        text=story_data.get("full_narration", ""),
        voice_provider=voice_provider,
        voice_id=voice_id,
        elevenlabs_key=elevenlabs_key,
        output_audio=TEMP_DIR / f"{project_id}_voice.mp3"
    ))

    # 4. Animate Video with Ken Burns Motion and Viral Captions
    output_filename = f"{project_id}.mp4"
    log(f"Rendering {num_images} scenes into polished video (Captions: {caption_style.upper()})...")
    video_path = animate_story_video(
        image_paths=valid_images,
        voice_audio_path=voice_audio,
        words=words,
        output_filename=output_filename,
        format_type=format_type,
        caption_style=caption_style,
        progress_callback=progress_cb
    )

    # 5. Save Record
    total_dur = words[-1]["end"] if words else 15.0
    try:
        db.execute(
            "INSERT INTO projects (id, user_id, title, prompt, script, format_type, niche, voice_provider, voice_id, caption_style, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (project_id, user_id or "default_user", story_data.get("title"), prompt or "", story_data.get("full_narration"), format_type, niche, voice_provider, voice_id, caption_style, "completed")
        )
        db.execute(
            "INSERT INTO videos (id, project_id, user_id, title, format_type, filename, video_url, duration, caption_style) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (project_id, project_id, user_id or "default_user", story_data.get("title"), format_type, output_filename, f"/videos_static/{output_filename}", total_dur, caption_style)
        )
        log("Saved project record to database!")
    except Exception as dbe:
        print(f"Notice: database insert notice: {dbe}")
        
    meta = {
        "id": project_id,
        "user_id": user_id,
        "format_type": format_type,
        "niche": niche,
        "title": story_data.get("title"),
        "description": story_data.get("description"),
        "tags": story_data.get("tags", []),
        "hook": story_data.get("hook"),
        "full_narration": story_data.get("full_narration"),
        "scenes": story_data.get("scenes", []),
        "video_filename": output_filename,
        "video_path": str(video_path),
        "caption_style": caption_style,
        "status": "ready",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    with open(VIDEOS_DIR / f"{project_id}.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
        
    return meta
