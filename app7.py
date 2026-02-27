import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from scipy.stats import binomtest
from assets import ASSET_CATEGORIES, get_all_assets_flat
import warnings
warnings.filterwarnings('ignore')

# ─────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Inside Bar Strategy Analyzer — Multi-Asset",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main .block-container {padding-top: 1rem; padding-bottom: 1rem; max-width: 1400px;}
    div[data-testid="stMetricValue"] {font-size: 22px;}
    .stTabs [data-baseweb="tab-list"] {gap: 4px;}
    .stTabs [data-baseweb="tab"] {padding: 6px 12px; font-size: 13px;}
</style>
""", unsafe_allow_html=True)

COLORS = {
    'win': '#00c853', 'loss': '#ff1744', 'gold': '#ffd700',
    'blue': '#2196f3', 'purple': '#9c27b0', 'orange': '#ff9800',
    'cyan': '#00bcd4', 'teal': '#009688',
}

# ─────────────────────────────────────────────────────────────
# WICK CLASSIFICATION SYSTEM
# ─────────────────────────────────────────────────────────────
def classify_wick_profile(open_p, close_p, high, low):
    body_top = max(open_p, close_p)
    body_bot = min(open_p, close_p)
    total_range = high - low
    if total_range == 0:
        return 'Doji', 0, 0, 0, close_p >= open_p
    upper_wick = high - body_top
    lower_wick = body_bot - low
    body = body_top - body_bot
    upper_pct = upper_wick / total_range * 100
    lower_pct = lower_wick / total_range * 100
    body_pct = body / total_range * 100
    is_bullish = close_p > open_p
    if body_pct < 10:
        label = 'Doji'
    elif upper_pct > 30 and lower_pct > 30:
        label = 'Wicks Both Sides'
    elif upper_pct > lower_pct * 2 and upper_pct > 20:
        label = 'Heavy Upper Wick'
    elif lower_pct > upper_pct * 2 and lower_pct > 20:
        label = 'Heavy Lower Wick'
    elif body_pct > 75:
        label = 'Full Body (Marubozu)'
    elif upper_pct > lower_pct + 5:
        label = 'Slight Upper Wick'
    elif lower_pct > upper_pct + 5:
        label = 'Slight Lower Wick'
    else:
        label = 'Balanced'
    return label, round(upper_pct, 1), round(lower_pct, 1), round(body_pct, 1), is_bullish


def get_scenario_key(c1_bullish, c1_wick, c2_bullish, c2_wick):
    c1c = 'Green' if c1_bullish else 'Red'
    c2c = 'Green' if c2_bullish else 'Red'
    return f"C1:{c1c}/{c1_wick} -> C2:{c2c}/{c2_wick}"


def wick_bucket(label):
    if label in ('Heavy Upper Wick','Slight Upper Wick'): return 'Upper Wick'
    if label in ('Heavy Lower Wick','Slight Lower Wick'): return 'Lower Wick'
    if label == 'Full Body (Marubozu)': return 'Full Body'
    if label == 'Wicks Both Sides': return 'Both Wicks'
    if label == 'Doji': return 'Doji'
    return 'Balanced'


# ─────────────────────────────────────────────────────────────
# ECONOMIC EVENTS
# ─────────────────────────────────────────────────────────────
@st.cache_data
def get_major_event_dates():
    fomc = ["2024-01-31","2024-03-20","2024-05-01","2024-06-12","2024-07-31",
        "2024-09-18","2024-11-07","2024-12-18","2025-01-29","2025-03-19",
        "2025-05-07","2025-06-18","2025-07-30","2025-09-17","2025-10-29",
        "2025-12-17","2026-01-28"]
    nfp = []
    for year in [2024, 2025, 2026]:
        for month in range(1, 13):
            try:
                d = datetime(year, month, 1)
                days_ahead = 4 - d.weekday()
                if days_ahead < 0: days_ahead += 7
                nfp.append((d + timedelta(days=days_ahead)).strftime("%Y-%m-%d"))
            except: pass
    cpi = ["2024-01-11","2024-02-13","2024-03-12","2024-04-10","2024-05-15",
        "2024-06-12","2024-07-11","2024-08-14","2024-09-11","2024-10-10",
        "2024-11-13","2024-12-11","2025-01-15","2025-02-12","2025-03-12",
        "2025-04-10","2025-05-13","2025-06-11","2025-07-15","2025-08-12",
        "2025-09-10","2025-10-14","2025-11-12","2025-12-10"]
    dates = set()
    for d in fomc + nfp + cpi:
        try: dates.add(pd.Timestamp(d).date())
        except: pass
    return dates


# ─────────────────────────────────────────────────────────────
# DATA
# ─────────────────────────────────────────────────────────────
# yfinance confirmed limits (from source code):
#   1m: 30 days | 2m,5m,15m,30m,90m: 60 days | 1h,60m: 730 days | 1d+: unlimited
INTERVAL_MAX_DAYS = {'15m': 59, '30m': 59, '1h': 729, '4h': 729}

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_asset_data(ticker, interval='1h', period_years=2):
    """Fetch data respecting yfinance's per-interval limits."""
    max_days = INTERVAL_MAX_DAYS.get(interval, 729)
    requested_days = min(period_years * 365, max_days)
    end = datetime.now()
    start = end - timedelta(days=requested_days)

    # yfinance uses '1h' not '1H', '15m' not '15M'
    yf_interval = interval.lower()
    if yf_interval == '4h':
        # No native 4h in yfinance — fetch 1h and resample
        yf_interval = '1h'

    df = yf.download(ticker, start=start, end=end, interval=yf_interval, progress=False)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    if df.empty: return df
    df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_convert('UTC').tz_localize(None)
    return df

def resample_to_4h(df):
    return df.resample('4h').agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()

def resample_to_interval(df_1h, target):
    """Resample 1h data to 4h. For 15m/30m we fetch directly."""
    if target == '4h' or target == '4H':
        return resample_to_4h(df_1h)
    return df_1h  # 1h stays as-is


# ─────────────────────────────────────────────────────────────
# ZONES
# ─────────────────────────────────────────────────────────────
def detect_zones(df, zone_atr_min=1.5):
    df = df.copy()
    df['Body'] = abs(df['Close'] - df['Open'])
    df['TR'] = np.maximum(df['High']-df['Low'], np.maximum(abs(df['High']-df['Close'].shift(1)), abs(df['Low']-df['Close'].shift(1))))
    df['ATR'] = df['TR'].rolling(14).mean()
    df['IsBullish'] = df['Close'] > df['Open']
    zones = []
    for i in range(20, len(df)):
        r = df.iloc[i]
        if pd.isna(r['ATR']) or r['ATR']==0 or r['Body'] < r['ATR']*zone_atr_min: continue
        strength = r['Body'] / r['ATR']
        if r['IsBullish']:
            zones.append({'datetime':df.index[i],'zone_top':r['Open'],'zone_bottom':r['Low'],
                         'zone_type':'demand','strength':round(strength,2),
                         'origin_body':r['Body'],'origin_range':r['High']-r['Low']})
        else:
            zones.append({'datetime':df.index[i],'zone_top':r['High'],'zone_bottom':r['Open'],
                         'zone_type':'supply','strength':round(strength,2),
                         'origin_body':r['Body'],'origin_range':r['High']-r['Low']})
    return pd.DataFrame(zones) if zones else pd.DataFrame(
        columns=['datetime','zone_top','zone_bottom','zone_type','strength','origin_body','origin_range'])

def classify_zone(dt, price, zones_df, lookback_hours=720, proximity_pct=0.003):
    """Classify zone and return dict with zone type, distance, and strength."""
    result = {'zone': 'neutral', 'zone_dist_pct': None, 'zone_strength': None,
              'nearest_zone_type': None, 'nearest_zone_top': None, 'nearest_zone_bottom': None,
              'zone_proximity_band': 'No Zone'}
    if zones_df.empty:
        return result
    cutoff = dt - pd.Timedelta(hours=lookback_hours)
    recent = zones_df[(zones_df['datetime']>=cutoff)&(zones_df['datetime']<dt)]
    if recent.empty:
        return result

    near_s = near_d = False
    min_dist_pct = float('inf')
    nearest = None

    for _, z in recent.iterrows():
        # Distance to nearest edge of zone
        if z['zone_bottom'] <= price <= z['zone_top']:
            dist_pct = 0.0  # inside the zone
        else:
            dist_top = abs(price - z['zone_top']) / price
            dist_bot = abs(price - z['zone_bottom']) / price
            dist_pct = min(dist_top, dist_bot)

        if dist_pct < min_dist_pct:
            min_dist_pct = dist_pct
            nearest = z

        if dist_pct <= proximity_pct:
            if z['zone_type'] == 'supply':
                near_s = True
            else:
                near_d = True

    # Determine zone classification
    if near_s and near_d:
        zone_type = 'contested'
    elif near_s:
        zone_type = 'supply'
    elif near_d:
        zone_type = 'demand'
    else:
        zone_type = 'neutral'

    # Proximity band for analysis dimension
    if min_dist_pct == 0:
        prox_band = 'Inside Zone'
    elif min_dist_pct <= 0.001:
        prox_band = 'Touching (≤0.1%)'
    elif min_dist_pct <= 0.003:
        prox_band = 'Very Close (0.1-0.3%)'
    elif min_dist_pct <= 0.006:
        prox_band = 'Near (0.3-0.6%)'
    elif min_dist_pct <= 0.01:
        prox_band = 'Moderate (0.6-1%)'
    else:
        prox_band = 'Far (>1%)'

    result['zone'] = zone_type
    result['zone_dist_pct'] = round(min_dist_pct * 100, 3)
    result['zone_proximity_band'] = prox_band
    if nearest is not None:
        result['zone_strength'] = nearest.get('strength', None)
        result['nearest_zone_type'] = nearest['zone_type']
        result['nearest_zone_top'] = nearest['zone_top']
        result['nearest_zone_bottom'] = nearest['zone_bottom']

    return result


# ─────────────────────────────────────────────────────────────
# SESSION / NEWS
# ─────────────────────────────────────────────────────────────
def classify_session(dt):
    h = dt.hour
    if 0<=h<8: return 'Asian'
    elif 8<=h<13: return 'London'
    elif 13<=h<21: return 'New York'
    else: return 'Off-Hours'

