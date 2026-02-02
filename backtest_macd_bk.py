# backtest_macd_zero_cross_altbtc.py
# - ดึงแท่งวันจาก Binance ผ่าน ccxt
# - กลยุทธ์: MACD zero-line cross (12,26,9) ซื้อเมื่อ MACD>0 จาก <=0, ขายเมื่อ MACD<0 จาก >=0
# - วัด PnL เป็น BTC (base currency) เทียบ HODL BTC = 0% (เพราะ denom เป็น BTC)
# ใช้: python backtest_macd_zero_cross_altbtc.py

# backtest_macd.py

import ccxt, pandas as pd, numpy as np, time, logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

EXCHANGE = 'binance'
TIMEFRAME = '1d'
PAIRS = [
    'BTC', 'ETH', 'USDT', 'BNB', 'XRP', 'USDC', 'SOL', 'TRX', 'DOGE', 'ADA',
    'BCH', 'HYPE', 'XMR', 'LEO', 'CC', 'LINK', 'USDe', 'XLM', 'DAI', 'ZEC', 
    'USD1', 'LTC', 'AVAX', 'SUI', 'SHIB', 'HBAR', 'PYUSD', 'WLFI', 'TON', 'CRO',
    'DOT', 'UNI', 'XAUt', 'MNT', 'BGB', 'PAXG', 'TAO', 'AAVE', 'OKB', 'PEPE',
    'M', 'USDG', 'NEAR', 'ETC', 'ICP', 'SKY',  'ASTER', 'MYX', 'PI', 'ONDO',
    'RLUSD', 'KCS', 'WLD', 'POL', 'ENA', 'USDD', 'TRUMP', 'APT', 'ATOM', 'GT',
    'PUMP', 'ALGO', 'KAS', 'FLR', 'QNT', 'ARB', 'RENDER', 'FIL', 'NIGHT', 'U',
    'VET', 'XDC', 'BONK', 'JUP', 'SEI', 'DASH', 'ZRO', 'NEXO', 'IP', 'CAKE',
    'XTZ', 'TUSD', 'PENGU', 'CHZ', 'STX', 'STABLE', 'FDUSD', 'OP', 'MORPHO', 'FET',
    'EURC', 'CRV', 'VIRTUAL', 'LIT', '2Z', 'JST', 'RIVER', 'IMX', 'INJ', 'LDO',
    # other not in top 100 by volume
    'SPX', 'AERO', 'FLOKI', 'TIA', 'ETHFI', 'JASMY', 'GRT', 'IOTA',
    # best performers
    'CFX','THETA','ENS'
    # worst performers
]

PAIRS = [pair if '/' in pair else f"{pair}/BTC" for pair in PAIRS]
PAIRS = list(dict.fromkeys(PAIRS))
logging.info(f"{len(PAIRS)} unique pairs to test")

def macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    sig = macd.ewm(span=signal, adjust=False).mean()
    hist = macd - sig
    return macd, sig, hist

def backtest_zero_cross(df):
    close = df['close']
    macd_line, signal, _ = macd(close)
    macd_prev = macd_line.shift(1)
    buy  = (macd_prev <= 0) & (macd_line > 0)
    sell = (macd_prev >= 0) & (macd_line < 0)

    position = 0
    entry = 0.0
    pnl_btc = 0.0

    for i in range(1, len(df)):
        if buy.iloc[i] and position == 0:
            position = 1
            entry = close.iloc[i]
        elif sell.iloc[i] and position == 1:
            exitp = close.iloc[i]
            pnl_btc += (exitp/entry - 1.0)
            position = 0

    if position == 1:
        exitp = close.iloc[-1]
        pnl_btc += (exitp/entry - 1.0)

    return pnl_btc

def fetch_ohlcv(exchange, symbol, timeframe):
    ms = exchange.parse_timeframe(timeframe) * 1000
    since = exchange.parse8601('2009-01-01T00:00:00Z')
    all_rows = []
    while True:
        data = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=1000)
        if not data:
            break
        all_rows += data
        since = data[-1][0] + ms
        time.sleep(exchange.rateLimit/1000 + 0.1)
        if len(data) < 1000:
            break
    df = pd.DataFrame(all_rows, columns=['time','open','high','low','close','volume'])
    if df.empty:
        return df
    df['time'] = pd.to_datetime(df['time'], unit='ms', utc=True)
    df = df.set_index('time').sort_index()
    return df

def main():
    ex = getattr(ccxt, EXCHANGE)({'enableRateLimit': True})
    # load markets once
    markets = ex.load_markets()
    symbols = set(ex.symbols)
    results = []

    for sym in PAIRS:
        try:
            if sym not in symbols:
                logging.debug(f"skip {sym}: not in exchange symbols")
                continue
            df = fetch_ohlcv(ex, sym, TIMEFRAME)
            if df.empty or len(df) < 200:
                logging.debug(f"skip {sym}: insufficient data ({len(df) if not df.empty else 0})")
                continue
            pnl_btc = backtest_zero_cross(df)
            if pnl_btc > 0:
                results.append((sym, pnl_btc))
        except Exception as e:
            logging.warning(f"error {sym}: {e}")
            continue

    # remove duplicates just in case, then build DataFrame and pretty-print
    unique_results = {}
    for sym, pnl in results:
        unique_results[sym] = pnl  # last one wins, but duplicates removed

    out = pd.DataFrame([(k, f'{v:.2%}', 'OK') for k, v in sorted(unique_results.items())],
                       columns=['pair','return_vs_btc','status'])
    if out.empty:
        print("No winners")
    else:
        print(out.to_string(index=False))

if __name__ == '__main__':
    main()