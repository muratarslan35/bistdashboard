# dashboard_web.py (WEB SERVİSİ - Sadece Arayüz)

import json
import time
from datetime import datetime
from flask import Flask, Response, render_template_string, request, jsonify
from flask_cors import CORS

# bot.py'den veri yapısını içe aktar (Bu, Worker'daki güncel veriyi çeker)
from bot import latest_state

# -----------------------
# FLASK APP & SSE STREAM
# -----------------------
app = Flask("bist_dashboard")
CORS(app)

# SSE STREAM (EventSource) - (bot.py'den taşındı)
def sse_stream():
    last_payload = None
    while True:
        try:
            # latest_state, bot.py dosyasından içe aktarılan global yapıdır
            payload = json.dumps({
                "last_run": latest_state.get("last_run"),
                "last_signal": latest_state.get("last_signal"),
                "signals": latest_state.get("signals"),
                "per_symbol": latest_state.get("per_symbol"),
                "count_symbols": len(latest_state.get("per_symbol", {})),
                "errors": latest_state.get("errors")
            }, default=str)
            if payload != last_payload:
                yield f"event: update\ndata: {payload}\n\n"
                last_payload = payload
            else:
                yield f"event: heartbeat\ndata: {datetime.utcnow().isoformat()} \n\n"
        except GeneratorExit:
            break
        except Exception:
            pass
        time.sleep(2)

