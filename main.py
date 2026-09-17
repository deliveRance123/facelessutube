import sys
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
import uvicorn
from core.config import HOST, PORT, GEMINI_API_KEY, PEXELS_API_KEY, CLIENT_SECRET_FILE
from core.pipeline import generate_video_pipeline

def print_banner():
    print("=" * 65)
    print("  🚀 DELIVERACE • YOUTUBE AUTOMATION PLATFORM (AUTOSHORTS)")
    print("  Dark Psychology & Stoic Life Laws Auto-Pilot")
    print("=" * 65)
    print(f"  ● Gemini API Key:     {'Configured ✓' if GEMINI_API_KEY else 'MISSING ✗'}")
    print(f"  ● Pexels API Key:     {'Configured ✓' if PEXELS_API_KEY else 'MISSING ✗'}")
    print(f"  ● YouTube Secret:     {'Configured ✓' if CLIENT_SECRET_FILE.exists() else 'MISSING ✗'}")
    print(f"  ● Dashboard URL:      http://{HOST}:{PORT}")
    print("=" * 65)

def main():
    print_banner()

    if len(sys.argv) > 1 and sys.argv[1] == "--test-gen":
        print("\n[Mode: Test Generation via CLI]")
        topic = "The Psychology of Controlled Silence"
        metadata = generate_video_pipeline(custom_topic=topic)
        print("\nTest Video Successfully Created!")
        print(f"File: {metadata['video_path']}")
        print(f"Title: {metadata['title']}")
        return

    print("\nStarting Deliverace Web Server...")
    print(f"Open your browser and navigate to: http://{HOST}:{PORT}\n")
    uvicorn.run("web.app:app", host=HOST, port=PORT, reload=False)

if __name__ == "__main__":
    main()
