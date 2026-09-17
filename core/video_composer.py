import os
import math
import subprocess
from pathlib import Path
import imageio_ffmpeg
from core.config import VIDEOS_DIR, TEMP_DIR, MUSIC_DIR, FACE_IMAGE_PATH

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()

def format_timestamp_srt(seconds: float) -> str:
    """Formats seconds into SRT format: 00:00:01,500"""
    millis = int((seconds % 1) * 1000)
    seconds = int(seconds)
    mins = seconds // 60
    secs = seconds % 60
    hours = mins // 60
    mins = mins % 60
    return f"{hours:02d}:{mins:02d}:{secs:02d},{millis:03d}"

def generate_srt_file(words: list, srt_path: Path, words_per_caption: int = 3) -> Path:
    """
    Groups words into short, punchy 2-4 word captions for fast viral retention.
    Writes standard SRT file.
    """
    srt_path = Path(srt_path)
    if not words:
        srt_path.write_text("1\n00:00:00,000 --> 00:00:05,000\n...\n", encoding="utf-8")
        return srt_path
        
    entries = []
    chunk = []
    
    for w in words:
        chunk.append(w)
        if len(chunk) >= words_per_caption:
            start_t = chunk[0]["start"]
            end_t = chunk[-1]["end"]
            text = " ".join([item["word"].upper() for item in chunk])
            entries.append((start_t, end_t, text))
            chunk = []
            
    if chunk:
        start_t = chunk[0]["start"]
        end_t = chunk[-1]["end"]
        text = " ".join([item["word"].upper() for item in chunk])
        entries.append((start_t, end_t, text))

    with open(srt_path, "w", encoding="utf-8") as f:
        for i, (s, e, text) in enumerate(entries, 1):
            f.write(f"{i}\n")
            f.write(f"{format_timestamp_srt(s)} --> {format_timestamp_srt(e)}\n")
            f.write(f"{text}\n\n")

    return srt_path

def create_ambient_music_if_missing(music_path: Path, duration: int = 120):
    """
    Generates a lush, pristine cinematic ambient musical pad using FFmpeg.
    Uses gentle harmonious minor chords with soft attack, smooth highpass/lowpass filtering,
    eliminating muddy subterranean rumble ('underground sound') completely.
    """
    music_path = Path(music_path)
    if music_path.exists() and music_path.stat().st_size > 1000:
        return music_path
        
    music_path.parent.mkdir(parents=True, exist_ok=True)
    # Generate warm, airy cinematic ambient harmonic drone (A minor 220Hz + 330Hz) with natural envelope
    cmd = [
        FFMPEG_EXE, "-y",
        "-loglevel", "error",
        "-f", "lavfi", "-i", f"sine=frequency=220:duration={duration}",
        "-f", "lavfi", "-i", f"sine=frequency=330:duration={duration}",
        "-filter_complex",
        "[0:a]volume=0.018,tremolo=f=0.25:d=0.6,lowpass=f=500,highpass=f=160[p1];"
        "[1:a]volume=0.012,tremolo=f=0.18:d=0.5,lowpass=f=450,highpass=f=160[p2];"
        "[p1][p2]amix=inputs=2:duration=first,volume=0.025,afade=t=in:ss=0:d=2[out]",
        "-map", "[out]",
        "-c:a", "libmp3lame",
        str(music_path)
    ]
    subprocess.run(cmd)
    return music_path

