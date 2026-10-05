import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# ─────────────────────────────────────────────────────────────
# PAGINA CONFIGURATIE (Samengevoegd)
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Stoxline Ultimate Trading Scanner",
    page_icon="📊",
    layout="wide"
)

st.title("📈 Stoxline Ultimate Trading Scanner")
st.caption("Kies hieronder de gewenste scanner voor gedetailleerde aandelenanalyse.")

# Maak tabbladen aan om de twee scanners netjes te scheiden
tab1, tab2 = st.tabs(["📈 Stoxline AI Rating Scanner", "📊 Multi-Timeframe Score Scanner"])

# ==============================================================================
# DEEL 1: STOXXLINE AI RATING SCANNER FUNCTIES
# ==============================================================================

def calculate_rsi(series, period=14):
    """Bereken RSI (14) conform Wilder's Smoothing (gelijk aan TradingView/Yahoo)"""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def get_star_html(rating):
    """Gekleurde sterren op basis van score: 4-5 Groen, 2-3 Blauw, 0-1 Rood"""
    if rating in [4, 5]:
        color = "#28a745"
    elif rating in [2, 3]:
        color = "#007bff"
    else:
        color = "#dc3545"
    filled_stars = "★" * rating
    empty_stars = "☆" * (5 - rating)
    return f'<span style="color: {color}; font-weight: bold;">{filled_stars}{empty_stars} ({rating}/5)</span>'

def get_rsi_html(rsi):
    """RSI Kleur: >55 Groen, <45 Rood, Anders Grijs"""
    if rsi > 55:
        color = "#28a745"
    elif rsi < 45:
        color = "#dc3545"
    else:
        color = "#6c757d"
    return f'<span style="color: {color}; font-weight: bold;">{rsi:.1f}</span>'

def get_pcr_html(pcr):
    """Put/Call Ratio Kleur: <0.8 Groen, >1.0 Rood, Anders Grijs"""
    if pcr is None or np.isnan(pcr):
        return "<span style='color: #6c757d;'>N/A</span>"
    if pcr < 0.8:
        color = "#28a745"
    elif pcr > 1.0:
        color = "#dc3545"
    else:
        color = "#6c757d"
    return f'<span style="color: {color}; font-weight: bold;">{pcr:.2f}</span>'

def get_short_float_html(sf):
    """Short Float Kleur: <5% Groen, >15% Rood, Anders Grijs"""
    if sf is None or np.isnan(sf):
        return "<span style='color: #6c757d;'>N/A</span>"
    sf_pct = sf * 100 if sf < 1 else sf
    if sf_pct < 5.0:
        color = "#28a745"
    elif sf_pct > 15.0:
        color = "#dc3545"
    else:
        color = "#6c757d"
    return f'<span style="color: {color}; font-weight: bold;">{sf_pct:.2f}%</span>'

@st.cache_data(ttl=600)
def fetch_stock_data(symbol):
    """Slaat UITSLUITEND eenvoudige data op (DataFrame + simpele dict)"""
    try:
        stock = yf.Ticker(symbol)
        df = stock.history(period="1y", timeout=10)
        info_data = {}
        try:
            info_data['shortPercentOfFloat'] = stock.info.get('shortPercentOfFloat', None)
        except Exception:
            info_data['shortPercentOfFloat'] = None
        return df, info_data
    except Exception:
        return None, {}

def get_put_call_ratio(symbol):
    """Haalt veilig optiedata op zonder de app te laten bevriezen"""
    try:
        stock = yf.Ticker(symbol)
        options = stock.options
        if not options:
            return None
        opt = stock.option_chain(options[0])
        if opt.calls.empty or opt.puts.empty:
            return None
        total_calls = opt.calls['volume'].sum()
        total_puts = opt.puts['volume'].sum()
        if total_calls > 0:
            return total_puts / total_calls
    except Exception:
        return None
    return None

