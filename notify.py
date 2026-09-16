import os
import requests

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def send(message: str) -> None:
    """Send a Telegram message. Never raises — a notification failure must
    never crash or interrupt the search."""
    if not BOT_TOKEN or not CHAT_ID:
        print(f"[notify] Telegram not configured, message was:\n{message}")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": message},
            timeout=15,
        )
    except Exception as e:
        print(f"[notify] Telegram send failed: {e}")