def classify_news(dt, event_dates, daily_vol):
    d = dt.date() if hasattr(dt,'date') else dt
    if d in event_dates: return 'Major Event'
    if daily_vol is not None and d in daily_vol.index:
        if daily_vol.loc[d] > daily_vol.quantile(0.85): return 'High Volatility'
    return 'Normal'


# ─────────────────────────────────────────────────────────────
# NARRATIVE GENERATOR
# ─────────────────────────────────────────────────────────────
def generate_narrative(s):
    c1c = "green (bullish)" if s['c1_bullish'] else "red (bearish)"
    c2c = "green (bullish)" if s['c2_bullish'] else "red (bearish)"
    c3c = "green (bullish)" if s['c3_bullish'] else "red (bearish)"
    c1_atr_x = s['c1_body'] / s['c1_atr'] if s['c1_atr'] > 0 else 0

    n = f"**Setup on {s['datetime'].strftime('%A, %B %d, %Y at %H:%M UTC')}**\n\n"

    n += f"**Candle 1 (Big Candle)** was **{c1c}** with body covering **{s['c1_body_pct']:.1f}%** of range "
    n += f"(O: ${s['c1_open']:.2f}, C: ${s['c1_close']:.2f}, H: ${s['c1_high']:.2f}, L: ${s['c1_low']:.2f}). "
    n += f"Body was **{c1_atr_x:.1f}x ATR**. "
    n += f"Wick profile: **\"{s['c1_wick_label']}\"** — "

    if s['c1_upper_wick_pct'] > s['c1_lower_wick_pct'] + 10:
        n += f"{s['c1_upper_wick_pct']:.0f}% upper vs {s['c1_lower_wick_pct']:.0f}% lower wick — selling pressure near highs. "
    elif s['c1_lower_wick_pct'] > s['c1_upper_wick_pct'] + 10:
        n += f"{s['c1_lower_wick_pct']:.0f}% lower vs {s['c1_upper_wick_pct']:.0f}% upper wick — buying pressure from below. "
    else:
        n += f"balanced wicks ({s['c1_upper_wick_pct']:.0f}% upper, {s['c1_lower_wick_pct']:.0f}% lower) — clean directional move. "

    n += f"\n\n**Candle 2 (Inside Bar)** was **{c2c}**, fully contained within C1 "
    n += f"(H: ${s['c2_high']:.2f} <= ${s['c1_high']:.2f}, L: ${s['c2_low']:.2f} >= ${s['c1_low']:.2f}). "
    n += f"Wick profile: **\"{s['c2_wick_label']}\"** ({s['c2_upper_wick_pct']:.0f}% upper, {s['c2_lower_wick_pct']:.0f}% lower, {s['c2_body_pct']:.0f}% body). "

    if s['c1_bullish'] and not s['c2_bullish']:
        if 'Lower' in s['c2_wick_label']:
            n += "Red C2 with lower wick after green C1 = sellers tried but found support — likely bullish continuation. "
        elif 'Upper' in s['c2_wick_label']:
            n += "Red C2 with upper wick after green C1 = fade from highs, sellers present — potential reversal signal. "
        else:
            n += "Red C2 after green C1 signals some profit-taking during consolidation. "
    elif not s['c1_bullish'] and s['c2_bullish']:
        if 'Upper' in s['c2_wick_label']:
            n += "Green C2 with upper wick after red C1 = buyers tried but met resistance — likely bearish continuation. "
        elif 'Lower' in s['c2_wick_label']:
            n += "Green C2 with lower wick after red C1 = buying pressure building from below — potential reversal. "
        else:
            n += "Green C2 after red C1 signals some relief buying during consolidation. "
    elif s['c1_bullish'] and s['c2_bullish']:
        n += "Both candles bullish — consolidation confirms upward bias. "
    else:
        n += "Both candles bearish — consolidation confirms downward bias. "

    n += f"\n\n**Candle 3 (Breakout)** closed at **${s['c3_close']:.2f}**, which is "
    if s['direction'] == 'LONG':
        n += f"**above C2's high** of ${s['c2_high']:.2f} by ${s['c3_breakout_margin']:.2f} "
        n += f"({s['c3_breakout_margin_pct']:.2f}%, {s['c3_breakout_margin_r']:.2f}R). "
    else:
        n += f"**below C2's low** of ${s['c2_low']:.2f} by ${s['c3_breakout_margin']:.2f} "
        n += f"({s['c3_breakout_margin_pct']:.2f}%, {s['c3_breakout_margin_r']:.2f}R). "
    n += f"Candle was **{c3c}** (O: ${s['c3_open']:.2f} → C: ${s['c3_close']:.2f}), confirming **{s['direction']}** breakout. "
    if s['c1_direction_match']:
        n += "This **aligns** with C1 — momentum continuation. "
    else:
        n += "This **reverses** C1 — counter-trend breakout. "

    n += f"\n\n**Entry** at C3 close: **${s['entry_price']:.2f}** going **{s['direction']}**, "
    n += f"SL at ${s['stop_loss']:.2f} ({'C2 low' if s['direction']=='LONG' else 'C2 high'}), "
    n += f"risk: ${s['risk']:.2f} ({s['risk_pct']:.3f}%). "

    # Zone context with proximity
    n += f"\n\n**Zone Context:** "
    if s['zone'] == 'neutral':
        n += "No supply/demand zone nearby — **neutral** territory. "
        if pd.notna(s.get('zone_dist_pct')) and s['zone_dist_pct'] is not None:
            n += f"Nearest zone is {s['zone_dist_pct']:.2f}% away"
            if s.get('nearest_zone_type'):
                n += f" ({s['nearest_zone_type']} zone"
                if pd.notna(s.get('nearest_zone_top')):
                    n += f" at ${s['nearest_zone_top']:.2f}-${s['nearest_zone_bottom']:.2f}"
                n += ")"
            n += ". "
    elif s['zone'] == 'supply':
        n += f"At a **SUPPLY zone** (heavy prior selling). "
        if pd.notna(s.get('zone_dist_pct')):
            n += f"Dist: **{s['zone_dist_pct']:.2f}%** ({s.get('zone_proximity_band','')})."
        if pd.notna(s.get('zone_strength')):
            n += f" Strength: **{s['zone_strength']:.1f}×** ATR. "
        if pd.notna(s.get('nearest_zone_top')):
            n += f"Zone: ${s['nearest_zone_bottom']:.2f}-${s['nearest_zone_top']:.2f}. "
        n += f"{'**With-zone** (SHORT at supply).' if s['direction']=='SHORT' else '**Against-zone** (LONG at supply).'} "
    elif s['zone'] == 'demand':
        n += f"At a **DEMAND zone** (heavy prior buying). "
        if pd.notna(s.get('zone_dist_pct')):
            n += f"Dist: **{s['zone_dist_pct']:.2f}%** ({s.get('zone_proximity_band','')})."
        if pd.notna(s.get('zone_strength')):
            n += f" Strength: **{s['zone_strength']:.1f}×** ATR. "
        if pd.notna(s.get('nearest_zone_top')):
            n += f"Zone: ${s['nearest_zone_bottom']:.2f}-${s['nearest_zone_top']:.2f}. "
        n += f"{'**With-zone** (LONG at demand).' if s['direction']=='LONG' else '**Against-zone** (SHORT at demand).'} "
    elif s['zone'] == 'contested':
        n += "Both supply and demand overlap here — **contested**. "

    n += f"\n\nSession: {s['session']}, News: {s['news']}."

    # C4/C5/C6 follow-through
    n += f"\n\n**Follow-Through Analysis:**\n"
    for lbl, cr, fol in [('C4', s.get('c4_close_r'), s.get('c4_followed')),
                         ('C5', s.get('c5_close_r'), s.get('c5_followed')),
                         ('C6', s.get('c6_close_r'), s.get('c6_followed'))]:
        if cr is not None:
            emoji = "✅" if fol else "❌"
            n += f"- **{lbl}**: closed at **{cr:+.2f}R** from entry {emoji} {'(followed)' if fol else '(reversed)'}\n"
    n += f"- **{s.get('follow_count', 0)}/3 candles** followed the breakout direction\n"

    n += f"\n**Result:** "
    if s['win_1r']:
        n += f"**WIN** — 1R target reached. "
    else:
        n += f"**LOSS** — stopped out. "
    n += f"MFE: {s['max_favorable_r']:.2f}R, MAE: {s['max_adverse_r']:.2f}R."
    if s['hit_2r']: n += " Reached 2R — wider TP would have captured more."
    elif s['hit_15r']: n += " Reached 1.5R."

    return n


