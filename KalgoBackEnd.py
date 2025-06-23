import pandas as pd
import numpy as np
import requests
import time
from sqlalchemy import create_engine
import mysql.connector

# ==== Polygon API Key ====
POLYGON_API_KEY = 'Bvc2OpzVeWsfR_L5hORh5daSpdk9_0PE'

# ==== MySQL Database Credentials ====
MYSQL_USER = 'root'
MYSQL_PASSWORD = ''
MYSQL_HOST = 'localhost'
MYSQL_DB = 'stock_db'

# ==== List of Top 50 Blue-Chip Stock Tickers ====
tickers = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'JPM', 'JNJ', 'V',
    'PG', 'UNH', 'HD', 'MA', 'XOM', 'BAC', 'PFE', 'KO', 'CSCO', 'CVX',
    'PEP', 'ABBV', 'T', 'DIS', 'INTC', 'VZ', 'WMT', 'ADBE', 'MRK', 'CMCSA',
    'NFLX', 'CRM', 'NKE', 'MCD', 'TXN', 'ORCL', 'LLY', 'COST', 'IBM', 'ABT',
    'QCOM', 'AVGO', 'AMD', 'UPS', 'SBUX', 'GE', 'CAT', 'GS', 'MS', 'BA'
]

# ==== Fetch Latest Trades using Polygon ====
def get_latest_polygon_trade(symbol):
    url = f"https://api.polygon.io/v2/last/trade/{symbol}?apiKey={POLYGON_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return {
            'symbol': symbol,
            'price': data['trade']['p'],
            'timestamp': pd.to_datetime(data['trade']['t'], unit='ms')
        }
    else:
        print(f"Error fetching {symbol}: {response.status_code}")
        return None

# ==== Collect Data ====
data = []
for symbol in tickers:
    trade = get_latest_polygon_trade(symbol)
    if trade:
        data.append(trade)
    time.sleep(0.25)  # stay under Polygon's free tier rate limits

df = pd.DataFrame(data)

# ==== Save Data to MySQL ====
engine = create_engine(f'mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}/{MYSQL_DB}')

# Save to live_stock_prices and stock_prices
df.to_sql('live_stock_prices', con=engine, if_exists='append', index=False)
df.to_sql('stock_prices', con=engine, if_exists='append', index=False)

# Trim stock_prices to keep only the latest 7800 entries per ticker
with engine.begin() as conn:
    for ticker in tickers:
        conn.execute(f"""
            DELETE FROM stock_prices
            WHERE symbol = '{ticker}'
              AND timestamp NOT IN (
                SELECT timestamp FROM (
                    SELECT timestamp
                    FROM stock_prices
                    WHERE symbol = '{ticker}'
                    ORDER BY timestamp DESC
                    LIMIT 7800
                ) AS sub
            );
        """)

# ==== Compute and Store 20-day SMA ====
for symbol in tickers:
    result = engine.execute(f"""
        SELECT price FROM stock_prices
        WHERE symbol = '{symbol}'
        ORDER BY timestamp DESC
        LIMIT 7800
    """).fetchall()

    if len(result) == 7800:
        prices = [r[0] for r in result][::-1]
        sma_20d = np.mean(prices)
        engine.execute(f"""
            INSERT INTO sma_20d (symbol, sma)
            VALUES ('{symbol}', {sma_20d})
            ON DUPLICATE KEY UPDATE sma = {sma_20d};
        """)

# ==== Connect for Analysis ====
conn = mysql.connector.connect(
    host=MYSQL_HOST,
    user=MYSQL_USER,
    password=MYSQL_PASSWORD,
    database=MYSQL_DB
)
cursor = conn.cursor()

# ==== Bollinger Bands ====
def get_bollinger_bands(symbol, cursor):
    cursor.execute("""
        SELECT price
        FROM stock_prices
        WHERE symbol = %s
        ORDER BY timestamp DESC
        LIMIT 7800
    """, (symbol,))
    rows = cursor.fetchall()
    prices = [row[0] for row in rows]

    if len(prices) < 7800:
        return None

    prices.reverse()
    sma = np.mean(prices)
    std = np.std(prices)
    upper = sma + 2 * std
    lower = sma - 2 * std
    return sma, upper, lower

# ==== Bollinger Band Signal ====
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
        print(f"🔻 Buy signal for {symbol} (Price below lower band)")
    elif current_price > upper and is_held:
        print(f"🔺 Sell signal for {symbol} (Price above upper band)")

# ==== Stop Loss Trigger ====
def check_stop_loss(symbol, cursor, entry_price, stop_loss_percent=5.0):
    cursor.execute("""
        SELECT price 
        FROM stock_prices 
        WHERE symbol = %s 
        ORDER BY timestamp DESC 
        LIMIT 1
    """, (symbol,))
    result = cursor.fetchone()
    if not result:
        return

    current_price = result[0]
    stop_loss_price = entry_price * (1 - stop_loss_percent / 100)

    if current_price <= stop_loss_price:
        print(f"⚠️ Stop loss triggered for {symbol}! Current: ${current_price:.2f}, Entry: ${entry_price:.2f}, Limit: ${stop_loss_price:.2f}")

# ==== Run Checks ====
for ticker in tickers:
    check_bollinger_signal(ticker, cursor)
    # kush an Example for us could be: check_stop_loss(ticker, cursor, entry_price=150.00)

# ==== Cleanup ====
cursor.close()
conn.close()
