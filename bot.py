# bot.py (KESİNTİSİZ ÇALIŞACAK WORKER - Sinyal Analiz ve Telegram Gönderimi)

import time
import json
from datetime import datetime
import yfinance as yf
import numpy as np
import pandas as pd
import requests

# config.py'dan gizli ayarları içe aktar
from config import TELEGRAM_TOKEN, CHAT_IDS
# scipy.signal'i bot.py'ye taşıdık
from scipy.signal import argrelextrema 

# -----------------------
# CONFIG (İlk koddan kopyalandı)
# -----------------------
CHECK_INTERVAL = 300          # 5 dakika
VOL_FACTOR = 1.7
RSI_PERIOD = 14
SR_ORDER = 5
SR_LOOKBACK = 100

SYMBOLS = [
    "AKBNK.IS","ARCLK.IS","ASELS.IS","BIMAS.IS","EKGYO.IS","EREGL.IS","FROTO.IS",
    "GARAN.IS","HEKTS.IS","ISCTR.IS","KCHOL.IS","KOZAA.IS","KOZAL.IS","KRDMD.IS",
    "PETKM.IS","PGSUS.IS","SAHOL.IS","SASA.IS","SISE.IS","TCELL.IS","THYAO.IS",
    "TUPRS.IS","YKBNK.IS"
]

latest_state = {
    "last_run": None,
    "last_signal": None,
    "signals": [],
    "per_symbol": {},
    "running": False,
    "errors": []
}

# -----------------------
# TELEGRAM GÖNDERİM FONKSİYONU
# -----------------------
def send_telegram_message(message):
    """Mesajı config.py'daki tüm CHAT_IDS'lere HTML formatında gönderir."""
    if not TELEGRAM_TOKEN or not CHAT_IDS:
        print("Telegram ayarları eksik. Mesaj gönderilemedi.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    payload = {
        "text": message,
        "parse_mode": "HTML"
    }
    
    for chat_id in CHAT_IDS:
        try:
            payload["chat_id"] = chat_id
            response = requests.post(url, data=payload)
            if response.status_code != 200:
                print(f"Telegram'a gönderme hatası ({chat_id}): {response.text}")
        except Exception as e:
            print(f"Telegram gönderme istisnası: {e}")

# -----------------------
# ANALİZ FONKSİYONLARI (İLK KOD BLOKUNDAN KOPYALANDI)
# -----------------------
def safe_download(symbol, period="90d", interval="4h"):
    try:
        df = yf.download(symbol, period=period, interval=interval, progress=False, threads=False)
        if df is None or df.empty:
            return None
        return df
    except Exception:
        return None

def compute_rsi(series: pd.Series, period=RSI_PERIOD):
    if series is None or len(series) < period + 1:
        return None
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    try:
        return float(rsi.iloc[-1])
    except:
        return None

def support_resistance(df, lookback=SR_LOOKBACK, order=SR_ORDER):
    prices = df["Close"].tail(lookback)
    if prices.empty or len(prices) < (order*2 + 3):
        return [], []
    vals = prices.values
    max_idx = argrelextrema(vals, np.greater, order=order)[0]
    min_idx = argrelextrema(vals, np.less, order=order)[0]
    local_max = [float(vals[i]) for i in max_idx]
    local_min = [float(vals[i]) for i in min_idx]
    cur = float(prices.iloc[-1])
    supports = sorted([v for v in local_min if v < cur], reverse=True)[:3]
    resistances = sorted([v for v in local_max if v > cur])[:3]
    return supports, resistances

