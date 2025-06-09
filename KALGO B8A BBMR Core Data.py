import mysql.connector
import numpy as np

# $ curl -v https://paper-api.alpaca.markets/v2/account
# ...
# > GET /v2/account HTTP/1.1
# > Host: paper-api.alpaca.markets
# > User-Agent: curl/7.88.1
# > Accept: */*
# >
# < HTTP/1.1 403 Forbidden
# < Date: Fri, 25 Aug 2023 09:34:40 GMT
# < Content-Type: application/json
# < Content-Length: 26
# < Connection: keep-alive
# < X-Request-ID: 649c5a79da1ab9cb20742ffdada0a7bb
# <
# ...

conn = mysql.connector.connect(
    host='localhost',
    user='your_username',
    password='your_password',
    database='your_database'
)
cursor = conn.cursor()

def get_bollinger_bands(symbol, cursor):
    query = """
        SELECT price
        FROM stock_prices
        WHERE symbol = %s
        ORDER BY datetime DESC
        LIMIT 7800
    """
    cursor.execute(query, (symbol,))
    rows = cursor.fetchall()
    prices = [row[0] for row in rows]

    if len(prices) < 7800:
        return None

    prices.reverse()  # Reverse to oldest → newest

    sma = np.mean(prices)
    std = np.std(prices)
    upper = sma + 2 * std
    lower = sma - 2 * std
    return sma, upper, lower

def check_bollinger_signal(symbol, cursor, is_held):
    cursor.execute("""
        SELECT price
        FROM stock_prices
        WHERE symbol = %s
        ORDER BY datetime DESC
        LIMIT 1
    """, (symbol,))
    row = cursor.fetchone()
    if not row:
        return+




    current_price = row[0]
    bands = get_bollinger_bands(symbol, cursor)

    if bands is None:
        return

    sma, upper, lower = bands

    print(f"{symbol}: Price={current_price:.2f}, SMA={sma:.2f}, Upper={upper:.2f}, Lower={lower:.2f}")

    if current_price < lower and not is_held:
        print(f" Buy signal for {symbol} (Price hit lower band)")
    elif current_price > upper and is_held:
        print(f" Sell signal for {symbol} (Price hit upper band)")