# ─────────────────────────────────────────────────────────────
# PATTERN DETECTION
# ─────────────────────────────────────────────────────────────
def detect_setups(df, body_ratio_thresh=0.65, atr_mult=1.3):
    """
    Detect the Inside Bar Breakout setup:
    C1: Big candle (body >> wicks, body > ATR * mult)
    C2: Inside bar (H2 <= H1, L2 >= L1)
    C3: Breakout candle — must CLOSE beyond C2's range:
        - LONG: C3 close > C2 high
        - SHORT: C3 close < C2 low
    Entry: At C3's close price
    Stop: Opposite end of C2 (C2 low for LONG, C2 high for SHORT)
    Track: C4, C5, C6 candle-by-candle follow-through
    """
    if len(df) < 20: return pd.DataFrame()
    df = df.copy()
    df['Body'] = abs(df['Close'] - df['Open'])
    df['Range'] = df['High'] - df['Low']
    df['BodyRatio'] = df['Body'] / df['Range'].replace(0, np.nan)
    df['IsBullish'] = df['Close'] > df['Open']
    df['TR'] = np.maximum(df['High']-df['Low'], np.maximum(abs(df['High']-df['Close'].shift(1)), abs(df['Low']-df['Close'].shift(1))))
    df['ATR'] = df['TR'].rolling(14).mean()
    setups = []
    indices = df.index.tolist()

    for i in range(14, len(df) - 6):  # need at least C1..C6
        c1, c2, c3 = df.iloc[i], df.iloc[i+1], df.iloc[i+2]
        c4 = df.iloc[i+3]
        c5 = df.iloc[i+4] if i+4 < len(df) else None
        c6 = df.iloc[i+5] if i+5 < len(df) else None

        if pd.isna(c1['ATR']) or c1['ATR']==0: continue
        # C1: Big candle
        if c1['BodyRatio'] < body_ratio_thresh: continue
        if c1['Body'] < c1['ATR'] * atr_mult: continue
        # C2: Inside bar
        if not (c2['High'] <= c1['High'] and c2['Low'] >= c1['Low']): continue

        # C3: Breakout — must CLOSE beyond C2's range
        if c3['Close'] > c2['High']:
            direction = 'LONG'
        elif c3['Close'] < c2['Low']:
            direction = 'SHORT'
        else:
            continue  # C3 didn't close beyond C2 range — no valid breakout

        c3_bull = c3['Close'] > c3['Open']

        # Entry at C3 close
        entry = c3['Close']
        sl = c2['Low'] if direction=='LONG' else c2['High']
        risk = entry - sl if direction=='LONG' else sl - entry
        if risk <= 0: continue

        # ── Wick profiles ──
        c1_wl, c1_up, c1_lp, c1_bp, c1_bull = classify_wick_profile(c1['Open'],c1['Close'],c1['High'],c1['Low'])
        c2_wl, c2_up, c2_lp, c2_bp, c2_bull = classify_wick_profile(c2['Open'],c2['Close'],c2['High'],c2['Low'])

        # ── Track C4, C5, C6 individually ──
        def candle_result(candle, entry_px, risk_px, d):
            if candle is None:
                return {'close_r': None, 'high_r': None, 'low_r': None, 'followed': None}
            if d == 'LONG':
                close_r = (candle['Close'] - entry_px) / risk_px
                high_r = (candle['High'] - entry_px) / risk_px
                low_r = (entry_px - candle['Low']) / risk_px  # adverse
                followed = candle['Close'] > entry_px
            else:
                close_r = (entry_px - candle['Close']) / risk_px
                high_r = (entry_px - candle['Low']) / risk_px  # favorable for short
                low_r = (candle['High'] - entry_px) / risk_px  # adverse for short
                followed = candle['Close'] < entry_px
            return {'close_r': round(close_r, 3), 'mfe_r': round(max(0, high_r), 3),
                    'mae_r': round(max(0, low_r), 3), 'followed': followed}

        c4_res = candle_result(c4, entry, risk, direction)
        c5_res = candle_result(c5, entry, risk, direction)
        c6_res = candle_result(c6, entry, risk, direction)

        # ── Track target hits over C4-C6 and beyond (up to 20 candles) ──
        hit_1r=hit_15r=hit_2r=hit_sl=False
        first_hit=None; mfe=0; mae=0

        for j in range(i+3, min(i+23, len(df))):
            c = df.iloc[j]
            if direction=='LONG':
                fav = (c['High']-entry)/risk
                adv = (entry-c['Low'])/risk
            else:
                fav = (entry-c['Low'])/risk
                adv = (c['High']-entry)/risk
            mfe=max(mfe,fav); mae=max(mae,adv)
            if direction=='LONG':
                if c['Low']<=sl and not hit_sl:
                    hit_sl=True
                    if first_hit is None: first_hit='SL'
                if c['High']>=entry+risk and not hit_1r:
                    hit_1r=True
                    if first_hit is None: first_hit='1R'
                if c['High']>=entry+1.5*risk: hit_15r=True
                if c['High']>=entry+2*risk: hit_2r=True
            else:
                if c['High']>=sl and not hit_sl:
                    hit_sl=True
                    if first_hit is None: first_hit='SL'
                if c['Low']<=entry-risk and not hit_1r:
                    hit_1r=True
                    if first_hit is None: first_hit='1R'
                if c['Low']<=entry-1.5*risk: hit_15r=True
                if c['Low']<=entry-2*risk: hit_2r=True

        win = hit_1r if first_hit=='1R' else (False if first_hit=='SL' else (c4_res['close_r'] is not None and c4_res['close_r']>0))

        # C3 breakout margin — how far beyond C2 range did C3 close?
        if direction == 'LONG':
            breakout_margin = c3['Close'] - c2['High']
        else:
            breakout_margin = c2['Low'] - c3['Close']
        breakout_margin_pct = (breakout_margin / entry) * 100
        breakout_margin_r = breakout_margin / risk if risk > 0 else 0

        # How many of C4/C5/C6 followed the direction?
        follow_count = sum(1 for r in [c4_res, c5_res, c6_res] if r['followed'] is True)

        c1wb = wick_bucket(c1_wl)
        c2wb = wick_bucket(c2_wl)

        setups.append({
            'datetime': indices[i],
            'c1_open':c1['Open'],'c1_close':c1['Close'],'c1_high':c1['High'],'c1_low':c1['Low'],
            'c1_body':c1['Body'],'c1_range':c1['Range'],'c1_body_ratio':c1['BodyRatio'],
            'c1_bullish':c1_bull,'c1_atr':c1['ATR'],
            'c1_wick_label':c1_wl,'c1_upper_wick_pct':c1_up,'c1_lower_wick_pct':c1_lp,'c1_body_pct':c1_bp,
            'c1_wick_bucket': c1wb,
            'c2_open':c2['Open'],'c2_close':c2['Close'],'c2_high':c2['High'],'c2_low':c2['Low'],
            'c2_bullish':c2_bull,
            'c2_wick_label':c2_wl,'c2_upper_wick_pct':c2_up,'c2_lower_wick_pct':c2_lp,'c2_body_pct':c2_bp,
            'c2_wick_bucket': c2wb,
            'c3_open':c3['Open'],'c3_close':c3['Close'],'c3_high':c3['High'],'c3_low':c3['Low'],
            'c3_bullish':c3_bull,
            'c3_breakout_margin': round(breakout_margin, 2),
            'c3_breakout_margin_pct': round(breakout_margin_pct, 3),
            'c3_breakout_margin_r': round(breakout_margin_r, 3),
            'direction': direction, 'entry_price':entry, 'stop_loss':sl,
            'risk':risk, 'risk_pct':(risk/entry)*100,
            # C4 candle-by-candle
            'c4_close_r': c4_res['close_r'], 'c4_mfe_r': c4_res['mfe_r'],
            'c4_mae_r': c4_res['mae_r'], 'c4_followed': c4_res['followed'],
            'c4_open': c4['Open'], 'c4_close': c4['Close'], 'c4_high': c4['High'], 'c4_low': c4['Low'],
            # C5
            'c5_close_r': c5_res['close_r'], 'c5_mfe_r': c5_res['mfe_r'],
            'c5_mae_r': c5_res['mae_r'], 'c5_followed': c5_res['followed'],
            'c5_open': c5['Open'] if c5 is not None else None,
            'c5_close': c5['Close'] if c5 is not None else None,
            'c5_high': c5['High'] if c5 is not None else None,
            'c5_low': c5['Low'] if c5 is not None else None,
            # C6
            'c6_close_r': c6_res['close_r'], 'c6_mfe_r': c6_res['mfe_r'],
            'c6_mae_r': c6_res['mae_r'], 'c6_followed': c6_res['followed'],
            'c6_open': c6['Open'] if c6 is not None else None,
            'c6_close': c6['Close'] if c6 is not None else None,
            'c6_high': c6['High'] if c6 is not None else None,
            'c6_low': c6['Low'] if c6 is not None else None,
            # Follow-through
            'follow_count': follow_count,
            # Overall outcomes
            'hit_1r':hit_1r,'hit_15r':hit_15r,'hit_2r':hit_2r,'hit_sl':hit_sl,
            'first_hit':first_hit,'win_1r':win,
            'max_favorable_r':mfe,'max_adverse_r':mae,
            'c1_direction_match': c1_bull == (direction=='LONG'),
            'c1_color': 'Green' if c1_bull else 'Red',
            'c2_color': 'Green' if c2_bull else 'Red',
            'scenario_key': get_scenario_key(c1_bull, c1wb, c2_bull, c2wb),
        })
    return pd.DataFrame(setups)


def detect_setups_with_diagnostics(df, body_ratio_thresh=0.65, atr_mult=1.3):
    """Wrapper that returns both setups and a diagnostic funnel."""
    diag = {
        'total_scanned': 0, 'pass_body_ratio': 0, 'pass_body_atr': 0,
        'pass_both_c1': 0, 'pass_inside_bar': 0, 'pass_c3_breakout': 0,
        'pass_valid_risk': 0,
    }
    if len(df) < 20:
        return pd.DataFrame(), diag

    df_c = df.copy()
    df_c['Body'] = abs(df_c['Close'] - df_c['Open'])
    df_c['Range'] = df_c['High'] - df_c['Low']
    df_c['BodyRatio'] = df_c['Body'] / df_c['Range'].replace(0, np.nan)
    df_c['TR'] = np.maximum(df_c['High']-df_c['Low'],
                            np.maximum(abs(df_c['High']-df_c['Close'].shift(1)),
                                       abs(df_c['Low']-df_c['Close'].shift(1))))
    df_c['ATR'] = df_c['TR'].rolling(14).mean()

    for i in range(14, len(df_c) - 6):
        c1 = df_c.iloc[i]
        if pd.isna(c1['ATR']) or c1['ATR'] == 0:
            continue
        diag['total_scanned'] += 1

        br_pass = c1['BodyRatio'] >= body_ratio_thresh
        atr_pass = c1['Body'] >= c1['ATR'] * atr_mult
        if br_pass:
            diag['pass_body_ratio'] += 1
        if atr_pass:
            diag['pass_body_atr'] += 1
        if not (br_pass and atr_pass):
            continue
        diag['pass_both_c1'] += 1

        c2 = df_c.iloc[i+1]
        if not (c2['High'] <= c1['High'] and c2['Low'] >= c1['Low']):
            continue
        diag['pass_inside_bar'] += 1

        c3 = df_c.iloc[i+2]
        if c3['Close'] > c2['High']:
            direction = 'LONG'
        elif c3['Close'] < c2['Low']:
            direction = 'SHORT'
        else:
            continue
        diag['pass_c3_breakout'] += 1

        entry = c3['Close']
        sl = c2['Low'] if direction == 'LONG' else c2['High']
        risk = entry - sl if direction == 'LONG' else sl - entry
        if risk > 0:
            diag['pass_valid_risk'] += 1

    setups = detect_setups(df, body_ratio_thresh, atr_mult)
    return setups, diag