def detect_ma_crosses(df_day):
    if df_day is None or df_day.empty or len(df_day) < 210:
        return []
    ma20 = df_day["Close"].rolling(20).mean()
    ma50 = df_day["Close"].rolling(50).mean()
    ma200 = df_day["Close"].rolling(200).mean()
    try:
        ma20_now, ma20_prev = float(ma20.iloc[-1]), float(ma20.iloc[-2])
        ma50_now, ma50_prev = float(ma50.iloc[-1]), float(ma50.iloc[-2])
        ma200_now, ma200_prev = float(ma200.iloc[-1]), float(ma200.iloc[-2])
    except Exception:
        return []
    out = []
    if ma20_prev <= ma50_prev and ma20_now > ma50_now:
        out.append("MA20↑MA50")
    if ma20_prev >= ma50_prev and ma20_now < ma50_now:
        out.append("MA20↓MA50")
    if ma50_prev <= ma200_prev and ma50_now > ma200_now:
        out.append("MA50↑MA200")
    if ma50_prev >= ma200_prev and ma50_now < ma200_now:
        out.append("MA50↓MA200")
    return out

def detect_volume_spike(df_h4):
    if df_h4 is None or df_h4.empty or len(df_h4) < 22:
        return False, None, None
    vols = df_h4["Volume"].astype(float)
    avg20 = vols.iloc[-21:-1].mean()
    last = float(vols.iloc[-1])
    if avg20 > 0 and last > avg20 * VOL_FACTOR:
        return True, last, avg20
    return False, last, avg20

def is_yesil1_daily(df_day):
    if df_day is None or len(df_day) < 2:
        return False
    last = df_day.iloc[-1]
    if float(last["Close"]) <= float(last["Open"]):
        return False
    rsi_prev = compute_rsi(df_day["Close"].iloc[:-1])
    rsi_now = compute_rsi(df_day["Close"])
    if rsi_prev is None or rsi_now is None:
        return False
    return rsi_now > rsi_prev

def is_yesil2_4h(df_h4):
    if df_h4 is None or len(df_h4) < 2:
        return False
    last1 = df_h4.iloc[-1]
    last2 = df_h4.iloc[-2]
    if not (float(last1["Close"]) > float(last1["Open"]) and float(last2["Close"]) > float(last2["Open"])):
        return False
    rsi_now = compute_rsi(df_h4["Close"])
    if rsi_now is None or rsi_now > 60:
        return False
    ema20 = df_h4["Close"].ewm(span=20).mean().iloc[-1]
    if float(last1["Close"]) < ema20:
        return False
    return True

def today_trend_break(df):
    if df is None or len(df) < 5:
        return None
    supports, resistances = support_resistance(df, lookback=SR_LOOKBACK, order=SR_ORDER)
    closes = df["Close"].values
    highs = df["High"].values
    lows = df["Low"].values
    prev_close = float(closes[-2])
    if resistances:
        last_res = resistances[-1]
        today_high = float(highs[-1])
        if today_high > last_res and prev_close <= last_res:
            return ("res_break", last_res)
    if supports:
        last_sup = supports[0]
        today_low = float(lows[-1])
        if today_low < last_sup and prev_close >= last_sup:
            return ("sup_break", last_sup)
    return None

def decide_strength(g1, g2, ma_crosses, vol_spike, rsi4h):
    # default None
    # strong buy: G1+G2 + MA50↑MA200 (golden) + vol spike
    if g1 and g2 and ("MA50↑MA200" in ma_crosses) and vol_spike and (rsi4h is None or rsi4h < 70):
        return "strong_buy"
    # buy: g1+g2 or MA20↑MA50
    if (g1 and g2) or ("MA20↑MA50" in ma_crosses):
        return "buy"
    # strong sell: MA50↓MA200 + vol spike + RSI high
    if ("MA50↓MA200" in ma_crosses) and vol_spike and (rsi4h is not None and rsi4h > 60):
        return "strong_sell"
    # sell: MA20↓MA50
    if ("MA20↓MA50" in ma_crosses):
        return "sell"
    return None

