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
    #  1-10
    'ETH/BTC',
    'USDT/BTC',
    'XRP/BTC',
    'BNB/BTC',
    'USDC/BTC',
    'SOL/BTC',
    'TRX/BTC',
    'DOGE/BTC',
    'ADA/BTC',
    # 11-20
    'BCH/BTC',
    'HYPE/BTC',
    'LEO/BTC',
    'LINK/BTC',
    'XMR/BTC',
    'XLM/BTC',
    'USDe/BTC',
    'ZEC/BTC',
    'LTC/BTC',
    'HBAR/BTC',
    # 21-30
    'AVAX/BTC',
    'DAI/BTC',
    'SUI/BTC',
    'SHIB/BTC',
    'WLFI/BTC',
    'PYUSD/BTC',
    'CRO/BTC',
    'TON/BTC',
    'UNI/BTC',
    'DOT/BTC',
    # 31-40
    'MNTBTC',
    'CC/BTC',
    'TAO/BTC',
    'USD1/BTC',
    'AAVE/BTC',
    'BGB/BTC',
    'ASTER/BTC',
    'NEAR/BTC',
    'OKB/BTC',
    'ETC/BTC',
    # 41-50
    'ICP/BTC',
    'PI/BTC',
    'ENA/BTC',
    'PEPE/BTC',
    'XAUt/BTC',
    'KAS/BTC',
    'ONDO/BTC',
    'M/BTC',
    'PAXG/BTC',
    'WLD/BTC',
    # 51-60
    'APT/BTC',
    'POL/BTC',
    'KCS/BTC',
    'USDG/BTC',
    'SKY/BTC',
    'QNT/BTC',
    'ALGO/BTC',
    'TRUMP/BTC',
    'ARB/BTC',
    'FLR/BTC',
    # 61-70
    'ATOM/BTC',
    'FIL/BTC',
    'VET/BTC',
    'RLUSD/BTC',
    'PUMP/BTC',
    'XDC/BTC',
    'FDUSD/BTC',
    'RENDER/BTC',
    'SEI/BTC',
    'IP/BTC',
    # 71-80
    'GT/BTC',
    'CAKE/BTC',
    'BONK/BTC',
    'JUP/BTC',
    'MYX/BTC',
    'PENGU/BTC',
    'DASH/BTC',
    'NEXO/BTC',
    'SPX/BTC',
    'OP/BTC',
    # 81-90
    'AERO/BTC',
    'IMX/BTC',
    'STRK/BTC',
    'CRV/BTC',
    'VIRTUAL/BTC',
    'FET/BTC',
    'LDO/BTC',
    'AB/BTC',
    'INJ/BTC',
    'STX/BTC',
     # 91-100
    'USDD/BTC',
    'MORPHO/BTC',
    'TIA/BTC',
    'XTZ/BTC',
    'GRT/BTC',
    'TUSD/BTC',
    'TEL/BTC',
    'ETHFI/BTC',
    'KAIA/BTC',
    'IOTA/BTC',
    # other not in top 100 by volume
    # best performers
    'CFX/BTC',
    'THETA/BTC',
    # worst performers
    'FLOKI/BTC',
    '2Z/BTC',
    'DEXE/BTC',
    'PYTH/BTC',
    'ENS/BTC',
    'H/BTC'
    'TWT/BTC',
    'SAND/BTC',
]

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