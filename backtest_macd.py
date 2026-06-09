# backtest_macd_zero_cross_altbtc.py
# - ดึงแท่งวันจาก Binance ผ่าน ccxt
# - กลยุทธ์: MACD zero-line cross (12,26,9)
# - ซื้อเมื่อ MACD > 0 จาก <= 0
# - ขายเมื่อ MACD < 0 จาก >= 0
# - PnL เป็น % (BTC pair = relative vs BTC, USDT pair = absolute)

import ccxt, pandas as pd, numpy as np, time, logging, json
from urllib.request import Request, urlopen

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

EXCHANGE = 'binance'
TIMEFRAME = '1d'
CMC_TOP_URL = (
    'https://api.coinmarketcap.com/data-api/v3/cryptocurrency/listing'
    '?start=1&limit={limit}&sortBy=market_cap&sortType=desc&convert=USD'
    '&cryptoType=all&tagType=all'
)

def fetch_cmc_top_symbols(limit=100):
    url = CMC_TOP_URL.format(limit=limit)
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})

    try:
        with urlopen(req, timeout=20) as resp:
            payload = json.loads(resp.read().decode('utf-8'))

        rows = payload.get('data', {}).get('cryptoCurrencyList', [])
        symbols = []
        for row in rows:
            sym = row.get('symbol')
            if isinstance(sym, str) and sym.strip():
                symbols.append(sym.strip())

        symbols = list(dict.fromkeys(symbols))
        if not symbols:
            raise ValueError('CMC returned no symbols')

        logging.info(f"loaded {len(symbols)} symbols from CMC top list")
        return symbols
    except Exception as e:
        logging.warning(f"CMC fetch failed ({e})")
        return []

def build_btc_pairs(symbols):
    pairs = [symbol if '/' in symbol else f"{symbol}/BTC" for symbol in symbols]
    return list(dict.fromkeys(pairs))

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
    markets = ex.load_markets()
    spot_symbols = {
        symbol for symbol, market in markets.items()
        if market.get('spot') and market.get('active', True)
    }

    cmc_symbols = fetch_cmc_top_symbols(limit=100)
    if not cmc_symbols:
        logging.error("No CMC symbols available. Abort run.")
        return

    pairs = build_btc_pairs(cmc_symbols)
    logging.info(f"{len(pairs)} unique pairs to test")

    results = []

    for sym in pairs:
        try:
            if sym not in spot_symbols:
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
