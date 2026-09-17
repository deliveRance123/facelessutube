import asyncio
from pathlib import Path
import edge_tts
from core.config import get_default_voice, TEMP_DIR

def get_voice_clone_profile() -> dict:
    """
    Reads the cloned voice profile generated from the user's voice.wav recording,
    or analyzes voice.wav using Gemini to match timbre, accent, pitch, and speed.
    """
    from core.config import get_channel_settings, save_channel_settings, VOICE_SAMPLE_PATH, GEMINI_API_KEY
    settings = get_channel_settings()
    if "voice_clone_profile" in settings:
        return settings["voice_clone_profile"]

    # Default baseline clone profile (matches Nigerian deliberate male delivery)
    profile = {
        "base_voice": "en-NG-AbeoNeural",
        "pitch": "+0Hz",
        "rate": "+0%",
        "tone": "deliberate, authoritative",
        "accent": "Nigerian"
    }

    if VOICE_SAMPLE_PATH.exists() and VOICE_SAMPLE_PATH.stat().st_size > 1000 and GEMINI_API_KEY:
        try:
            from google import genai
            from google.genai import types
            import json

            client = genai.Client(api_key=GEMINI_API_KEY)
            prompt = """
Analyze this voice recording carefully.
Determine:
1. Speaker gender (male or female).
2. Accent and dialect (e.g. Nigerian/West African, American, British, etc.).
3. Tone and cadence.
4. Best matching Microsoft Edge-TTS voice name from:
- en-NG-AbeoNeural (Nigerian English Male)
- en-NG-EzinneNeural (Nigerian English Female)
- en-US-ChristopherNeural (US Deep Male)
- en-US-GuyNeural (US Clear Male)
- en-US-BrianNeural (US Natural Male)
- en-GB-RyanNeural (UK Male)
- en-KE-ChilembaNeural (Kenyan Male)
- en-ZA-LukeNeural (South African Male)
- en-US-JennyNeural (US Female)

Return JSON with keys:
base_voice, pitch, rate, accent, tone
"""
            with open(VOICE_SAMPLE_PATH, "rb") as f:
                data = f.read()

            for model_name in ["gemini-3.6-flash", "gemini-3.5-flash"]:
                try:
                    resp = client.models.generate_content(
                        model=model_name,
                        contents=[types.Part.from_bytes(data=data, mime_type="audio/wav"), prompt],
                        config=types.GenerateContentConfig(response_mime_type="application/json")
                    )
                    if resp and resp.text:
                        p_data = json.loads(resp.text.strip())
                        profile["base_voice"] = p_data.get("base_voice", profile["base_voice"])
                        profile["pitch"] = p_data.get("pitch", profile["pitch"])
                        profile["rate"] = p_data.get("rate", profile["rate"])
                        profile["accent"] = p_data.get("accent", profile["accent"])
                        profile["tone"] = p_data.get("tone", profile["tone"])
                        break
                except Exception:
                    continue
        except Exception as e:
            print(f"[Voice Clone Analyzer] Notice: {e}")

    save_channel_settings({"voice_clone_profile": profile})
    return profile

async def generate_speech_async(text: str, output_path: Path, voice: str = None, pitch: str = None, rate: str = None) -> dict:
    """
    Synthesizes speech using edge-tts with voice cloning parameters (pitch, rate)
    and captures sentence & word-level timestamps.
    """
    if not voice:
        voice = get_default_voice()

    # If user selected custom cloned voice, apply clone profile parameters
    if voice == "custom":
        profile = get_voice_clone_profile()
        actual_voice = profile.get("base_voice", "en-NG-AbeoNeural")
        pitch = pitch or profile.get("pitch", "+0Hz")
        rate = rate or profile.get("rate", "+0%")
    else:
        actual_voice = voice

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure Communicate with pitch and rate modulation for true voice clone reproduction
    comm_kwargs = {}
    if pitch and pitch != "+0Hz":
        comm_kwargs["pitch"] = pitch
    if rate and rate != "+0%":
        comm_kwargs["rate"] = rate

    communicate = edge_tts.Communicate(text, actual_voice, **comm_kwargs)
    
    audio_data = bytearray()
    sentences = []
    words = []
    
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_data.extend(chunk["data"])
        elif chunk["type"] == "WordBoundary":
            start_sec = chunk["offset"] / 10_000_000.0
            dur_sec = chunk["duration"] / 10_000_000.0
            words.append({
                "word": chunk["text"],
                "start": round(start_sec, 3),
                "end": round(start_sec + dur_sec, 3)
            })
        elif chunk["type"] == "SentenceBoundary":
            start_sec = chunk["offset"] / 10_000_000.0
            dur_sec = chunk["duration"] / 10_000_000.0
            sentences.append({
                "text": chunk["text"],
                "start": round(start_sec, 3),
                "end": round(start_sec + dur_sec, 3)
            })

    # If WordBoundary wasn't sent, interpolate words from SentenceBoundary
    if not words and sentences:
        for s in sentences:
            s_words = s["text"].split()
            if not s_words:
                continue
            total_dur = s["end"] - s["start"]
            word_dur = total_dur / len(s_words)
            for i, w in enumerate(s_words):
                w_start = s["start"] + (i * word_dur)
                w_end = w_start + word_dur
                words.append({
                    "word": w,
                    "start": round(w_start, 3),
                    "end": round(w_end, 3)
                })

    with open(output_path, "wb") as f:
        f.write(audio_data)
        
    return {
        "audio_path": output_path,
        "words": words,
        "sentences": sentences
    }