def analyze_ticker(symbol):
    df, info = fetch_stock_data(symbol)
    if df is None or df.empty or len(df) < 50:
        return None

    df['SMA_5'] = df['Close'].rolling(window=5).mean()
    df['SMA_20'] = df['Close'].rolling(window=20).mean()
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    df['RSI'] = calculate_rsi(df['Close'], 14)

    ema_12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema_26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema_12 - ema_26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    close_price = latest['Close']
    price_change = close_price - prev['Close']
    pct_change = (price_change / prev['Close']) * 100

    recent_df = df.tail(10)
    support_level = recent_df['Low'].min()
    resistance_level = recent_df['High'].max()
    
    support_pct = ((support_level - close_price) / close_price) * 100
    resistance_pct = ((resistance_level - close_price) / close_price) * 100

    short_float = info.get('shortPercentOfFloat', None)
    pcr = get_put_call_ratio(symbol)

    st_points = 0
    if close_price > latest['SMA_5']: st_points += 1.25
    if latest['SMA_5'] > prev['SMA_5']: st_points += 1.25
    if 45 <= latest['RSI'] <= 70: st_points += 1.25
    elif latest['RSI'] > 70: st_points += 0.5
    if latest['MACD'] > latest['MACD_Signal']: st_points += 1.25
    st_stars = min(max(int(round(st_points)), 0), 5)

    mt_points = 0
    if close_price > latest['SMA_20']: mt_points += 1.25
    if close_price > latest['SMA_50']: mt_points += 1.25
    if latest['SMA_20'] > latest['SMA_50']: mt_points += 1.25
    if latest['MACD'] > 0: mt_points += 1.25
    mt_stars = min(max(int(round(mt_points)), 0), 5)

    if price_change > 0:
        arrow = "⬆️ UP"
    elif price_change < 0:
        arrow = "⬇️ DOWN"
    else:
        arrow = "➡️ NEUTRAL"

    return {
        "symbol": symbol, "close": close_price, "change": price_change,
        "pct_change": pct_change, "arrow": arrow, "st_stars": st_stars,
        "mt_stars": mt_stars, "rsi": latest['RSI'], "pcr": pcr,
        "short_float": short_float, "support": support_level,
        "support_pct": support_pct, "resistance": resistance_level,
        "resistance_pct": resistance_pct
    }

# ==============================================================================
# DEEL 2: MULTI-TIMEFRAME SCORE SCANNER FUNCTIES
# ==============================================================================

def calculate_trading_score(df: pd.DataFrame) -> pd.DataFrame:
    """Berekent de indicatoren en 5 regels exact zoals in Pine Script v5."""
    df = df.copy()
    df.index = pd.to_datetime(df.index)

    df["EMA5"] = df["Close"].ewm(span=5, adjust=False).mean()
    df["EMA15"] = df["Close"].ewm(span=15, adjust=False).mean()

    df["HLC3"] = (df["High"] + df["Low"] + df["Close"]) / 3
    df["PV"] = df["HLC3"] * df["Volume"]

    dates = df.index.date
    cum_pv = df.groupby(dates)["PV"].cumsum()
    cum_vol = df.groupby(dates)["Volume"].cumsum()

    df["VWAP"] = np.where(cum_vol != 0, cum_pv / cum_vol, df["HLC3"])
    df["VolSMA20"] = df["Volume"].rolling(window=20).mean()

    df["Rule1"] = (df["EMA5"] > df["EMA15"]).astype(int)
    df["Rule2"] = (df["Close"] > df["VWAP"]).astype(int)
    df["Rule3"] = (df["Volume"] > df["VolSMA20"]).astype(int)
    df["Rule4"] = (df["Close"] > df["EMA5"]).astype(int)
    df["Rule5"] = (df["EMA15"] > df["EMA15"].shift(1)).astype(int)

    df["Score"] = df["Rule1"] + df["Rule2"] + df["Rule3"] + df["Rule4"] + df["Rule5"]
    return df

