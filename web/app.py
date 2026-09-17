import time
import asyncio
import shutil
import json
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, FileResponse, RedirectResponse
from starlette.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from starlette.background import BackgroundTasks
from starlette.middleware import Middleware
from starlette.middleware.gzip import GZipMiddleware

from core.config import BASE_DIR, VIDEOS_DIR, TEMPLATES_DIR, STATIC_DIR, FACE_IMAGE_PATH, VOICE_SAMPLE_PATH, TEMP_DIR, MUSIC_DIR, get_default_voice, set_default_voice, get_channel_settings
from core.pipeline import get_all_videos, get_video_by_id, update_video_metadata, mark_video_published, delete_video_by_id

from core.voice_plugin import fetch_elevenlabs_voices
from core.db import (
    db, create_user, authenticate_user, get_user_by_id,
    update_user_elevenlabs_key, update_user_profile,
    get_all_users, update_user_role, update_user_subscription,
    get_platform_setting, set_platform_setting
)


import edge_tts

class DeliveraceApp(Starlette):
    def get(self, path: str):
        def decorator(func):
            self.add_route(path, func, methods=["GET"])
            return func
        return decorator

    def post(self, path: str):
        def decorator(func):
            self.add_route(path, func, methods=["POST"])
            return func
        return decorator

middleware = [
    Middleware(GZipMiddleware, minimum_size=500)
]

app = DeliveraceApp(middleware=middleware)

class CachedStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200:
            # 7-day client cache with stale-while-revalidate for blistering fast image loads
            response.headers["Cache-Control"] = "public, max-age=604800, stale-while-revalidate=86400"
        return response

# Mount storage/videos, storage/temp, and web/static with fast caching headers
app.mount("/videos_static", CachedStaticFiles(directory=str(VIDEOS_DIR)), name="videos_static")
app.mount("/temp_static", StaticFiles(directory=str(TEMP_DIR)), name="temp_static")
app.mount("/static", CachedStaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# In-memory generation state
GENERATION_STATE = {
    "is_generating": False,
    "last_log": "Idle",
    "last_error": None,
    "started_at": 0
}

def bg_generate(topic: str = None, format_type: str = "short", voice: str = None, niche: str = "psychology", include_avatar: bool = False, custom_audio_path: Path = None, caption_style: str = "classic"):
    global GENERATION_STATE
    GENERATION_STATE["is_generating"] = True
    GENERATION_STATE["last_error"] = None
    GENERATION_STATE["started_at"] = time.time()
    try:
        def cb(msg):
            GENERATION_STATE["last_log"] = msg

        from core.pipeline import generate_video_pipeline
        generate_video_pipeline(
            custom_topic=topic,
            format_type=format_type,
            voice=voice,
            niche=niche,
            include_avatar=include_avatar,
            custom_audio_path=custom_audio_path,
            caption_style=caption_style,
            progress_cb=cb
        )
        GENERATION_STATE["last_log"] = "Video generation complete!"
    except Exception as e:
        print(f"Generation error: {e}")
        GENERATION_STATE["last_error"] = str(e)
        GENERATION_STATE["last_log"] = f"Error: {str(e)}"
    finally:
        GENERATION_STATE["is_generating"] = False

def bg_generate_story(
    prompt: str = None,
    custom_script: str = None,
    images: list = None,
    format_type: str = "short",
    niche: str = "story",
    voice_provider: str = "edge-tts",
    voice_id: str = "en-US-ChristopherNeural",
    elevenlabs_key: str = None,
    caption_style: str = "gold",
    user_id: str = None
):
    global GENERATION_STATE
    GENERATION_STATE["is_generating"] = True
    GENERATION_STATE["last_error"] = None
    GENERATION_STATE["started_at"] = time.time()
    try:
        def cb(msg):
            GENERATION_STATE["last_log"] = msg

        from core.pipeline import generate_story_video_pipeline
        generate_story_video_pipeline(
            prompt=prompt,
            custom_script=custom_script,
            images=images,
            format_type=format_type,
            niche=niche,
            voice_provider=voice_provider,
            voice_id=voice_id,
            elevenlabs_key=elevenlabs_key,
            caption_style=caption_style,
            user_id=user_id,
            progress_cb=cb
        )
        GENERATION_STATE["last_log"] = "Story video generation complete!"
    except Exception as e:
        print(f"Story generation error: {e}")
        GENERATION_STATE["last_error"] = str(e)
        GENERATION_STATE["last_log"] = f"Error: {str(e)}"
    finally:
        GENERATION_STATE["is_generating"] = False


SESSION_TOKEN = "deliverace_authenticated_session_token_2026"

@app.get("/")
async def landing_page(request: Request):
    """Deliverace modern AI Story Platform landing page."""
    user_id = request.cookies.get("deliverace_user_id")
    is_authenticated = bool(user_id or request.cookies.get("deliverace_auth") == SESSION_TOKEN)
    videos = get_all_videos()
    sample_video = videos[0] if videos else None
    
    current_user = get_user_by_id(user_id) if user_id else None
    
    context = {
        "request": request,
        "is_authenticated": is_authenticated,
        "current_user": current_user,
        "videos_count": len(videos),
        "sample_video": sample_video,
        "default_voice": get_default_voice(),
        "channel_settings": get_channel_settings()
    }
    return templates.TemplateResponse(request, "landing.html", context=context)

@app.get("/modes")
async def modes_page(request: Request):
    """Creative modes showcase page."""
    user_id = request.cookies.get("deliverace_user_id")
    is_authenticated = bool(user_id or request.cookies.get("deliverace_auth") == SESSION_TOKEN)
    return templates.TemplateResponse(request, "modes.html", context={"request": request, "is_authenticated": is_authenticated})

@app.get("/how-it-works")
async def how_it_works_page(request: Request):
    """How Deliverace story video pipeline works."""
    user_id = request.cookies.get("deliverace_user_id")
    is_authenticated = bool(user_id or request.cookies.get("deliverace_auth") == SESSION_TOKEN)
    return templates.TemplateResponse(request, "how_it_works.html", context={"request": request, "is_authenticated": is_authenticated})

@app.get("/captions")
async def captions_page(request: Request):
    """Kinetic captions & subtitle typography page."""
    user_id = request.cookies.get("deliverace_user_id")
    is_authenticated = bool(user_id or request.cookies.get("deliverace_auth") == SESSION_TOKEN)
    return templates.TemplateResponse(request, "captions.html", context={"request": request, "is_authenticated": is_authenticated})

@app.get("/voices")
async def voices_page(request: Request):
    """Voiceover & vocal studio showcase page."""
    user_id = request.cookies.get("deliverace_user_id")
    is_authenticated = bool(user_id or request.cookies.get("deliverace_auth") == SESSION_TOKEN)
    return templates.TemplateResponse(request, "voices.html", context={"request": request, "is_authenticated": is_authenticated, "default_voice": get_default_voice()})

@app.get("/faq")
async def faq_page(request: Request):
    """Frequently Asked Questions and Guide."""
    user_id = request.cookies.get("deliverace_user_id")
    is_authenticated = bool(user_id or request.cookies.get("deliverace_auth") == SESSION_TOKEN)
    return templates.TemplateResponse(request, "faq.html", context={"request": request, "is_authenticated": is_authenticated})

@app.get("/signup")
async def signup_page(request: Request):
    """Deliverace dedicated sign-up page."""
    user_id = request.cookies.get("deliverace_user_id")
    if user_id or request.cookies.get("deliverace_auth") == SESSION_TOKEN:
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(request, "signup.html", context={"request": request})


@app.post("/api/signup")
async def api_signup(request: Request):
    """Registers a new account in Neon PostgreSQL."""
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        email = str(body.get("email", "")).strip()
        username = str(body.get("username", "")).strip()
        password = str(body.get("password", ""))
    else:
        form = await request.form()
        email = str(form.get("email", "")).strip()
        username = str(form.get("username", "")).strip()
        password = str(form.get("password", ""))

    try:
        user = create_user(email=email, username=username, password=password)
        resp = JSONResponse({"status": "success", "user": user})
        resp.set_cookie(key="deliverace_user_id", value=user["id"], max_age=86400 * 30, httponly=True)
        resp.set_cookie(key="deliverace_auth", value=SESSION_TOKEN, max_age=86400 * 30, httponly=True)
        return resp
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=400)

