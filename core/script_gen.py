import json
import re
import random
import urllib.request
import urllib.error
from core.config import GEMINI_API_KEY, NICHE

# Curated Seed Fallbacks (used only if offline or API quota delay occurs)
SEED_PSYCHOLOGY_TOPICS = [
    "The Law of Controlled Silence: Why remaining quiet in an argument disarms your opponent instantly",
    "The Power of Strategic Absence: Why being less available makes people respect and desire your presence",
    "Emotional Detachment: The dark art of never letting someone else control your pulse or reactions",
    "The Mirror Trap: How reflecting someone's exact energy reveals their hidden motives",
    "The Art of Under-Speaking: Why powerful people say less than necessary",
    "Calculated Mystery: Why unpredictable people command subconscious fear and authority",
    "The Illusion of Agreement: How nodding silently makes people reveal their secrets without realizing it",
    "The Law of Never Complaining: Why silence in pain builds an aura of invincibility",
    "The Reverse Psychology of Respect: Why people only value the boundaries you strictly enforce",
    "The Observer Paradox: How listening reveals the hidden insecurities of the loudest person in the room"
]

SEED_TECH_TOPICS = [
    "The Living GPU: Why tech giants are secretly replacing silicon chips with living human brain neurons",
    "Autonomous AI Swarms: How one developer deployed 50 self-governing AI agents and built a software empire",
    "The Death of Search Engines: Why conversational AI agents just made web browsers obsolete",
    "Quantum Decryption: How a 10-second quantum experiment just threatened 30 years of global internet security",
    "Humanoid Assembly Lines: Why Figure 02 and Optimus robots are quietly taking over physical labor",
    "The Energy Crisis of Artificial Intelligence: Why tech giants are purchasing nuclear reactors for data centers"
]

def call_gemini_api(prompt: str) -> str:
    """Direct REST call to Gemini 3.6 Flash. Pure Python, zero C-extensions, fully resilient."""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY is not set in .env")

    candidate_models = ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.1-flash-lite"]
    last_err = None

    for model in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        payload = json.dumps({
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.7}
        }).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts and "text" in parts[0]:
                        return parts[0]["text"]
        except Exception as e:
            last_err = e
            continue

    raise RuntimeError(f"Could not generate content from Gemini API: {last_err}")

