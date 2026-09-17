import sys
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

import os
import subprocess
import requests
from io import BytesIO
from pathlib import Path
from core.config import VIDEOS_DIR, FACE_IMAGE_PATH, BASE_DIR

PIL_AVAILABLE = False
try:
    from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageChops
    PIL_AVAILABLE = True
except (ImportError, Exception):
    PIL_AVAILABLE = False

def extract_topic_tag(title: str) -> str:
    """Extracts a high-impact, topic-relevant category tag for the thumbnail badge."""
    t = title.lower()
    if any(k in t for k in ["ai", "tech", "singularity", "robot", "neuralink", "quantum", "chip", "gpt", "model"]):
        return "FUTURE TECH & AI"
    elif any(k in t for k in ["stoic", "stoicism", "calm", "silence", "peace"]):
        return "STOIC PHILOSOPHY"
    elif any(k in t for k in ["psychology", "manipulat", "dark", "predator", "sovereign"]):
        return "DARK PSYCHOLOGY"
    elif any(k in t for k in ["mindset", "discipline", "focus", "habit", "mind"]):
        return "UNBREAKABLE MINDSET"
    elif any(k in t for k in ["money", "wealth", "rich", "escape", "income", "profit"]):
        return "WEALTH & FREEDOM"
    elif any(k in t for k in ["power", "control", "destiny", "apex", "rule"]):
        return "POWER & DESTINY"
    else:
        words = [w for w in title.replace("#shorts", "").split() if len(w) > 2]
        if words:
            return " ".join(words[:2]).upper()
        return "INSIGHT & STRATEGY"

def fetch_watermark_free_background(topic_or_title: str, width: int, height: int, is_long: bool, niche: str = "psychology"):
    """
    Creates a 100% watermark-free, clean, cinematic dark studio lighting background.
    - Tech niche: Deep electric cyan, obsidian teal, neon blue server matrix tones.
    - Psychology niche: Deep crimson, moody slate, gold rim ambient depth.
    """
    is_tech = (niche.lower() == "tech") or any(k in topic_or_title.lower() for k in ["ai", "tech", "singularity", "robot", "quantum", "chip"])

    if is_tech:
        # Deep obsidian cyberpunk cyan palette
        bg = Image.new("RGB", (width, height), (3, 8, 16))
        draw = ImageDraw.Draw(bg)
        for y in range(height):
            r = int(2 + (y / height) * 6)
            g = int(8 + (y / height) * 22)
            b = int(18 + (y / height) * 45)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        spotlight = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        sdraw = ImageDraw.Draw(spotlight)
        if is_long:
            sdraw.ellipse([int(width * 0.2), 30, int(width * 0.7), height - 30], fill=(0, 220, 255, 55))
            sdraw.ellipse([int(width * 0.6), 80, width + 120, height], fill=(0, 140, 255, 40))
        else:
            sdraw.ellipse([80, int(height * 0.18), width - 80, int(height * 0.72)], fill=(0, 220, 255, 50))
            sdraw.ellipse([160, int(height * 0.45), width + 100, height], fill=(0, 150, 255, 35))
    else:
        # Moody dark stoic / psychology crimson palette
        bg = Image.new("RGB", (width, height), (7, 4, 10))
        draw = ImageDraw.Draw(bg)
        for y in range(height):
            r = int(7 + (y / height) * 26)
            g = int(4 + (y / height) * 10)
            b = int(10 + (y / height) * 20)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        spotlight = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        sdraw = ImageDraw.Draw(spotlight)
        if is_long:
            sdraw.ellipse([int(width * 0.22), 40, int(width * 0.65), height - 40], fill=(225, 29, 72, 45))
            sdraw.ellipse([int(width * 0.65), 100, width + 100, height], fill=(245, 158, 11, 35))
        else:
            sdraw.ellipse([100, int(height * 0.2), width - 100, int(height * 0.7)], fill=(225, 29, 72, 40))
            sdraw.ellipse([200, int(height * 0.5), width + 100, height], fill=(245, 158, 11, 30))

    spotlight = spotlight.filter(ImageFilter.GaussianBlur(80 if is_long else 100))
    bg = Image.alpha_composite(bg.convert("RGBA"), spotlight).convert("RGB")
    return bg

