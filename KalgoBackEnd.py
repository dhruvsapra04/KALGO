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

# 1. Save to 'live_stock_prices'
df.to_sql('live_stock_prices', con=engine, if_exists='append', index=False)

# 2. Save to 'stock_prices', keeping 7800 entries per ticker max
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

# 3. Compute and store the 20-day SMA in 'sma_20d'
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
    query = '''
        SELECT price
        FROM stock_prices
        WHERE symbol = %s
        ORDER BY timestamp DESC
        LIMIT 7800
    '''
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
    cursor.execute('''
        SELECT price
        FROM stock_prices
        WHERE symbol = %s
        ORDER BY timestamp DESC
        LIMIT 1
    ''', (symbol,))
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

# ==== Check for Stop Loss Trigger ====
def check_stop_loss(symbol, cursor, entry_price, stop_loss_percent=5.0):
    """
    This function checks if the current price of a stock has fallen
    below the defined stop loss percentage of the entry price.
    If it has, it'll print an alert.
    """
    # Get the most recent price from the database
    cursor.execute("""
        SELECT price 
        FROM stock_prices 
        WHERE symbol = %s 
        ORDER BY timestamp DESC 
        LIMIT 1
    """, (symbol,))
    result = cursor.fetchone()
    if not result:
        # No data found for this symbol
        return

    current_price = result[0]
    stop_loss_price = entry_price * (1 - stop_loss_percent / 100)

    # Compare the current price with the calculated stop loss price
    if current_price <= stop_loss_price:
        print(f"⚠️ Stop loss triggered for {symbol}! Current: ${current_price:.2f}, Entry: ${entry_price:.2f}, Stop loss limit: ${stop_loss_price:.2f}")


# ==== Run Bollinger Signal Checks ====
for ticker in tickers:
    check_bollinger_signal(ticker, cursor)

# ==== Cleanup ====
cursor.close()
conn.close()
