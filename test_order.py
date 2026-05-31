# -*- coding: utf-8 -*-
"""
MT5 Order Test -- Places a real MARKET BUY on XAUUSD (0.02 lot demo)
then immediately closes it.
Run: py test_order.py
"""
import sys
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import os
import sys
import time
from dotenv import load_dotenv
import MetaTrader5 as mt5

load_dotenv()

LOGIN = int(os.getenv("MT5_LOGIN", "0"))
PASSWORD = os.getenv("MT5_PASSWORD", "")
SERVER = os.getenv("MT5_SERVER", "")
SYMBOL = "XAUUSD"
LOT = 0.02
MAGIC = 234001


def check(label, ok, detail=""):
    icon = "✅" if ok else "❌"
    print(f"  {icon} {label}" + (f": {detail}" if detail else ""))
    return ok


def connect():
    print("\n[1/5] Connecting to MT5...")
    if not mt5.initialize():
        check("MT5 initialize", False, str(mt5.last_error()))
        sys.exit(1)
    check("MT5 initialize", True)

    authorized = mt5.login(login=LOGIN, password=PASSWORD, server=SERVER)
    if not authorized:
        check("MT5 login", False, str(mt5.last_error()))
        mt5.shutdown()
        sys.exit(1)

    info = mt5.account_info()
    check("MT5 login", True, f"Account #{info.login} | Balance: ${info.balance:.2f} {info.currency}")
    return info


def get_tick():
    print(f"\n[2/5] Getting live tick for {SYMBOL}...")
    # Make sure symbol is visible
    if not mt5.symbol_select(SYMBOL, True):
        check("Symbol select", False, str(mt5.last_error()))
        return None

    tick = mt5.symbol_info_tick(SYMBOL)
    if tick is None:
        check("Get tick", False, str(mt5.last_error()))
        return None

    check("Get tick", True, f"Bid: {tick.bid} | Ask: {tick.ask} | Spread: {round((tick.ask - tick.bid)*10, 1)}pts")
    return tick


def place_order(tick):
    print(f"\n[3/5] Placing MARKET BUY {LOT} lot @ {tick.ask}...")

    # Get symbol filling mode
    sym_info = mt5.symbol_info(SYMBOL)
    filling = mt5.ORDER_FILLING_IOC
    if sym_info:
        modes = sym_info.filling_mode
        if modes & 1:
            filling = mt5.ORDER_FILLING_FOK
        elif modes & 2:
            filling = mt5.ORDER_FILLING_IOC
        else:
            filling = mt5.ORDER_FILLING_RETURN

    sl = round(tick.ask - 20.0, 2)    # 20pt SL
    tp = round(tick.ask + 30.0, 2)    # 30pt TP

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": LOT,
        "type": mt5.ORDER_TYPE_BUY,
        "price": tick.ask,
        "sl": sl,
        "tp": tp,
        "deviation": 30,
        "magic": MAGIC,
        "comment": "goldbot_test",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": filling,
    }

    print(f"  Request: BUY {LOT} {SYMBOL} @ {tick.ask} | SL: {sl} | TP: {tp}")
    result = mt5.order_send(request)

    if result is None:
        check("Order send", False, str(mt5.last_error()))
        return None

    if result.retcode == mt5.TRADE_RETCODE_DONE:
        check("Order FILLED", True, f"Ticket: {result.order} | Fill price: {result.price}")
    else:
        check("Order result", False, f"retcode={result.retcode} | {result.comment}")
        return None

    return result


def verify_position(ticket):
    print(f"\n[4/5] Verifying open position ticket {ticket}...")
    time.sleep(1)
    positions = mt5.positions_get(ticket=ticket)
    if positions:
        pos = positions[0]
        check("Position visible", True,
              f"Ticket: {pos.ticket} | {pos.volume} lots @ {pos.price_open} | PnL: ${pos.profit:.2f}")
        return pos
    else:
        check("Position visible", False, "Not found in positions list")
        return None


def close_position(ticket):
    print(f"\n[5/5] Closing position {ticket}...")
    positions = mt5.positions_get(ticket=ticket)
    if not positions:
        check("Position found for close", False)
        return

    pos = positions[0]
    tick = mt5.symbol_info_tick(SYMBOL)

    sym_info = mt5.symbol_info(SYMBOL)
    filling = mt5.ORDER_FILLING_IOC
    if sym_info:
        modes = sym_info.filling_mode
        if modes & 1:
            filling = mt5.ORDER_FILLING_FOK
        elif modes & 2:
            filling = mt5.ORDER_FILLING_IOC
        else:
            filling = mt5.ORDER_FILLING_RETURN

    close_price = tick.bid  # Close BUY at Bid

    close_req = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": SYMBOL,
        "volume": pos.volume,
        "type": mt5.ORDER_TYPE_SELL,
        "position": ticket,
        "price": close_price,
        "deviation": 30,
        "magic": MAGIC,
        "comment": "goldbot_test_close",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": filling,
    }

    result = mt5.order_send(close_req)
    if result and result.retcode == mt5.TRADE_RETCODE_DONE:
        check("Position closed", True, f"Close price: {result.price} | PnL: ${pos.profit:.2f}")
    else:
        check("Position closed", False,
              f"retcode={result.retcode if result else '?'} | {result.comment if result else mt5.last_error()}")


if __name__ == "__main__":
    print("=" * 60)
    print("  MT5 ORDER EXECUTION TEST — DEMO ACCOUNT")
    print("  This will place a 0.02 lot BUY and immediately close it.")
    print("=" * 60)

    account = connect()
    tick = get_tick()
    if tick is None:
        mt5.shutdown()
        sys.exit(1)

    result = place_order(tick)
    if result is None:
        mt5.shutdown()
        sys.exit(1)

    ticket = result.order
    pos = verify_position(ticket)

    time.sleep(2)  # Let it breathe

    close_position(ticket)

    mt5.shutdown()

    print("\n" + "=" * 60)
    print("  🟢 MT5 ORDER TEST COMPLETE")
    print("  The bot CAN place and close orders on your demo account.")
    print("=" * 60)
