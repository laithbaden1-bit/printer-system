import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, flash, session

# تعديل مسار القوالب ليتوافق مع مجلداتك الحالية في GitHub
app = Flask(__name__, template_folder='templates/templates')
app.secret_key = 'supersecretkey'

# إعداد مسار قاعدة البيانات
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "printer_system.db")

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS printers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                ip TEXT NOT NULL,
                code TEXT,
                notes TEXT
            )
        ''')

@app.route('/')
def index():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    conn = get_db()
    printers = conn.execute('SELECT * FROM printers').fetchall()
    conn.close()
    return render_template('index.html', printers=printers)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == ADMIN_USERNAME and request.form['password'] == ADMIN_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            flash('خطأ في اسم المستخدم أو كلمة المرور', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/add', methods=['POST'])
def add_printer():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    name = request.form['name']
    ip = request.form['ip']
    code = request.form.get('code', '')
    notes = request.form.get('notes', '')
    if name and ip:
        conn = get_db()
        conn.execute('INSERT INTO printers (name, ip, code, notes) VALUES (?, ?, ?, ?)',
                     (name, ip, code, notes))
        conn.commit()
        conn.close()
    return redirect(url_for('index'))

@app.route('/delete/<int:id>')
def delete_printer(id):
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    conn = get_db()
    conn.execute('DELETE FROM printers WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run(debug=False)
