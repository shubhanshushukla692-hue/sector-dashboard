"""
Sector Performance Dashboard: Indian Equities
Run with:  streamlit run app.py
"""

import hmac
import io
import time
import zipfile
from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import analysis as an
from analysis import BENCHMARK, BENCHMARK_NAME, SECTORS

st.set_page_config(page_title='Sector Performance', page_icon='📈', layout='wide')


# ============================================================
# PASSWORD GATE
# ============================================================
def check_password():
    """Show a password form until the shared access key is entered."""
    if st.session_state.get('authenticated'):
        return

    expected = st.secrets.get('APP_PASSWORD', '')
    if not expected:
        st.error('APP_PASSWORD is not set. Add it to .streamlit/secrets.toml '
                 '(locally) or to the app\'s Secrets (when hosted).')
        st.stop()

    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown('## 📈 Sector Performance')
        st.caption('Enter the access key to continue.')
        with st.form('login'):
            key = st.text_input('Access key', type='password')
            submitted = st.form_submit_button('Unlock', use_container_width=True)
        if submitted:
            if hmac.compare_digest(key.encode(), expected.encode()):
                st.session_state['authenticated'] = True
                st.rerun()
            time.sleep(1)  # slow down guessing
            st.error('Incorrect access key.')
    st.stop()


check_password()


# ============================================================
# HELPERS
# ============================================================
@st.cache_data(ttl=6 * 60 * 60, show_spinner='Downloading prices from Yahoo Finance...')
def load_close(start, end):
    tickers = [t for stocks in SECTORS.values() for t in stocks] + [BENCHMARK]
    return an.download_close(tickers, start, end)


def to_csv(df):
    return df.to_csv().encode('utf-8')


def csv_button(df, label, filename, key):
    st.download_button(f'⬇ {label}', to_csv(df), file_name=filename,
                       mime='text/csv', key=key)


def slug(text):
    return text.lower().replace(' ', '_')


def combine(tables, transpose=False):
    """Stack per-sector tables into one, with Sector as the outer index."""
    parts = {s: (t.T if transpose else t) for s, t in tables.items() if not t.empty}
    if not parts:
        return pd.DataFrame()
    return pd.concat(parts, names=['Sector', parts[next(iter(parts))].index.name or 'Stock'])


# ============================================================
# CHARTS
# ============================================================
def growth_chart(growth, sector):
    fig = go.Figure()
    for col in growth.columns:
        is_bench = col == BENCHMARK_NAME
        fig.add_trace(go.Scatter(
            x=growth.index, y=growth[col], name=col, mode='lines',
            line=dict(color='gray', dash='dash', width=2.5) if is_bench else dict(width=1.8),
        ))
    fig.update_layout(title=f'{sector}: Growth of Rs. 100 Invested',
                      yaxis_title='Value (Rs., log scale)', yaxis_type='log',
                      hovermode='x unified', height=450, legend_title_text='')
    return fig


def yearly_chart(yearly, sector):
    long = yearly.reset_index().melt(id_vars='Year', var_name='Stock', value_name='Return %')
    long['Year'] = long['Year'].astype(str)
    fig = px.bar(long, x='Year', y='Return %', color='Stock', barmode='group',
                 title=f'{sector}: Calendar-Year Returns (%)')
    fig.add_hline(y=0, line_color='gray', line_width=1)
    fig.update_layout(height=450, legend_title_text='')
    return fig


def monthly_heatmap(avg, sector):
    fig = px.imshow(avg.T, text_auto='.1f', aspect='auto',
                    color_continuous_scale='RdYlGn', color_continuous_midpoint=0,
                    labels=dict(color='Avg return %'),
                    title=f'{sector}: Average Return by Calendar Month (%)')
    fig.update_layout(height=120 + 45 * len(avg.columns), xaxis_title='', yaxis_title='')
    return fig