# ─────────────────────────────────────────────────────────────
# ENRICHMENT
# ─────────────────────────────────────────────────────────────
def enrich_setups(sdf, df_1h, zones_df, event_dates, zone_lookback=720, zone_proximity=0.003):
    if sdf.empty: return sdf
    s = sdf.copy()
    dr = df_1h.resample('D').agg({'High':'max','Low':'min'})
    dr['DR'] = dr['High']-dr['Low']
    dv = dr['DR'].dropna(); dv.index = dv.index.date

    # Classify zones with full context
    zone_info = s.apply(
        lambda r: classify_zone(r['datetime'], r['entry_price'], zones_df,
                                lookback_hours=zone_lookback, proximity_pct=zone_proximity/100),
        axis=1
    )
    zone_df = pd.DataFrame(zone_info.tolist(), index=s.index)
    s['zone'] = zone_df['zone']
    s['zone_dist_pct'] = zone_df['zone_dist_pct']
    s['zone_strength'] = zone_df['zone_strength']
    s['nearest_zone_type'] = zone_df['nearest_zone_type']
    s['nearest_zone_top'] = zone_df['nearest_zone_top']
    s['nearest_zone_bottom'] = zone_df['nearest_zone_bottom']
    s['zone_proximity_band'] = zone_df['zone_proximity_band']

    s['session'] = s['datetime'].apply(classify_session)
    s['news'] = s['datetime'].apply(lambda dt: classify_news(dt, event_dates, dv))
    s['date'] = s['datetime'].dt.date
    s['month_name'] = s['datetime'].dt.strftime('%b')
    s['year_month'] = s['datetime'].dt.to_period('M').astype(str)
    s['day_name'] = s['datetime'].dt.strftime('%a')
    s['hour'] = s['datetime'].dt.hour
    s['day_of_week'] = s['datetime'].dt.dayofweek
    s['alignment'] = s['c1_direction_match'].map({True:'Aligned',False:'Counter'})
    s['pnl_r'] = s['win_1r'].apply(lambda w: 1.0 if w else -1.0)
    s['cumulative_r'] = s['pnl_r'].cumsum()
    return s


# ─────────────────────────────────────────────────────────────
# STATS
# ─────────────────────────────────────────────────────────────
def calc_stats(df_sub, label=""):
    n = len(df_sub)
    if n==0:
        return {'Label':label,'Trades':0,'Win Rate':0,'Avg R':0,'PF':0,'Hit 1R%':0,'Hit 1.5R%':0,'Hit 2R%':0,'Avg MFE':0,'Avg MAE':0}
    wins = df_sub['win_1r'].sum()
    tw = df_sub[df_sub['pnl_r']>0]['pnl_r'].sum()
    tl = abs(df_sub[df_sub['pnl_r']<0]['pnl_r'].sum())
    return {'Label':label,'Trades':n,'Win Rate':round(wins/n*100,1),'Avg R':round(df_sub['pnl_r'].mean(),3),
        'PF':round(tw/tl,2) if tl>0 else 999,
        'Hit 1R%':round(df_sub['hit_1r'].mean()*100,1),'Hit 1.5R%':round(df_sub['hit_15r'].mean()*100,1),
        'Hit 2R%':round(df_sub['hit_2r'].mean()*100,1),
        'Avg MFE':round(df_sub['max_favorable_r'].mean(),2),'Avg MAE':round(df_sub['max_adverse_r'].mean(),2)}

def seg_analysis(setups, col, col_name):
    rows = [calc_stats(setups[setups[col]==v], str(v)) for v in sorted(setups[col].unique())]
    return pd.DataFrame(rows).rename(columns={'Label':col_name})


# ─────────────────────────────────────────────────────────────
# CHARTS
# ─────────────────────────────────────────────────────────────
def plot_equity(s, title="Equity (R)"):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=s['datetime'],y=s['cumulative_r'],mode='lines',
        line=dict(color=COLORS['gold'],width=2),fill='tozeroy',fillcolor='rgba(255,215,0,0.08)'))
    fig.add_hline(y=0,line_dash="dash",line_color="gray",opacity=0.4)
    fig.update_layout(title=title,template='plotly_dark',height=370,margin=dict(l=40,r=40,t=50,b=40))
    return fig