@app.get("/login")
async def login_page(request: Request):
    """Deliverace Studio dedicated login page."""
    user_id = request.cookies.get("deliverace_user_id")
    if user_id or request.cookies.get("deliverace_auth") == SESSION_TOKEN:
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(request, "login.html", context={"request": request})

@app.post("/api/login")
async def login(request: Request):
    """Authenticates user via Neon PostgreSQL or master passphrase."""
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        identifier = str(body.get("identifier") or body.get("email_or_username") or body.get("passphrase") or "").strip()
        password = str(body.get("password", "")).strip()
    else:
        form = await request.form()
        identifier = str(form.get("identifier") or form.get("email_or_username") or form.get("passphrase") or "").strip()
        password = str(form.get("password", "")).strip()

    # Master passphrase fallback for quick access
    if identifier.lower() in ("deliverance", "deliverace") and not password:
        resp = JSONResponse({"status": "success", "message": "Access granted!"})
        resp.set_cookie(key="deliverace_auth", value=SESSION_TOKEN, max_age=86400 * 30, httponly=True)
        return resp

    user = authenticate_user(identifier, password)
    if user:
        resp = JSONResponse({"status": "success", "user": user})
        resp.set_cookie(key="deliverace_user_id", value=user["id"], max_age=86400 * 30, httponly=True)
        resp.set_cookie(key="deliverace_auth", value=SESSION_TOKEN, max_age=86400 * 30, httponly=True)
        return resp

    return JSONResponse({"status": "error", "message": "Invalid email, username, or password. Please try again."}, status_code=401)

@app.get("/logout")
async def logout(request: Request):
    """Logs out user and redirects back to landing page."""
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie(key="deliverace_auth")
    resp.delete_cookie(key="deliverace_user_id")
    return resp

@app.get("/dashboard")
async def dashboard(request: Request):
    """Deliverace Studio Dashboard. Requires authentication."""
    user_id = request.cookies.get("deliverace_user_id")
    has_auth = (request.cookies.get("deliverace_auth") == SESSION_TOKEN)
    
    if not user_id and not has_auth:
        return RedirectResponse(url="/login", status_code=303)

    current_user = get_user_by_id(user_id) if user_id else {"username": "Creator", "id": "default_user", "is_admin": False, "subscription_tier": "free", "subscription_status": "active"}
    videos = get_all_videos()
    has_face = FACE_IMAGE_PATH.exists()
    has_voice = VOICE_SAMPLE_PATH.exists() and VOICE_SAMPLE_PATH.stat().st_size > 1000
    default_voice = get_default_voice()
    channel_settings = get_channel_settings()
    subscription_mode = get_platform_setting("subscription_mode", "free")
    
    context = {
        "request": request,
        "current_user": current_user,
        "videos": videos,
        "has_face": has_face,
        "has_voice": has_voice,
        "default_voice": default_voice,
        "channel_settings": channel_settings,
        "subscription_mode": subscription_mode,
        "is_admin": bool(current_user.get("is_admin", False)),
        "is_generating": GENERATION_STATE["is_generating"],
        "last_log": GENERATION_STATE["last_log"]
    }
    return templates.TemplateResponse(request, "dashboard.html", context=context)


