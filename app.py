import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = 'printer_secret'

DATABASE = 'database.db'

def init_db():
    with sqlite3.connect(DATABASE) as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS printers (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, ip TEXT)')

@app.route('/')
def index():
    if not session.get('logged_in'): return redirect(url_for('login'))
    with sqlite3.connect(DATABASE) as conn:
        conn.row_factory = sqlite3.Row
        printers = conn.execute('SELECT * FROM printers').fetchall()
    return render_template('index.html', printers=printers)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['user'] == 'admin' and request.form['pass'] == 'admin123':
            session['logged_in'] = True
            return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/add', methods=['POST'])
def add():
    with sqlite3.connect(DATABASE) as conn:
        conn.execute('INSERT INTO printers (name, ip) VALUES (?, ?)', (request.form['name'], request.form['ip']))
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db()
    app.run()
