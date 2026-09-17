"""
Deliverace Studio — Lightweight Video Editor Engine
Fast CapCut-style video slicing, trimming, segment concatenation, and audio track mixing via native FFmpeg.
Runs purely locally with zero watermarks and sub-5-second render times.
"""

import os
import math
import subprocess
from pathlib import Path
import imageio_ffmpeg
from core.config import VIDEOS_DIR, TEMP_DIR, MUSIC_DIR

FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()


def get_video_duration(video_path: Path) -> float:
    """Returns video duration in seconds using ffprobe/ffmpeg."""
    cmd = [FFMPEG_EXE, "-i", str(video_path)]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for line in p.stderr.splitlines():
        if "Duration:" in line:
            parts = line.split("Duration:")[1].split(",")[0].strip().split(":")
            if len(parts) == 3:
                try:
                    return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
                except ValueError:
                    pass
    return 30.0


def has_audio_stream(video_path: Path) -> bool:
    """Checks if a video file contains an audio stream."""
    cmd = [FFMPEG_EXE, "-i", str(video_path)]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return "Audio:" in p.stderr


def render_edited_video(
    source_video_path: Path,
    segments: list,
    output_filename: str,
    bg_audio_path: Path = None,
    bg_audio_volume: float = 0.20,
    orig_audio_volume: float = 1.0,
    progress_callback = None
) -> Path:
    """
    Renders an edited video based on kept timeline segments.
    - segments: list of dicts with 'start' and 'end' in seconds
    - bg_audio_path: optional path to music or sound FX track
    - bg_audio_volume: 0.0 to 1.0 (defaults to 0.20 for background ducking)
    - orig_audio_volume: 0.0 to 1.5 (defaults to 1.0)
    - Zero watermarks added.
    """
    source_path = Path(source_video_path)
    if not source_path.exists() or source_path.stat().st_size < 1000:
        raise FileNotFoundError(f"Source video not found: {source_path}")

    out_str = str(output_filename)
    if os.path.isabs(out_str):
        output_path = Path(out_str)
    else:
        output_path = VIDEOS_DIR / output_filename
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not segments:
        total_dur = get_video_duration(source_path)
        segments = [{"start": 0.0, "end": total_dur}]

    if progress_callback:
        progress_callback(f"Analyzing {len(segments)} timeline segment(s)...")

    source_has_audio = has_audio_stream(source_path)

    filter_parts = []
    v_nodes = []
    a_nodes = []

    total_kept_duration = 0.0
    valid_seg_idx = 0
    for seg in segments:
        start = max(0.0, float(seg.get("start", 0.0)))
        end = float(seg.get("end", 0.0))
        if end <= start:
            continue

        dur = end - start
        total_kept_duration += dur

        v_node = f"v{valid_seg_idx}"
        filter_parts.append(
            f"[0:v]trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS[{v_node}]"
        )
        v_nodes.append(f"[{v_node}]")

        if source_has_audio:
            a_node = f"a{valid_seg_idx}"
            filter_parts.append(
                f"[0:a]atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS,volume={orig_audio_volume:.2f}[{a_node}]"
            )
            a_nodes.append(f"[{a_node}]")
        valid_seg_idx += 1

    if not v_nodes:
        raise ValueError("All editing segments were empty or invalid.")

    num_segments = len(v_nodes)
    filter_parts.append(
        f"{''.join(v_nodes)}concat=n={num_segments}:v=1:a=0[v_concat]"
    )

    if source_has_audio:
        filter_parts.append(
            f"{''.join(a_nodes)}concat=n={num_segments}:v=0:a=1[a_orig_concat]"
        )
        final_orig_audio = "[a_orig_concat]"
    else:
        filter_parts.append(
            f"anullsrc=channel_layout=stereo:sample_rate=44100,atrim=end={total_kept_duration:.3f}[a_silent]"
        )
        final_orig_audio = "[a_silent]"

    inputs = ["-i", str(source_path)]

    has_bg_audio = bg_audio_path and Path(bg_audio_path).exists() and Path(bg_audio_path).stat().st_size > 1000
    if has_bg_audio:
        inputs.extend(["-stream_loop", "-1", "-i", str(bg_audio_path)])
        filter_parts.append(
            f"[1:a]volume={bg_audio_volume:.2f}[bg_vol];"
            f"{final_orig_audio}[bg_vol]amix=inputs=2:duration=first:dropout_transition=2[a_final]"
        )
        final_a_node = "[a_final]"
    else:
        final_a_node = final_orig_audio

    filter_complex = ";".join(filter_parts)

    cmd = [
        FFMPEG_EXE, "-y",
        "-loglevel", "error",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[v_concat]",
        "-map", final_a_node,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "24",
        "-c:a", "aac",
        "-b:a", "192k",
        "-t", f"{total_kept_duration:.2f}",
        "-movflags", "+faststart",
        str(output_path)
    ]

    if progress_callback:
        progress_callback(f"Rendering cuts and audio mix ({total_kept_duration:.1f}s)...")

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        err_msg = res.stderr.decode("utf-8", errors="ignore")
        raise RuntimeError(f"Video editor FFmpeg failed: {err_msg}")

    if not output_path.exists() or output_path.stat().st_size < 5000:
        raise RuntimeError("Rendered video was empty or corrupted.")

    if progress_callback:
        progress_callback("Render complete! Video ready.")

    return output_path


