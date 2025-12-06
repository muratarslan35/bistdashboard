# bot.py (KESİNTİSİZ ÇALIŞACAK WORKER - Durum Dosyasına Yazar)

import time
import json
from datetime import datetime
import yfinance as yf
# ... Diğer kütüphane importları (numpy, pandas, requests, argrelextrema, config'den importlar) ...
from config import TELEGRAM_TOKEN, CHAT_IDS
from scipy.signal import argrelextrema 

# Durum dosyasının adı
STATUS_FILE = "status.json" 

# -----------------------
# (TÜM ANALİZ FONKSİYONLARI BURADA KALIR - safe_download, compute_rsi, etc.)
# ...

# -----------------------
# YARDIMCI: Durumu Dosyaya Yazma Fonksiyonu
# -----------------------
def update_status_file():
    """latest_state içeriğini yerel bir JSON dosyasına yazar."""
    global latest_state
    
    # Per_symbol detaylarını bu dosyaya yazmak gereksiz yük getirir. Sadece özet yazalım.
    summary_state = {
        "running": latest_state.get("running", False),
        "last_run": latest_state.get("last_run"),
        "total_signals": len(latest_state.get("signals", [])),
        "last_signal_time": latest_state.get("last_signal", {}).get("time", "Yok"),
        "errors_count": len(latest_state.get("errors", [])),
        "worker_heartbeat": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    try:
        with open(STATUS_FILE, 'w') as f:
            json.dump(summary_state, f, indent=4)
    except Exception as e:
        print(f"HATA: Durum dosyasına yazılamadı: {e}")


# -----------------------
# SCANNER (ANA İŞ DÖNGÜSÜ)
# -----------------------
def scanner_loop():
    global latest_state
    latest_state["running"] = True
    # ... Diğer scanner_loop mantığı (Tarama, Sinyal Tespiti, Telegram Gönderimi) ...

    while True:
        # ... (Tüm tarama ve sinyal kodu burada kalır) ...
        
        # Döngünün sonunda durumu dosyaya yaz
        update_status_file() 
        
        elapsed = (datetime.now() - t0).total_seconds()
        wait = max(1, CHECK_INTERVAL - elapsed)
        print(f"Tarama tamamlandı. {len(new_signals)} yeni sinyal bulundu. {wait:.1f} saniye bekleniyor...")
        time.sleep(wait)

# -----------------------
# WORKER BAŞLANGICI
# -----------------------
if __name__ == "__main__":
    print("BIST Sinyal Worker Başlatılıyor...")
    send_telegram_message("🔔 <b>BIST Sinyal Worker Aktif!</b>\nTarama döngüsü başlatıldı.")
    
    # Başlangıçta boş bir durum dosyası oluştur
    update_status_file() 
    
    scanner_loop()
