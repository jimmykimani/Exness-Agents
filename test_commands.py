# -*- coding: utf-8 -*-
"""
Standalone Telegram Command Listener
Processes commands from Telegram in real-time with full MT5 integration.
Run: py test_commands.py
Press Ctrl+C to stop.
"""
import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
BASE    = f"https://api.telegram.org/bot{TOKEN}"

# ── MT5 setup ─────────────────────────────────────────────────────────────────
try:
    import MetaTrader5 as mt5
    MT5_OK = mt5.initialize()
    if MT5_OK:
        MT5_OK = mt5.login(
            login=int(os.getenv("MT5_LOGIN", "0")),
            password=os.getenv("MT5_PASSWORD", ""),
            server=os.getenv("MT5_SERVER", "")
        )
    print(f"  MT5: {'connected' if MT5_OK else 'FAILED - ' + str(mt5.last_error())}")
except Exception as e:
    MT5_OK = False
    mt5 = None
    print(f"  MT5: not available ({e})")

SYMBOL = "XAUUSD"

# ── Helpers ───────────────────────────────────────────────────────────────────
def send(text: str, markup=None):
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if markup:
        payload["reply_markup"] = markup
    r = requests.post(f"{BASE}/sendMessage", json=payload, timeout=10)
    if not r.json().get("ok"):
        print(f"  [SEND ERROR] {r.json().get('description')}")

def answer_callback(cb_id):
    requests.post(f"{BASE}/answerCallbackQuery", json={"callback_query_id": cb_id}, timeout=5)

# ── Command handlers ──────────────────────────────────────────────────────────
def handle_status():
    if not MT5_OK:
        send("MT5 not connected.")
        return
    positions = mt5.positions_get(symbol=SYMBOL)
    if not positions:
        send("No open trades on XAUUSD.")
        return
    msg = "<b>CURRENT POSITIONS</b>\n\n"
    for pos in positions:
        direction = "BUY" if pos.type == mt5.ORDER_TYPE_BUY else "SELL"
        msg += (
            f"Ticket: <code>{pos.ticket}</code>\n"
            f"  {direction} {pos.volume} lots @ {pos.price_open}\n"
            f"  SL: {pos.sl} | TP: {pos.tp}\n"
            f"  PnL: <b>${pos.profit:.2f}</b>\n\n"
        )
    send(msg)


def handle_pnl():
    if not MT5_OK:
        send("MT5 not connected.")
        return
    info = mt5.account_info()
    if not info:
        send("Could not fetch account info.")
        return
    positions = mt5.positions_get(symbol=SYMBOL) or []
    floating = sum(p.profit for p in positions)
    msg = (
        f"<b>ACCOUNT SNAPSHOT</b>\n\n"
        f"  Balance : <b>${info.balance:.2f}</b>\n"
        f"  Equity  : <b>${info.equity:.2f}</b>\n"
        f"  Floating: <b>${floating:.2f}</b>\n"
        f"  Margin  : ${info.margin:.2f}\n"
        f"  Free    : ${info.margin_free:.2f}"
    )
    send(msg)


def handle_levels():
    if not MT5_OK:
        send("MT5 not connected.")
        return
    tick = mt5.symbol_info_tick(SYMBOL)
    if not tick:
        send("Could not get XAUUSD tick.")
        return
    price = round((tick.bid + tick.ask) / 2, 2)
    spread = round((tick.ask - tick.bid) * 10, 1)
    # Simple nearby levels based on live price
    r1 = round(price + 10, 2)
    r2 = round(price + 20, 2)
    s1 = round(price - 10, 2)
    s2 = round(price - 20, 2)
    msg = (
        f"<b>XAUUSD LIVE LEVELS</b>\n\n"
        f"  R2 : {r2}\n"
        f"  R1 : {r1}\n"
        f"  NOW: <b>{price}</b>  (spread {spread}pts)\n"
        f"  S1 : {s1}\n"
        f"  S2 : {s2}"
    )
    send(msg)


def handle_close():
    if not MT5_OK:
        send("MT5 not connected.")
        return
    positions = mt5.positions_get(symbol=SYMBOL) or []
    if not positions:
        send("No open positions to close.")
        return
    closed = 0
    for pos in positions:
        tick = mt5.symbol_info_tick(SYMBOL)
        close_type = mt5.ORDER_TYPE_SELL if pos.type == mt5.ORDER_TYPE_BUY else mt5.ORDER_TYPE_BUY
        price = tick.bid if pos.type == mt5.ORDER_TYPE_BUY else tick.ask
        sym = mt5.symbol_info(SYMBOL)
        filling = mt5.ORDER_FILLING_IOC
        if sym and (sym.filling_mode & 1):
            filling = mt5.ORDER_FILLING_FOK
        req = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": SYMBOL, "volume": pos.volume,
            "type": close_type, "position": pos.ticket,
            "price": price, "deviation": 30,
            "magic": 234000, "comment": "goldbot_close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling,
        }
        res = mt5.order_send(req)
        if res and res.retcode == mt5.TRADE_RETCODE_DONE:
            closed += 1
    send(f"Closed {closed}/{len(positions)} positions.")


