# backtest_macd_zero_cross_altbtc.py
# - ดึงแท่งวันจาก Binance ผ่าน ccxt
# - กลยุทธ์: MACD zero-line cross (12,26,9)
# - ซื้อเมื่อ MACD > 0 จาก <= 0
# - ขายเมื่อ MACD < 0 จาก >= 0
# - PnL เป็น % (BTC pair = relative vs BTC, USDT pair = absolute)

import ccxt, pandas as pd, numpy as np, time, logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

EXCHANGE = 'binance'
TIMEFRAME = '1m'

PAIRS = [
    'BTC', 'ETH', 'USDT', 'BNB', 'XRP', 'USDC', 'SOL', 'TRX', 'DOGE', 'ADA',
    'BCH', 'HYPE', 'XMR', 'LEO', 'CC', 'LINK', 'USDe', 'XLM', 'DAI', 'ZEC', 
    'USD1', 'LTC', 'AVAX', 'SUI', 'SHIB', 'HBAR', 'PYUSD', 'WLFI', 'TON', 'CRO',
    'DOT', 'UNI', 'XAUt', 'MNT', 'BGB', 'PAXG', 'TAO', 'AAVE', 'OKB', 'PEPE',
    'M', 'USDG', 'NEAR', 'ETC', 'ICP', 'SKY', 'ASTER', 'MYX', 'PI', 'ONDO',
    'RLUSD', 'KCS', 'WLD', 'POL', 'ENA', 'USDD', 'TRUMP', 'APT', 'ATOM', 'GT',
    'PUMP', 'ALGO', 'KAS', 'FLR', 'QNT', 'ARB', 'RENDER', 'FIL', 'NIGHT', 'U',
    'VET', 'XDC', 'BONK', 'JUP', 'SEI', 'DASH', 'ZRO', 'NEXO', 'IP', 'CAKE',
    'XTZ', 'TUSD', 'PENGU', 'CHZ', 'STX', 'STABLE', 'FDUSD', 'OP', 'MORPHO', 'FET',
    'EURC', 'CRV', 'VIRTUAL', 'LIT', '2Z', 'JST', 'RIVER', 'IMX', 'INJ', 'LDO',
    # other not in top 100 by volume
    # best performers
    'CFX','THETA','ENS','TIA', 'IOTA',
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

            # ---- fallback to USDT if BTC pair insufficient ----
            if df.empty or len(df) < 200:
                base = sym.split('/')[0]
                usdt_pair = f"{base}/USDT"
                if usdt_pair in symbols:
                    logging.info(f"{sym} insufficient data → fallback {usdt_pair}")
                    df = fetch_ohlcv(ex, usdt_pair, TIMEFRAME)
                    sym = usdt_pair
                else:
                    continue

            if df.empty or len(df) < 200:
                continue
            # ---------------------------------------------------

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
