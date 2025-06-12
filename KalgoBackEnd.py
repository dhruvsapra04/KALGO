import pandas as pd
import numpy as np
from sqlalchemy import create_engine
from alpaca_trade_api.rest import REST
import mysql.connector

# ==== Alpaca API Credentials ====
ALPACA_API_KEY = 'Aplaca key'
ALPACA_SECRET_KEY = 'Our alpaca key'
BASE_URL = 'https://paper-api.alpaca.markets'

# ==== MySQL Database Credentials ====
MYSQL_USER = 'root'
MYSQL_PASSWORD = 'your_password'
MYSQL_HOST = 'localhost'
MYSQL_DB = 'stock_db'

# ==== List of Stock Tickers ====
tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA']

# ==== Connect to Alpaca ====
api = REST(ALPACA_API_KEY, ALPACA_SECRET_KEY, BASE_URL)

# ==== Fetch Latest Trades ====
trades = api.get_latest_trade_many(tickers)

# ==== Format the Data ====
data = []
for symbol, trade in trades.items():
    data.append({
        'symbol': symbol,
        'price': trade.price,
        'timestamp': trade.timestamp
    })

df = pd.DataFrame(data)

# ==== Save Data to MySQL ====
engine = create_engine(f'mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}/{MYSQL_DB}')
df.to_sql('stock_prices', con=engine, if_exists='append', index=False)
print("✔️ Stock data saved to MySQL.")

# ==== Connect using mysql-connector for analysis ====
conn = mysql.connector.connect(
    host=MYSQL_HOST,
    user=MYSQL_USER,
    password=MYSQL_PASSWORD,
    database=MYSQL_DB
)
cursor = conn.cursor()

# ==== Bollinger Bands Calculation ====
def get_bollinger_bands(symbol, cursor):
    query = """
        SELECT price
        FROM stock_prices
        WHERE symbol = %s
        ORDER BY timestamp DESC
        LIMIT 7800
    """
    cursor.execute(query, (symbol,))
    rows = cursor.fetchall()
    prices = [row[0] for row in rows]

    if len(prices) < 7800:
        return None

    prices.reverse()  # Oldest to newest
    sma = np.mean(prices)
    std = np.std(prices)
    upper = sma + 2 * std
    lower = sma - 2 * std
    return sma, upper, lower

# ==== Check for Bollinger Signal ====
def check_bollinger_signal(symbol, cursor, is_held=False):
    cursor.execute("""
        SELECT price
        FROM stock_prices
        WHERE symbol = %s
        ORDER BY timestamp DESC
        LIMIT 1
    """, (symbol,))
    row = cursor.fetchone()
    if not row:
        return

    current_price = row[0]
    bands = get_bollinger_bands(symbol, cursor)
    if bands is None:
        return

    sma, upper, lower = bands

    print(f"{symbol}: Price={current_price:.2f}, SMA={sma:.2f}, Upper={upper:.2f}, Lower={lower:.2f}")

    if current_price < lower and not is_held:
        print(f"🔻 Buy signal for {symbol} (Price hit lower band)")
    elif current_price > upper and is_held:
        print(f"🔺 Sell signal for {symbol} (Price hit upper band)")

# ==== Run Bollinger Signal Checks ====
for ticker in tickers:
    check_bollinger_signal(ticker, cursor)

# ==== Cleanup ====
cursor.close()
conn.close()