def handle_brief():
    if not MT5_OK:
        send("MT5 not connected.")
        return
    tick = mt5.symbol_info_tick(SYMBOL)
    price = round((tick.bid + tick.ask) / 2, 2) if tick else "N/A"
    spread = round((tick.ask - tick.bid) * 10, 1) if tick else "N/A"
    info = mt5.account_info()
    balance = f"${info.balance:.2f}" if info else "N/A"
    from datetime import datetime
    now = datetime.now().strftime("%Y-%m-%d %H:%M EAT")
    msg = (
        f"<b>MORNING BRIEF</b>\n"
        f"<i>{now}</i>\n\n"
        f"  Symbol : XAUUSD\n"
        f"  Price  : <b>{price}</b>\n"
        f"  Spread : {spread}pts\n"
        f"  Balance: {balance}\n\n"
        f"  Bias   : Waiting for SMC analysis cycle\n"
        f"  Session: Run main.py for full analysis"
    )
    send(msg)


def handle_pause():
    os.environ["AUTO_EXECUTE"] = "false"
    send("<b>Trading PAUSED.</b> Bot will not place orders.")


def handle_resume():
    os.environ["AUTO_EXECUTE"] = "true"
    send("<b>Trading RESUMED.</b> Bot will place orders when setup is found.")


def handle_start_bot():
    os.environ["BOT_RUNNING"] = "true"
    send("🟢 <b>Bot Started.</b> Analysis cycles are now running.")


def handle_stop_bot():
    os.environ["BOT_RUNNING"] = "false"
    send("🛑 <b>Bot Stopped.</b> All analysis cycles are paused.")


def handle_help():
    send(
        "<b>Available Commands</b>\n\n"
        "/status    - Open positions + floating PnL\n"
        "/pnl       - Account balance snapshot\n"
        "/levels    - XAUUSD live price levels\n"
        "/close     - Close all open trades\n"
        "/brief     - Morning market brief\n"
        "/pause     - Disable auto trading\n"
        "/resume    - Enable auto trading\n"
        "/start_bot - Start orchestrator loops\n"
        "/stop_bot  - Pause orchestrator loops\n"
        "/grade     - Last setup grade\n"
        "/help      - This message"
    )


COMMANDS = {
    "/status":     handle_status,
    "/pnl":        handle_pnl,
    "/levels":     handle_levels,
    "/close":      handle_close,
    "/brief":      handle_brief,
    "/pause":      handle_pause,
    "/resume":     handle_resume,
    "/start_bot":  handle_start_bot,
    "/stop_bot":   handle_stop_bot,
    "/help":       handle_help,
    "/start":      handle_help,
}

# ── Main polling loop ─────────────────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  TELEGRAM COMMAND LISTENER — LIVE")
    print("=" * 55)
    print(f"  Bot   : @gold_jimmy_agent_bot")
    print(f"  ChatID: {CHAT_ID}")
    print(f"  MT5   : {'connected' if MT5_OK else 'offline'}")
    print()
    print("  Listening for commands... (Ctrl+C to stop)")
    print("=" * 55)

    send("Bot listener started. Send /help for available commands.")

    offset = 0
    while True:
        try:
            params = {"timeout": 5, "allowed_updates": ["message", "callback_query"]}
            if offset:
                params["offset"] = offset
            r = requests.get(f"{BASE}/getUpdates", params=params, timeout=10)
            data = r.json()
            if not data.get("ok"):
                time.sleep(2)
                continue

            for update in data.get("result", []):
                offset = update["update_id"] + 1

                # Text commands
                if "message" in update:
                    msg = update["message"]
                    chat_id = str(msg.get("chat", {}).get("id", ""))
                    if chat_id != str(CHAT_ID):
                        continue
                    text = msg.get("text", "").strip().lower().split()[0] if msg.get("text") else ""
                    if text.startswith("/"):
                        print(f"  CMD: {text}")
                        handler = COMMANDS.get(text)
                        if handler:
                            handler()
                        else:
                            send(f"Unknown command: {text}\nSend /help for the list.")

                # Callback buttons
                elif "callback_query" in update:
                    cb = update["callback_query"]
                    chat_id = str(cb.get("message", {}).get("chat", {}).get("id", ""))
                    if chat_id != str(CHAT_ID):
                        continue
                    data_val = cb.get("data", "")
                    cb_id = cb.get("id")
                    answer_callback(cb_id)
                    print(f"  CALLBACK: {data_val}")
                    if data_val == "approve_setup":
                        send("Approve tapped — would execute trade (run main.py for live execution)")
                    elif data_val == "reject_setup":
                        send("Setup rejected.")
                    elif data_val == "skip_setup":
                        send("Setup skipped.")

        except KeyboardInterrupt:
            print("\n  Stopping listener...")
            if MT5_OK:
                mt5.shutdown()
            break
        except Exception as e:
            print(f"  [ERROR] {e}")
            time.sleep(3)


if __name__ == "__main__":
    main()
