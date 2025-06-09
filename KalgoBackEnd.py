import pandas as pd
from sqlalchemy import create_engine
from alpaca_trade_api.rest import REST

# ==== Alpaca API Credentials ====
ALPACA_API_KEY = #OUR ALPACA KEY
ALPACA_SECRET_KEY = #OUR ALPACA SECRET KEY
BASE_URL = 'https://paper-api.alpaca.markets'

# ==== MySQL Database Credentials ====
MYSQL_USER = 'root'            # Change when MySQL connected
MYSQL_PASSWORD = '#password'  # Replace withMySQL password
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

# ==== Connect to MySQL ====
engine = create_engine(f'mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}/{MYSQL_DB}')

# ==== Save Data to MySQL ====
df.to_sql('live_stock_prices', con=engine, if_exists='append', index=False)

print("✔️ Stock data saved to MySQL.")
