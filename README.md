# facelessutube • Deliverace AI Video Platform & Studio

Deliverace is an autonomous AI-powered faceless video generation platform and CapCut-style multi-clip sequence editor designed for short-form (YouTube Shorts, TikTok, Instagram Reels) and long-form video creation.

Built with high-speed native video concatenation, neural speech synthesis, 4K photorealistic visual generation, and zero watermarks.

---

## 🚀 Key Features

### 1. ✂️ CapCut Multi-Clip Sequence Studio
- **Multi-Video Joining**: Import multiple video files (`.mp4`, `.mov`, `.webm`, `.mkv`) or library assets into a sequential timeline.
- **Precision Trimming & Reordering**: Move clips up/down, set millisecond in/out points, and inspect playhead timestamps.
- **`✂️ Split at Playhead`**: Split any active clip into two independent segments on the fly.
- **100% Free Plan**: Unrestricted timeline editing with zero export watermarks.

### 2. 🎙️ Automatic Long Narration & Audio Studio
- **AI Speech Synthesis**: Type or paste complete voiceover scripts (hundreds of words) directly in the editor.
- **Multi-Voice Roster**: High-definition neural voices (Stoic, Cinema, British, Narrative) with instant audio previews.
- **Multi-Track Volume Mixing**: Independent volume controls for Master Narration (0–150%), Video Original Sound (ducked), and Background Ambient Music (0–100%).

### 3. 🎨 4K Photorealistic Visual Engine
- **Lifelike Human Photography**: Enforces real living human beings (authentic skin pores, natural expressive eyes, modern studio rim lighting, 85mm portrait cinematography).
- **Anti-Statue / Relic Filter**: Strict automated ban against stone statues, marble busts, ruins, or museum relics.
- **100% Clean Video Frames**: Native edge post-processing guarantees zero watermarks across all visual generations.

### 4. ⚡ Autonomous Video Pipeline
- **One-Click Generation**: End-to-end automated scriptwriting, speech synthesis, B-roll sourcing, dynamic camera motion, kinetic subtitle burn-in, and ambient music mastering.
- **Sub-30s Render Times**: Hardware-accelerated processing engine.

### 5. 🛡️ Isolated Standalone Admin Portal
- **Zero Admin Exposure**: Standard creator dashboard (`/dashboard`) contains zero administrative links or tabs.
- **Dedicated Admin Login**: [`/admin/login`](http://127.0.0.1:8000/admin/login) with isolated authentication.
- **Governance Console**: [`/admin`](http://127.0.0.1:8000/admin) featuring user directory, subscription tier manager (`Free`, `Pro`, `Enterprise`), and global platform subscription mode toggle.

---

## 🛠️ Tech Stack & Requirements

- **Backend**: Python 3.10+ / FastAPI & Starlette / Uvicorn
- **Rendering Engine**: Native FFmpeg with GPU/CPU acceleration
- **Voice Synthesis**: Neural TTS & ElevenLabs BYOK Integration
- **Database**: PostgreSQL (Neon Cloud) with SQLite fallback

---

## 💻 Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/deliveRance123/facelessutube.git
cd facelessutube
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` and insert your API keys:
```bash
cp .env.example .env
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Launch the Server
```bash
python -m uvicorn web.app:app --host 127.0.0.1 --port 8000
```
Open **`http://127.0.0.1:8000`** in your browser.

---

## 📄 License
MIT License. Free for creators and commercial video production.
