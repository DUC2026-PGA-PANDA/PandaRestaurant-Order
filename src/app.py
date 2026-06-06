"""Project entry point wrapper kept under `src/`.

This file wraps the existing `backend.app` implementation so the project
follows the requested `src/` layout without requiring a full rewrite.
"""
try:
    from backend.app import app  # existing Flask app
except Exception:
    app = None

try:
    from backend.telegram_bot import start_bot_thread
except Exception:
    start_bot_thread = None

def run(host='0.0.0.0', port=5000, debug=False):
    if app is None:
        print('App not available')
        return

    print("\n" + "="*60)
    print("🐼 PANDA RESTAURANT - Full System")
    print("="*60)
    print("🌐 Server: http://localhost:5000")
    print("📱 Menu: http://localhost:5000/mobile-menu")
    print("http://localhost:5000/admin")
    print("💾 Backup: http://localhost:5000/backup")
    print("="*60 + "\n")

    if start_bot_thread:
        try:
            start_bot_thread()
            print("🤖 Telegram bot thread started.")
        except Exception as e:
            print(f"⚠️ Failed to start bot thread: {e}")

    app.run(host=host, port=port, debug=debug)

if __name__ == '__main__':
    run()
