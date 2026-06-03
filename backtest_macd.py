# backtest_macd_zero_cross_altbtc.py
# - ดึงแท่งวันจาก Binance ผ่าน ccxt
# - กลยุทธ์: MACD zero-line cross (12,26,9)
# - ซื้อเมื่อ MACD > 0 จาก <= 0
# - ขายเมื่อ MACD < 0 จาก >= 0
# - PnL เป็น % (BTC pair = relative vs BTC, USDT pair = absolute)

import ccxt, pandas as pd, numpy as np, time, logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

EXCHANGE = 'binance'
TIMEFRAME = '1d'

PAIRS = [
    'BTC', 'ETH', 'USDT', 'XRP', 'BNB', 'USDC', 'SOL', 'TRX', 'DOGE', 'HYPE',
    'LEO', 'BCH', 'ADA', 'XMR', 'LINK', 'ZEC', 'CC', 'XLM', 'DAI', 'USD1',
    'LTC', 'AVAX', 'USDe', 'HBAR', 'M', 'SHIB', 'SUI', 'PYUSD', 'TON', 'CRO',
    'TAO', 'USDG', 'USDG', 'PAXG', 'MNT', 'UNI', 'DOT', 'SKY', 'PI', 'WLFI',
    'OKB', 'ASTER', 'NEAR', 'PEPE', 'RLUSD', 'USDD', 'AAVE', 'BGB', 'ETC', 'ONDO',
    'ICP', 'KCS', 'U', 'POL', 'ALGO', 'ATOM', 'MORPHO', 'ENA', 'DEXE', 'KAS',
    'RENDER', 'QNT', 'GT', 'APT', 'WLD', 'ARB', 'STABLE', 'JST', 'FIL', 'FLR',
    'PENGU', 'VET', 'PUMP', 'JUP', 'XDC', 'NEXO', 'BONK', 'TRUMP', 'NIGHT', 'SIREN',
    'H', 'TUSD', 'DASH', 'CAKE', 'VIRTUAL', 'FET', 'ZRO', 'EURC', 'CHZ', 'AERO',
    'VVV', 'EDGE', 'STX', 'SEI', 'FDUSD', 'XTZ', 'LUNAC', 'INJ', 'MON', 'SUN',
    # other not in top 100 by volume 
    # best performers
    'CFX', 'THETA', 'ENS', 'TIA', 'IOTA', 'OP', 'LDO'
    # worst performers
]

# default = BTC pair
PAIRS = [pair if '/' in pair else f"{pair}/BTC" for pair in PAIRS]
PAIRS = list(dict.fromkeys(PAIRS))

logging.info(f"{len(PAIRS)} unique pairs to test")

def macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    sig = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - sig
    return macd_line, sig, hist

def backtest_zero_cross(df):
    close = df['close']
    macd_line, _, _ = macd(close)
    macd_prev = macd_line.shift(1)

    buy  = (macd_prev <= 0) & (macd_line > 0)
    sell = (macd_prev >= 0) & (macd_line < 0)

    position = 0
    entry = 0.0
    pnl = 0.0

    for i in range(1, len(df)):
        if buy.iloc[i] and position == 0:
            position = 1
            entry = close.iloc[i]
        elif sell.iloc[i] and position == 1:
            exitp = close.iloc[i]
            pnl += (exitp / entry - 1.0)
            position = 0

    if position == 1:
        exitp = close.iloc[-1]
        pnl += (exitp / entry - 1.0)

    return pnl

def fetch_ohlcv(exchange, symbol, timeframe):
    ms = exchange.parse_timeframe(timeframe) * 1000
    since = exchange.parse8601('2009-01-01T00:00:00Z')
    rows = []

    while True:
        data = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=1000)
        if not data:
            break
        rows += data
        since = data[-1][0] + ms
        time.sleep(exchange.rateLimit / 1000 + 0.1)
        if len(data) < 1000:
            break

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows, columns=['time','open','high','low','close','volume'])
    df['time'] = pd.to_datetime(df['time'], unit='ms', utc=True)
    return df.set_index('time').sort_index()

def main():
    ex = getattr(ccxt, EXCHANGE)({'enableRateLimit': True})
    ex.load_markets()
    symbols = set(ex.symbols)

    results = []

    for sym in PAIRS:
        try:
            if sym not in symbols:
                continue

            df = fetch_ohlcv(ex, sym, TIMEFRAME)

            if df.empty or len(df) < 200:
                continue

            pnl = backtest_zero_cross(df)
            if pnl > 0:
                results.append((sym, pnl))

        except Exception as e:
            logging.warning(f"error {sym}: {e}")

    unique = {sym: pnl for sym, pnl in results}

    out = pd.DataFrame(
        [(k, f"{v:.2%}", "OK") for k, v in sorted(unique.items())],
        columns=['pair', 'return', 'status']
    )

    if out.empty:
        print("No winners")
    else:
        print(out.to_string(index=False))

if __name__ == '__main__':
    main()
