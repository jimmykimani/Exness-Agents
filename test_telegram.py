# -*- coding: utf-8 -*-
"""
Telegram Diagnostic Test
Checks: bot reachable, chat ID correct, message sending, getUpdates polling.
Run: py test_telegram.py
"""
import sys
import os
import requests

# Fix Windows cp1252 emoji crash
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv()

TOKEN  = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
BASE   = f"https://api.telegram.org/bot{TOKEN}"


def check(label, ok, detail=""):
    icon = "[OK]" if ok else "[FAIL]"
    line = f"  {icon} {label}"
    if detail:
        line += f": {detail}"
    print(line)
    return ok


# ─── 1. Bot identity ────────────────────────────────────────────
def test_bot_info():
    print("\n[1/4] Bot Identity")
    r = requests.get(f"{BASE}/getMe", timeout=10)
    data = r.json()
    if data.get("ok") and data.get("result"):
        bot = data["result"]
        check("Bot reachable", True, f"@{bot['username']} | {bot['first_name']}")
        return True
    check("Bot reachable", False, data.get("description", "Unknown error"))
    return False


# ─── 2. Send a message ──────────────────────────────────────────
def test_send_message():
    print("\n[2/4] Send Test Message")
    if not CHAT_ID:
        check("TELEGRAM_CHAT_ID set", False, "Empty in .env")
        return False
    payload = {
        "chat_id": CHAT_ID,
        "text": "\U0001f916 <b>Goldbot Diagnostic</b>\n\nTelegram connection confirmed!",
        "parse_mode": "HTML"
    }
    r = requests.post(f"{BASE}/sendMessage", json=payload, timeout=10)
    data = r.json()
    ok = data.get("ok", False)
    check("Message sent", ok,
          f"Chat ID: {CHAT_ID}" if ok else data.get("description", ""))
    return ok


# ─── 3. Poll updates ────────────────────────────────────────────
def test_get_updates():
    print("\n[3/4] getUpdates — Check incoming commands work")
    r = requests.get(f"{BASE}/getUpdates", params={"limit": 5, "timeout": 3}, timeout=10)
    data = r.json()
    if not data.get("ok"):
        check("getUpdates", False, data.get("description", ""))
        return False

    updates = data.get("result", [])
    check("getUpdates working", True, f"{len(updates)} pending updates")

    if updates:
        print("  Last messages received by bot:")
        for u in updates[-3:]:
            if "message" in u:
                msg     = u["message"]
                sender  = msg.get("from", {}).get("username", "unknown")
                text    = msg.get("text", "(no text)")
                chat_id = msg.get("chat", {}).get("id", "?")
                match   = "(MATCH)" if str(chat_id) == str(CHAT_ID) else f"(MISMATCH - expected {CHAT_ID})"
                print(f"    From @{sender} | chat_id={chat_id} {match} | text={text!r}")
    else:
        print("  (No pending messages - send /status to the bot first)")
    return True


# ─── 4. Inline keyboard ─────────────────────────────────────────
def test_inline_keyboard():
    print("\n[4/4] Inline Keyboard Button Test")
    markup = {
        "inline_keyboard": [[
            {"text": "APPROVE", "callback_data": "approve_setup"},
            {"text": "REJECT",  "callback_data": "reject_setup"},
            {"text": "SKIP",    "callback_data": "skip_setup"},
        ]]
    }
    payload = {
        "chat_id": CHAT_ID,
        "text": (
            "\U0001f3af <b>TEST SETUP ALERT</b>\n\n"
            "BUY XAUUSD @ 4540.00\n"
            "SL: 4530 | TP1: 4550 | TP3: 4570\n\n"
            "Tap a button to test callback routing:"
        ),
        "parse_mode": "HTML",
        "reply_markup": markup
    }
    r = requests.post(f"{BASE}/sendMessage", json=payload, timeout=10)
    data = r.json()
    ok = data.get("ok", False)
    check("Inline keyboard sent", ok,
          "Check Telegram now!" if ok else data.get("description", ""))
    return ok


if __name__ == "__main__":
    print("=" * 55)
    print("  TELEGRAM AGENT DIAGNOSTIC")
    print("=" * 55)
    token_preview = f"...{TOKEN[-10:]}" if len(TOKEN) > 10 else TOKEN
    print(f"  Token : {token_preview}")
    print(f"  ChatID: {CHAT_ID}")

    all_ok  = test_bot_info()
    all_ok &= test_send_message()
    all_ok &= test_get_updates()
    test_inline_keyboard()

    print("\n" + "=" * 55)
    if all_ok:
        print("  ALL CHECKS PASSED - Telegram is fully operational!")
    else:
        print("  ISSUES FOUND - fixes:")
        print("  1. Wrong Chat ID? Send /start to the bot, re-run and")
        print("     check [3/4] output for your real chat_id.")
        print("  2. Commands not working? Make sure only ONE process is")
        print("     running getUpdates at a time (no duplicate bots).")
    print("=" * 55)