def stock_vs_bench_chart(pair, stock):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=pair.index, y=pair[stock], name=stock,
                             line=dict(width=2)))
    fig.add_trace(go.Scatter(x=pair.index, y=pair[BENCHMARK_NAME], name=BENCHMARK_NAME,
                             line=dict(color='gray', dash='dash')))
    fig.update_layout(title=stock, height=300, margin=dict(l=10, r=10, t=40, b=10),
                      yaxis_title='Start = 100', hovermode='x unified',
                      legend=dict(orientation='h', y=-0.2))
    return fig


# ============================================================
# SIDEBAR: FILTERS
# ============================================================
st.sidebar.title('Filters')

today = date.today()
date_range = st.sidebar.date_input(
    'Date range', value=(date(2021, 1, 1), today),
    min_value=date(2000, 1, 1), max_value=today, format='DD/MM/YYYY',
)
if not isinstance(date_range, tuple) or len(date_range) != 2:
    st.info('Pick an end date to complete the date range.')
    st.stop()
start, end = date_range
if (end - start).days < 31:
    st.error('Please choose a date range of at least one month.')
    st.stop()

selected = st.sidebar.multiselect('Industry / sector', list(SECTORS), default=list(SECTORS))
if not selected:
    st.info('Select at least one sector in the sidebar.')
    st.stop()

with st.sidebar.expander('Stocks in selected sectors'):
    for s in selected:
        st.markdown(f'**{s}**  \n' + ', '.join(SECTORS[s].values()))


# ============================================================
# DATA + CALCULATIONS
# ============================================================
st.title('📈 Sector Performance: Indian Equities')
st.caption(f'{start:%d %b %Y} – {end:%d %b %Y} · Benchmark: {BENCHMARK_NAME} · '
           'Prices: Yahoo Finance (adjusted close)')

try:
    close = load_close(start, end)
except Exception as exc:
    st.error(f'Could not download prices: {exc}')
    st.stop()

if close.empty or BENCHMARK not in close or close[BENCHMARK].isna().all():
    st.error('No price data returned for this date range. Try a different range.')
    st.stop()

prices, growth, yearly, monthly, vs_nifty, failed = {}, {}, {}, {}, {}, []
for sector in selected:
    p, f = an.sector_prices(close, sector)
    failed += f
    prices[sector] = p
    growth[sector] = an.growth_of_100(p)
    yearly[sector] = an.calendar_year_returns(p)
    monthly[sector] = an.average_monthly_returns(p)
    vs_nifty[sector] = an.performance_vs_benchmark(p)

if failed:
    st.warning(f'No data for: {", ".join(failed)} in this range (not listed yet, '
               'renamed or delisted). They are left out.')

ranking = combine(vs_nifty)
if not ranking.empty:
    ranking = (ranking.reset_index()
               .sort_values('Outperformance (pp)', ascending=False)
               .reset_index(drop=True))
    ranking.index += 1
    ranking.index.name = 'Rank'

final_vals = {s: an.final_values(g).to_frame() for s, g in growth.items()}
all_prices = pd.concat(prices, axis=1, names=['Sector', 'Stock'])
all_prices.index.name = 'Date'

# Download everything as a zip of CSVs
bundle = io.BytesIO()
with zipfile.ZipFile(bundle, 'w', zipfile.ZIP_DEFLATED) as z:
    z.writestr('1_growth_of_100_final.csv', combine(final_vals).to_csv())
    z.writestr('1_growth_of_100_daily.csv', pd.concat(growth, axis=1).to_csv())
    z.writestr('2_calendar_year_returns.csv', combine(yearly, transpose=True).to_csv())
    z.writestr('3_monthly_avg_returns.csv', combine(monthly, transpose=True).to_csv())
    z.writestr('4_vs_nifty.csv', combine(vs_nifty).to_csv())
    z.writestr('overall_ranking.csv', ranking.to_csv())
    z.writestr('prices.csv', all_prices.to_csv())