# -----------------------
# SCANNER (ANA İŞ DÖNGÜSÜ)
# -----------------------
def scanner_loop():
    global latest_state
    latest_state["running"] = True
    while True:
        t0 = datetime.now()
        latest_state["last_run"] = t0.strftime("%Y-%m-%d %H:%M:%S")
        new_signals = [] 
        errors = []
        per_symbol = {}
        
        for sym in SYMBOLS:
            try:
                # ANALİZ YAP
                df_day = safe_download(sym, period="120d", interval="1d")
                df_4h = safe_download(sym, period="90d", interval="4h")
                if df_day is None or df_4h is None: continue
                
                price = float(df_4h["Close"].iloc[-1])
                rsi4h = compute_rsi(df_4h["Close"])
                supports, resistances = support_resistance(df_4h)
                ma_crosses = detect_ma_crosses(df_day)
                vol_spike, last_vol, avg_vol = detect_volume_spike(df_4h)
                g1 = is_yesil1_daily(df_day)
                g2 = is_yesil2_4h(df_4h)
                trend = today_trend_break(df_4h)

                # Sembol detaylarını kaydet (Dashboard için)
                summary = {"symbol": sym, "price": price, "rsi4h": rsi4h,
                           "supports": supports, "resistances": resistances,
                           "ma_crosses": ma_crosses, "vol_spike": vol_spike,
                           "last_vol": int(last_vol) if last_vol else None, 
                           "avg_vol": int(avg_vol) if avg_vol else None,
                           "g1": g1, "g2": g2, "trend": trend,
                           "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                per_symbol[sym] = summary

                # Sinyal Tespiti
                triggered = {}
                if g1 and g2: triggered["green12"] = True
                if vol_spike: triggered["volume"] = {"last": int(last_vol), "avg": int(avg_vol)}
                if ma_crosses: triggered["ma"] = ma_crosses
                if trend: triggered["trend"] = trend
                if rsi4h is not None and rsi4h < 20: triggered["rsi_low"] = round(rsi4h,1)
                if rsi4h is not None and rsi4h > 80: triggered["rsi_high"] = round(rsi4h,1)

                strength = decide_strength(g1, g2, ma_crosses, vol_spike, rsi4h)
                
                # Sinyal Tetiklenirse
                if triggered:
                    parts = []
                    if "green12" in triggered: parts.append("Günlük G1 + 4H G2")
                    if "volume" in triggered: parts.append("Hacim Spike")
                    if "ma" in triggered: parts.append(",".join(triggered["ma"]))
                    if "trend" in triggered: parts.append("Trend Kırılımı")
                    if "rsi_low" in triggered: parts.append(f"RSI Düşük({triggered['rsi_low']})")
                    if "rsi_high" in triggered: parts.append(f"RSI Yüksek({triggered['rsi_high']})")

                    msg = {"symbol": sym, "price": price, "parts": parts, "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "strength": strength}
                    
                    # TELEGRAM GÖNDERİMİ
                    emoji = "🚀 AL" if "buy" in strength else ("🔻 SAT" if "sell" in strength else "🔔 SİNYAL")
                    price_str = f"{msg['price']:.2f} ₺"
                    
                    telegram_msg = (
                        f"{emoji} <b>CANLI SİNYAL: {msg['symbol'].replace('.IS','')}</b>\n"
                        f"  • Güç: <b>{strength.upper() if strength else 'NORMAL'}</b>\n"
                        f"  • Fiyat: {price_str}\n"
                        f"  • Tetikleyiciler: {', '.join(msg['parts'])}\n"
                        f"  • Zaman: {msg['time']}"
                    )
                    send_telegram_message(telegram_msg)

                    # Dashboard için sinyal listesine ekle
                    new_signals.append(msg)
                    latest_state["last_signal"] = msg
                    
            except Exception as e:
                errors.append({"symbol": sym, "error": str(e)})

        latest_state["per_symbol"] = per_symbol
        latest_state["signals"].extend(new_signals) 
        latest_state["errors"] = errors
        
        elapsed = (datetime.now() - t0).total_seconds()
        wait = max(1, CHECK_INTERVAL - elapsed)
        print(f"Tarama tamamlandı. {len(new_signals)} yeni sinyal bulundu. {wait:.1f} saniye bekleniyor...")
        time.sleep(wait)

# -----------------------
# WORKER BAŞLANGICI
# -----------------------
if __name__ == "__main__":
    print("BIST Sinyal Worker Başlatılıyor...")
    scanner_loop()