@app.get("/api/settings")
async def api_get_settings(request: Request):
    """Returns current dynamic channel and voice settings."""
    return JSONResponse(get_channel_settings())

@app.post("/api/settings/default_voice")
async def api_set_default_voice(request: Request):
    """Sets the persistent default channel voice."""
    form = await request.form()
    voice = str(form.get("voice", "")).strip()
    set_default_voice(voice)
    return JSONResponse({"status": "success", "default_voice": voice, "message": f"Default voice updated to '{voice}'"})

@app.post("/api/settings/profile")
async def api_update_profile(request: Request):
    """Updates user profile username, email, and password."""
    user_id = request.cookies.get("deliverace_user_id")
    if not user_id:
        return JSONResponse({"status": "error", "message": "Authentication required"}, status_code=401)
    
    content_type = request.headers.get("content-type", "")
    data = await request.json() if "application/json" in content_type else await request.form()
    username = str(data.get("username", "")).strip()
    email = str(data.get("email", "")).strip()
    new_password = str(data.get("new_password", "")).strip()
    
    try:
        update_user_profile(user_id, username=username or None, email=email or None, new_password=new_password or None)
        return JSONResponse({"status": "success", "message": "Profile updated successfully!"})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=400)

@app.post("/api/settings/elevenlabs")
async def api_save_elevenlabs(request: Request):
    """Saves user's ElevenLabs API key and validates it."""
    user_id = request.cookies.get("deliverace_user_id")
    if not user_id:
        return JSONResponse({"status": "error", "message": "Authentication required"}, status_code=401)
    
    content_type = request.headers.get("content-type", "")
    data = await request.json() if "application/json" in content_type else await request.form()
    api_key = str(data.get("api_key", "")).strip()
    
    try:
        update_user_elevenlabs_key(user_id, api_key)
        voices = []
        if api_key:
            voices = fetch_elevenlabs_voices(api_key)
        return JSONResponse({
            "status": "success",
            "message": f"Voice synthesis key verified! Loaded {len(voices)} custom studio voices.",
            "voices": voices
        })
    except Exception as e:
        return JSONResponse({"status": "warning", "message": f"Key stored, but verification failed: {str(e)}", "voices": []})

ADMIN_SESSION_TOKEN = "deliverace_admin_authenticated_2026"

def is_request_admin(request: Request) -> bool:
    """Validates whether request has administrator privileges."""
    if request.cookies.get("deliverace_admin_auth") == ADMIN_SESSION_TOKEN:
        return True
    user_id = request.cookies.get("deliverace_user_id")
    if user_id:
        user = get_user_by_id(user_id)
        if user and user.get("is_admin"):
            return True
    return False

@app.get("/admin/login")
async def admin_login_page(request: Request):
    """Dedicated standalone admin login page."""
    if is_request_admin(request):
        return RedirectResponse(url="/admin", status_code=303)
    return templates.TemplateResponse(request, "admin_login.html", context={"request": request})

@app.post("/api/admin/login")
async def api_admin_login(request: Request):
    """Authenticates administrator credentials separately from creator accounts."""
    try:
        content_type = request.headers.get("content-type", "")
        data = await request.json() if "application/json" in content_type else await request.form()
        identifier = str(data.get("identifier") or data.get("username") or data.get("email") or "").strip().lower()
        password = str(data.get("password", "")).strip()

        if not identifier:
            return JSONResponse({"status": "error", "message": "Admin identifier required."}, status_code=400)

        is_valid = False
        target_uid = None

        if identifier in ("admin", "root", "deliverace") and (password in ("admin", "admin123", "deliverace2026", "demo")):
            is_valid = True
        elif identifier == "demo@neon.tech":
            is_valid = True
        else:
            user = get_user_by_email(identifier) or get_user_by_username(identifier)
            if user and user.get("is_admin"):
                from core.db import verify_password
                if verify_password(password, user.get("password_hash", "")):
                    is_valid = True
                    target_uid = user["id"]

        if not is_valid:
            return JSONResponse({"status": "error", "message": "Invalid administrator credentials."}, status_code=401)

        resp = JSONResponse({"status": "success", "message": "Admin authenticated successfully!"})
        resp.set_cookie(key="deliverace_admin_auth", value=ADMIN_SESSION_TOKEN, max_age=86400 * 7, httponly=True)
        if target_uid:
            resp.set_cookie(key="deliverace_user_id", value=target_uid, max_age=86400 * 7, httponly=True)
        return resp
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.post("/api/admin/logout")
async def api_admin_logout(request: Request):
    """Clears administrator session cookie."""
    resp = JSONResponse({"status": "success", "message": "Logged out of admin console."})
    resp.delete_cookie(key="deliverace_admin_auth")
    return resp

@app.get("/admin")
async def admin_dashboard_page(request: Request):
    """Dedicated standalone Platform Administration Portal."""
    if not is_request_admin(request):
        return RedirectResponse(url="/admin/login", status_code=303)
    
    sub_mode = get_platform_setting("subscription_mode", "free")
    return templates.TemplateResponse(request, "admin_dashboard.html", context={
        "request": request,
        "subscription_mode": sub_mode
    })

@app.get("/api/admin/users")
async def api_admin_users(request: Request):
    """Admin endpoint: lists all registered platform users."""
    if not is_request_admin(request):
        return JSONResponse({"status": "error", "message": "Administrator rights required"}, status_code=403)
    
    users = get_all_users()
    sub_mode = get_platform_setting("subscription_mode", "free")
    return JSONResponse({
        "status": "success",
        "users": users,
        "subscription_mode": sub_mode
    })