def fetch_topic_watermark_element(topic_or_title: str):
    """
    Fetches a high-CTR, topic-relevant iconic visual element from Pexels or cache
    (e.g., Microchip AI processor, Roman marble bust, chess king, human skull).
    Processes it into a semi-transparent, luminous atmospheric watermark element for the thumbnail background.
    """
    t = topic_or_title.lower()

    # Check local high-quality cache first for instant reliability
    cache_dir = BASE_DIR / "storage" / "thumbnails_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    preferred_cache = None
    if any(k in t for k in ["ai", "tech", "singularity", "robot", "neuralink", "quantum", "chip", "gpt", "model", "cyber"]):
        preferred_cache = cache_dir / "elem_tech.png"
    elif any(k in t for k in ["stoic", "stoicism", "marcus", "philosophy", "calm", "silence", "destiny"]):
        preferred_cache = cache_dir / "elem_stoic.png"
    elif any(k in t for k in ["psychology", "dark", "manipulat", "mind", "brain", "predator", "sovereign"]):
        preferred_cache = cache_dir / "elem_chess.png" if (cache_dir / "elem_chess.png").exists() else (cache_dir / "elem_stoic.png")
    elif any(k in t for k in ["power", "control", "apex", "rule", "king"]):
        preferred_cache = cache_dir / "elem_chess.png"

    if preferred_cache and preferred_cache.exists():
        try:
            return Image.open(preferred_cache).convert("RGBA")
        except Exception:
            pass

    # Fallback to stoic bust or chess piece
    for fallback_name in ["elem_tech.png", "elem_stoic.png", "elem_chess.png"]:
        fb = cache_dir / fallback_name
        if fb.exists():
            try:
                return Image.open(fb).convert("RGBA")
            except Exception:
                pass
    return None

