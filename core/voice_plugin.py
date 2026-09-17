import os
import asyncio
import json
import urllib.request
import urllib.error
from pathlib import Path
import edge_tts
from core.config import TEMP_DIR

DEFAULT_VOICE = "en-US-ChristopherNeural"

async def generate_edge_tts_audio(text: str, voice: str = DEFAULT_VOICE, output_audio: Path = None) -> tuple[Path, list]:
    """
    Synthesizes speech using Microsoft Edge-TTS and extracts exact word-level timestamps.
    Returns (audio_path, words_list).
    """
    if output_audio is None:
        output_audio = TEMP_DIR / "speech.mp3"
        
    output_audio.parent.mkdir(parents=True, exist_ok=True)
    
    communicate = edge_tts.Communicate(text, voice)
    submaker = edge_tts.SubMaker()
    
    words = []
    
    with open(output_audio, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                # offset and duration in 100ns units -> convert to seconds
                start_sec = chunk["offset"] / 10_000_000
                dur_sec = chunk["duration"] / 10_000_000
                words.append({
                    "word": chunk["text"],
                    "start": start_sec,
                    "end": start_sec + dur_sec
                })

    return output_audio, words

def generate_elevenlabs_audio(text: str, voice_id: str, api_key: str, output_audio: Path = None) -> tuple[Path, list]:
    """
    Synthesizes speech using ElevenLabs API (or MCP voice service).
    Returns (audio_path, simulated_word_timestamps).
    """
    if output_audio is None:
        output_audio = TEMP_DIR / "elevenlabs_speech.mp3"
        
    output_audio.parent.mkdir(parents=True, exist_ok=True)
    
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key
    }
    payload = json.dumps({
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.8
        }
    }).encode("utf-8")
    
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            data = resp.read()
            with open(output_audio, "wb") as f:
                f.write(data)
                
        # Approximate timestamps based on word length for subtitle timing
        words_raw = text.split()
        total_chars = max(1, len(text))
        # Estimate duration ~ 150 words per minute -> 2.5 words per sec
        estimated_duration = max(len(words_raw) / 2.5, 3.0)
        
        words = []
        cur_t = 0.0
        time_per_char = estimated_duration / total_chars
        for w in words_raw:
            w_dur = max(len(w) * time_per_char, 0.2)
            words.append({
                "word": w,
                "start": round(cur_t, 2),
                "end": round(cur_t + w_dur, 2)
            })
            cur_t += w_dur
            
        return output_audio, words
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"ElevenLabs API Error: {err_msg}")

async def synthesize_voice(
    text: str,
    voice_provider: str = "edge-tts",
    voice_id: str = DEFAULT_VOICE,
    elevenlabs_key: str = None,
    output_audio: Path = None
) -> tuple[Path, list]:
    """
    Unified voice synthesizer with automatic fallback.
    """
    if voice_provider == "elevenlabs" and elevenlabs_key and voice_id:
        try:
            return generate_elevenlabs_audio(text, voice_id, elevenlabs_key, output_audio)
        except Exception as e:
            print(f"[VoicePlugin] ElevenLabs synthesis failed ({e}), falling back to Edge-TTS.")
            
    # Default to Edge-TTS
    edge_voice = voice_id if (voice_id and "Neural" in voice_id) else DEFAULT_VOICE
    return await generate_edge_tts_audio(text, edge_voice, output_audio)

def fetch_elevenlabs_voices(api_key: str) -> list:
    """Fetches user's available ElevenLabs voices."""
    url = "https://api.elevenlabs.io/v1/voices"
    headers = {"xi-api-key": api_key}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            voices = []
            for v in data.get("voices", []):
                voices.append({
                    "voice_id": v.get("voice_id"),
                    "name": v.get("name"),
                    "category": v.get("category", "premade"),
                    "preview_url": v.get("preview_url")
                })
            return voices
    except Exception as e:
        print(f"[VoicePlugin] Failed to fetch ElevenLabs voices: {e}")
        return []
