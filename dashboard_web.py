# dashboard_web.py placeholder
from flask import Flask
app = Flask(__name__)

@app.route('/')
def home():
    return "<h1>Dashboard Works</h1>"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