def generate_speech(text: str, output_path: Path, voice: str = None, pitch: str = None, rate: str = None) -> dict:
    """Synchronous wrapper for generate_speech_async"""
    return asyncio.run(generate_speech_async(text, output_path, voice=voice, pitch=pitch, rate=rate))

def transcribe_custom_audio(audio_path: Path, format_type: str = "short", custom_topic: str = None) -> dict:
    """
    Transcribes user's custom recorded voice audio using Google Gemini,
    extracts word/phrase timestamps for animated subtitles, and creates
    matching scenes, viral title, and description.
    """
    from google import genai
    from google.genai import types
    from core.config import GEMINI_API_KEY
    import json

    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not configured in .env")

    audio_path = Path(audio_path)
    if not audio_path.exists() or audio_path.stat().st_size < 1000:
        raise FileNotFoundError(f"Custom audio file not found: {audio_path}")

    suffix = audio_path.suffix.lower()
    mime = "audio/wav" if suffix == ".wav" else ("audio/mpeg" if suffix in (".mp3", ".mpga") else "audio/mp4")

    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    client = genai.Client(api_key=GEMINI_API_KEY)

    topic_prompt = f"Topic context: {custom_topic}." if custom_topic else "Theme: Dark psychology, stoic wisdom, personal power."
    prompt = f"""
Listen to this voiceover audio recording.
{topic_prompt}

1. Transcribe the spoken text word-for-word accurately into 'full_narration'.
2. Provide word-level timestamps (every word with 'word', 'start', and 'end' in seconds).
3. Create a magnetic, click-worthy YouTube title (under 70 chars with 🗿 or #shorts).
4. Create an engaging YouTube description with relevant hashtags.
5. Extract 4 to 8 visual search scenes with atmospheric keywords for HD cinematic B-roll stock video search (e.g. 'ancient marble statue', 'shadowy street night rain', 'chess game moody', 'foggy dark forest').

Return ONLY a valid JSON object matching this schema:
{{
  "title": "Title...",
  "description": "Description...",
  "tags": ["psychology", "stoicism", "mindset", "life lessons"],
  "full_narration": "Full transcript...",
  "words": [
    {{"word": "FIRST", "start": 0.0, "end": 0.5}},
    {{"word": "WORD", "start": 0.5, "end": 0.9}}
  ],
  "scenes": [
    {{"visual_search": "ancient statue dark marble", "narration": "..."}}
  ]
}}
"""

    candidate_models = ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-2.5-flash"]
    response = None
    last_err = None

    for model_name in candidate_models:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[
                    types.Part.from_bytes(data=audio_bytes, mime_type=mime),
                    prompt
                ],
                config=types.GenerateContentConfig(response_mime_type="application/json")
            )
            if response and response.text:
                break
        except Exception as e:
            last_err = e

    if not response or not response.text:
        raise RuntimeError(f"Could not transcribe audio with Gemini: {last_err}")

    raw_text = response.text.strip()
    if raw_text.startswith("```json"):
        raw_text = raw_text[7:]
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]

    data = json.loads(raw_text.strip())
    data["audio_path"] = audio_path
    return data

if __name__ == "__main__":
    test_text = "Most people will never understand why silence is the deadliest weapon in human psychology."
    test_out = TEMP_DIR / "test_voice.mp3"
    result = generate_speech(test_text, test_out)
    print("Voice generated successfully:", result["audio_path"])
    print(f"Captured {len(result['words'])} words and {len(result['sentences'])} sentences.")
    print("Sample words:", result["words"][:4])
