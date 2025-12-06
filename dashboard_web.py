# dashboard_web.py (WEB SERVİSİ - Webhook Eklendi)

import json
import time
from datetime import datetime
from flask import Flask, Response, render_template_string, request, jsonify
from flask_cors import CORS
import requests

# bot.py'den sadece veri yapısını import ediyoruz (analiz fonksiyonlarını değil)
# Ancak, Worker belleği yerine artık durum bilgisini dosyadan okuyacağız.
# 'bot' importu artık sadece status için yeterli olmayabilir.
# Bu örnek için, sadeleştirilmiş bir 'latest_state' yapısını koruyalım
# ve durumu dosyadan okuyalım.
STATUS_FILE = "status.json"

app = Flask("bist_dashboard")
CORS(app)

# -----------------------
# YARDIMCI: Durum Dosyasını Okuma
# -----------------------
def get_worker_status():
    """Worker'ın kaydettiği durum dosyasını okur."""
    try:
        with open(STATUS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"running": False, "error": "Status dosyası bulunamadı."}
    except Exception as e:
        return {"running": False, "error": f"Dosya okuma hatası: {e}"}

# -----------------------
# TELEGRAM Webhook Fonksiyonları
# -----------------------

# Render'ın verdiği URL'yi alıcı olarak Telegram'a kaydeder.
# Render'da her dağıtımdan sonra bu uç noktayı çalıştırmalısın!
@app.route("/set_webhook")
def set_webhook():
    from config import TELEGRAM_TOKEN
    webhook_url = request.url_root.replace("http://", "https://") + "telegram_webhook"
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook?url={webhook_url}"
    response = requests.get(api_url).json()
    return jsonify(response)

# Telegram'dan gelen komutları işler
@app.route("/telegram_webhook", methods=['POST'])
def telegram_webhook():
    from config import TELEGRAM_TOKEN
    
    update = request.get_json()
    if not update or 'message' not in update:
        return jsonify(ok=True)

    message = update['message']
    chat_id = message['chat']['id']
    text = message.get('text', '').lower()

    if text.startswith('/status') or text.startswith('/test'):
        status = get_worker_status()
        
        # Durum mesajı oluşturma
        if status.get("running", False):
            msg_text = (
                "✅ <b>Sistem Aktif!</b>\n"
                f"Worker Son Çalışma: {status.get('worker_heartbeat', 'Bilinmiyor')}\n"
                f"Toplam Sinyal Sayısı: {status.get('total_signals', 0)}\n"
                f"Son Sinyal Zamanı: {status.get('last_signal_time', 'Yok')}\n"
                f"Hata Sayısı: {status.get('errors_count', 0)}"
            )
        else:
            msg_text = f"❌ <b>Sistem Aktif Değil!</b>\nWorker'dan veri alınamıyor: {status.get('error', 'Bilinmeyen Hata')}"

        # Yanıtı Telegram'a geri gönderme
        api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(api_url, json={
            'chat_id': chat_id,
            'text': msg_text,
            'parse_mode': 'HTML'
        })

    return jsonify(ok=True)


# -----------------------
# DASHBOARD UÇ NOKTALARI (Aynı Kalır)
# -----------------------
# ... (INDEX_HTML ve diğer uç noktaları aynı kalır) ...