def calculate_stable_rs_score(df_stock: pd.DataFrame, df_spy: pd.DataFrame, atr_max_pct: float = 3.0) -> int:
    """Berekent de Stable Relative Strength Score (0 - 100) exact volgens het Pine Script."""
    try:
        combined = pd.DataFrame({
            "stock_close": df_stock["Close"], "stock_high": df_stock["High"],
            "stock_low": df_stock["Low"], "stock_volume": df_stock["Volume"],
            "spy_close": df_spy["Close"]
        }).dropna()

        if len(combined) < 22:
            return 0

        stock_ret = combined["stock_close"] / combined["stock_close"].shift(1)
        spy_ret = combined["spy_close"] / combined["spy_close"].shift(1)
        rs_ratio = stock_ret / spy_ret

        latest_rs = rs_ratio.iloc[-1]
        if latest_rs >= 1.0: rs_score = 35
        elif latest_rs >= 0.99: rs_score = 20
        else: rs_score = 0

        ema9 = combined["stock_close"].ewm(span=9, adjust=False).mean()
        ema21 = combined["stock_close"].ewm(span=21, adjust=False).mean()

        close_last = combined["stock_close"].iloc[-1]
        ema9_last = ema9.iloc[-1]
        ema21_last = ema21.iloc[-1]

        if close_last > ema9_last and ema9_last > ema21_last: trend_score = 25
        elif close_last > ema21_last: trend_score = 15
        else: trend_score = 0

        prev_close = combined["stock_close"].shift(1)
        tr1 = combined["stock_high"] - combined["stock_low"]
        tr2 = (combined["stock_high"] - prev_close).abs()
        tr3 = (combined["stock_low"] - prev_close).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        atr14 = tr.ewm(alpha=1/14, adjust=False).mean()
        atr_val = atr14.iloc[-1]
        atr_pct = (atr_val / close_last) * 100

        if atr_pct <= atr_max_pct: vol_score = 25
        elif atr_pct <= (atr_max_pct + 1.5): vol_score = 15
        else: vol_score = 0

        sma_vol20 = combined["stock_volume"].rolling(window=20).mean()
        rvol = (combined["stock_volume"] / sma_vol20).iloc[-1]

        if rvol >= 1.2: rvol_score = 15
        elif rvol >= 1.0: rvol_score = 10
        else: rvol_score = 0

        return int(rs_score + trend_score + vol_score + rvol_score)
    except Exception:
        return 0

def calculate_daily_rvol_and_diff(df_stock: pd.DataFrame):
    """Berekent de RVOL score én het percentage waarin het volume van vandaag afwijkt t.o.v. het 20-daags gemiddelde."""
    try:
        if len(df_stock) < 20:
            return 0, "N/A"

        avg_vol_20d = df_stock["Volume"].rolling(window=20).mean().iloc[-1]
        latest_vol = float(df_stock["Volume"].iloc[-1])

        if avg_vol_20d == 0:
            return 0, "N/A"

        rvol = latest_vol / avg_vol_20d

        if rvol >= 3.0: rvol_score = 100
        elif rvol >= 2.0: rvol_score = 75
        elif rvol >= 1.5: rvol_score = 50
        elif rvol >= 1.0: rvol_score = 25
        else: rvol_score = 0

        diff_pct = ((latest_vol - avg_vol_20d) / avg_vol_20d) * 100
        diff_str = f"{diff_pct:+.1f}%"

        return rvol_score, diff_str
    except Exception:
        return 0, "N/A"

def get_signal_badge(score: int) -> str:
    """Vertaalt de score naar een compact signaal met emoji."""
    mapping = {
        5: "🚀 Strong Buy (5)", 4: "📈 Buy (4)", 3: "⚖️ Hold (3)",
        2: "📉 Sell (2)", 1: "🔴 Strong Sell (1)", 0: "🔴 Strong Sell (0)",
    }
    return mapping.get(score, "N/A")


# ==============================================================================
# DEEL 3: GEBRUIKERSINTERFACE (UI)
# ==============================================================================