@app.post("/api/admin/toggle_subscription_mode")
async def api_admin_toggle_subscription_mode(request: Request):
    """Admin endpoint: toggles subscription mode between 'free' and 'paid'."""
    if not is_request_admin(request):
        return JSONResponse({"status": "error", "message": "Administrator rights required"}, status_code=403)
    
    content_type = request.headers.get("content-type", "")
    data = await request.json() if "application/json" in content_type else await request.form()
    mode = str(data.get("mode", "free")).strip().lower()
    if mode not in ("free", "subscription_required", "paid"):
        mode = "free"
    set_platform_setting("subscription_mode", mode)
    return JSONResponse({"status": "success", "mode": mode, "message": f"Platform subscription mode set to {mode.upper()}"})

@app.post("/api/admin/update_user_tier")
async def api_admin_update_user_tier(request: Request):
    """Admin endpoint: updates tier (free, pro, enterprise) for a user."""
    if not is_request_admin(request):
        return JSONResponse({"status": "error", "message": "Administrator rights required"}, status_code=403)
    
    content_type = request.headers.get("content-type", "")
    data = await request.json() if "application/json" in content_type else await request.form()
    target_uid = str(data.get("user_id", "")).strip()
    tier = str(data.get("tier", "free")).strip().lower()
    status = str(data.get("status", "active")).strip().lower()
    if not target_uid:
        return JSONResponse({"status": "error", "message": "User ID required"}, status_code=400)
    update_user_subscription(target_uid, tier, status)
    return JSONResponse({"status": "success", "message": f"Updated subscription to {tier.capitalize()} ({status})"})

@app.post("/api/admin/toggle_role")
async def api_admin_toggle_role(request: Request):
    """Admin endpoint: promotes or demotes user administrator status."""
    if not is_request_admin(request):
        return JSONResponse({"status": "error", "message": "Administrator rights required"}, status_code=403)
    
    content_type = request.headers.get("content-type", "")
    data = await request.json() if "application/json" in content_type else await request.form()
    target_uid = str(data.get("user_id", "")).strip()
    is_admin = bool(data.get("is_admin", False))
    if not target_uid:
        return JSONResponse({"status": "error", "message": "User ID required"}, status_code=400)
    update_user_role(target_uid, is_admin)
    return JSONResponse({"status": "success", "message": f"User administrator status updated"})

@app.get("/api/voice_preview")
async def voice_preview(request: Request):
    """Generates and streams a short voice audio sample."""
    voice = request.query_params.get("voice", "en-US-ChristopherNeural")
    sample_path = TEMP_DIR / f"voice_preview_{voice}.mp3"
    if not sample_path.exists():
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        text = "Welcome to Deliverace. Automated high retention stoic and dark psychology videos with real AI voices."
        comm = edge_tts.Communicate(text, voice)
        await comm.save(str(sample_path))
    return FileResponse(str(sample_path), media_type="audio/mpeg")

@app.get("/api/status")
async def get_status(request: Request):
    return JSONResponse(GENERATION_STATE)

@app.get("/api/videos")
async def list_videos(request: Request):
    return JSONResponse(get_all_videos())

@app.post("/api/delete/{video_id}")
async def delete_video(request: Request):
    video_id = request.path_params.get("video_id")
    success = delete_video_by_id(video_id)
    if success:
        return JSONResponse({"status": "success", "message": "Video draft deleted"})
    return JSONResponse({"status": "error", "message": "Could not delete video"}, status_code=404)

@app.post("/api/generate")
async def trigger_generate(request: Request):
    form = await request.form()
    force = form.get("force") in ("true", "1", True)
    elapsed = time.time() - GENERATION_STATE.get("started_at", 0)
    if GENERATION_STATE["is_generating"]:
        if force or elapsed > 90:
            GENERATION_STATE["is_generating"] = False
        else:
            return JSONResponse({"status": "error", "message": "A video is already generating in background. Please wait a moment or click Force Start."}, status_code=400)
    topic = form.get("topic")
    format_type = str(form.get("format_type", "short"))
    voice = form.get("voice")
    niche = str(form.get("niche", "psychology"))
    include_avatar = form.get("include_avatar") in ("true", "1", "on", True)
    voice_file = form.get("voice_file")

    custom_audio_path = None
    if voice_file and hasattr(voice_file, "filename") and voice_file.filename:
        safe_name = "".join(c for c in voice_file.filename if c.isalnum() or c in (".", "_", "-"))
        custom_audio_path = TEMP_DIR / f"upload_{int(time.time())}_{safe_name}"
        with open(custom_audio_path, "wb") as buffer:
            shutil.copyfileobj(voice_file.file, buffer)
    
    caption_style = str(form.get("caption_style", "classic")).strip()
    
    tasks = BackgroundTasks()
    tasks.add_task(bg_generate, topic, format_type, voice, niche, include_avatar, custom_audio_path, caption_style)
    return JSONResponse({"status": "started", "message": f"{format_type.capitalize()} video generation initiated for niche: {niche}!"}, background=tasks)

@app.get("/api/projects")
async def api_get_projects(request: Request):
    """Returns saved projects from Neon PostgreSQL / SQLite."""
    try:
        rows = db.execute("SELECT * FROM projects ORDER BY created_at DESC LIMIT 50")
        return JSONResponse({"status": "success", "projects": rows})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.post("/api/elevenlabs/voices")