# -----------------------
# FLASK ROTALARI (Routes) - (İlk koddan kopyalandı)
# -----------------------
INDEX_HTML = r"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>BIST Live Dashboard - Rich</title>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <style>
    :root{
      --bg:#071722; --card:#0b2b36; --muted:#9fb0c8; --accent:#0bb98f;
      --danger:#ef4444; --glass: rgba(255,255,255,0.03);
    }
    body{font-family:Inter,ui-sans-serif,system-ui,Arial; background:var(--bg); color:#e6eef8; margin:0; padding:18px;}
    header{display:flex; justify-content:space-between; align-items:center; margin-bottom:14px;}
    .title{font-size:20px; font-weight:700;}
    .muted{color:var(--muted); font-size:13px;}
    .grid{display:grid; grid-template-columns:1fr 420px; gap:16px;}
    .card{background:var(--card); padding:12px; border-radius:10px; box-shadow:0 6px 18px rgba(0,0,0,0.5);}
    .table{width:100%; border-collapse:collapse;}
    .table th{text-align:left; padding:10px; font-size:13px; color:var(--muted); border-bottom:1px solid var(--glass);}
    .table td{padding:10px; border-bottom:1px dashed rgba(255,255,255,0.03); font-size:14px;}
    .sym{font-weight:700;}
    .parts{font-size:13px; color:var(--muted);}
    .badge{display:inline-block; padding:6px 8px; border-radius:8px; background:#092d37; color:#bfe;}
    .sigcount{font-weight:700; font-size:16px;}
    .signal-row{display:flex; justify-content:space-between; align-items:center; gap:10px; padding:10px; border-radius:8px; background:linear-gradient(90deg, rgba(255,255,255,0.01), rgba(255,255,255,0.00)); margin-bottom:8px;}
    .sig-left{display:flex; gap:12px; align-items:center;}
    .sig-right{display:flex; gap:8px; align-items:center;}
    .small{font-size:12px; color:var(--muted);}
    .blink-green{ animation: blink-green 1s linear infinite; color: #00ff88; font-size:18px; }
    .blink-red{ animation: blink-red 1s linear infinite; color: #ff5c5c; font-size:18px; }
    @keyframes blink-green{ 0%{opacity:1;}50%{opacity:0.15;}100%{opacity:1;} }
    @keyframes blink-red{ 0%{opacity:1;}50%{opacity:0.15;}100%{opacity:1;} }

    /* strong arrows */
    .arrow { font-size:20px; }
    .arrow.up { color:#00d29b; transform:translateY(-1px); }
    .arrow.down { color:#ff6b6b; transform:translateY(1px); }

    /* responsive */
    @media (max-width:900px){
      .grid{grid-template-columns:1fr;}
    }

    .controls{display:flex; gap:8px; margin-bottom:12px;}
    input[type=text]{padding:8px; border-radius:8px; background:#02141a; border:1px solid rgba(255,255,255,0.03); color:#bfe;}
    button.btn{background:#0b6b4a; color:white; border:none; padding:8px 10px; border-radius:8px; cursor:pointer;}
    .sr { color:#9fb0c8; font-size:13px; margin-top:6px;}
  </style>
</head>
<body>
  <header>
    <div>
      <div class="title">📊 BIST Live Dashboard — Zengin Görünüm</div>
      <div class="muted">Otomatik güncellenen sinyaller & zengin tablo</div>
    </div>
    <div style="text-align:right;">
      <div id="last_run" class="muted">Son tarama: -</div>
      <div id="counts" class="muted">Sinyal: 0 — Taranan: 0</div>
    </div>
  </header>

  <div class="controls">
    <input id="search" type="text" placeholder="Ara (ör: ASELS, GARAN) veya boş bırak" />
    <button class="btn" onclick="clearSignals()">Sinyalleri temizle</button>
  </div>

  <div class="grid">
    <div>
      <div class="card">
        <h3 style="margin:0 0 8px 0;">Canlı Sinyaller</h3>
        <div id="signals" style="max-height:60vh; overflow:auto;"></div>
        <div class="sr">Not: Güçlü sinyaller <span style="color:#00ff88">YEŞİL</span>/<span style="color:#ff6b6b">KIRMIZI</span> ok ile gösterilir. Al → yeşil yanıp söner. Sat → kırmızı yanıp söner.</div>
      </div>

      <div class="card" style="margin-top:12px;">
        <h3 style="margin:0 0 8px 0;">Sembol Tablosu</h3>
        <table class="table">
          <thead><tr>
            <th>Sembol</th><th>Fiyat</th><th>RSI(4H)</th><th>MA Cross</th><th>Hacim</th><th>Sinyaller</th>
          </tr></thead>
          <tbody id="symtable"></tbody>
        </table>
      </div>
    </div>

    <div>
      <div class="card">
        <h3 style="margin:0 0 8px 0;">Seçili Sembol Detay</h3>
        <div id="detail">Sinyallerden birine tıklayın veya alttan sembol seçin.</div>
      </div>

      <div class="card" style="margin-top:12px;">
        <h3 style="margin:0 0 8px 0;">Hata & Log</h3>
        <div id="errors" style="max-height:28vh; overflow:auto;"></div>
      </div>
    </div>
  </div>

<script>
let evt = new EventSource("/stream");
let latest = null;
evt.addEventListener("update", function(e){
  const data = JSON.parse(e.data);
  latest = data;
  document.getElementById("last_run").innerText = "Son tarama: " + (data.last_run || "-");
  document.getElementById("counts").innerText = "Sinyal: " + (data.signals?data.signals.length:0) + " — Taranan: " + (data.count_symbols||0);

  // signals panel
  const signalsDiv = document.getElementById("signals");
  signalsDiv.innerHTML = "";
  if (data.signals && data.signals.length>0){
    // reverse so newest first
    data.signals.slice().reverse().forEach(s => {
      const el = document.createElement("div");
      el.className = "signal-row";
      // arrow/strength
      let arrowHtml = "";
      if (s.strength === "strong_buy"){
        arrowHtml = `<span class="blink-green arrow up">▲</span>`;
      } else if (s.strength === "buy"){
        arrowHtml = `<span class="arrow up" style="color:#00d29b;">▲</span>`;
      } else if (s.strength === "strong_sell"){
        arrowHtml = `<span class="blink-red arrow down">▼</span>`;
      } else if (s.strength === "sell"){
        arrowHtml = `<span class="arrow down" style="color:#ff6b6b;">▼</span>`;
      }

      const left = document.createElement("div");
      left.className = "sig-left";
      left.innerHTML = `<div><div class="sym">${s.symbol.replace('.IS','')}</div><div class="small muted">${s.time}</div></div>`;

      const mid = document.createElement("div");
      mid.className = "parts";
      mid.innerHTML = (s.parts && s.parts.length? s.parts.join(" • "): "-");

      const right = document.createElement("div");
      right.className = "sig-right";
      right.innerHTML = `<div style="text-align:right;"><div style="font-weight:700;">${s.price.toFixed(2)} ₺</div>${arrowHtml}</div><div><button class="btn" onclick="showDetail('${s.symbol}')">Detay</button></div>`;

      el.appendChild(left);
      el.appendChild(mid);
      el.appendChild(right);
      signalsDiv.appendChild(el);
    });
  } else {
    signalsDiv.innerHTML = "<div class='muted'>Şu anda yeni sinyal yok.</div>";
  }

  // symbol table
  const tableBody = document.getElementById("symtable");
  tableBody.innerHTML = "";
  const per = data.per_symbol || {};
  const keys = Object.keys(per).sort();
  keys.forEach(k=>{
    const v = per[k];
    const tr = document.createElement("tr");
    const parts = [];
    if (v.g1 && v.g2) parts.push("G1+G2");
    if (v.ma_crosses && v.ma_crosses.length) parts.push(v.ma_crosses.join(","));
    if (v.vol_spike) parts.push("Vol Spike");
    const sigTxt = parts.length? parts.join(" • "): "-";
    tr.innerHTML = `<td><b>${k.replace('.IS','')}</b></td>
                    <td>${v.price? v.price.toFixed(2): '-'}</td>
                    <td>${v.rsi4h? v.rsi4h.toFixed(1): 'N/A'}</td>
                    <td>${v.ma_crosses? v.ma_crosses.join(","):'-'}</td>
                    <td>${v.vol_spike? 'YES':'-'}</td>
                    <td class="parts">${sigTxt}</td>`;
    tableBody.appendChild(tr);
  });

  // errors
  const errDiv = document.getElementById("errors");
  errDiv.innerHTML = "";
  if (data.errors && data.errors.length>0){
    data.errors.slice().reverse().forEach(e=>{
      const el = document.createElement("div");
      el.innerText = `${e.symbol || ''} — ${e.error || JSON.stringify(e)}`;
      errDiv.appendChild(el);
    });
  } else {
    errDiv.innerHTML = "<div class='muted'>Hata yok.</div>";
  }
});

function showDetail(sym){
  fetch("/summary?symbol="+encodeURIComponent(sym))
    .then(r=>r.json())
    .then(d=>{
      if (!d.ok){ document.getElementById("detail").innerText = "Detay bulunamadı."; return; }
      const html = `<div><h4>${d.symbol.replace('.IS','')}</h4>
        <div>Fiyat: <b>${d.price? d.price.toFixed(2): '-' } ₺</b></div>
        <div>RSI(4H): ${d.rsi4h? d.rsi4h.toFixed(1): 'N/A'}</div>
        <div>MA Crosses: ${d.ma_crosses && d.ma_crosses.length? d.ma_crosses.join(', '): '-'}</div>
        <div>Hacim: ${d.vol_spike? ('Spike (last:'+d.last_vol+')'): 'Normal'}</div>
        <div>Destek: ${d.supports? d.supports.join(', '): '-'}</div>
        <div>Direnç: ${d.resistances? d.resistances.join(', '): '-'}</div>
        <div class="small muted">Güncelleme: ${d.ts || '-'}</div>
      </div>`;
      document.getElementById("detail").innerHTML = html;
    }).catch(()=>{ document.getElementById("detail").innerText = "Hata alındı." })
}

function clearSignals(){
  document.getElementById("signals").innerHTML = "<div class='muted'>Sinyaller temizlendi (yerel görüntü).</div>";
}

document.getElementById("search").addEventListener("input", function(e){
  const q = e.target.value.trim().toUpperCase();
  const rows = document.querySelectorAll("#symtable tr");
  rows.forEach(r=>{
    const txt = r.innerText.toUpperCase();
    r.style.display = txt.indexOf(q) >= 0 ? "" : "none";
  });
});
</script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(INDEX_HTML)

@app.route("/stream")
def stream():
    return Response(sse_stream(), mimetype="text/event-stream")

@app.route("/status_json")
def status_json():
    return jsonify({
        "running": latest_state.get("running", False),
        "last_run": latest_state.get("last_run"),
        "signals_count": len(latest_state.get("signals", [])),
        "last_signal": latest_state.get("last_signal"),
        "errors": latest_state.get("errors", [])
    })

@app.route("/summary")
def summary():
    sym = request.args.get("symbol")
    ps = latest_state.get("per_symbol", {})
    if not sym or sym not in ps:
        return jsonify({"ok": False})
    return jsonify({"ok": True, **ps[sym]})

if __name__ == "__main__":
    print("Starting dashboard on http://0.0.0.0:5000")
    # Not: Render'da gunicorn ile çalışacağı için bu kısım Worker tarafından yönetilir.
    app.run(host="0.0.0.0", port=5000, threaded=True)