def compose_video(
    clips: list,
    voice_audio: Path,
    words: list,
    output_name: str,
    format_type: str = "short",
    include_avatar: bool = False,
    caption_style: str = "classic"
) -> Path:
    """
    Assembles the final video:
    - Dynamic pacing across sharp background b-roll
    - Compact, non-intrusive subtitles (or clean video with captions OFF)
    - Optional small corner avatar (if include_avatar=True)
    - Mixed ambient soundtrack
    """
    output_path = VIDEOS_DIR / output_name
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    is_long = (format_type == "long")
    width, height = (1920, 1080) if is_long else (1080, 1920)
    font_size = 18 if is_long else 16
    margin_v = 45 if is_long else 85
    
    # 1. Subtitles (Compact, sleek, subtle shadow, or disabled if 'off'/'none')
    use_subtitles = caption_style and caption_style.lower() not in ("none", "off", "false", "0", "")
    if use_subtitles:
        srt_file = TEMP_DIR / f"{output_name}_subs.srt"
        generate_srt_file(words, srt_file, words_per_caption=3 if is_long else 2)
        escaped_srt = str(srt_file).replace("\\", "/").replace(":", "\\:")
        sub_filter = (
            f"subtitles='{escaped_srt}':force_style="
            f"'FontName=Arial,Bold=1,FontSize={font_size},PrimaryColour=&H00FFFFFF,OutlineColour=&H00141414,BorderStyle=1,Outline=1,Shadow=0,Alignment=2,MarginV={margin_v}'"
        )
    else:
        sub_filter = ""

    # 2. Ambient music
    ambient_music = MUSIC_DIR / "dark_ambient.mp3"
    create_ambient_music_if_missing(ambient_music, 300 if is_long else 60)

    # 3. Check if user's face avatar should be displayed
    has_face = include_avatar and FACE_IMAGE_PATH.exists() and FACE_IMAGE_PATH.stat().st_size > 5000
    
    # Calculate audio duration from word timestamps
    if words and len(words) > 0:
        total_duration = max(words[-1]["end"] + 0.5, 6.0)
    else:
        total_duration = 35.0

    # Filter valid clip files that exist and have non-empty size
    valid_clips = []
    if clips:
        for c in clips:
            cp = Path(c)
            if cp.exists() and cp.stat().st_size > 10_000:
                valid_clips.append(cp)

    # Dynamic Scene Pacing:
    # Shorts change scene every ~3.5 to 4.5 seconds for maximum retention
    # Long-form documentaries change scene every ~5.0 to 6.5 seconds
    scene_dur = 5.5 if is_long else 4.0
    num_scenes = max(1, int(math.ceil(total_duration / scene_dur)))

    video_inputs = []
    if valid_clips:
        for c in valid_clips:
            ext = c.suffix.lower()
            if ext in [".jpg", ".jpeg", ".png", ".webp"]:
                video_inputs.extend(["-loop", "1", "-i", str(c)])
            else:
                video_inputs.extend(["-stream_loop", "-1", "-i", str(c)])
        
        num_valid = len(valid_clips)
        filter_parts = []
        concat_nodes = []

        for s in range(num_scenes):
            clip_idx = s % num_valid
            node_name = f"s{s}"
            c_file = valid_clips[clip_idx]
            is_image = c_file.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]
            start_trim = (s // num_valid) * scene_dur
            end_trim = start_trim + scene_dur

            if is_image:
                # Animate images with dynamic Ken Burns slow zoom-in
                frames_dur = int(scene_dur * 30)
                filter_parts.append(
                    f"[{clip_idx}:v]scale=3840:2160:force_original_aspect_ratio=increase,crop=3840:2160,"
                    f"zoompan=z='min(zoom+0.0015,1.25)':d={frames_dur}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height},"
                    f"trim=0:{scene_dur},setpts=PTS-STARTPTS,fps=30,setsar=1[{node_name}]"
                )
            else:
                filter_parts.append(
                    f"[{clip_idx}:v]scale={width}:{height}:force_original_aspect_ratio=increase,"
                    f"crop={width}:{height},"
                    f"trim={start_trim}:{end_trim},"
                    f"setpts=PTS-STARTPTS,"
                    f"fps=30,setsar=1[{node_name}]"
                )
            concat_nodes.append(f"[{node_name}]")

        concat_str = "".join(concat_nodes) + f"concat=n={num_scenes}:v=1:a=0[bg];"
        bg_filter = ";".join(filter_parts) + ";" + concat_str
    else:
        video_inputs = ["-f", "lavfi", "-i", f"color=c=0x09090b:s={width}x{height}:d={int(total_duration)+5}"]
        bg_filter = "[0:v]null[bg];"

    num_video_inputs = len(valid_clips) if valid_clips else 1

    extra_inputs = []
    current_layer = "bg"

    # If avatar requested, overlay as a sleek, non-intrusive circular host badge in the top corner
    if has_face:
        avatar_idx = num_video_inputs
        extra_inputs.extend(["-i", str(FACE_IMAGE_PATH)])
        
        if is_long:
            avatar_w = 200
            avatar_filter = f"[{avatar_idx}:v]scale={avatar_w}:{avatar_w}[avatar];[{current_layer}][avatar]overlay=W-w-50:50[layer1];"
        else:
            # Discreet host badge at top-right so background video remains 100% visible
            avatar_w = 200
            avatar_filter = f"[{avatar_idx}:v]scale={avatar_w}:{avatar_w}[avatar];[{current_layer}][avatar]overlay=W-w-40:50[layer1];"
            
        current_layer = "layer1"
    else:
        avatar_filter = ""
        
    if sub_filter:
        final_v_filter = f"{bg_filter}{avatar_filter}[{current_layer}]{sub_filter}[v]"
    else:
        final_v_filter = f"{bg_filter}{avatar_filter}[{current_layer}]null[v]"
    
    audio_idx = num_video_inputs + (1 if has_face else 0)
    music_idx = audio_idx + 1

    cmd = [
        FFMPEG_EXE, "-y",
        "-loglevel", "error",
        *video_inputs,
        *extra_inputs,
        "-i", str(voice_audio),
        "-stream_loop", "-1",
        "-i", str(ambient_music),
        "-filter_complex",
        f"{final_v_filter};[{audio_idx}:a]volume=1.0[voice];[{music_idx}:a]volume=0.06[music];[voice][music]amix=inputs=2:duration=first[a]",
        "-map", "[v]",
        "-map", "[a]",
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-shortest",
        str(output_path)
    ]

    print(f"Rendering Deliverace Video ({output_name}, format={format_type})...")
    subprocess.run(cmd)
    return output_path