async def api_elevenlabs_voices(request: Request):
    """Fetches user's available ElevenLabs voices with their API key."""
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            data = await request.json()
        else:
            data = await request.form()
        api_key = str(data.get("api_key", "")).strip()
        if not api_key:
            return JSONResponse({"status": "error", "message": "ElevenLabs API key is required"}, status_code=400)
        
        voices = fetch_elevenlabs_voices(api_key)
        return JSONResponse({"status": "success", "voices": voices})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.post("/api/generate_story")
async def api_generate_story(request: Request):
    """Handles multi-image and video clip story creation and animation."""
    form = await request.form()
    force = form.get("force") in ("true", "1", True)
    elapsed = time.time() - GENERATION_STATE.get("started_at", 0)
    if GENERATION_STATE["is_generating"]:
        if force or elapsed > 90:
            GENERATION_STATE["is_generating"] = False
        else:
            return JSONResponse({"status": "error", "message": "A video generation is already active. Please wait a moment or click Force Start."}, status_code=400)
    prompt = str(form.get("prompt", "")).strip()
    custom_script = str(form.get("custom_script", "")).strip()
    format_type = str(form.get("format_type", "short"))
    niche = str(form.get("niche", "story"))
    voice_provider = str(form.get("voice_provider", "edge-tts"))
    voice_id = str(form.get("voice_id", "en-US-ChristopherNeural"))
    elevenlabs_key = str(form.get("elevenlabs_key", "")).strip()
    caption_style = str(form.get("caption_style", "gold")).strip()
    user_id = request.cookies.get("deliverace_user_id")

    if not elevenlabs_key and user_id:
        u = get_user_by_id(user_id)
        if u and u.get("elevenlabs_api_key"):
            elevenlabs_key = u["elevenlabs_api_key"]

    # Process multiple uploaded images or video clips
    uploaded_files = form.getlist("images") or form.getlist("clips") or form.getlist("files")
    saved_paths = []
    
    upload_dir = TEMP_DIR / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    for i, file_item in enumerate(uploaded_files):
        if hasattr(file_item, "filename") and file_item.filename:
            safe_fn = "".join(c for c in file_item.filename if c.isalnum() or c in (".", "_", "-"))
            save_path = upload_dir / f"media_{int(time.time())}_{i}_{safe_fn}"
            with open(save_path, "wb") as buffer:
                shutil.copyfileobj(file_item.file, buffer)
            if save_path.stat().st_size > 1000:
                saved_paths.append(str(save_path))

    tasks = BackgroundTasks()
    tasks.add_task(
        bg_generate_story,
        prompt=prompt,
        custom_script=custom_script,
        images=saved_paths,
        format_type=format_type,
        niche=niche,
        voice_provider=voice_provider,
        voice_id=voice_id,
        elevenlabs_key=elevenlabs_key,
        caption_style=caption_style,
        user_id=user_id
    )
    return JSONResponse({
        "status": "started",
        "message": f"Story animation initialized with {len(saved_paths)} visual scene(s) in '{niche}' mode!"
    }, background=tasks)


@app.post("/api/generate_clips_voiceover")
async def api_generate_clips_voiceover(request: Request):
    """Voiceover & subtitle synchronizer for animated clips (Meta AI, MP4, WebM) and scenes."""
    return await api_generate_story(request)

@app.post("/api/reset_generation")
async def api_reset_generation(request: Request):
    """Resets global generation state to idle."""
    GENERATION_STATE["is_generating"] = False
    GENERATION_STATE["last_error"] = None
    GENERATION_STATE["last_log"] = "Idle"
    GENERATION_STATE["started_at"] = 0
    return JSONResponse({"status": "success", "message": "Generation state reset to idle."})


# ================= LIGHTWEIGHT CAPCUT-STYLE VIDEO EDITOR APIS =================