def render_multi_clip_timeline(
    clips: list,
    output_filename: str,
    long_audio_path: str = None,
    long_audio_volume: float = 1.0,
    orig_audio_volume: float = 1.0,
    bg_music_path: str = None,
    bg_music_volume: float = 0.20,
    format_type: str = "short",
    progress_callback = None
) -> Path:
    """
    Renders multiple video clips into a single unified CapCut-style timeline sequence.
    - clips: list of dicts with:
        'source_path': Path or string to video file
        'start': float (seconds)
        'end': float (seconds)
    - output_filename: output MP4 file name or absolute path
    - long_audio_path: optional path to master long audio track (voiceover/narration)
    - long_audio_volume: 0.0 to 1.5
    - orig_audio_volume: volume of the video clips' original audio
    - bg_music_path: optional background ambient music
    - bg_music_volume: volume of background music
    - format_type: 'short' (9:16 vertical 720x1280) or 'long' (16:9 1280x720)
    - Zero watermarks added.
    """
    if not clips:
        raise ValueError("No video clips provided for timeline sequence.")

    out_str = str(output_filename)
    if os.path.isabs(out_str):
        output_path = Path(out_str)
    else:
        output_path = VIDEOS_DIR / output_filename
    output_path.parent.mkdir(parents=True, exist_ok=True)

    is_long = (format_type == "long")
    w, h = (1280, 720) if is_long else (720, 1280)

    if progress_callback:
        progress_callback(f"Preparing {len(clips)} clip(s) for timeline rendering...")

    inputs = []
    filter_parts = []
    v_nodes = []
    a_nodes = []

    total_sequence_duration = 0.0
    input_idx = 0

    for clip_info in clips:
        raw_p = clip_info.get("source_path") or clip_info.get("filename") or clip_info.get("path")
        if not raw_p:
            continue
        p = Path(raw_p)
        if not p.exists() or p.stat().st_size < 1000:
            # Check in VIDEOS_DIR or TEMP_DIR/uploads
            candidate = VIDEOS_DIR / p.name
            if candidate.exists() and candidate.stat().st_size > 1000:
                p = candidate
            else:
                candidate2 = TEMP_DIR / "uploads" / p.name
                if candidate2.exists() and candidate2.stat().st_size > 1000:
                    p = candidate2
                else:
                    print(f"Warning: Clip file not found, skipping: {raw_p}")
                    continue

        clip_dur = get_video_duration(p)
        start = max(0.0, float(clip_info.get("start", 0.0)))
        end = float(clip_info.get("end", clip_dur))
        if end <= start or end > clip_dur + 0.1:
            end = clip_dur
        seg_len = max(0.2, end - start)
        total_sequence_duration += seg_len

        inputs.extend(["-i", str(p)])
        curr_in = input_idx
        v_node = f"v{curr_in}"
        a_node = f"a{curr_in}"

        # Standardize video dimensions, SAR, and framerate across heterogeneous sources
        filter_parts.append(
            f"[{curr_in}:v]trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS,"
            f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps=30[{v_node}]"
        )
        v_nodes.append(f"[{v_node}]")

        has_audio = has_audio_stream(p)
        if has_audio:
            filter_parts.append(
                f"[{curr_in}:a]atrim=start={start:.3f}:end={end:.3f},asetpts=PTS-STARTPTS,"
                f"volume={orig_audio_volume:.2f},aformat=sample_rates=44100:channel_layouts=stereo[{a_node}]"
            )
            a_nodes.append(f"[{a_node}]")
        else:
            filter_parts.append(
                f"anullsrc=channel_layout=stereo:sample_rate=44100,atrim=end={seg_len:.3f}[{a_node}]"
            )
            a_nodes.append(f"[{a_node}]")

        input_idx += 1

    if not v_nodes:
        raise ValueError("None of the specified video clips could be loaded.")

    num_clips = len(v_nodes)
    filter_parts.append(
        f"{''.join(v_nodes)}concat=n={num_clips}:v=1:a=0[v_seq]"
    )
    filter_parts.append(
        f"{''.join(a_nodes)}concat=n={num_clips}:v=0:a=1[a_seq]"
    )

    audio_mix_sources = ["[a_seq]"]

    # Handle Master Long Audio Track (Voiceover / Speech / Narration)
    has_long_audio = False
    if long_audio_path:
        la_p = Path(long_audio_path)
        if not la_p.exists():
            la_p2 = TEMP_DIR / "uploads" / la_p.name
            if la_p2.exists():
                la_p = la_p2
        if la_p.exists() and la_p.stat().st_size > 500:
            has_long_audio = True
            inputs.extend(["-i", str(la_p)])
            la_idx = input_idx
            input_idx += 1
            filter_parts.append(
                f"[{la_idx}:a]volume={long_audio_volume:.2f},aformat=sample_rates=44100:channel_layouts=stereo[a_long]"
            )
            audio_mix_sources.append("[a_long]")

    # Handle Background Music Track
    has_bg_music = False
    if bg_music_path:
        bm_p = Path(bg_music_path)
        if not bm_p.exists():
            bm_p2 = MUSIC_DIR / bm_p.name
            if bm_p2.exists():
                bm_p = bm_p2
            else:
                bm_p3 = TEMP_DIR / "uploads" / bm_p.name
                if bm_p3.exists():
                    bm_p = bm_p3
        if bm_p.exists() and bm_p.stat().st_size > 500:
            has_bg_music = True
            inputs.extend(["-stream_loop", "-1", "-i", str(bm_p)])
            bm_idx = input_idx
            input_idx += 1
            filter_parts.append(
                f"[{bm_idx}:a]volume={bg_music_volume:.2f},aformat=sample_rates=44100:channel_layouts=stereo[a_bgm]"
            )
            audio_mix_sources.append("[a_bgm]")

    # Mix audio layers
    if len(audio_mix_sources) > 1:
        mix_inputs = "".join(audio_mix_sources)
        filter_parts.append(
            f"{mix_inputs}amix=inputs={len(audio_mix_sources)}:duration=first:dropout_transition=2[a_final]"
        )
        final_a_node = "[a_final]"
    else:
        final_a_node = "[a_seq]"

    filter_complex = ";".join(filter_parts)

    cmd = [
        FFMPEG_EXE, "-y",
        "-loglevel", "error",
        *inputs,
        "-filter_complex", filter_complex,
        "-map", "[v_seq]",
        "-map", final_a_node,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "24",
        "-c:a", "aac",
        "-b:a", "192k",
        "-t", f"{total_sequence_duration:.2f}",
        "-movflags", "+faststart",
        str(output_path)
    ]

    if progress_callback:
        progress_callback(f"Rendering multi-clip sequence ({total_sequence_duration:.1f}s, {num_clips} clips)...")

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        err_msg = res.stderr.decode("utf-8", errors="ignore")
        raise RuntimeError(f"Multi-clip render failed: {err_msg}")

    if not output_path.exists() or output_path.stat().st_size < 5000:
        raise RuntimeError("Multi-clip rendered file was empty or corrupted.")

    if progress_callback:
        progress_callback("Sequence render complete! 100% clean watermark-free video.")

    return output_path
