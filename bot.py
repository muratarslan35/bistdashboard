# bot.py (NİHAİ VERSİYON: Çalışma Hataları Giderildi, Analiz ve Durum Kaydı Mevcut)

import time
import json
from datetime import datetime
import yfinance as yf
import numpy as np
import pandas as pd
import requests

# config.py'dan gizli ayarları içe aktar
# (config.py'nin de doğru token ve ID ile güncellendiğinden emin olmalısın!)
from config import TELEGRAM_TOKEN, CHAT_IDS
from scipy.signal import argrelextrema 

# Durum dosyasının adı (Web servisi buradan okuyacak)
STATUS_FILE = "status.json"

# -----------------------
# CONFIG (Analiz Ayarları)
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

# latest_state sözlüğünün doğru başlangıç değerleri:
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
# YARDIMCI: Durumu Dosyaya Yazma Fonksiyonu
# -----------------------
def update_status_file():
    """latest_state içeriğini yerel bir JSON dosyasına yazar."""
    global latest_state
    
    # Hata yaşanan kısım burasıydı. latest_state'in boş (None) gelmediğinden 
    # ve last_signal'ın bir sözlük olduğundan emin olunuyor.
    last_signal_time = latest_state.get("last_signal")
    if last_signal_time:
        last_signal_time = last_signal_time.get("time", "Yok")
    else:
        last_signal_time = "Yok"

    summary_state = {
        "running": latest_state.get("running", False),
        "last_run": latest_state.get("last_run"),
        "total_signals": len(latest_state.get("signals", [])),
        "last_signal_time": last_signal_time,
        "errors_count": len(latest_state.get("errors", [])),
        "worker_heartbeat": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        with open(STATUS_FILE, 'w') as f:
            json.dump(summary_state, f, indent=4)
    except Exception as e:
        print(f"HATA: Durum dosyasına yazılamadı: {e}")

# -----------------------
# ANALİZ FONKSİYONLARI (KESİNTİSİZ ÇALIŞMA İÇİN GEREKLİ TÜM KOD)
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
        return float(rsi.iloc[-1].item())
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
    cur = float(prices.iloc[-1].item())
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
        ma20_now, ma20_prev = float(ma20.iloc[-1].item()), float(ma20.iloc[-2].item())
        ma50_now, ma50_prev = float(ma50.iloc[-1].item()), float(ma50.iloc[-2].item())
        ma200_now, ma200_prev = float(ma200.iloc[-1].item()), float(ma200.iloc[-2].item())
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
    last = float(vols.iloc[-1].item())
    if avg20 > 0 and last > avg20 * VOL_FACTOR:
        return True, last, avg20
    return False, last, avg20

def is_yesil1_daily(df_day):
    if df_day is None or len(df_day) < 2:
        return False
    last = df_day.iloc[-1]
    if float(last["Close"].item()) <= float(last["Open"].item()):
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
    if not (float(last1["Close"].item()) > float(last1["Open"].item()) and float(last2["Close"].item()) > float(last2["Open"].item())):
        return False
    rsi_now = compute_rsi(df_h4["Close"])
    if rsi_now is None or rsi_now > 60:
        return False
    ema20 = df_h4["Close"].ewm(span=20).mean().iloc[-1].item()
    if float(last1["
