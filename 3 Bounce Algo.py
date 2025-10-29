import yfinance as yf
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from datetime import datetime

ticker = "AAPL"
interval = "5m"
window = 2
min_spacing = 3

def find_swing_lows(df, window=2, min_spacing=3):
    lows = df['Low'].values
    swing_lows = []
    for i in range(window, len(lows) - window):
        local_window = lows[i - window:i + window + 1]
        if lows[i] == np.min(local_window):
            if not swing_lows or (i - swing_lows[-1][0]) >= min_spacing:
                swing_lows.append((i, df.index[i], float(lows[i])))
    return swing_lows

def get_latest_data():
    df = yf.download(ticker, interval=interval, period="2d", auto_adjust=True)
    if df.empty:
        print("No data received from yfinance.")
        return None
    # only keep regular market hours (avoids shelves)
    df = df.between_time("09:30", "16:00")
    return df

# Initialize first load
df = get_latest_data()
if df is None or df.empty:
    raise SystemExit("No data available to plot.")

fig, ax = plt.subplots(figsize=(10, 5))

def update(frame):
    df = get_latest_data()
    if df is None or df.empty:
        return
    swing_lows = find_swing_lows(df, window, min_spacing)
    ax.clear()

    # draw price line
    ax.plot(df.index, df["Low"], color="gray", linewidth=1.2, label="Low Price")

    # plot swing lows
    for idx, ts, price in swing_lows:
        ax.scatter(ts, price, color="limegreen", s=40,
                   label="Swing Low" if idx == swing_lows[0][0] else "")

    ax.set_title(f"{ticker} Swing Lows (Updated {datetime.now().strftime('%H:%M:%S')})")
    ax.set_xlabel("Time")
    ax.set_ylabel("Price ($)")
    ax.legend(loc="upper left")
    ax.grid(alpha=0.3)

# draw initial frame immediately
update(0)

# refresh every 60 seconds (no freezing)
ani = FuncAnimation(fig, update, interval=60000)
plt.tight_layout()
plt.show()
