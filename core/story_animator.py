import os
import math
import subprocess
from pathlib import Path
import imageio_ffmpeg
from core.config import VIDEOS_DIR, TEMP_DIR, MUSIC_DIR
from core.video_composer import generate_srt_file, create_ambient_music_if_missing

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

CAPTION_STYLES = {
    "classic": "FontName=Arial,Bold=1,FontSize={font_size},PrimaryColour=&H00FFFFFF,OutlineColour=&H00141414,BorderStyle=1,Outline=1,Shadow=0,Alignment=2,MarginV={margin_v}",
    "subtle_white": "FontName=Arial,Bold=1,FontSize={font_size},PrimaryColour=&H00FFFFFF,OutlineColour=&H00141414,BorderStyle=1,Outline=1,Shadow=0,Alignment=2,MarginV={margin_v}",
    "gold": "FontName=Arial,Bold=1,FontSize={font_size},PrimaryColour=&H0045D4FF,OutlineColour=&H00141414,BorderStyle=1,Outline=1,Shadow=0,Alignment=2,MarginV={margin_v}",
    "neon": "FontName=Arial,Bold=1,FontSize={font_size},PrimaryColour=&H00E0E000,OutlineColour=&H00141414,BorderStyle=1,Outline=1,Shadow=0,Alignment=2,MarginV={margin_v}",
    "minimal": "FontName=Arial,Bold=0,FontSize={font_size},PrimaryColour=&H00EDEDED,OutlineColour=&H001C1C1C,BorderStyle=1,Outline=1,Shadow=0,Alignment=2,MarginV={margin_v}"
}