def _create_pil_thumbnail(
    title: str,
    output_path: Path,
    format_type: str = "short",
    include_avatar: bool = False,
    niche: str = "psychology"
) -> Path:
    """
    Generates a clean, professional, high-CTR YouTube thumbnail:
    - 100% Watermark-Free cinematic atmospheric studio background
    - Niche-aware visual themes:
      * Tech: Cyan/neon accents, glowing microchip/AI neural background, electric cyan pill badge
      * Psychology: Crimson/gold accents, moody marble statue/chess background, crimson pill badge
    - Natural PNG host overlay standing naturally (no artificial circles or hoops)
    - Dynamic topic-specific pill badge
    - Crisp dual-tone Impact typography (White + Gold/Cyan with 3D drop shadow)
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    is_long = (format_type == "long")
    w, h = (1280, 720) if is_long else (1080, 1920)

    # 1. Background image (Clean, rich studio lighting tailored to niche)
    raw_bg = fetch_watermark_free_background(title, w, h, is_long, niche=niche)
    thumb = raw_bg.convert("RGBA")

    # 2. Transparent topic-related visual element in background
    topic_elem = fetch_topic_watermark_element(title)
    if topic_elem:
        try:
            if is_long:
                # Target majestic scale: ~98% of height, positioned between text and avatar
                target_h = int(h * 0.98)
                aspect = topic_elem.width / topic_elem.height
                target_w = int(target_h * aspect)
                scaled_elem = topic_elem.resize((target_w, target_h), Image.Resampling.LANCZOS)
                
                # Positioned slightly left of center so it bridges behind the title and host
                elem_x = int(w * 0.26)
                elem_y = h - target_h + 10

                # Ambient back-light behind the element for depth
                elem_glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                gdraw = ImageDraw.Draw(elem_glow)
                gdraw.ellipse([elem_x - 30, elem_y + 40, elem_x + target_w + 30, elem_y + target_h], fill=(0, 190, 255, 38))
                elem_glow = elem_glow.filter(ImageFilter.GaussianBlur(50))
                thumb = Image.alpha_composite(thumb, elem_glow)

                thumb.paste(scaled_elem, (elem_x, elem_y), scaled_elem)
            else:
                # Vertical Shorts: Positioned prominently in upper-center
                target_w = int(w * 0.85)
                aspect = topic_elem.height / topic_elem.width
                target_h = int(target_w * aspect)
                scaled_elem = topic_elem.resize((target_w, target_h), Image.Resampling.LANCZOS)
                elem_x = (w - target_w) // 2
                elem_y = int(h * 0.18)

                elem_glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                gdraw = ImageDraw.Draw(elem_glow)
                gdraw.ellipse([elem_x - 40, elem_y + 40, elem_x + target_w + 40, elem_y + target_h], fill=(0, 190, 255, 35))
                elem_glow = elem_glow.filter(ImageFilter.GaussianBlur(60))
                thumb = Image.alpha_composite(thumb, elem_glow)

                thumb.paste(scaled_elem, (elem_x, elem_y), scaled_elem)
        except Exception as e:
            print(f"[Thumbnail Engine] Notice: Could not paste topic element: {e}")

    # 3. Vignette shadow overlay over the text area so typography is 100% razor sharp
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    odraw = ImageDraw.Draw(overlay)
    
    if is_long:
        for x in range(w):
            if x < 460:
                alpha = int(max(0, 225 - (x / 460) * 225))
            else:
                alpha = 0
            odraw.line([(x, 0), (x, h)], fill=(4, 6, 16, alpha))
    else:
        for y in range(h):
            if y < 750:
                alpha = int(140 + (y / 750) * 80)
            else:
                alpha = int(180 + ((y - 750) / (h - 750)) * 60)
            odraw.line([(0, y), (w, y)], fill=(4, 6, 16, min(240, alpha)))

    thumb = Image.alpha_composite(thumb, overlay).convert("RGB")

    # 4. Natural Overlay PNG of Host / Person (Standing on right or bottom)
    host_img_path = None
    for p in [BASE_DIR / "face.png", BASE_DIR / "face_clean.png", FACE_IMAGE_PATH]:
        if p.exists() and p.stat().st_size > 5000:
            host_img_path = p
            break

    if include_avatar and host_img_path:
        try:
            face_raw = Image.open(host_img_path).convert("RGBA")
            aspect = face_raw.width / face_raw.height

            if is_long:
                # Stand tall on the right side of the 16:9 thumbnail
                target_h = 700
                target_w = int(target_h * aspect)
                face_scaled = face_raw.resize((target_w, target_h), Image.Resampling.LANCZOS)

                # Soft blend mask for edges so it merges naturally
                mask = Image.new("L", (target_w, target_h), 255)
                fade_left = 60
                for x in range(min(fade_left, target_w)):
                    for y in range(target_h):
                        mask.putpixel((x, y), int(255 * (x / fade_left)))
                fade_bot = 40
                for y in range(max(0, target_h - fade_bot), target_h):
                    for x in range(target_w):
                        cur = mask.getpixel((x, y))
                        mask.putpixel((x, y), min(cur, int(255 * (1 - (y - (target_h - fade_bot)) / fade_bot))))

                from PIL import ImageChops
                orig_alpha = face_scaled.split()[-1]
                combined_alpha = ImageChops.multiply(orig_alpha, mask)
                face_scaled.putalpha(combined_alpha)

                pos_x = w - target_w + 30
                pos_y = h - target_h
                thumb.paste(face_scaled, (pos_x, pos_y), face_scaled)
            else:
                # Stand anchored at bottom of 9:16 Shorts thumbnail
                target_h = 1000
                target_w = int(target_h * aspect)
                face_scaled = face_raw.resize((target_w, target_h), Image.Resampling.LANCZOS)

                mask = Image.new("L", (target_w, target_h), 255)
                fade_top = 80
                for y in range(min(fade_top, target_h)):
                    for x in range(target_w):
                        mask.putpixel((x, y), int(255 * (y / fade_top)))
                fade_bot = 40
                for y in range(max(0, target_h - fade_bot), target_h):
                    for x in range(target_w):
                        cur = mask.getpixel((x, y))
                        mask.putpixel((x, y), min(cur, int(255 * (1 - (y - (target_h - fade_bot)) / fade_bot))))

                from PIL import ImageChops
                orig_alpha = face_scaled.split()[-1]
                combined_alpha = ImageChops.multiply(orig_alpha, mask)
                face_scaled.putalpha(combined_alpha)

                pos_x = (w - target_w) // 2
                pos_y = h - target_h
                thumb.paste(face_scaled, (pos_x, pos_y), face_scaled)
        except Exception as e:
            print(f"Notice: Host overlay rendering notice: {e}")

    draw = ImageDraw.Draw(thumb)

    # 4. Typography Fonts
    font_paths = [
        r"C:\Windows\Fonts\impact.ttf",
        r"C:\Windows\Fonts\arialbd.ttf"
    ]
    font_impact = None
    for fp in font_paths:
        if os.path.exists(fp):
            font_impact = fp
            break

    try:
        font_main = ImageFont.truetype(font_impact or "arialbd.ttf", 76 if is_long else 88)
        font_sub = ImageFont.truetype(font_impact or "arialbd.ttf", 68 if is_long else 76)
        font_tag = ImageFont.truetype(r"C:\Windows\Fonts\arialbd.ttf", 18 if is_long else 22)
    except Exception:
        font_main = ImageFont.load_default()
        font_sub = font_main
        font_tag = font_main

    # 5. Clean Title Parsing into 2 High-Contrast Punchy Lines
    clean_title = title.replace("#shorts", "").replace("🗿", "").replace(":", " -").strip()
    words = clean_title.split()

    if len(words) >= 4:
        split_pt = max(2, len(words) // 2)
        line1 = " ".join(words[:split_pt]).upper()
        line2 = " ".join(words[split_pt:split_pt+4]).upper()
    elif len(words) >= 2:
        line1 = words[0].upper()
        line2 = " ".join(words[1:]).upper()
    else:
        line1 = clean_title.upper()
        line2 = "BLUEPRINT"

    # 6. Dynamic Topic-Related Category Pill Badge (Replaces generic 'NEW' text)
    tag_text = extract_topic_tag(title)
    tag_bbox = draw.textbbox((0, 0), tag_text, font=font_tag)
    tag_w = tag_bbox[2] - tag_bbox[0] + 28
    tag_h = tag_bbox[3] - tag_bbox[1] + 16
    tag_x, tag_y = (60, 100) if is_long else (50, 120)

    # Niche-specific badge color (Tech: Electric Cyan, Psychology: Crimson)
    is_tech = (niche.lower() == "tech") or ("tech" in tag_text.lower())
    badge_fill = (6, 182, 212) if is_tech else (225, 29, 72)
    badge_text_color = (0, 0, 0) if is_tech else (255, 255, 255)

    draw.rounded_rectangle([tag_x, tag_y, tag_x + tag_w, tag_y + tag_h], radius=8, fill=badge_fill)
    draw.text((tag_x + 14, tag_y + 8), tag_text, font=font_tag, fill=badge_text_color)

    # 7. Render Title Lines with 3D Drop Shadow
    text_x = 60 if is_long else 50
    line1_y = tag_y + tag_h + (35 if is_long else 45)

    # Line 1: Pure White
    for dx in range(-5, 6):
        for dy in range(-5, 6):
            draw.text((text_x + dx, line1_y + dy), line1, font=font_main, fill=(0, 0, 0))
    draw.text((text_x, line1_y), line1, font=font_main, fill=(255, 255, 255))

    # Line 2: Vibrant Cyan for Tech, Gold/Yellow for Psychology
    line2_color = (0, 235, 255) if is_tech else (255, 217, 0)
    line2_y = line1_y + (92 if is_long else 100)
    for dx in range(-5, 6):
        for dy in range(-5, 6):
            draw.text((text_x + dx, line2_y + dy), line2, font=font_sub, fill=(0, 0, 0))
    draw.text((text_x, line2_y), line2, font=font_sub, fill=line2_color)

    # Save High-Quality Image with ZERO Watermarks
    thumb.save(output_path, "JPEG", quality=96)
    print(f"[Thumbnail Engine] 🖼️ Created watermark-free overlay thumbnail: {output_path.name}")
    return output_path

def create_ffmpeg_thumbnail(title: str, output_path: Path, format_type: str = "short", niche: str = "psychology") -> Path:
    """Generates a clean, atmospheric video thumbnail using FFmpeg."""
    import imageio_ffmpeg
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    is_long = (format_type == "long")
    w, h = (1280, 720) if is_long else (720, 1280)

    # Check for existing static cinematic backdrop
    static_dir = BASE_DIR / "web" / "static"
    candidates = [
        static_dir / "genre_cinema.jpg",
        static_dir / "opt_genre_cinema.jpg",
        static_dir / "genre_cyberpunk.jpg",
        static_dir / "genre_cartoon.jpg",
    ]
    bg_img = None
    for cand in candidates:
        if cand.exists() and cand.stat().st_size > 1000:
            bg_img = cand
            break

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if bg_img:
        cmd = [
            ffmpeg_exe, "-i", str(bg_img),
            "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}",
            "-vframes", "1", "-q:v", "2", str(output_path), "-y"
        ]
    else:
        bg_color = "0x09090b" if niche == "tech" else "0x120710"
        cmd = [
            ffmpeg_exe, "-f", "lavfi", "-i", f"color=c={bg_color}:s={w}x{h}:d=1",
            "-vframes", "1", "-q:v", "2", str(output_path), "-y"
        ]

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    print(f"[Thumbnail Engine] 🖼️ Created FFmpeg thumbnail: {output_path.name}")
    return output_path

def create_video_thumbnail(
    title: str,
    output_path: Path,
    format_type: str = "short",
    include_avatar: bool = False,
    niche: str = "psychology",
    video_path: Path = None
) -> Path:
    """
    Main resilient thumbnail generator.
    1. If video_path is provided, extracts a real frame from the video using FFmpeg.
    2. If PIL is available, renders high-CTR typography overlay.
    3. Gracefully falls back to FFmpeg-generated backdrop to prevent DLL errors.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Primary: Extract real frame from assembled video with FFmpeg
    if video_path and Path(video_path).exists() and Path(video_path).stat().st_size > 1000:
        try:
            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            cmd = [
                ffmpeg_exe, "-ss", "00:00:02", "-i", str(video_path),
                "-vframes", "1", "-q:v", "2", str(output_path), "-y"
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            if output_path.exists() and output_path.stat().st_size > 1000:
                print(f"[Thumbnail Engine] 🖼️ Extracted frame thumbnail from video: {output_path.name}")
                return output_path
        except Exception as fe:
            print(f"Notice: FFmpeg video frame extraction notice: {fe}")

    # 2. Secondary: PIL typography rendering if PIL C-extension is allowed
    if PIL_AVAILABLE:
        try:
            return _create_pil_thumbnail(title, output_path, format_type, include_avatar, niche)
        except Exception as pe:
            print(f"Notice: PIL thumbnail generation notice: {pe}")

    # 3. Resilient Fallback: FFmpeg cinematic backdrop thumbnail
    return create_ffmpeg_thumbnail(title, output_path, format_type, niche)

if __name__ == "__main__":
    out = VIDEOS_DIR / "test_thumb.jpg"
    create_video_thumbnail("The Dark Psychology of Mastered Destiny", out, format_type="long", include_avatar=True)
    print("Thumbnail generated:", out)