with tab1:
    st.header("📈 Stoxline AI Rating Scanner")
    st.caption("Voer meerdere tickers in gescheiden door een komma (bijv: AMBA, NVDA, TSLA, ASML.AS)")
    
    input_tickers = st.text_input("Voer ticker(s) in (gescheiden door komma):", "AMBA, NVDA, TSLA, ASML.AS")

    if st.button("🔍 Scan Aandelen") or input_tickers:
        tickers_list = [t.strip().upper() for t in input_tickers.split(",") if t.strip()]

        if not tickers_list:
            st.warning("Voer minimaal één geldige ticker in.")
        else:
            results = []
            with st.spinner("Aandelen en marktgegevens analyseren..."):
                for symbol in tickers_list:
                    res = analyze_ticker(symbol)
                    if res:
                        results.append(res)
                    else:
                        st.error(f"❌ Geen data gevonden voor **{symbol}**")

            if results:
                st.markdown("---")
                st.subheader("📊 Resultaten Overzicht (3-5 Dagen Swingtrade Window)")

                summary_data = []
                for r in results:
                    summary_data.append({
                        "Ticker": f"<b>{r['symbol']}</b>",
                        "Koers": f"${r['close']:.2f}",
                        "Verandering": f"<span style='color: {'#28a745' if r['change'] > 0 else '#dc3545'};'>{r['pct_change']:+.2f}%</span>",
                        "Richting": r["arrow"],
                        "Short-Term": get_star_html(r['st_stars']),
                        "Mid-Term": get_star_html(r['mt_stars']),
                        "RSI (14)": get_rsi_html(r['rsi']),
                        "Put/Call Ratio": get_pcr_html(r['pcr']),
                        "Short Float": get_short_float_html(r['short_float']),
                        "Support (10d)": f"${r['support']:.2f} (<span style='color:#dc3545;'>{r['support_pct']:.1f}%</span>)",
                        "Resistance (10d)": f"${r['resistance']:.2f} (<span style='color:#28a745;'>{r['resistance_pct']:+.1f}%</span>)"
                    })
                
                df_html = pd.DataFrame(summary_data).to_html(escape=False, index=False)
                st.markdown(df_html, unsafe_allow_html=True)

                st.markdown("---")
                st.subheader("🔍 Gedetailleerde Kaarten")

                cols = st.columns(2)
                for idx, r in enumerate(results):
                    col = cols[idx % 2]
                    with col:
                        with st.container(border=True):
                            st.markdown(f"### {r['symbol']} &nbsp; {r['arrow']}")
                            st.metric("Huidige Koers", f"${r['close']:.2f}", f"{r['change']:+.2f} ({r['pct_change']:+.2f}%)")
                            
                            col_a, col_b = st.columns(2)
                            with col_a:
                                st.write("**Short-Term Rating:**")
                                st.markdown(get_star_html(r['st_stars']), unsafe_allow_html=True)
                                st.write("**Mid-Term Rating:**")
                                st.markdown(get_star_html(r['mt_stars']), unsafe_allow_html=True)
                                st.write("**RSI (14):**")
                                st.markdown(get_rsi_html(r['rsi']), unsafe_allow_html=True)
                            
                            with col_b:
                                st.write("**Put/Call Ratio:**")
                                st.markdown(get_pcr_html(r['pcr']), unsafe_allow_html=True)
                                st.write("**Short Float:**")
                                st.markdown(get_short_float_html(r['short_float']), unsafe_allow_html=True)
                            
                            st.markdown("---")
                            st.write(f"**Swing Support (10d):** ${r['support']:.2f} ({r['support_pct']:.1f}%)")
                            st.write(f"**Swing Resistance (10d):** ${r['resistance']:.2f} ({r['resistance_pct']:+.1f}%)")

