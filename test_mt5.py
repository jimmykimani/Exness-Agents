import os
import sys
from dotenv import load_dotenv
import MetaTrader5 as mt5

def test_connection():
    print("Loading .env file...")
    load_dotenv()
    
    login = int(os.getenv("MT5_LOGIN", "0"))
    password = os.getenv("MT5_PASSWORD", "")
    server = os.getenv("MT5_SERVER", "")
    
    print(f"Connecting to MT5...")
    print(f"Login: {login}")
    print(f"Server: {server}")
    
    if not mt5.initialize():
        print(f"initialize() failed, error code: {mt5.last_error()}")
        sys.exit(1)
        
    authorized = mt5.login(login=login, password=password, server=server)
    
    if authorized:
        print("SUCCESS: Connected to MT5 and authorized!")
        account_info = mt5.account_info()
        if account_info:
            print(f"Balance: {account_info.balance} {account_info.currency}")
            print(f"Equity: {account_info.equity}")
            print(f"Leverage: {account_info.leverage}")
    else:
        print(f"FAILED to authorize. Error code: {mt5.last_error()}")
        
    mt5.shutdown()

if __name__ == "__main__":
    test_connection()