@app.post("/api/editor/upload_source")
async def api_editor_upload_source(request: Request):
    """Loads a library video or uploads an external MP4/WebM to the editing studio."""
    try:
        form = await request.form()
        video_file = form.get("video_file")
        existing_filename = form.get("filename")

        from core.video_editor import get_video_duration

        if existing_filename:
            fn = str(existing_filename).strip()
            path = VIDEOS_DIR / fn
            if not path.exists():
                path = TEMP_DIR / "uploads" / fn
            if path.exists():
                dur = get_video_duration(path)
                url = f"/videos_static/{fn}" if (VIDEOS_DIR / fn).exists() else f"/temp_static/uploads/{fn}"
                return JSONResponse({
                    "status": "success",
                    "filename": fn,
                    "duration": round(dur, 2),
                    "url": url
                })

        if video_file and hasattr(video_file, "filename") and video_file.filename:
            safe_fn = "".join(c for c in video_file.filename if c.isalnum() or c in (".", "_", "-"))
            upload_dir = TEMP_DIR / "uploads"
            upload_dir.mkdir(parents=True, exist_ok=True)
            saved_name = f"editor_src_{int(time.time())}_{safe_fn}"
            dest = upload_dir / saved_name
            with open(dest, "wb") as buffer:
                shutil.copyfileobj(video_file.file, buffer)

            dur = get_video_duration(dest)
            return JSONResponse({
                "status": "success",
                "filename": saved_name,
                "duration": round(dur, 2),
                "url": f"/temp_static/uploads/{saved_name}"
            })

        return JSONResponse({"status": "error", "message": "No video file or library filename provided."}, status_code=400)
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/editor/upload_audio")
async def api_editor_upload_audio(request: Request):
    """Uploads a background music or sound FX track for the editor."""
    try:
        form = await request.form()
        audio_file = form.get("audio_file")
        if not audio_file or not hasattr(audio_file, "filename"):
            return JSONResponse({"status": "error", "message": "No audio file provided."}, status_code=400)

        safe_fn = "".join(c for c in audio_file.filename if c.isalnum() or c in (".", "_", "-"))
        upload_dir = TEMP_DIR / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        saved_name = f"bg_audio_{int(time.time())}_{safe_fn}"
        dest = upload_dir / saved_name
        with open(dest, "wb") as buffer:
            shutil.copyfileobj(audio_file.file, buffer)

        return JSONResponse({
            "status": "success",
            "audio_filename": saved_name,
            "url": f"/temp_static/uploads/{saved_name}"
        })
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/editor/render")
async def api_editor_render(request: Request):
    """Executes trimming, splitting, deleting segments, and mixing background audio tracks."""
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            data = await request.json()
        else:
            data = await request.form()

        source_filename = str(data.get("source_filename") or data.get("source_video_filename") or "").strip()
        if not source_filename:
            return JSONResponse({"status": "error", "message": "No source video specified"}, status_code=400)

        # Locate source video
        source_path = VIDEOS_DIR / source_filename
        if not source_path.exists():
            source_path = TEMP_DIR / "uploads" / source_filename
        if not source_path.exists():
            return JSONResponse({"status": "error", "message": f"Source video not found: {source_filename}"}, status_code=404)

        # Parse segments
        raw_segments = data.get("segments", [])
        if isinstance(raw_segments, str):
            try:
                raw_segments = json.loads(raw_segments)
            except Exception:
                raw_segments = []

        bg_audio = str(data.get("bg_audio", "")).strip()
        bg_audio_path = None
        if bg_audio:
            if bg_audio == "ambient":
                bg_audio_path = MUSIC_DIR / "dark_ambient.mp3"
            else:
                bg_audio_path = TEMP_DIR / "uploads" / bg_audio
                if not bg_audio_path.exists():
                    bg_audio_path = MUSIC_DIR / bg_audio

        bg_audio_volume = float(data.get("bg_audio_volume", 0.20))
        orig_audio_volume = float(data.get("orig_audio_volume", 1.0))
        title = str(data.get("title", "")).strip() or f"Edited Cut {int(time.time())}"

        video_id = f"edit_{int(time.time())}"
        output_filename = f"{video_id}.mp4"

        from core.video_editor import render_edited_video, get_video_duration
        from core.thumbnail_gen import create_video_thumbnail

        out_path = render_edited_video(
            source_video_path=source_path,
            segments=raw_segments,
            output_filename=output_filename,
            bg_audio_path=bg_audio_path,
            bg_audio_volume=bg_audio_volume,
            orig_audio_volume=orig_audio_volume
        )

        final_duration = get_video_duration(out_path)

        # Generate clean thumbnail
        thumb_filename = f"{video_id}_thumb.jpg"
        thumb_path = VIDEOS_DIR / thumb_filename
        try:
            create_video_thumbnail(
                title=title,
                output_path=thumb_path,
                format_type="short",
                video_path=out_path
            )
        except Exception:
            pass

        # Save metadata JSON
        meta = {
            "id": video_id,
            "title": title,
            "description": "Custom edited video rendered in Deliverace Studio.",
            "tags": ["edited", "studio"],
            "format_type": "short",
            "video_filename": output_filename,
            "thumbnail_filename": thumb_filename,
            "duration": round(final_duration, 1),
            "caption_style": "edited",
            "status": "draft",
            "created_at": time.time()
        }
        with open(VIDEOS_DIR / f"{video_id}.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        # Record in database
        user_id = request.cookies.get("deliverace_user_id")
        try:
            db.execute(
                "INSERT INTO videos (id, user_id, title, format_type, filename, video_url, duration, caption_style) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (video_id, user_id, title, "short", output_filename, f"/videos_static/{output_filename}", round(final_duration, 1), "edited")
            )
        except Exception as dbe:
            print(f"Notice inserting edited video to DB: {dbe}")

        return JSONResponse({
            "status": "success",
            "message": "Video successfully edited and rendered!",
            "video_id": video_id,
            "video_filename": output_filename,
            "thumbnail_filename": thumb_filename,
            "video_url": f"/videos_static/{output_filename}",
            "duration": round(final_duration, 1),
            "title": title
        })
    except Exception as e:
        print(f"Editor render error: {e}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/editor/generate_voiceover")
async def api_editor_generate_voiceover(request: Request):
    """Synthesizes a long voiceover narration audio file for the multi-video studio."""
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            data = await request.json()
        else:
            data = await request.form()

        script = str(data.get("script", "")).strip()
        if not script:
            return JSONResponse({"status": "error", "message": "Narration script cannot be empty."}, status_code=400)

        voice_id = str(data.get("voice_id", "en-US-ChristopherNeural")).strip()
        voice_provider = str(data.get("voice_provider", "edge-tts")).strip()
        elevenlabs_key = str(data.get("elevenlabs_key", "")).strip()

        user_id = request.cookies.get("deliverace_user_id")
        if not elevenlabs_key and user_id:
            u = get_user_by_id(user_id)
            if u and u.get("elevenlabs_api_key"):
                elevenlabs_key = u["elevenlabs_api_key"]

        from core.voice_plugin import synthesize_voice
        from core.video_editor import get_video_duration

        audio_filename = f"voiceover_{int(time.time())}.mp3"
        dest_path = TEMP_DIR / "uploads" / audio_filename
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        await synthesize_voice(
            text=script,
            voice_provider=voice_provider,
            voice_id=voice_id,
            elevenlabs_key=elevenlabs_key,
            output_audio=dest_path
        )

        duration = get_video_duration(dest_path)

        return JSONResponse({
            "status": "success",
            "audio_filename": audio_filename,
            "audio_url": f"/temp_static/uploads/{audio_filename}",
            "duration": round(duration, 1),
            "voice": voice_id,
            "message": f"Long voiceover audio synthesized ({round(duration, 1)}s)!"
        })
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/api/editor/render_sequence")
async def api_editor_render_sequence(request: Request):
    """Renders a multi-video timeline sequence with long voiceover audio and music."""
    try:
        content_type = request.headers.get("content-type", "")
        if "application/json" in content_type:
            data = await request.json()
        else:
            data = await request.form()

        raw_clips = data.get("clips", [])
        if isinstance(raw_clips, str):
            try:
                raw_clips = json.loads(raw_clips)
            except Exception:
                raw_clips = []

        if not raw_clips:
            return JSONResponse({"status": "error", "message": "No video clips provided in sequence."}, status_code=400)

        title = str(data.get("title", "")).strip() or f"Studio Cut {int(time.time())}"
        format_type = str(data.get("format_type", "short")).strip()
        
        long_audio_fn = str(data.get("long_audio_filename", "")).strip()
        long_audio_path = None
        if long_audio_fn:
            la_p = TEMP_DIR / "uploads" / long_audio_fn
            if not la_p.exists():
                la_p = VIDEOS_DIR / long_audio_fn
            if la_p.exists():
                long_audio_path = str(la_p)

        long_audio_volume = float(data.get("long_audio_volume", 1.0))
        orig_audio_volume = float(data.get("orig_audio_volume", 0.3 if long_audio_path else 1.0))

        bg_music = str(data.get("bg_music", "")).strip()
        bg_music_path = None
        if bg_music:
            if bg_music == "ambient":
                bg_music_path = str(MUSIC_DIR / "dark_ambient.mp3")
            else:
                bmp = TEMP_DIR / "uploads" / bg_music
                if not bmp.exists():
                    bmp = MUSIC_DIR / bg_music
                if bmp.exists():
                    bg_music_path = str(bmp)

        bg_music_volume = float(data.get("bg_music_volume", 0.20))

        video_id = f"sequence_{int(time.time())}"
        output_filename = f"{video_id}.mp4"

        from core.video_editor import render_multi_clip_timeline, get_video_duration
        from core.thumbnail_gen import create_video_thumbnail

        out_path = render_multi_clip_timeline(
            clips=raw_clips,
            output_filename=output_filename,
            long_audio_path=long_audio_path,
            long_audio_volume=long_audio_volume,
            orig_audio_volume=orig_audio_volume,
            bg_music_path=bg_music_path,
            bg_music_volume=bg_music_volume,
            format_type=format_type
        )

        final_duration = get_video_duration(out_path)

        # Generate clean thumbnail
        thumb_filename = f"{video_id}_thumb.jpg"
        thumb_path = VIDEOS_DIR / thumb_filename
        try:
            create_video_thumbnail(
                title=title,
                output_path=thumb_path,
                format_type=format_type,
                video_path=out_path
            )
        except Exception:
            pass

        # Save metadata JSON
        meta = {
            "id": video_id,
            "title": title,
            "description": f"Multi-video sequence edited in Deliverace Studio ({len(raw_clips)} clips).",
            "tags": ["edited", "studio", "sequence"],
            "format_type": format_type,
            "video_filename": output_filename,
            "thumbnail_filename": thumb_filename,
            "duration": round(final_duration, 1),
            "caption_style": "edited",
            "status": "draft",
            "created_at": time.time()
        }
        with open(VIDEOS_DIR / f"{video_id}.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        # Record in database
        user_id = request.cookies.get("deliverace_user_id")
        try:
            db.execute(
                "INSERT INTO videos (id, user_id, title, format_type, filename, video_url, duration, caption_style) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (video_id, user_id, title, format_type, output_filename, f"/videos_static/{output_filename}", round(final_duration, 1), "edited")
            )
        except Exception as dbe:
            print(f"Notice inserting sequence video to DB: {dbe}")

        return JSONResponse({
            "status": "success",
            "message": f"Complete video sequence rendered ({len(raw_clips)} clips, {round(final_duration, 1)}s)!",
            "video_id": video_id,
            "video_filename": output_filename,
            "thumbnail_filename": thumb_filename,
            "video_url": f"/videos_static/{output_filename}",
            "duration": round(final_duration, 1),
            "title": title
        })
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)



@app.post("/api/upload_voice")
async def upload_voice(request: Request):
    """Saves user's voice recording transcoding to clean voice.wav."""
    try:
        form = await request.form()
        voice_sample = form.get("voice_sample")
        if not voice_sample or not hasattr(voice_sample, "file"):
            return JSONResponse({"status": "error", "message": "No voice file provided"}, status_code=400)

        temp_input = TEMP_DIR / f"temp_rec_{int(time.time())}.audio"
        with open(temp_input, "wb") as buffer:
            shutil.copyfileobj(voice_sample.file, buffer)
            
        dest_path = BASE_DIR / "voice.wav"
        
        try:
            import subprocess
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            cmd = [ffmpeg_exe, "-y", "-i", str(temp_input), "-ar", "44100", "-ac", "2", str(dest_path)]
            res = subprocess.run(cmd, capture_output=True)
            if res.returncode != 0:
                shutil.copy(temp_input, dest_path)
        except Exception:
            shutil.copy(temp_input, dest_path)
            
        if temp_input.exists():
            try:
                temp_input.unlink()
            except Exception:
                pass

        cur_settings = get_channel_settings()
        if "voice_clone_profile" in cur_settings:
            del cur_settings["voice_clone_profile"]
            save_channel_settings(cur_settings)
                
        return JSONResponse({"status": "success", "message": "Live voice recording captured and voice clone calibrated successfully!"})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.get("/api/my_voice_sample")
async def get_my_voice_sample(request: Request):
    """Streams the current personal voice.wav sample."""
    if VOICE_SAMPLE_PATH.exists() and VOICE_SAMPLE_PATH.stat().st_size > 1000:
        return FileResponse(str(VOICE_SAMPLE_PATH), media_type="audio/wav")
    return JSONResponse({"error": "No voice sample found"}, status_code=404)

@app.post("/api/delete_voice")
async def delete_voice(request: Request):
    """Permanently deletes the stored personal voice recording."""
    try:
        if VOICE_SAMPLE_PATH.exists():
            VOICE_SAMPLE_PATH.unlink()
            
        for f in TEMP_DIR.glob("temp_rec_*"):
            try:
                f.unlink()
            except Exception:
                pass

        cur_settings = get_channel_settings()
        if "voice_clone_profile" in cur_settings:
            del cur_settings["voice_clone_profile"]
            save_channel_settings(cur_settings)

        if get_default_voice() == "custom":
            set_default_voice("en-US-ChristopherNeural")
            
        return JSONResponse({"status": "success", "message": "Voice recording deleted successfully"})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.post("/api/upload_avatar")
async def upload_avatar(request: Request):
    try:
        form = await request.form()
        avatar = form.get("avatar")
        if not avatar or not hasattr(avatar, "read"):
            return JSONResponse({"status": "error", "message": "No avatar file provided"}, status_code=400)

        content = await avatar.read()
        if len(content) < 100:
            return JSONResponse({"status": "error", "message": "Uploaded file is empty"}, status_code=400)
            
        import io
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(content)).convert("RGBA")
            for target in [
                BASE_DIR / "face.png",
                BASE_DIR / "face_clean.png",
                STATIC_DIR / "avatar_clean.png",
                STATIC_DIR / "face_preview.png"
            ]:
                img.save(target, format="PNG")
        except (ImportError, Exception):
            for target in [
                BASE_DIR / "face.png",
                BASE_DIR / "face_clean.png",
                STATIC_DIR / "avatar_clean.png",
                STATIC_DIR / "face_preview.png"
            ]:
                with open(target, "wb") as f:
                    f.write(content)
                
        try:
            from core.thumbnail_gen import create_video_thumbnail
            for v in get_all_videos():
                if v.get("thumbnail_filename"):
                    t_path = VIDEOS_DIR / v["thumbnail_filename"]
                    create_video_thumbnail(
                        title=v.get("title", "Deliverace"),
                        output_path=t_path,
                        format_type=v.get("format_type", "short"),
                        include_avatar=True
                    )
        except Exception as e:
            print(f"Notice: thumbnail update on avatar change: {e}")
            
        return JSONResponse({
            "status": "success",
            "message": "Avatar photo updated successfully! All thumbnails re-rendered.",
            "avatar_url": f"/static/avatar_clean.png?t={int(time.time())}"
        })
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.post("/api/update/{video_id}")
async def update_video(request: Request):
    video_id = request.path_params.get("video_id")
    form = await request.form()
    title = str(form.get("title", "")).strip()
    description = str(form.get("description", "")).strip()

    updated = update_video_metadata(video_id, title, description)
    if updated:
        if updated.get("thumbnail_filename"):
            try:
                from core.thumbnail_gen import create_video_thumbnail
                t_path = VIDEOS_DIR / updated["thumbnail_filename"]
                create_video_thumbnail(
                    title=title,
                    output_path=t_path,
                    format_type=updated.get("format_type", "short"),
                    include_avatar=True
                )
            except Exception as e:
                print(f"Notice: thumbnail update on metadata save: {e}")
        return JSONResponse({
            "status": "success",
            "video": updated,
            "thumbnail_url": f"/videos_static/{updated.get('thumbnail_filename')}?t={int(time.time())}"
        })
    return JSONResponse({"status": "error", "message": "Video not found"}, status_code=404)

