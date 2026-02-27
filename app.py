import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = 'printer_secret'

# استخدام مسار كامل لقاعدة البيانات لضمان عملها على السيرفر
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'database.db')

def init_db():
    with sqlite3.connect(DATABASE) as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS printers (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, ip TEXT)')

# تشغيل إنشاء القاعدة فوراً لضمان وجود الجداول قبل دخول أي مستخدم
init_db()

@app.route('/')
def index():
    if not session.get('logged_in'): 
        return redirect(url_for('login'))
    
    with sqlite3.connect(DATABASE) as conn:
        conn.row_factory = sqlite3.Row
        printers = conn.execute('SELECT * FROM printers').fetchall()
    return render_template('index.html', printers=printers)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # تأكد أن الأسماء (user و pass) تطابق الـ name في ملف login.html
        if request.form.get('user') == 'admin' and request.form.get('pass') == 'admin123':
            session['logged_in'] = True
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/add', methods=['POST'])
def add():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
        
    name = request.form.get('name')
    ip = request.form.get('ip')
    
    if name and ip:
        with sqlite3.connect(DATABASE) as conn:
            conn.execute('INSERT INTO printers (name, ip) VALUES (?, ?)', (name, ip))
    
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=False)