def plot_rolling_wr(s, w=20):
    if len(s)<w: w=max(3,len(s)//2)
    s=s.copy(); s['rwr']=s['win_1r'].rolling(w).mean()*100
    fig=go.Figure()
    fig.add_trace(go.Scatter(x=s['datetime'],y=s['rwr'],mode='lines',line=dict(color=COLORS['cyan'],width=2)))
    fig.add_hline(y=50,line_dash="dash",line_color="gray",opacity=0.4)
    fig.update_layout(title=f"Rolling Win Rate ({w}-trade)",template='plotly_dark',height=340,margin=dict(l=40,r=40,t=50,b=40))
    return fig

def plot_bar(ds, xc, title):
    cs=[COLORS['win'] if wr>55 else COLORS['loss'] if wr<45 else COLORS['gold'] for wr in ds['Win Rate']]
    fig=go.Figure(go.Bar(x=ds[xc],y=ds['Win Rate'],marker_color=cs,
        text=[f"{wr}%\nn={n}" for wr,n in zip(ds['Win Rate'],ds['Trades'])],textposition='outside',textfont=dict(size=10)))
    fig.add_hline(y=50,line_dash="dash",line_color="gray",opacity=0.4)
    fig.update_layout(title=title,template='plotly_dark',height=380,yaxis=dict(range=[0,100]),margin=dict(l=40,r=40,t=50,b=70))
    return fig

def plot_monthly(s):
    m=s.groupby('year_month').agg(trades=('win_1r','count'),wins=('win_1r','sum'),total_r=('pnl_r','sum')).reset_index()
    m['wr']=m['wins']/m['trades']*100
    fig=make_subplots(specs=[[{"secondary_y":True}]])
    fig.add_trace(go.Bar(x=m['year_month'],y=m['total_r'],marker_color=[COLORS['win'] if r>0 else COLORS['loss'] for r in m['total_r']],name='Total R'),secondary_y=False)
    fig.add_trace(go.Scatter(x=m['year_month'],y=m['wr'],mode='lines+markers',line=dict(color=COLORS['gold'],width=2),name='Win Rate %'),secondary_y=True)
    fig.update_layout(title='Monthly Performance',template='plotly_dark',height=370,margin=dict(l=40,r=40,t=50,b=70),xaxis_tickangle=-45)
    return fig

def plot_heatmap(s, rc, cc, ro=None, title="Heatmap"):
    pv=s.pivot_table(values='win_1r',index=rc,columns=cc,aggfunc='mean')
    ct=s.pivot_table(values='win_1r',index=rc,columns=cc,aggfunc='count').fillna(0)
    if ro: pv=pv.reindex([r for r in ro if r in pv.index]); ct=ct.reindex([r for r in ro if r in ct.index])
    txt=[]
    for i in range(len(pv)):
        row=[]
        for j in range(len(pv.columns)):
            v=pv.iloc[i,j]; c=ct.iloc[i,j] if not pd.isna(ct.iloc[i,j]) else 0
            row.append(f"{v*100:.0f}%\nn={int(c)}" if not pd.isna(v) else '')
        txt.append(row)
    fig=go.Figure(go.Heatmap(z=pv.values*100,x=[str(c) for c in pv.columns],y=pv.index,
        colorscale=[[0,COLORS['loss']],[0.5,'#333'],[1,COLORS['win']]],zmid=50,
        text=txt,texttemplate="%{text}",textfont=dict(size=9),colorbar=dict(title='Win%')))
    fig.update_layout(title=title,template='plotly_dark',height=max(300,len(pv)*50+100),margin=dict(l=80,r=40,t=50,b=60))
    return fig

def plot_scenario_matrix(s):
    s=s.copy()
    s['c1p']=s['c1_color']+' / '+s['c1_wick_bucket']
    s['c2p']=s['c2_color']+' / '+s['c2_wick_bucket']
    pv=s.pivot_table(values='win_1r',index='c1p',columns='c2p',aggfunc='mean')
    ct=s.pivot_table(values='win_1r',index='c1p',columns='c2p',aggfunc='count').fillna(0)
    txt=[]
    for i in range(len(pv)):
        row=[]
        for j in range(len(pv.columns)):
            v=pv.iloc[i,j]; c=ct.iloc[i,j] if not pd.isna(ct.iloc[i,j]) else 0
            row.append(f"{v*100:.0f}%\nn={int(c)}" if not pd.isna(v) and c>=2 else '')
        txt.append(row)
    fig=go.Figure(go.Heatmap(z=pv.values*100,x=pv.columns.tolist(),y=pv.index.tolist(),
        colorscale=[[0,COLORS['loss']],[0.5,'#444'],[1,COLORS['win']]],zmid=50,
        text=txt,texttemplate="%{text}",textfont=dict(size=9),colorbar=dict(title='Win%')))
    fig.update_layout(title='Scenario Matrix: C1 Profile (rows) x C2 Profile (cols)',
        template='plotly_dark',height=max(450,len(pv)*55+120),margin=dict(l=160,r=40,t=60,b=120),xaxis_tickangle=-35)
    return fig

def plot_candlestick_example(df, s, n_before=5, n_after=10):
    idx=df.index.get_indexer([s['datetime']],method='nearest')[0]
    st_i=max(0,idx-n_before); en=min(len(df),idx+n_after); sub=df.iloc[st_i:en]
    fig=go.Figure(go.Candlestick(x=sub.index,open=sub['Open'],high=sub['High'],low=sub['Low'],close=sub['Close'],
        increasing_line_color=COLORS['win'],decreasing_line_color=COLORS['loss']))
    labels = [(0,'C1: Big',COLORS['purple']),(1,'C2: Inside',COLORS['blue']),
              (2,'C3: Breakout',COLORS['orange']),(3,'C4',COLORS['gold']),
              (4,'C5',COLORS['cyan']),(5,'C6','#aaa')]
    for off,lbl,clr in labels:
        ci=idx+off
        if ci<len(df):
            c=df.iloc[ci]
            fig.add_annotation(x=df.index[ci],y=c['High'],text=lbl,showarrow=True,arrowhead=2,arrowcolor=clr,font=dict(color=clr,size=9),yshift=12)
    fig.add_hline(y=s['entry_price'],line_dash="dot",line_color=COLORS['gold'],opacity=0.5,annotation_text="Entry (C3 close)")
    fig.add_hline(y=s['stop_loss'],line_dash="dot",line_color=COLORS['loss'],opacity=0.5,annotation_text="SL")
    # Mark C2 range
    fig.add_hline(y=s['c2_high'],line_dash="dash",line_color=COLORS['blue'],opacity=0.3,annotation_text="C2 High")
    fig.add_hline(y=s['c2_low'],line_dash="dash",line_color=COLORS['blue'],opacity=0.3,annotation_text="C2 Low")
    res="WIN" if s['win_1r'] else "LOSS"
    follow = f" | {s.get('follow_count',0)}/3 followed" if 'follow_count' in s.index else ""
    fig.update_layout(title=f"{s['direction']} | {res}{follow} | {s['datetime'].strftime('%Y-%m-%d %H:%M')}",
        template='plotly_dark',height=430,xaxis_rangeslider_visible=False,margin=dict(l=40,r=40,t=50,b=40))
    return fig


# ─────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────
def main():
    st.title("📊 Inside Bar Strategy Analyzer")
    st.caption("Multi-Asset · Enhanced Wick Analysis · Scenario Testing · Candle-by-Candle Narratives")

    with st.sidebar:
        st.header("⚙️ Configuration")
        st.subheader("🔍 Asset Selection")
        categories = st.multiselect("Categories", list(ASSET_CATEGORIES.keys()), default=["🏆 Commodities"])
        available = {}
        for cat in categories:
            available.update(ASSET_CATEGORIES[cat])
        if not available:
            st.warning("Select at least one category."); return
        selected = st.multiselect("Assets", list(available.keys()),
            default=[list(available.keys())[0]] if available else [])
        if not selected:
            st.info("Select at least one asset."); return

        st.markdown("---")
        st.subheader("📐 Timeframe")
        timeframes = st.multiselect("Timeframes",
            ['15m','30m','1H','4H'], default=['1H','4H'],
            help="15m and 30m: Yahoo Finance limits these to ~60 days of history. "
                 "1H: up to 730 days (~2 years). 4H: resampled from 1H data.")
        if any(t in timeframes for t in ['15m','30m']):
            st.info("⚠️ Yahoo Finance limits 15m/30m data to **~60 days**. "
                    "This means fewer setups for statistical analysis. 1H/4H give ~2 years.")

        st.subheader("🕯️ Big Candle Definition")
        body_ratio = st.slider("Min body ratio", 0.50, 0.85, 0.60, 0.05,
            help="What % of the candle's total range (high-low) must be body (open-close). "
                 "Example: A candle with High=110, Low=100 (range=10) and Open=101, Close=109 "
                 "(body=8) has a body ratio of 80%. Higher = stricter = fewer setups. "
                 "60% is a good starting point.")
        atr_mult = st.slider("Min body size (× ATR-14)", 0.5, 2.5, 1.0, 0.1,
            help="The body must be at least this many times the 14-period ATR. "
                 "ATR measures average volatility. 1.0× means the body equals one average range. "
                 "1.5× means 50% bigger than average. Lower this to get more setups, "
                 "raise it to only catch the biggest moves. Start at 1.0×.")
        st.subheader("📍 Zone Settings")
        zone_lb = st.slider("Zone lookback (hrs)", 120, 1440, 720, 120,
            help="How far back to look for supply/demand zones. 720h ≈ 30 days.")
        zone_prox = st.slider("Zone proximity (%)", 0.1, 1.5, 0.3, 0.1,
            help="How close price must be to a zone boundary to count as 'at zone'. "
                 "At $2600 gold, 0.3% ≈ $7.80 distance.")
        zone_strength_min = st.slider("Min zone strength (×ATR)", 1.0, 3.0, 1.5, 0.25,
            help="Minimum candle body vs ATR to create a zone. Higher = only the strongest zones.")
        st.subheader("📅 Data")
        data_years = st.selectbox("Lookback", [1,2], index=1,
            help="1H/4H: Yahoo provides up to 2 years. "
                 "15m/30m: Yahoo limits to ~60 days regardless of this setting.")
        st.markdown("---")
        run = st.button("🚀 Run Analysis", type="primary", use_container_width=True)

    if not run and 'results' not in st.session_state:
        st.info("👈 Select assets and parameters, then click **Run Analysis**.")
        with st.expander("📖 Strategy Logic & Wick Analysis", expanded=True):
            st.markdown("""
**The Inside Bar Breakout Strategy:**

1. **C1 (Big Candle):** Body is much larger than wicks (configurable ratio) and exceeds ATR threshold. Signals strong directional conviction.
2. **C2 (Inside Bar):** Fully contained within C1 (high ≤ C1 high, low ≥ C1 low). Signals consolidation.
3. **C3 (Breakout):** Must **close beyond C2's range** — above C2 high = LONG, below C2 low = SHORT. This is the confirmation.
4. **Entry** at C3's close. Stop loss at opposite end of C2. Then we track C4, C5, C6 to see if the breakout direction holds.

**Wick Profiles:** Full Body (Marubozu), Heavy Upper/Lower Wick, Both Wicks, Balanced, Doji

**Scenario Testing:** Tests all C1 color/wick × C2 color/wick combos

**Dimensions:** Supply/Demand Zones (with proximity & strength), Sessions, News Events, Day/Month, Alignment, Follow-Through
            """)
        return

    event_dates = get_major_event_dates()
    all_results = {}
    all_diagnostics = {}
    progress = st.progress(0, text="Starting...")
    total = len(selected) * len(timeframes); ti = 0

    for aname in selected:
        ticker = available[aname]
        # Cache dataframes per interval to avoid re-fetching
        fetched_dfs = {}

        for tf in timeframes:
            ti += 1
            progress.progress(ti/max(total,1), text=f"Fetching {aname} {tf}...")

            # Determine which raw interval to fetch
            if tf in ['15m', '30m']:
                raw_interval = tf
                if raw_interval not in fetched_dfs:
                    try:
                        fetched_dfs[raw_interval] = fetch_asset_data(ticker, interval=raw_interval, period_years=data_years)
                    except Exception as e:
                        st.warning(f"Failed {aname} {tf}: {e}"); continue
                df = fetched_dfs[raw_interval]
            elif tf in ['1H', '4H']:
                if '1h' not in fetched_dfs:
                    try:
                        fetched_dfs['1h'] = fetch_asset_data(ticker, interval='1h', period_years=data_years)
                    except Exception as e:
                        st.warning(f"Failed {aname} {tf}: {e}"); continue
                if tf == '1H':
                    df = fetched_dfs['1h']
                else:
                    df = resample_to_4h(fetched_dfs['1h'])

            if df is None or df.empty or len(df) < 50:
                st.warning(f"Insufficient data for {aname} {tf} ({len(df) if df is not None else 0} candles)")
                continue

            progress.progress(ti/max(total,1), text=f"Detecting: {aname} {tf} ({len(df):,} candles)...")

            # Detect zones
            zones = detect_zones(df, zone_strength_min)

            # Detect setups WITH diagnostics
            setups, diag = detect_setups_with_diagnostics(df, body_ratio, atr_mult)

            key = f"{aname} — {tf}"
            all_diagnostics[key] = diag
            all_diagnostics[key]['total_candles'] = len(df)
            all_diagnostics[key]['date_range'] = f"{df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')}"

            if setups.empty:
                st.warning(f"No setups for {key} — see diagnostics below")
                continue

            # Enrich — use the 1h df if available for daily vol, otherwise use the tf df
            enrich_df = fetched_dfs.get('1h', df)
            setups = enrich_setups(setups, enrich_df, zones, event_dates,
                                   zone_lookback=zone_lb, zone_proximity=zone_prox)
            all_results[key] = {'setups':setups,'df':df,'zones':zones,'asset':aname,'ticker':ticker,'tf':tf}

    progress.empty()

    # ── Show diagnostics for ALL timeframes including ones with 0 setups ──
    with st.expander("🔬 Setup Detection Diagnostics — Why are there this many (or few) setups?", expanded=True):
        st.caption("This funnel shows how many candles pass each filter stage. "
                   "If too few setups, look for the biggest drop-off and adjust that slider.")
        for key, diag in all_diagnostics.items():
            st.markdown(f"**{key}** — {diag['date_range']} — {diag['total_candles']:,} candles")
            funnel_data = {
                'Stage': [
                    f"1. Total candles scanned",
                    f"2. Pass C1 body ratio (≥{body_ratio*100:.0f}%)",
                    f"3. Pass C1 body size (≥{atr_mult}× ATR)",
                    f"4. Pass C1 body ratio AND size",
                    f"5. C2 is inside bar (H≤C1H, L≥C1L)",
                    f"6. C3 closes beyond C2 range",
                    f"7. Valid risk (entry - SL > 0)",
                ],
                'Count': [
                    diag['total_scanned'],
                    diag['pass_body_ratio'],
                    diag['pass_body_atr'],
                    diag['pass_both_c1'],
                    diag['pass_inside_bar'],
                    diag['pass_c3_breakout'],
                    diag['pass_valid_risk'],
                ],
            }
            funnel_df = pd.DataFrame(funnel_data)
            funnel_df['% of Total'] = (funnel_df['Count'] / max(diag['total_scanned'],1) * 100).round(1)
            funnel_df['Drop-off'] = ['—'] + [
                f"-{funnel_df['Count'].iloc[i-1] - funnel_df['Count'].iloc[i]:,}"
                for i in range(1, len(funnel_df))
            ]
            st.dataframe(funnel_df, use_container_width=True, hide_index=True)
            st.markdown("---")

    if not all_results:
        st.error("No setups found on any timeframe. Check the diagnostics above — "
                 "the biggest drop-off tells you which filter to relax.")
        st.markdown("""
**Common fixes:**
- **Big drop at Stage 2 (body ratio)?** → Lower "Min body ratio" slider (try 55%)
- **Big drop at Stage 3 (ATR)?** → Lower "Min body size" slider (try 0.8×)
- **Big drop at Stage 5 (inside bar)?** → This is strict by definition — nothing to adjust
- **Big drop at Stage 6 (C3 breakout)?** → This is the strictest rule. C3 must CLOSE above C2 high or below C2 low. This is correct per your strategy.
        """)
        return
    st.session_state['results'] = all_results
    st.success(f"Found setups across {len(all_results)} asset/timeframe combinations")

    tab_names = list(all_results.keys())
    if len(all_results) > 1: tab_names.append("📋 Cross-Asset Comparison")
    tabs = st.tabs(tab_names)

    for tab_i, (key, result) in enumerate(all_results.items()):
        setups = result['setups']; df = result['df']
        with tabs[tab_i]:
            st.header(f"{key} — {len(setups)} Setups")
            days_of_data = (df.index[-1] - df.index[0]).days
            data_note = ""
            if result['tf'] in ['15m','30m'] and days_of_data < 65:
                data_note = f" ⚠️ Yahoo limits {result['tf']} to ~60 days"
            st.caption(f"{df.index[0].strftime('%Y-%m-%d')} to {df.index[-1].strftime('%Y-%m-%d')} "
                       f"({days_of_data} days) | {len(df):,} candles{data_note}")

            ov = calc_stats(setups)
            m1,m2,m3,m4,m5,m6 = st.columns(6)
            m1.metric("Setups",ov['Trades']); m2.metric("Win Rate",f"{ov['Win Rate']}%")
            m3.metric("PF",ov['PF']); m4.metric("Avg R",f"{ov['Avg R']:.3f}")
            c4f_rate = setups['c4_followed'].mean()*100 if 'c4_followed' in setups.columns else 0
            m5.metric("C4 Follow Rate",f"{c4f_rate:.0f}%")
            m6.metric("Hit 2R",f"{ov['Hit 2R%']}%")

            inner = st.tabs(["📈 Overview","🧬 Scenarios","🏗️ Zones","🕐 Time","📰 News","🔍 Breakdown","📝 Log","🕯️ Examples"])

            with inner[0]:
                st.plotly_chart(plot_equity(setups,f"Equity — {key}"),use_container_width=True)
                c1,c2=st.columns(2)
                with c1: st.plotly_chart(plot_rolling_wr(setups),use_container_width=True)
                with c2: st.plotly_chart(plot_monthly(setups),use_container_width=True)
                ds=seg_analysis(setups,'direction','Direction')
                st.plotly_chart(plot_bar(ds,'Direction','Win Rate by Direction'),use_container_width=True)

                st.markdown("---")
                st.subheader("📊 C4 / C5 / C6 Follow-Through Analysis")
                st.caption("After entering at C3 close, how often does each subsequent candle continue in the breakout direction?")

                fc1,fc2,fc3,fc4 = st.columns(4)
                c4_follow = setups['c4_followed'].mean()*100 if 'c4_followed' in setups.columns else 0
                c5_follow = setups['c5_followed'].dropna().mean()*100 if 'c5_followed' in setups.columns else 0
                c6_follow = setups['c6_followed'].dropna().mean()*100 if 'c6_followed' in setups.columns else 0
                avg_follow = setups['follow_count'].mean() if 'follow_count' in setups.columns else 0
                with fc1: st.metric("C4 Follow Rate", f"{c4_follow:.1f}%")
                with fc2: st.metric("C5 Follow Rate", f"{c5_follow:.1f}%")
                with fc3: st.metric("C6 Follow Rate", f"{c6_follow:.1f}%")
                with fc4: st.metric("Avg Candles Following", f"{avg_follow:.1f}/3")

                # Follow-through by direction
                for d in ['LONG','SHORT']:
                    sub_d = setups[setups['direction']==d]
                    if len(sub_d) > 0:
                        c4f = sub_d['c4_followed'].mean()*100
                        c5f = sub_d['c5_followed'].dropna().mean()*100
                        c6f = sub_d['c6_followed'].dropna().mean()*100
                        st.markdown(f"**{d}**: C4={c4f:.0f}% C5={c5f:.0f}% C6={c6f:.0f}% "
                                    f"(avg {sub_d['follow_count'].mean():.1f}/3 followed, n={len(sub_d)})")

                # Follow-through count as dimension
                if 'follow_count' in setups.columns:
                    fc_stats = seg_analysis(setups, 'follow_count', 'Candles Following (of 3)')
                    st.plotly_chart(plot_bar(fc_stats, 'Candles Following (of 3)',
                        'Win Rate by # Candles Following Breakout Direction'), use_container_width=True)

                st.markdown("---")
                st.subheader("📐 Breakout Margin Analysis")
                st.caption("How far C3 closed beyond C2's range — does a stronger breakout predict better outcomes?")
                if 'c3_breakout_margin_r' in setups.columns:
                    bm = setups.copy()
                    bm['breakout_band'] = pd.cut(
                        bm['c3_breakout_margin_r'],
                        bins=[-0.01, 0.25, 0.5, 1.0, 1.5, float('inf')],
                        labels=['0-0.25R', '0.25-0.5R', '0.5-1.0R', '1.0-1.5R', '1.5R+']
                    ).astype(str)
                    bm_stats = seg_analysis(bm, 'breakout_band', 'Breakout Margin')
                    st.plotly_chart(plot_bar(bm_stats, 'Breakout Margin',
                        'Win Rate by C3 Breakout Margin (distance beyond C2 range)'), use_container_width=True)
                    st.dataframe(bm_stats, use_container_width=True, hide_index=True)

            with inner[1]:
                st.subheader("🧬 Scenario Matrix: C1 × C2 Profiles → Win Rate")
                st.caption("Rows = Big candle color/wick profile. Columns = Inside bar color/wick profile. Cell = Win rate.")
                st.plotly_chart(plot_scenario_matrix(setups),use_container_width=True)
                st.markdown("---")

                st.subheader("Scenario Breakdown Table")
                sc_rows = []
                for sc in setups['scenario_key'].unique():
                    sub = setups[setups['scenario_key']==sc]
                    if len(sub)>=3:
                        ln=(sub['direction']=='LONG').sum(); sn=(sub['direction']=='SHORT').sum()
                        lw=sub[sub['direction']=='LONG']['win_1r'].mean()*100 if ln>0 else None
                        sw=sub[sub['direction']=='SHORT']['win_1r'].mean()*100 if sn>0 else None
                        sc_rows.append({'Scenario':sc,'Total':len(sub),'Longs':ln,'Shorts':sn,
                            'Long WR':f"{lw:.1f}%" if lw is not None else '—',
                            'Short WR':f"{sw:.1f}%" if sw is not None else '—',
                            'Overall WR':f"{sub['win_1r'].mean()*100:.1f}%"})
                if sc_rows:
                    st.dataframe(pd.DataFrame(sc_rows).sort_values('Total',ascending=False),
                        use_container_width=True,hide_index=True,height=500)

                st.markdown("---")
                st.subheader("Wick Profile Win Rates")
                c1c,c2c=st.columns(2)
                with c1c:
                    c1ws=seg_analysis(setups,'c1_wick_label','C1 Wick')
                    st.plotly_chart(plot_bar(c1ws,'C1 Wick','C1 Wick → Win Rate'),use_container_width=True)
                with c2c:
                    c2ws=seg_analysis(setups,'c2_wick_label','C2 Wick')
                    st.plotly_chart(plot_bar(c2ws,'C2 Wick','C2 Wick → Win Rate'),use_container_width=True)

                st.subheader("C1 Color × C2 Color")
                st.plotly_chart(plot_heatmap(setups,'c1_color','c2_color',title='Win Rate: C1 Color × C2 Color'),use_container_width=True)

            with inner[2]:
                st.subheader("🏗️ Supply & Demand Zone Analysis")

                # ── Zone Definitions ──
                with st.expander("📖 What Are Supply & Demand Zones? (Click to expand)", expanded=False):
                    st.markdown(f"""
**How Zones Are Detected:**

The dashboard identifies zones by scanning for **strong candles** — candles where the body
(open-to-close distance) exceeds **{zone_strength_min}× the 14-period ATR** (configurable
in the sidebar as "Min zone strength"). These represent moments of aggressive buying or selling.

**Supply Zone (🔴 Selling Pressure):**
A supply zone is created at the **origin of a strong bearish (red) candle**. The zone spans
from the candle's high down to its open price. The logic: institutional sellers entered aggressively
at this level. If price revisits, the same sellers (or similar order flow) may push price down again.

**Demand Zone (🟢 Buying Pressure):**
A demand zone is created at the **origin of a strong bullish (green) candle**. The zone spans
from the candle's open price down to its low. Institutional buyers entered here — a revisit
may find buyers again.

**How Lookback Works:**
The "Zone lookback" slider (currently **{zone_lb} hours ≈ {zone_lb//24} days**) controls how
far back the dashboard looks for zones. Zones older than this are ignored — they've likely been
consumed or invalidated.

**How Proximity Works:**
The "Zone proximity" slider (currently **{zone_prox}%**) determines how close the entry price
must be to a zone boundary to classify the setup as "at a zone". At ~$2600 gold, {zone_prox}%
≈ ${2600 * zone_prox / 100:.1f}. If the entry price is within this distance of any zone edge
(or inside the zone itself), the setup is classified as being at that zone type.

**Zone Strength:**
Each zone has a strength rating = the originating candle's body ÷ ATR. A zone with strength
2.5× means the candle that created it was 2.5 times the average range — a very aggressive move.
Stronger zones may hold better when revisited.

**Zone Classification for Each Setup:**
- **Supply**: Entry price is near/inside a supply zone
- **Demand**: Entry price is near/inside a demand zone
- **Contested**: Both supply and demand zones overlap near the entry
- **Neutral**: No recent zone is nearby
""")

                # ── Current Zone Stats ──
                zones_data = result['zones']
                if not zones_data.empty:
                    zc1, zc2, zc3 = st.columns(3)
                    supply_zones = zones_data[zones_data['zone_type']=='supply']
                    demand_zones = zones_data[zones_data['zone_type']=='demand']
                    with zc1:
                        st.metric("Total Zones Detected", len(zones_data))
                    with zc2:
                        st.metric("🔴 Supply Zones", len(supply_zones),
                                  f"Avg strength: {supply_zones['strength'].mean():.1f}×" if len(supply_zones)>0 else "")
                    with zc3:
                        st.metric("🟢 Demand Zones", len(demand_zones),
                                  f"Avg strength: {demand_zones['strength'].mean():.1f}×" if len(demand_zones)>0 else "")

                st.markdown("---")

                # ── Win Rate by Zone Type ──
                st.subheader("Win Rate by Zone Classification")
                zs=seg_analysis(setups,'zone','Zone')
                st.plotly_chart(plot_bar(zs,'Zone','Win Rate by Zone'),use_container_width=True)
                st.dataframe(zs, use_container_width=True, hide_index=True)

                st.markdown("---")

                # ── Zone × Direction Heatmap ──
                st.subheader("Zone × Direction Interaction")
                st.plotly_chart(plot_heatmap(setups,'zone','direction',title='Zone × Direction Win Rate'),use_container_width=True)

                # ── With-Zone vs Against-Zone ──
                st.subheader("With-Zone vs Against-Zone Edge")
                st.caption("'With Zone' = LONG at demand or SHORT at supply (trading with expected zone reaction). "
                           "'Against Zone' = the opposite.")
                wz=setups[((setups['zone']=='demand')&(setups['direction']=='LONG'))|((setups['zone']=='supply')&(setups['direction']=='SHORT'))]
                az=setups[((setups['zone']=='demand')&(setups['direction']=='SHORT'))|((setups['zone']=='supply')&(setups['direction']=='LONG'))]
                nz=setups[setups['zone']=='neutral']
                co1,co2,co3=st.columns(3)
                ws=calc_stats(wz);azs=calc_stats(az);ns=calc_stats(nz)
                with co1:
                    st.markdown("**✅ With Zone**")
                    st.metric("WR",f"{ws['Win Rate']}%",f"n={ws['Trades']}")
                    st.metric("PF",ws['PF'])
                    st.metric("Avg MFE",f"{ws['Avg MFE']}R")
                with co2:
                    st.markdown("**❌ Against Zone**")
                    st.metric("WR",f"{azs['Win Rate']}%",f"n={azs['Trades']}")
                    st.metric("PF",azs['PF'])
                    st.metric("Avg MFE",f"{azs['Avg MFE']}R")
                with co3:
                    st.markdown("**⚪ Neutral**")
                    st.metric("WR",f"{ns['Win Rate']}%",f"n={ns['Trades']}")
                    st.metric("PF",ns['PF'])
                    st.metric("Avg MFE",f"{ns['Avg MFE']}R")

                st.markdown("---")

                # ── NEW: Proximity Band Analysis ──
                st.subheader("📏 Zone Proximity Analysis")
                st.caption(f"How does win rate change based on distance from the nearest zone? "
                           f"Current proximity threshold: {zone_prox}% "
                           f"(≈${setups['entry_price'].mean() * zone_prox / 100:.1f} at current gold prices)")

                prox_stats = seg_analysis(setups, 'zone_proximity_band', 'Proximity Band')
                # Order the bands logically
                band_order = ['Inside Zone', 'Touching (≤0.1%)', 'Very Close (0.1-0.3%)',
                              'Near (0.3-0.6%)', 'Moderate (0.6-1%)', 'Far (>1%)', 'No Zone']
                prox_stats['sort_key'] = prox_stats['Proximity Band'].apply(
                    lambda x: band_order.index(x) if x in band_order else 99)
                prox_stats = prox_stats.sort_values('sort_key').drop(columns=['sort_key'])
                st.plotly_chart(plot_bar(prox_stats, 'Proximity Band', 'Win Rate by Distance from Nearest Zone'),
                                use_container_width=True)
                st.dataframe(prox_stats, use_container_width=True, hide_index=True)

                # Proximity scatter plot
                prox_data = setups[setups['zone_dist_pct'].notna()].copy()
                if len(prox_data) > 5:
                    fig_prox = go.Figure()
                    wins_p = prox_data[prox_data['win_1r']==True]
                    losses_p = prox_data[prox_data['win_1r']==False]
                    fig_prox.add_trace(go.Scatter(
                        x=wins_p['zone_dist_pct'], y=wins_p['max_favorable_r'],
                        mode='markers', name='Wins',
                        marker=dict(color='#00c853', size=8, opacity=0.6),
                        text=[f"{r['datetime'].strftime('%Y-%m-%d %H:%M')}<br>"
                              f"Zone: {r['nearest_zone_type']}<br>"
                              f"Strength: {r['zone_strength']}×<br>"
                              f"MFE: {r['max_favorable_r']:.1f}R"
                              for _,r in wins_p.iterrows()],
                        hoverinfo='text',
                    ))
                    fig_prox.add_trace(go.Scatter(
                        x=losses_p['zone_dist_pct'], y=-losses_p['max_adverse_r'],
                        mode='markers', name='Losses',
                        marker=dict(color='#ff1744', size=8, opacity=0.6, symbol='x'),
                        text=[f"{r['datetime'].strftime('%Y-%m-%d %H:%M')}<br>"
                              f"Zone: {r['nearest_zone_type']}<br>"
                              f"Strength: {r['zone_strength']}×<br>"
                              f"MAE: {r['max_adverse_r']:.1f}R"
                              for _,r in losses_p.iterrows()],
                        hoverinfo='text',
                    ))
                    fig_prox.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.4)
                    fig_prox.add_vline(x=zone_prox, line_dash="dot", line_color="#ffd700", opacity=0.6,
                                       annotation_text=f"Proximity threshold ({zone_prox}%)")
                    fig_prox.update_layout(
                        title='Zone Distance vs Trade Outcome',
                        xaxis_title='Distance to Nearest Zone (%)',
                        yaxis_title='R-Multiple (positive=MFE, negative=MAE)',
                        template='plotly_dark', height=450,
                    )
                    st.plotly_chart(fig_prox, use_container_width=True)

                st.markdown("---")

                # ── NEW: Zone Strength Analysis ──
                st.subheader("💪 Zone Strength Analysis")
                st.caption("Does the strength of the zone (how aggressive the originating candle was) affect win rate?")

                strength_data = setups[setups['zone_strength'].notna()].copy()
                if len(strength_data) > 5:
                    # Bin zone strength
                    strength_data['strength_band'] = pd.cut(
                        strength_data['zone_strength'],
                        bins=[0, 1.5, 2.0, 2.5, 3.0, float('inf')],
                        labels=['1.0-1.5×', '1.5-2.0×', '2.0-2.5×', '2.5-3.0×', '3.0×+']
                    ).astype(str)
                    str_stats = seg_analysis(strength_data, 'strength_band', 'Zone Strength')
                    st.plotly_chart(plot_bar(str_stats, 'Zone Strength', 'Win Rate by Zone Strength'),
                                   use_container_width=True)
                    st.dataframe(str_stats, use_container_width=True, hide_index=True)
                else:
                    st.info("Not enough zone-classified setups for strength analysis.")

                st.markdown("---")

                # ── NEW: Proximity × Direction × Zone Table ──
                st.subheader("🔬 Proximity × Zone × Direction")
                prox_rows = []
                for band in setups['zone_proximity_band'].unique():
                    for zt in setups['zone'].unique():
                        for d in ['LONG', 'SHORT']:
                            sub = setups[(setups['zone_proximity_band']==band)&
                                        (setups['zone']==zt)&(setups['direction']==d)]
                            if len(sub) >= 3:
                                st3 = calc_stats(sub)
                                prox_rows.append({
                                    'Proximity': band, 'Zone': zt, 'Dir': d,
                                    'Trades': st3['Trades'], 'WR%': st3['Win Rate'],
                                    'PF': st3['PF'], 'Avg MFE': st3['Avg MFE']
                                })
                if prox_rows:
                    prox_bd = pd.DataFrame(prox_rows).sort_values('WR%', ascending=False)
                    st.dataframe(prox_bd, use_container_width=True, hide_index=True, height=400,
                        column_config={'WR%': st.column_config.ProgressColumn('WR%', min_value=0, max_value=100, format="%.1f%%")})
                else:
                    st.info("Not enough data for cross-dimensional proximity analysis (need ≥3 trades per cell).")

            with inner[3]:
                ss=seg_analysis(setups,'session','Session')
                st.plotly_chart(plot_bar(ss,'Session','Session Win Rate'),use_container_width=True)
                dw=seg_analysis(setups,'day_name','Day')
                dw['Day']=pd.Categorical(dw['Day'],['Mon','Tue','Wed','Thu','Fri'],ordered=True)
                dw=dw.sort_values('Day')
                st.plotly_chart(plot_bar(dw,'Day','Day of Week'),use_container_width=True)
                ms=seg_analysis(setups,'month_name','Month')
                mo=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
                ms['Month']=pd.Categorical(ms['Month'],mo,ordered=True); ms=ms.sort_values('Month')
                st.plotly_chart(plot_bar(ms,'Month','Month'),use_container_width=True)
                st.plotly_chart(plot_heatmap(setups,'day_name','hour',ro=['Mon','Tue','Wed','Thu','Fri'],
                    title='Day × Hour Heatmap'),use_container_width=True)

            with inner[4]:
                ns=seg_analysis(setups,'news','Event')
                st.plotly_chart(plot_bar(ns,'Event','News Impact'),use_container_width=True)
                st.dataframe(ns,use_container_width=True,hide_index=True)

            with inner[5]:
                al=seg_analysis(setups,'alignment','Alignment')
                st.plotly_chart(plot_bar(al,'Alignment','Trend Alignment'),use_container_width=True)

                # Zone proximity as a dimension
                st.subheader("Zone Proximity Dimension")
                prx=seg_analysis(setups,'zone_proximity_band','Proximity')
                band_order_map = {'Inside Zone':0,'Touching (≤0.1%)':1,'Very Close (0.1-0.3%)':2,
                                  'Near (0.3-0.6%)':3,'Moderate (0.6-1%)':4,'Far (>1%)':5,'No Zone':6}
                prx['_sort']=prx['Proximity'].map(band_order_map).fillna(99)
                prx=prx.sort_values('_sort').drop(columns=['_sort'])
                st.plotly_chart(plot_bar(prx,'Proximity','Win Rate by Zone Proximity'),use_container_width=True)
                st.dataframe(prx,use_container_width=True,hide_index=True)

                st.subheader("Multi-Dimensional Breakdown")
                rows=[]
                for z in setups['zone'].unique():
                    for se in setups['session'].unique():
                        for d in ['LONG','SHORT']:
                            sub=setups[(setups['zone']==z)&(setups['session']==se)&(setups['direction']==d)]
                            if len(sub)>=3:
                                st2=calc_stats(sub)
                                rows.append({'Zone':z,'Session':se,'Dir':d,'Trades':st2['Trades'],'WR%':st2['Win Rate'],'PF':st2['PF']})
                if rows:
                    bd=pd.DataFrame(rows).sort_values('WR%',ascending=False)
                    st.dataframe(bd,use_container_width=True,hide_index=True,height=500,
                        column_config={'WR%':st.column_config.ProgressColumn('WR%',min_value=0,max_value=100,format="%.1f%%")})
                st.subheader("Statistical Significance")
                nn=len(setups); ww=int(setups['win_1r'].sum())
                bt=binomtest(ww,nn,0.5); ci=bt.proportion_ci(confidence_level=0.95)
                st.markdown(f"**{ww/nn*100:.1f}%** ({ww}/{nn}) | p={bt.pvalue:.4f} | 95% CI: {ci.low*100:.1f}%-{ci.high*100:.1f}% | {'✅ Significant' if bt.pvalue<0.05 else '❌ Not significant'}")

            with inner[6]:
                st.subheader("📝 Complete Setup Log with Narratives")
                f1,f2,f3,f4=st.columns(4)
                with f1: fd=st.selectbox("Direction",['All','LONG','SHORT'],key=f"fd_{key}")
                with f2: fz=st.selectbox("Zone",['All']+sorted(setups['zone'].unique().tolist()),key=f"fz_{key}")
                with f3: fs=st.selectbox("Session",['All']+sorted(setups['session'].unique().tolist()),key=f"fs_{key}")
                with f4: fr=st.selectbox("Result",['All','Wins','Losses'],key=f"fr_{key}")

                fp1,fp2=st.columns(2)
                with fp1:
                    prox_opts=['All']+sorted(setups['zone_proximity_band'].unique().tolist())
                    fpx=st.selectbox("Zone Proximity",prox_opts,key=f"fpx_{key}")
                with fp2:
                    if 'scenario_key' in setups.columns:
                        scf_opts = ['All'] + sorted(setups['scenario_key'].unique().tolist())
                    else:
                        scf_opts = ['All']
                    scf = st.selectbox("Scenario filter", scf_opts, key=f"sc_{key}")

                filt=setups.copy()
                if fd!='All': filt=filt[filt['direction']==fd]
                if fz!='All': filt=filt[filt['zone']==fz]
                if fs!='All': filt=filt[filt['session']==fs]
                if fr=='Wins': filt=filt[filt['win_1r']==True]
                elif fr=='Losses': filt=filt[filt['win_1r']==False]
                if fpx!='All': filt=filt[filt['zone_proximity_band']==fpx]
                if 'scenario_key' in filt.columns and scf!='All': filt=filt[filt['scenario_key']==scf]

                srt=st.radio("Sort:",['Recent','Oldest','Best R','Worst R'],horizontal=True,key=f"sr_{key}")
                if srt=='Recent': filt=filt.sort_values('datetime',ascending=False)
                elif srt=='Oldest': filt=filt.sort_values('datetime',ascending=True)
                elif srt=='Best R': filt=filt.sort_values('max_favorable_r',ascending=False)
                else: filt=filt.sort_values('max_adverse_r',ascending=False)
                st.markdown(f"**{len(filt)} of {len(setups)} setups**")

                for idx,(_,s) in enumerate(filt.iterrows()):
                    re="✅ WIN" if s['win_1r'] else "❌ LOSS"
                    dist_txt = f" | Dist:{s['zone_dist_pct']:.2f}%" if pd.notna(s.get('zone_dist_pct')) else ""
                    str_txt = f" Str:{s['zone_strength']:.1f}×" if pd.notna(s.get('zone_strength')) else ""
                    with st.expander(
                        f"**#{idx+1}** {s['datetime'].strftime('%a %b %d, %Y %H:%M')} | {s['direction']} | {re} | "
                        f"{s['zone']}{dist_txt}{str_txt} | {s['session']} | C1:{s['c1_color']}/{s['c1_wick_bucket']} → C2:{s['c2_color']}/{s['c2_wick_bucket']}"):
                        st.markdown(generate_narrative(s))
                        st.markdown("---")

                        # Zone detail box
                        if s['zone'] != 'neutral':
                            zc1,zc2,zc3=st.columns(3)
                            with zc1:
                                st.markdown(f"**🏗️ Zone Type:** {s['zone'].upper()}")
                                if pd.notna(s.get('nearest_zone_top')):
                                    st.markdown(f"**Zone Range:** ${s['nearest_zone_bottom']:.2f} — ${s['nearest_zone_top']:.2f}")
                            with zc2:
                                if pd.notna(s.get('zone_dist_pct')):
                                    st.markdown(f"**Distance:** {s['zone_dist_pct']:.3f}%")
                                    st.markdown(f"**Band:** {s['zone_proximity_band']}")
                            with zc3:
                                if pd.notna(s.get('zone_strength')):
                                    st.markdown(f"**Strength:** {s['zone_strength']:.1f}× ATR")
                                wz = ((s['zone']=='demand' and s['direction']=='LONG') or
                                      (s['zone']=='supply' and s['direction']=='SHORT'))
                                st.markdown(f"**Alignment:** {'✅ With Zone' if wz else '⚠️ Against Zone'}")
                            st.markdown("---")

                        co1,co2=st.columns(2)
                        with co1:
                            st.markdown(f"**C1** O:${s['c1_open']:.2f} C:${s['c1_close']:.2f} H:${s['c1_high']:.2f} L:${s['c1_low']:.2f}\n\n"
                                f"Body:{s['c1_body_pct']:.1f}% UW:{s['c1_upper_wick_pct']:.1f}% LW:{s['c1_lower_wick_pct']:.1f}% | {s['c1_wick_label']}")
                        with co2:
                            st.markdown(f"**C2** O:${s['c2_open']:.2f} C:${s['c2_close']:.2f} H:${s['c2_high']:.2f} L:${s['c2_low']:.2f}\n\n"
                                f"Body:{s['c2_body_pct']:.1f}% UW:{s['c2_upper_wick_pct']:.1f}% LW:{s['c2_lower_wick_pct']:.1f}% | {s['c2_wick_label']}")
                        st.markdown(f"**C3 Breakout:** {s['c3_open']:.2f}→**{s['c3_close']:.2f}** "
                            f"({'above C2 high '+str(round(s['c2_high'],2)) if s['direction']=='LONG' else 'below C2 low '+str(round(s['c2_low'],2))} "
                            f"by ${s['c3_breakout_margin']:.2f}) → **{s['direction']}** | "
                            f"Entry @ C3 close: **${s['entry_price']:.2f}** | SL:${s['stop_loss']:.2f} | Risk:${s['risk']:.2f}")
                        # C4/C5/C6 follow-through
                        fc1,fc2,fc3=st.columns(3)
                        with fc1:
                            c4f = "✅" if s.get('c4_followed') else "❌"
                            st.markdown(f"**C4** {c4f} {s.get('c4_close_r',0):+.2f}R")
                        with fc2:
                            if s.get('c5_close_r') is not None:
                                c5f = "✅" if s.get('c5_followed') else "❌"
                                st.markdown(f"**C5** {c5f} {s['c5_close_r']:+.2f}R")
                        with fc3:
                            if s.get('c6_close_r') is not None:
                                c6f = "✅" if s.get('c6_followed') else "❌"
                                st.markdown(f"**C6** {c6f} {s['c6_close_r']:+.2f}R")
                        st.markdown(f"**{s.get('follow_count',0)}/3 followed** | "
                            f"1R:{'✅' if s['hit_1r'] else '❌'} 1.5R:{'✅' if s['hit_15r'] else '❌'} 2R:{'✅' if s['hit_2r'] else '❌'} | "
                            f"MFE:{s['max_favorable_r']:.2f}R MAE:{s['max_adverse_r']:.2f}R")

                st.markdown("---")
                csv=filt.to_csv(index=False)
                st.download_button(f"⬇️ CSV ({len(filt)} setups)",csv,f"setups_{key.replace(' ','_')}.csv","text/csv",key=f"dl_{key}")

            with inner[7]:
                ne=min(6,len(setups))
                et=st.radio("Show:",['Recent','Best Winners','Worst Losers','Random'],horizontal=True,key=f"ex_{key}")
                if et=='Recent': ex=setups.tail(ne)
                elif et=='Best Winners': ex=setups[setups['win_1r']].nlargest(ne,'max_favorable_r')
                elif et=='Worst Losers': ex=setups[~setups['win_1r']].nlargest(ne,'max_adverse_r')
                else: ex=setups.sample(min(ne,len(setups)))
                for _,s in ex.iterrows():
                    st.plotly_chart(plot_candlestick_example(df,s),use_container_width=True,key=f"cx_{key}_{s['datetime']}")

    if len(all_results)>1:
        with tabs[-1]:
            st.header("📋 Cross-Asset Comparison")
            comp=[{**calc_stats(r['setups'],k),'Asset':r['asset'],'TF':r['tf']} for k,r in all_results.items()]
            cd=pd.DataFrame(comp)
            cd=cd[['Label','Asset','TF','Trades','Win Rate','PF','Avg R','Hit 1R%','Hit 1.5R%','Hit 2R%','Avg MFE','Avg MAE']].sort_values('Win Rate',ascending=False)
            st.dataframe(cd,use_container_width=True,hide_index=True,
                column_config={'Win Rate':st.column_config.ProgressColumn('Win Rate',min_value=0,max_value=100,format="%.1f%%")})
            fig=go.Figure()
            pal=list(COLORS.values())
            for i,(k,r) in enumerate(all_results.items()):
                s=r['setups']
                fig.add_trace(go.Scatter(x=s['datetime'],y=s['cumulative_r'],mode='lines',name=k,line=dict(color=pal[i%len(pal)],width=2)))
            fig.add_hline(y=0,line_dash="dash",line_color="gray",opacity=0.4)
            fig.update_layout(title='Equity Curves',template='plotly_dark',height=450)
            st.plotly_chart(fig,use_container_width=True)
            st.subheader("🏆 Top Scenarios Across All Assets")
            asc=[]
            for k,r in all_results.items():
                s=r['setups']
                for sc in s['scenario_key'].unique():
                    sub=s[s['scenario_key']==sc]
                    if len(sub)>=5:
                        asc.append({'Asset':k,'Scenario':sc,'Trades':len(sub),'Win Rate':round(sub['win_1r'].mean()*100,1),'MFE':round(sub['max_favorable_r'].mean(),2)})
            if asc:
                asd=pd.DataFrame(asc).sort_values('Win Rate',ascending=False)
                st.dataframe(asd.head(30),use_container_width=True,hide_index=True,
                    column_config={'Win Rate':st.column_config.ProgressColumn('Win Rate',min_value=0,max_value=100,format="%.1f%%")})

if __name__ == "__main__":
    main()