st.sidebar.divider()
st.sidebar.download_button('⬇ Download all CSVs (ZIP)', bundle.getvalue(),
                           file_name=f'sector_performance_{start}_{end}.zip',
                           mime='application/zip', use_container_width=True)
if st.sidebar.button('Log out', use_container_width=True):
    st.session_state['authenticated'] = False
    st.rerun()


# ============================================================
# TABS
# ============================================================
tabs = st.tabs(['1 · Growth of ₹100', '2 · Calendar-year returns',
                '3 · Monthly seasonality', f'4 · vs {BENCHMARK_NAME}',
                '🏆 Overall ranking', 'Raw prices'])

with tabs[0]:
    csv_button(combine(final_vals), 'All selected sectors (CSV)',
               'growth_of_100_all.csv', 'g_all')
    for sector in selected:
        st.subheader(sector)
        c1, c2 = st.columns([3, 1])
        c1.plotly_chart(growth_chart(growth[sector], sector), use_container_width=True)
        c2.dataframe(final_vals[sector], use_container_width=True)
        csv_button(growth[sector].round(2), f'{sector} daily values (CSV)',
                   f'growth_{slug(sector)}.csv', f'g_{sector}')

with tabs[1]:
    st.caption('The first year is measured from the first trading day in your range, '
               'so it can be a partial year.')
    csv_button(combine(yearly, transpose=True), 'All selected sectors (CSV)',
               'calendar_year_returns_all.csv', 'y_all')
    for sector in selected:
        st.subheader(sector)
        st.plotly_chart(yearly_chart(yearly[sector], sector), use_container_width=True)
        st.dataframe(yearly[sector].T, use_container_width=True)
        csv_button(yearly[sector].T, f'{sector} (CSV)',
                   f'yearly_{slug(sector)}.csv', f'y_{sector}')

with tabs[2]:
    st.caption('Average of each month\'s return across all years in the range.')
    csv_button(combine(monthly, transpose=True), 'All selected sectors (CSV)',
               'monthly_avg_returns_all.csv', 'm_all')
    for sector in selected:
        st.subheader(sector)
        st.plotly_chart(monthly_heatmap(monthly[sector], sector), use_container_width=True)
        csv_button(monthly[sector].T, f'{sector} (CSV)',
                   f'monthly_{slug(sector)}.csv', f'm_{sector}')

with tabs[3]:
    csv_button(combine(vs_nifty), 'All selected sectors (CSV)', 'vs_nifty_all.csv', 'v_all')
    for sector in selected:
        st.subheader(sector)
        p = prices[sector]
        stocks = [c for c in p.columns if c != BENCHMARK_NAME]
        cols = st.columns(3)
        for i, stock in enumerate(stocks):
            pair = an.rebased_pair(p, stock)
            if not pair.empty:
                cols[i % 3].plotly_chart(stock_vs_bench_chart(pair, stock),
                                         use_container_width=True)
        st.dataframe(vs_nifty[sector], use_container_width=True)
        csv_button(vs_nifty[sector], f'{sector} (CSV)',
                   f'vs_nifty_{slug(sector)}.csv', f'v_{sector}')

with tabs[4]:
    st.subheader(f'All selected stocks ranked by outperformance vs {BENCHMARK_NAME}')
    if ranking.empty:
        st.info('No stocks to rank.')
    else:
        fig = px.bar(ranking, x='Outperformance (pp)', y='Stock', color='Sector',
                     orientation='h', height=max(400, 28 * len(ranking)))
        fig.update_layout(yaxis=dict(autorange='reversed'), yaxis_title='')
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(ranking, use_container_width=True)
        csv_button(ranking, 'Ranking (CSV)', 'overall_ranking.csv', 'rank')

with tabs[5]:
    st.caption('Daily adjusted closing prices (forward-filled over holidays).')
    st.dataframe(all_prices.round(2), use_container_width=True, height=500)
    csv_button(all_prices.round(2), 'Prices (CSV)', 'prices.csv', 'prices')