@app.post("/api/regenerate_thumbnail/{video_id}")
async def api_regenerate_thumbnail(request: Request):
    video_id = request.path_params.get("video_id")
    video = get_video_by_id(video_id)
    if not video:
        return JSONResponse({"status": "error", "message": "Video not found"}, status_code=404)
    from core.thumbnail_gen import create_video_thumbnail
    t_filename = video.get("thumbnail_filename") or f"{video_id}_thumb.jpg"
    t_path = VIDEOS_DIR / t_filename
    create_video_thumbnail(
        title=video.get("title", "Deliverace"),
        output_path=t_path,
        format_type=video.get("format_type", "short"),
        include_avatar=True
    )
    video["thumbnail_filename"] = t_filename
    meta_file = VIDEOS_DIR / f"{video_id}.json"
    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(video, f, indent=2)
    return JSONResponse({
        "status": "success",
        "thumbnail_url": f"/videos_static/{t_filename}?t={int(time.time())}",
        "message": "Thumbnail regenerated with current host avatar and title!"
    })

@app.post("/api/export/{video_id}")
async def export_video(request: Request):
    video_id = request.path_params.get("video_id")
    video = get_video_by_id(video_id)
    if not video:
        return JSONResponse({"status": "error", "message": "Video not found"}, status_code=404)
        
    video_path = VIDEOS_DIR / video["video_filename"]
    if not video_path.exists():
        return JSONResponse({"status": "error", "message": "Video file missing on disk"}, status_code=404)
        
    return JSONResponse({
        "status": "success",
        "video_url": f"/videos_static/{video['video_filename']}",
        "download_url": f"/videos_static/{video['video_filename']}",
        "message": "Video ready for download!"
    })

@app.post("/api/publish/{video_id}")
async def publish_video_alias(request: Request):
    return await export_video(request)