with tab2:
    st.header("📊 Multi-Timeframe Auto Trading Score Scanner")
    st.caption("Scant elk aandeel direct op 1D, 1H en 15M (MA5/15 + VWAP + Volume), Stable RS Score (0-100), Dagelijkse RVOL Score én Volume Vergelijking vs 20-daags gemiddelde.")
    
    st.sidebar.header("⚙️ Instellingen Multi-Timeframe")
    default_tickers = "AAPL, MSFT, NVDA, TSLA, AMZN, GOOGL, META, AMD, INTC, PLTR"
    ticker_input = st.sidebar.text_area("Tickers (gescheiden door komma)", default_tickers, height=140)
    SPY_TICKER = "SPY"
    ATR_MAX_PCT = 3.0

    if (st.sidebar.button("🚀 Start Multi-Timeframe Scan", type="primary") or "scanned" not in st.session_state):
        st.session_state["scanned"] = True
        results_mt = []

        progress_bar = st.progress(0)
        status_text = st.empty()

        try:
            spy_df_daily = yf.download(SPY_TICKER, period="60d", interval="1d", progress=False)
            if isinstance(spy_df_daily.columns, pd.MultiIndex):
                spy_df_daily.columns = spy_df_daily.columns.get_level_values(0)
        except Exception:
            spy_df_daily = pd.DataFrame()

        timeframes = [
            ("1d", "60d", "1D"),
            ("1h", "60d", "1H"),
            ("15m", "7d", "15M"),
        ]

        tickers_mt = [t.strip().upper() for t in ticker_input.split(",") if t.strip()]

        for i, ticker in enumerate(tickers_mt):
            status_text.text(f"Bezig met analyseren van {ticker} (1D, 1H, 15M, RS Score & Volume)...")
            ticker_data = {"Ticker": ticker, "Prijs ($)": "N/A"}
            total_score_sum = 0
            stock_daily_df = pd.DataFrame()

            for interval, period, label in timeframes:
                try:
                    data = yf.download(ticker, period=period, interval=interval, progress=False)

                    if not data.empty and len(data) >= 20:
                        if isinstance(data.columns, pd.MultiIndex):
                            data.columns = data.columns.get_level_values(0)

                        if interval == "1d":
                            stock_daily_df = data.copy()

                        df = calculate_trading_score(data)
                        latest = df.iloc[-1]

                        score = int(latest["Score"])
                        signal = get_signal_badge(score)

                        ticker_data["Prijs ($)"] = round(float(latest["Close"]), 2)
                        ticker_data[f"Score {label}"] = score
                        ticker_data[f"Signaal {label}"] = signal
                        total_score_sum += score
                    else:
                        ticker_data[f"Score {label}"] = 0
                        ticker_data[f"Signaal {label}"] = "Geen data"

                except Exception:
                    ticker_data[f"Score {label}"] = 0
                    ticker_data[f"Signaal {label}"] = "Fout"

            if not stock_daily_df.empty and not spy_df_daily.empty:
                rs_score_val = calculate_stable_rs_score(stock_daily_df, spy_df_daily, ATR_MAX_PCT)
                ticker_data["RS Score (0-100)"] = rs_score_val
            else:
                ticker_data["RS Score (0-100)"] = 0

            if not stock_daily_df.empty:
                rvol_daily_score, volume_diff = calculate_daily_rvol_and_diff(stock_daily_df)
                ticker_data["RVOL 1D Score"] = rvol_daily_score
                ticker_data["Volume vs Gem. (1D)"] = volume_diff
            else:
                ticker_data["RVOL 1D Score"] = 0
                ticker_data["Volume vs Gem. (1D)"] = "N/A"

            ticker_data["Totale Matrix Score"] = total_score_sum
            results_mt.append(ticker_data)

            progress_bar.progress((i + 1) / len(tickers_mt))

        status_text.empty()
        progress_bar.empty()

        if results_mt:
            res_df = pd.DataFrame(results_mt).sort_values(by="Totale Matrix Score", ascending=False)
            display_df = res_df.drop(columns=["Totale Matrix Score"])

            def highlight_scores(val):
                if isinstance(val, int):
                    if val >= 4: return "background-color: #28a745; color: white; font-weight: bold;"
                    elif val == 3: return "background-color: #ffc107; color: black; font-weight: bold;"
                    else: return "background-color: #dc3545; color: white; font-weight: bold;"
                return ""

            def highlight_rs_score(val):
                if isinstance(val, int):
                    if val >= 70: return "background-color: #28a745; color: white; font-weight: bold;"
                    elif val >= 50: return "background-color: #fd7e14; color: white; font-weight: bold;"
                    else: return "background-color: #dc3545; color: white; font-weight: bold;"
                return ""

            def highlight_rvol_score(val):
                if isinstance(val, int):
                    if val >= 75: return "background-color: #28a745; color: white; font-weight: bold;"
                    elif val >= 50: return "background-color: #ffc107; color: black; font-weight: bold;"
                    elif val >= 25: return "background-color: #fd7e14; color: white; font-weight: bold;"
                    else: return "background-color: #dc3545; color: white; font-weight: bold;"
                return ""

            def highlight_volume_diff(val):
                if isinstance(val, str) and val.endswith("%"):
                    if val.startswith("+"): return "background-color: #28a745; color: white; font-weight: bold;"
                    elif val.startswith("-"): return "background-color: #dc3545; color: white; font-weight: bold;"
                return ""

            st.subheader("📋 Multi-Timeframe Score Overzicht")
            st.dataframe(
                display_df.style
                .map(highlight_scores, subset=["Score 1D", "Score 1H", "Score 15M"])
                .map(highlight_rs_score, subset=["RS Score (0-100)"])
                .map(highlight_rvol_score, subset=["RVOL 1D Score"])
                .map(highlight_volume_diff, subset=["Volume vs Gem. (1D)"]),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.warning("Geen data gevonden voor de opgegeven tickers.")