def animate_story_video(
    image_paths: list[Path],
    voice_audio_path: Path,
    words: list,
    output_filename: str,
    format_type: str = "short",
    caption_style: str = "gold",
    progress_callback = None
) -> Path:
    """
    High-performance, accelerated story video generator:
    - Multiple caption templates (Viral Gold, Cyber Neon, Classic Cinema, Minimalist, or OFF)
    - Ken Burns dynamic camera motions (zoom-in, zoom-out, pan left, pan right)
    - Accelerated FFmpeg pipeline with -preset ultrafast and -crf 26 for compact file sizes (< 3MB)
    - Direct MP4 export
    """
    if progress_callback:
        progress_callback("Analyzing story timeline and image assets...")

    output_path = VIDEOS_DIR / output_filename
    output_path.parent.mkdir(parents=True, exist_ok=True)

    is_long = (format_type == "long")
    # Native web resolution for lightning fast encoding and small file size
    width, height = (1280, 720) if is_long else (720, 1280)
    font_size = 15 if is_long else 14
    margin_v = 35 if is_long else 65

    # Calculate total duration
    if words and len(words) > 0:
        total_duration = max(words[-1]["end"] + 0.5, 4.0)
    else:
        total_duration = 15.0

    valid_images = [Path(p) for p in image_paths if Path(p).exists() and Path(p).stat().st_size > 1000]
    if not valid_images:
        raise ValueError("No valid image files provided for story animation.")

    num_images = len(valid_images)
    scene_dur = max(total_duration / num_images, 2.5)
    num_scenes = num_images

    if progress_callback:
        progress_callback(f"Rendering {num_images} scenes with dynamic Ken Burns motion ({caption_style} captions)...")

    # Handle Optional Captions
    use_subtitles = caption_style and caption_style.lower() not in ("none", "off", "false", "0", "")
    sub_filter = ""
    if use_subtitles:
        srt_file = TEMP_DIR / f"{output_filename}_subs.srt"
        generate_srt_file(words, srt_file, words_per_caption=3 if is_long else 2)
        escaped_srt = str(srt_file).replace("\\", "/").replace(":", "\\:")
        
        style_template = CAPTION_STYLES.get(caption_style.lower(), CAPTION_STYLES["gold"])
        style_formatted = style_template.format(font_size=font_size, margin_v=margin_v)
        sub_filter = f"subtitles='{escaped_srt}':force_style='{style_formatted}'"

    # Ambient Music
    ambient_music = MUSIC_DIR / "dark_ambient.mp3"
    create_ambient_music_if_missing(ambient_music, int(total_duration) + 20)

    # Support both animated video clips (e.g. Meta AI MP4s, WebM, GIFs) and static images
    VIDEO_EXTENSIONS = (".mp4", ".mov", ".webm", ".mkv", ".gif")
    
    video_inputs = []
    filter_parts = []
    concat_nodes = []

    upscale_w = int(width * 1.15)
    upscale_h = int(height * 1.15)

    for i, asset in enumerate(valid_images):
        asset_path = Path(asset)
        is_video = asset_path.suffix.lower() in VIDEO_EXTENSIONS
        node = f"v{i}"
        frames = int((scene_dur + 0.1) * 25)
        
        if is_video:
            # Animated video clip input (stream_loop ensures clips shorter than scene_dur loop seamlessly)
            video_inputs.extend(["-stream_loop", "-1", "-t", f"{scene_dur + 0.5}", "-i", str(asset_path)])
            filter_parts.append(
                f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},"
                f"trim=0:{scene_dur},setpts=PTS-STARTPTS,fps=25,setsar=1[{node}]"
            )
        else:
            # Static image input with Ken Burns dynamic motion
            video_inputs.extend(["-loop", "1", "-t", f"{scene_dur + 0.3}", "-i", str(asset_path)])
            mode = i % 4
            if mode == 0:
                z_expr = "min(zoom+0.002,1.20)"
                x_expr = "iw/2-(iw/zoom/2)"
                y_expr = "ih/2-(ih/zoom/2)"
            elif mode == 1:
                z_expr = "if(eq(on,1),1.18,max(1.0,zoom-0.0018))"
                x_expr = "iw/2-(iw/zoom/2)"
                y_expr = "ih/2-(ih/zoom/2)"
            elif mode == 2:
                z_expr = "1.12"
                x_expr = "x+1.5"
                y_expr = "ih/2-(ih/zoom/2)"
            else:
                z_expr = "min(zoom+0.0018,1.16)"
                x_expr = "iw/2-(iw/zoom/2)"
                y_expr = "ih/4-(ih/zoom/4)"

            filter_parts.append(
                f"[{i}:v]scale={upscale_w}:{upscale_h}:force_original_aspect_ratio=increase,crop={upscale_w}:{upscale_h},"
                f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':d={frames}:s={width}x{height},"
                f"trim=0:{scene_dur},setpts=PTS-STARTPTS,fps=25,setsar=1[{node}]"
            )
            
        concat_nodes.append(f"[{node}]")

    concat_chain = "".join(concat_nodes) + f"concat=n={num_scenes}:v=1:a=0[raw_bg]"
    
    if use_subtitles:
        final_v_filter = f"{';'.join(filter_parts)};{concat_chain};[raw_bg]{sub_filter}[v]"
    else:
        final_v_filter = f"{';'.join(filter_parts)};{concat_chain};[raw_bg]null[v]"

    audio_idx = num_scenes
    music_idx = audio_idx + 1

    cmd = [
        FFMPEG_EXE, "-y",
        "-loglevel", "error",
        "-threads", "0",
        *video_inputs,
        "-i", str(voice_audio_path),
        "-stream_loop", "-1",
        "-i", str(ambient_music),
        "-filter_complex",
        f"{final_v_filter};[{audio_idx}:a]volume=1.0[voice];[{music_idx}:a]volume=0.05[music];[voice][music]amix=inputs=2:duration=first[a]",
        "-map", "[v]",
        "-map", "[a]",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "26",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-t", f"{total_duration}",
        str(output_path)
    ]

    if progress_callback:
        progress_callback("Encoding compact MP4 video...")

    subprocess.run(cmd, check=True)

    if progress_callback:
        progress_callback(f"Successfully rendered {output_filename}!")

    return output_path