def discover_viral_topic_with_ai(niche: str = "story", recent_titles: list = None) -> dict:
    """
    Autonomous multi-niche creative story & viral video strategist.
    Supports any niche: Cartoon, Sci-Fi, Movie, Anime, Tech, Crime, Psychology, History, or Custom.
    """
    import datetime
    now = datetime.datetime.now()
    calendar_context = f"Current Real-World Calendar Date: {now.strftime('%B %d, %Y')}"
    
    avoid_clause = ""
    if recent_titles:
        sample_recent = recent_titles[:8]
        avoid_clause = f"AVOID repeating these recent topics:\n" + "\n".join(f"- {t}" for t in sample_recent) + "\n"

    research_prompt = f"""You are a master creative director, screenwriter, and viral video strategist.
Niche / Style: {niche.upper()}
{calendar_context}

Your Goal:
Formulate ONE 100% ORIGINAL, captivating, ultra-high viral retention story or topic premise tailored specifically to the '{niche}' genre (e.g. story, cartoon, sci-fi, anime, movie, tech, mystery, psychology).

{avoid_clause}
VIRAL RETENTION RULES:
1. Create an instant emotional hook or curiosity gap within the first 2 seconds.
2. Deliver vivid cinematic drama, humor, wonder, or suspense.
3. Tailor vocabulary and tone perfectly to the '{niche}' genre.

Return ONLY a valid JSON object matching this structure:
{{
    "topic": "The captivating topic title / story premise",
    "hook_angle": "Why this story grips viewers immediately",
    "visual_theme": "cinematic visual styling for images"
}}
"""
    try:
        raw_resp = call_gemini_api(research_prompt)
        match = re.search(r'\{.*\}', raw_resp, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        print(f"Notice: Gemini topic discovery fallback used ({e})")

    return {
        "topic": f"A Gripping {niche.title()} Journey",
        "hook_angle": "High tension and suspense from the opening line",
        "visual_theme": f"cinematic {niche} high detail"
    }

def generate_multi_scene_story(
    prompt: str,
    niche: str = "story",
    format_type: str = "short",
    num_scenes: int = 4
) -> dict:
    """
    Generates a structured, scene-by-scene story script tailored for multi-image synchronization.
    Each scene corresponds directly to an uploaded or generated image.
    """
    duration_guide = "30 to 50 seconds total" if format_type == "short" else "2 to 3 minutes total"
    
    system_prompt = f"""You are an elite screenwriter and animated video director.
Genre / Niche: {niche.upper()}
Format: {format_type.upper()} ({duration_guide})
Required Scenes: EXACTLY {num_scenes} sequential scenes.

User Prompt / Premise:
"{prompt}"

Your Task:
Create a cohesive, immersive story script divided into exactly {num_scenes} scene beats that match sequential visual images (characters, action, environment).

Script Requirements:
1. Scene 1 MUST be a high-stakes hook that grabs attention instantly.
2. Scenes must flow seamlessly from one to the next in chronological order.
3. Total spoken narration must match {duration_guide}.
4. Do NOT include sound effect brackets or narrator labels in narration.
5. Visual descriptions MUST depict REAL LIVING HUMAN CHARACTERS and photorealistic cinematic scenes. NEVER depict stone statues, marble busts, ruins, or sculptures.

Return ONLY a valid JSON object matching this schema:
{{
    "title": "Compelling Title for this Story",
    "description": "Engaging description with relevant hashtags",
    "tags": ["story", "{niche}", "viral", "animation"],
    "hook": "The first 1-2 gripping opening sentences",
    "full_narration": "Full narration text combining all scenes into one continuous spoken script",
    "scenes": [
        {{
            "scene_index": 0,
            "narration": "Narration text for scene 1",
            "image_description": "Visual prompt describing the image for this scene"
        }}
    ]
}}
"""
    raw_response = call_gemini_api(system_prompt)
    clean_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
    if clean_match:
        try:
            return json.loads(clean_match.group())
        except json.JSONDecodeError:
            pass

    # Fallback
    return {
        "title": prompt.title()[:60],
        "description": f"An immersive {niche} story.",
        "tags": ["story", niche],
        "hook": prompt,
        "full_narration": prompt,
        "scenes": [{"scene_index": i, "narration": f"Scene {i+1} of the story.", "image_description": niche} for i in range(num_scenes)]
    }

def generate_video_script(custom_topic: str = None, format_type: str = "short", niche: str = "psychology", recent_titles: list = None) -> dict:
    """
    Generates an ultra-high viral retention script tailored to the chosen niche:
    niche: 'psychology' (Dark Psychology & Stoic Life Laws) or 'tech' (AI, Robotics & Future Tech).
    format_type: 'short' (35-45s vertical) or 'long' (3-5 mins horizontal documentary).
    If custom_topic is empty, dynamically uses AI Researcher to find the freshest viral topic.
    """
    is_tech = (niche.lower() == "tech")
    
    if not custom_topic or not custom_topic.strip():
        print(f"[Deliverace Engine] 🔍 AI Researcher is searching for today's highest-converting viral {niche} topic...")
        topic_info = discover_viral_topic_with_ai(niche=niche, recent_titles=recent_titles)
        chosen_topic = topic_info.get("topic")
    else:
        chosen_topic = custom_topic.strip()
    
    if is_tech:
        if format_type == "long":
            topic_clause = f"Core Subject: {chosen_topic}\nFocus: Mind-bending technological revelations, future forecasting, high retention cliffhangers, and urgent tech implications."
            duration_desc = "3 to 4 minutes high-octane tech documentary video script (16:9 horizontal)"
            scenes_count = "8 to 10 deep chapters with fast, engaging pacing"
        else:
            topic_clause = f"Core Subject: {chosen_topic}\nFocus: Shocking technological hook in the first 2.5 seconds, rapid-fire facts, zero fluff, ultra-high viral retention."
            duration_desc = "35-45 second script for a YouTube Short (vertical 9:16)"
            scenes_count = "4 to 6 concise scenes"

        prompt = f"""
You are the world's top viral scriptwriter for Future Tech, Artificial Intelligence, Robotics, and Silicon Valley innovations.
{topic_clause}

Create an electrifying, 100% ORIGINAL and ACCURATE {duration_desc}.
Target audience: curious, ambitious tech enthusiasts, developers, and futurists.

VIRAL TECH RULES:
1. The script MUST BE 100% ORIGINAL with breathtaking, mind-expanding tech insights.
2. The HOOK must stop scrolling instantly in the first 3 seconds with a shocking fact or paradigm shift.
3. The tone must be authoritative, urgent, cinematic, and fascinating.
4. Provide {scenes_count}. Each scene has narration text and high-impact visual search keywords suitable for Pexels stock video search (e.g. 'server room glowing blue', 'humanoid robot futuristic', 'microchip processor macro', 'cyberpunk city neon rain').
5. The ending must have a sharp, punchy call to action to subscribe.

Return ONLY a valid JSON object matching this exact structure:
{{
    "title": "A Magnetic Tech Title ⚡ #shorts",
    "description": "Original YouTube description with #tech #ai #robotics #futuretech #innovation",
    "tags": ["tech", "artificial intelligence", "future tech", "ai", "robotics", "singularity", "innovation"],
    "hook": "Opening intriguing line...",
    "scenes": [
        {{
            "narration": "Scene narration text...",
            "visual_search": "server room glowing blue"
        }}
    ],
    "full_narration": "Full combined text for speech synthesis..."
}}
"""
    else:
        if format_type == "long":
            topic_clause = f"Core Subject: {chosen_topic}\nFocus: High viral retention, cliffhangers, and deep psychological revelations that keep viewers watching until the final second."
            duration_desc = "3 to 4 minutes in-depth documentary video script (16:9 horizontal)"
            scenes_count = "8 to 10 deep chapters with rich explanations"
        else:
            topic_clause = f"Core Subject: {chosen_topic}\nFocus: Shocking psychological hook in first 3 seconds, ultra-fast pacing, zero fluff, high retention."
            duration_desc = "35-45 second script for a YouTube Short (vertical 9:16)"
            scenes_count = "4 to 6 concise scenes"
        
        prompt = f"""
You are the world's most elite, original scriptwriter for Dark Psychology, Human Behavior, and Stoicism videos.
{topic_clause}

Create an electrifying, 100% ORIGINAL and UNIQUE {duration_desc}.
Target audience: ambitious people who want to master human dynamics, respect, and self-control.

CRITICAL ANTI-DUPLICATION RULES (YOUTUBE POLICY COMPLIANT):
1. The script MUST BE 100% ORIGINAL. Do NOT use generic internet clichés or copied quotes.
2. Use sharp, psychological insight, original metaphors, and deep philosophical storytelling.
3. The HOOK must be unforgettable, shocking, or deeply intriguing in the first 5 seconds.
4. The tone must be calm, serious, mature, and deeply psychological—like a high-end cinematic documentary.
5. Provide {scenes_count}. Each scene has narration text and high-impact visual search keywords. CRITICAL: ABSOLUTELY NEVER use statues, marble busts, stone carvings, sculptures, or museum relics. ALWAYS use real living human beings and modern cinematic scenes (e.g. 'sharp portrait African man studio lighting 4k', 'confident Black woman entrepreneur sharp focus', 'modern sleek executive office high definition', 'cinematic urban Lagos golden hour', 'thoughtful leader portrait dramatic lighting', 'real human face expressive eyes cinematic 4k').
6. The ending must have a sharp, punchy call to action to subscribe or follow.

Return ONLY a valid JSON object matching this exact structure:
{{
    "title": "A Magnetic, Click-Worthy Title",
    "description": "Original description with #mindset #leadership #story #growth",
    "tags": ["mindset", "human behavior", "psychology", "storytelling", "wisdom"],
    "hook": "Opening intriguing line...",
    "scenes": [
        {{
            "narration": "Scene narration text...",
            "visual_search": "sharp African man portrait studio lighting 4k"
        }}
    ],
    "full_narration": "Full combined text for speech synthesis..."
}}
"""

    raw_text = call_gemini_api(prompt)
    clean_text = raw_text.strip()
    if clean_text.startswith("```"):
        clean_text = re.sub(r"^```(?:json)?", "", clean_text)
        clean_text = re.sub(r"```$", "", clean_text)
        clean_text = clean_text.strip()

    data = json.loads(clean_text)
    
    if "full_narration" not in data or not data["full_narration"]:
        data["full_narration"] = " ".join(scene["narration"] for scene in data.get("scenes", []))
        
    return data
