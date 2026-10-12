"""
Sector performance calculations for Indian equities.
Adapted from Schbang.ipynb; charts are built in app.py.
"""

import pandas as pd
import yfinance as yf

BENCHMARK = '^NSEI'
BENCHMARK_NAME = 'Nifty 50'
MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
          'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

SECTORS = {
    'Infrastructure': {
        'LT.NS': 'Larsen & Toubro', 'ADANIPORTS.NS': 'Adani Ports',
        'GMRAIRPORT.NS': 'GMR Airports', 'RVNL.NS': 'Rail Vikas Nigam',
        'IRCON.NS': 'IRCON International',
    },
    'Roads': {
        'IRB.NS': 'IRB Infrastructure', 'KNRCON.NS': 'KNR Constructions',
        'PNCINFRA.NS': 'PNC Infratech', 'GRINFRA.NS': 'G R Infraprojects',
        'ASHOKA.NS': 'Ashoka Buildcon',
    },
    'Paints': {
        'ASIANPAINT.NS': 'Asian Paints', 'BERGEPAINT.NS': 'Berger Paints',
        'KANSAINER.NS': 'Kansai Nerolac', 'INDIGOPNTS.NS': 'Indigo Paints',
        'AKZOINDIA.NS': 'Akzo Nobel India',
    },
    'Civil Construction': {
        'NCC.NS': 'NCC', 'NBCC.NS': 'NBCC', 'KPIL.NS': 'Kalpataru Projects',
        'KEC.NS': 'KEC International', 'ENGINERSIN.NS': 'Engineers India',
    },
    'Defence': {
        'HAL.NS': 'HAL', 'BEL.NS': 'BEL', 'MAZDOCK.NS': 'Mazagon Dock',
        'BDL.NS': 'BDL', 'COCHINSHIP.NS': 'Cochin Shipyard',
    },
}


# ============================================================
# DATA LOADING
# ============================================================
def download_close(tickers, start, end):
    """Closing prices for the given tickers. `end` is inclusive."""
    end_exclusive = pd.Timestamp(end) + pd.Timedelta(days=1)
    data = yf.download(list(tickers), start=pd.Timestamp(start), end=end_exclusive,
                       progress=False, auto_adjust=True)
    close = data['Close']
    if isinstance(close, pd.Series):
        close = close.to_frame(tickers[0])
    return close


def sector_prices(close, sector):
    """Prices for one sector, renamed to company names, with the benchmark column.

    Returns (prices, failed_tickers).
    """
    names = SECTORS[sector]
    failed = [t for t in names if t not in close or close[t].isna().all()]
    cols = [t for t in names if t not in failed]
    df = close[cols].rename(columns=names).ffill()
    df[BENCHMARK_NAME] = close[BENCHMARK].ffill()
    df.columns.name = 'Stock'
    return df, failed


# ============================================================
# OUTPUT 1: GROWTH OF RS. 100 INVESTED
# ============================================================
def growth_of_100(prices):
    """Value of Rs. 100 invested, each stock from its own first trading day."""
    return prices.apply(lambda s: s / s.dropna().iloc[0] * 100 if s.notna().any() else s)


def final_values(growth):
    return (growth.ffill().iloc[-1].round(0)
            .rename('Final value of Rs. 100')
            .sort_values(ascending=False))


# ============================================================
# OUTPUT 2: CALENDAR-YEAR RETURNS
# ============================================================
def _yearly(series):
    s = series.dropna()
    if s.empty:
        return pd.Series(dtype=float)
    year_end = s.resample('YE').last()
    prev = year_end.shift(1)
    # First year is measured from the first available price (partial year),
    # so the starting year is not dropped.
    prev.iloc[0] = s.iloc[0]
    out = (year_end / prev - 1) * 100
    out.index = out.index.year
    return out


def calendar_year_returns(prices):
    yearly = pd.DataFrame({c: _yearly(prices[c]) for c in prices.columns})
    yearly.index.name = 'Year'
    return yearly.round(1)


# ============================================================
# OUTPUT 3: AVERAGE RETURN BY CALENDAR MONTH
# ============================================================
def average_monthly_returns(prices):
    monthly = prices.resample('ME').last().pct_change(fill_method=None)
    avg = monthly.groupby(monthly.index.month).mean() * 100
    avg.index = [MONTHS[m - 1] for m in avg.index]
    avg.index.name = 'Month'
    return avg.round(1)


# ============================================================
# OUTPUT 4: STOCK PERFORMANCE VS NIFTY 50
# ============================================================
def rebased_pair(prices, stock):
    pair = prices[[stock, BENCHMARK_NAME]].dropna()
    return pair / pair.iloc[0] * 100


def performance_vs_benchmark(prices):
    rows = []
    for stock in [c for c in prices.columns if c != BENCHMARK_NAME]:
        pair = rebased_pair(prices, stock)
        if pair.empty:
            continue
        stock_ret = pair[stock].iloc[-1] - 100
        bench_ret = pair[BENCHMARK_NAME].iloc[-1] - 100
        rows.append({
            'Stock': stock,
            'From': pair.index[0].date(),
            'Stock return %': round(stock_ret, 1),
            f'{BENCHMARK_NAME} return %': round(bench_ret, 1),
            'Outperformance (pp)': round(stock_ret - bench_ret, 1),
        })
    if not rows:
        return pd.DataFrame()
    return (pd.DataFrame(rows).set_index('Stock')
            .sort_values('Outperformance (pp)', ascending=False))
