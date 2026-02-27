# 1. استيراد المكتبات الأساسية
import os
from flask import Flask, request, redirect, render_template_string, session, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3

# 2. إعدادات التطبيق الأساسية
app = Flask(__name__)
app.secret_key = 'printer_system_pro_2026'

# --- تعديل سيرفر Render: استخدام المسار المطلق لقاعدة البيانات ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "printer_system.db")
# -----------------------------------------------------------------

# 3. القاموس اللغوي
LANGS = {
    'ar': {
        'title': 'نظام إدارة الطابعات', 'home': 'الرئيسية', 'reports': 'التقارير', 'users_manage': 'إدارة المستخدمين',
        'add': 'إضافة', 'edit': 'تعديل', 'delete': 'حذف', 'search': 'بحث...', 'logout': 'خروج',
        'status': 'الحالة', 'working': 'تعمل', 'maintenance': 'صيانة', 'broken': 'لا تعمل',
        'serial': 'الرقم التسلسلي', 'dept': 'القسم', 'name': 'الاسم', 'role': 'الدور',
        'admin': 'مدير', 'entry': 'مدخل بيانات', 'user': 'مستخدم', 'save': 'حفظ التغييرات',
        'login': 'تسجيل الدخول', 'username': 'اسم المستخدم', 'password': 'كلمة المرور',
        'total': 'إجمالي الطابعات', 'depts_count': 'أقسام مسجلة',
        'code': 'الرمز', 'notes': 'ملاحظات', 'edit_printer': 'تعديل بيانات الطابعة'
    },
    'en': {
        'title': 'Printer System', 'home': 'Home', 'reports': 'Reports', 'users_manage': 'Manage Users',
        'add': 'Add', 'edit': 'Edit', 'delete': 'Delete', 'search': 'Search...', 'logout': 'Logout',
        'status': 'Status', 'working': 'Working', 'maintenance': 'Maintenance', 'broken': 'Not Working',
        'serial': 'Serial', 'dept': 'Dept', 'name': 'Name', 'role': 'Role',
        'admin': 'Admin', 'entry': 'Data Entry', 'user': 'User', 'save': 'Save Changes',
        'login': 'Login', 'username': 'Username', 'password': 'Password',
        'total': 'Total Printers', 'depts_count': 'Registered Depts',
        'code': 'Code', 'notes': 'Notes', 'edit_printer': 'Edit Printer Details'
    }
}

# --- 4. تعريف واجهات العرض ---

DASHBOARD_UI = """
<div class="row mb-4">
    <div class="col-md-6"><h3><i class="fas fa-list text-primary"></i> {{ L['home'] }}</h3></div>
    <div class="col-md-6 text-end">
        <form action="/" method="GET" class="d-flex">
            <input name="q" class="form-control me-2 shadow-sm" placeholder="{{ L['search'] }}" value="{{ query }}">
            <button class="btn btn-primary shadow-sm"><i class="fas fa-search"></i></button>
        </form>
    </div>
</div>

{% if session.get('role') in ['admin', 'entry'] %}
<div class="card p-4 mb-4 border-0 shadow-sm bg-light">
    <form action="/add" method="POST" class="row g-3">
        <div class="col-md-2"><input name="name" class="form-control" placeholder="{{ L['name'] }}" required></div>
        <div class="col-md-2"><input name="serial" class="form-control" placeholder="{{ L['serial'] }}" required></div>
        <div class="col-md-2"><input name="dept" class="form-control" placeholder="{{ L['dept'] }}"></div>
        <div class="col-md-2"><input name="code" class="form-control" placeholder="{{ L['code'] }}"></div>
        <div class="col-md-2">
            <select name="status" class="form-select">
                <option value="Working">{{ L['working'] }}</option>
                <option value="Maintenance">{{ L['maintenance'] }}</option>
                <option value="Broken">{{ L['broken'] }}</option>
            </select>
        </div>
        <div class="col-md-8"><input name="notes" class="form-control" placeholder="{{ L['notes'] }}"></div>
        <div class="col-md-4"><button class="btn btn-success w-100"><i class="fas fa-plus"></i> {{ L['add'] }}</button></div>
    </form>
</div>
{% endif %}

<div class="card overflow-hidden shadow-sm">
    <table class="table table-hover align-middle mb-0">
        <thead class="table-dark">
            <tr>
                <th>{{ L['code'] }}</th><th>{{ L['name'] }}</th><th>{{ L['serial'] }}</th>
                <th>{{ L['dept'] }}</th><th>{{ L['status'] }}</th><th>{{ L['notes'] }}</th>
                {% if session.get('role') in ['admin', 'entry'] %}<th>إجراءات</th>{% endif %}
            </tr>
        </thead>
        <tbody>
            {% for p in printers %}
            <tr>
                <td><span class="badge bg-secondary">{{ p.code }}</span></td>
                <td><strong>{{ p.name }}</strong></td>
                <td><code>{{ p.serial }}</code></td>
                <td>{{ p.department }}</td>
                <td><span class="badge status-{{ p.status }} p-2">{{ L[p.status.lower().replace(' ', '')] }}</span></td>
                <td><small class="text-muted">{{ p.notes }}</small></td>
                <td>
                    {% if session.get('role') in ['admin', 'entry'] %}
                    <a href="/edit/{{ p.id }}" class="btn btn-sm btn-outline-primary"><i class="fas fa-edit"></i></a>
                    {% endif %}
                    {% if session.get('role') == 'admin' %}
                    <a href="/delete/{{ p.id }}" class="btn btn-sm btn-outline-danger" onclick="return confirm('هل أنت متأكد؟')"><i class="fas fa-trash"></i></a>
                    {% endif %}
                </td>
            </tr>
            {% else %}
            <tr><td colspan="7" class="text-center py-4 text-muted">لا توجد بيانات لعرضها</td></tr>
            {% endfor %}
        </tbody>
    </table>
</div>
"""

EDIT_UI = """
<div class="row mb-4">
    <div class="col-12"><h3><i class="fas fa-edit text-primary"></i> {{ L['edit_printer'] }}</h3></div>
</div>
<div class="card p-4 border-0 shadow-sm bg-light">
    <form action="/edit/{{ printer.id }}" method="POST" class="row g-3">
        <div class="col-md-3"><label>{{ L['name'] }}</label><input name="name" class="form-control" value="{{ printer.name }}" required></div>
        <div class="col-md-3"><label>{{ L['serial'] }}</label><input name="serial" class="form-control" value="{{ printer.serial }}" required></div>
        <div class="col-md-3"><label>{{ L['dept'] }}</label><input name="dept" class="form-control" value="{{ printer.department }}"></div>
        <div class="col-md-3"><label>{{ L['code'] }}</label><input name="code" class="form-control" value="{{ printer.code }}"></div>
        
        <div class="col-md-4">
            <label>{{ L['status'] }}</label>
            <select name="status" class="form-select">
                <option value="Working" {% if printer.status == 'Working' %}selected{% endif %}>{{ L['working'] }}</option>
                <option value="Maintenance" {% if printer.status == 'Maintenance' %}selected{% endif %}>{{ L['maintenance'] }}</option>
                <option value="Broken" {% if printer.status == 'Broken' %}selected{% endif %}>{{ L['broken'] }}</option>
            </select>
        </div>
        <div class="col-md-8"><label>{{ L['notes'] }}</label><input name="notes" class="form-control" value="{{ printer.notes }}"></div>
        
        <div class="col-12 mt-4">
            <button class="btn btn-primary px-4"><i class="fas fa-save"></i> {{ L['save'] }}</button>
            <a href="/" class="btn btn-secondary px-4">{{ L['home'] }}</a>
        </div>
    </form>
</div>
"""

REPORTS_UI = """
<div class="row mb-4">
    <div class="col-12"><h3><i class="fas fa-chart-pie text-primary"></i> {{ L['reports'] }}</h3></div>
</div>
<div class="row g-4 text-center">
    <div class="col-md-12">
        <div class="card p-4 bg-white border-bottom border-primary border-4 shadow-sm">
            <h5 class="text-muted">{{ L['total'] }}</h5>
            <h1 class="text-primary fw-bold display-4">{{ stats.total }}</h1>
        </div>
    </div>
    <div class="col-md-4">
        <div class="card p-4 bg-white border-bottom border-success border-4 shadow-sm">
            <h5 class="text-muted">{{ L['working'] }}</h5>
            <h2 class="text-success fw-bold">{{ stats.active }}</h2>
        </div>
    </div>
    <div class="col-md-4">
        <div class="card p-4 bg-white border-bottom border-warning border-4 shadow-sm">
            <h5 class="text-muted">{{ L['maintenance'] }}</h5>
            <h2 class="text-warning fw-bold">{{ stats.maint }}</h2>
        </div>
    </div>
    <div class="col-md-4">
        <div class="card p-4 bg-white border-bottom border-danger border-4 shadow-sm">
            <h5 class="text-muted">{{ L['broken'] }}</h5>
            <h2 class="text-danger fw-bold">{{ stats.broken }}</h2>
        </div>
    </div>
</div>
"""

USERS_UI = """
<div class="row mb-4">
    <div class="col-12"><h3><i class="fas fa-users text-primary"></i> {{ L['users_manage'] }}</h3></div>
</div>
<div class="card p-4 mb-4 border-0 shadow-sm bg-light">
    <form action="/add_user" method="POST" class="row g-3">
        <div class="col-md-3"><input name="username" class="form-control" placeholder="{{ L['username'] }}" required></div>
        <div class="col-md-3"><input type="password" name="password" class="form-control" placeholder="{{ L['password'] }}" required></div>
        <div class="col-md-3">
            <select name="role" class="form-select">
                <option value="admin">{{ L['admin'] }}</option>
                <option value="entry">{{ L['entry'] }}</option>
                <option value="user">{{ L['user'] }}</option>
            </select>
        </div>
        <div class="col-md-3"><button class="btn btn-success w-100"><i class="fas fa-plus"></i> {{ L['add'] }}</button></div>
    </form>
</div>
<div class="card overflow-hidden shadow-sm">
    <table class="table table-hover align-middle mb-0">
        <thead class="table-dark">
            <tr><th>{{ L['username'] }}</th><th>{{ L['role'] }}</th><th>{{ L['delete'] }}</th></tr>
        </thead>
        <tbody>
            {% for u in users %}
            <tr>
                <td>{{ u.username }}</td>
                <td>{{ L[u.role] }}</td>
                <td>
                    {% if u.username != 'admin' %}
                    <a href="/delete_user/{{ u.id }}" class="btn btn-sm btn-outline-danger"><i class="fas fa-trash"></i></a>
                    {% endif %}
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>
"""

# --- 5. وظائف قاعدة البيانات ---

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS printers (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, serial TEXT UNIQUE, department TEXT, status TEXT, code TEXT, notes TEXT)")
        
        try: conn.execute("ALTER TABLE printers ADD COLUMN code TEXT")
        except: pass
        try: conn.execute("ALTER TABLE printers ADD COLUMN notes TEXT")
        except: pass

        conn.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT, role TEXT)")
        admin_pass = generate_password_hash('admin123')
        conn.execute("INSERT OR IGNORE INTO users (username, password, role) VALUES ('admin', ?, 'admin')", (admin_pass,))
        conn.commit()

# --- تعديل سيرفر Render: تشغيل الدالة إجبارياً لمنع خطأ 500 ---
init_db()
# ----------------------------------------------------------------

# --- 6. الهيكل العام (Layout) ---

def render_ui(content_html, **context):
    lang_code = session.get('lang', 'ar')
    L = LANGS[lang_code]
    layout = """
    <!DOCTYPE html>
    <html lang="{{ lang_code }}" dir="{{ 'rtl' if lang_code == 'ar' else 'ltr' }}">
    <head>
        <meta charset="UTF-8">
        <title>{{ L['title'] }}</title>
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap{% if lang_code == 'ar' %}.rtl{% endif %}.min.css">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            body { background: #f8f9fa; font-family: 'Segoe UI', Tahoma; }
            .navbar { background: #1a237e; }
            .status-Working { background: #d4edda; color: #155724; }
            .status-Maintenance { background: #fff3cd; color: #856404; }
            .status-Broken { background: #f8d7da; color: #721c24; }
        </style>
    </head>
    <body>
        <nav class="navbar navbar-expand-lg navbar-dark mb-4 p-3">
            <div class="container">
                <a class="navbar-brand" href="/">{{ L['title'] }}</a>
                {% if session.get('user') %}
                <div class="navbar-nav mx-auto">
                    <a class="nav-link" href="/">{{ L['home'] }}</a>
                    <a class="nav-link" href="/reports">{{ L['reports'] }}</a>
                    {% if session.get('role') == 'admin' %}<a class="nav-link" href="/users">{{ L['users_manage'] }}</a>{% endif %}
                </div>
                {% endif %}
                <a href="/set_lang/{% if lang_code == 'ar' %}en{% else %}ar{% endif %}" class="btn btn-sm btn-outline-light">{% if lang_code == 'ar' %}English{% else %}العربية{% endif %}</a>
                {% if session.get('user') %}<a href="/logout" class="btn btn-danger btn-sm ms-2"><i class="fas fa-sign-out-alt"></i></a>{% endif %}
            </div>
        </nav>
        <div class="container">
            {% with messages = get_flashed_messages() %}{% if messages %}{% for msg in messages %}<div class="alert alert-warning">{{ msg }}</div>{% endfor %}{% endif %}{% endwith %}
            """ + content_html + """
        </div>
    </body>
    </html>
    """
    return render_template_string(layout, L=L, lang_code=lang_code, **context)

# --- 7. المسارات (Routes) ---

@app.route('/')
def index():
    if 'user' not in session: return redirect(url_for('login'))
    q = request.args.get('q', '')
    with get_db() as conn:
        query_sql = f"%{q}%"
        printers = conn.execute("SELECT * FROM printers WHERE name LIKE ? OR serial LIKE ? OR department LIKE ? OR code LIKE ? OR notes LIKE ?", (query_sql, query_sql, query_sql, query_sql, query_sql)).fetchall()
    return render_ui(DASHBOARD_UI, printers=printers, query=q)

@app.route('/reports')
def reports():
    if 'user' not in session: return redirect(url_for('login'))
    with get_db() as conn:
        stats = {
            'total': conn.execute("SELECT COUNT(*) FROM printers").fetchone()[0],
            'active': conn.execute("SELECT COUNT(*) FROM printers WHERE status='Working'").fetchone()[0],
            'maint': conn.execute("SELECT COUNT(*) FROM printers WHERE status='Maintenance'").fetchone()[0],
            'broken': conn.execute("SELECT COUNT(*) FROM printers WHERE status='Broken'").fetchone()[0],
        }
    return render_ui(REPORTS_UI, stats=stats)

@app.route('/users')
def users():
    if session.get('role') != 'admin': return redirect(url_for('index'))
    with get_db() as conn:
        users_list = conn.execute("SELECT * FROM users").fetchall()
    return render_ui(USERS_UI, users=users_list)

@app.route('/add_user', methods=['POST'])
def add_user():
    if session.get('role') == 'admin':
        with get_db() as conn:
            conn.execute("INSERT INTO users (username, password, role) VALUES (?,?,?)", (request.form['username'], generate_password_hash(request.form['password']), request.form['role']))
            conn.commit()
    return redirect(url_for('users'))

@app.route('/delete_user/<int:uid>')
def delete_user(uid):
    if session.get('role') == 'admin':
        with get_db() as conn:
            conn.execute("DELETE FROM users WHERE id=? AND username!='admin'", (uid,))
            conn.commit()
    return redirect(url_for('users'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        with get_db() as conn:
            user = conn.execute("SELECT * FROM users WHERE username=?", (request.form['username'],)).fetchone()
            if user and check_password_hash(user['password'], request.form['password']):
                session['user'], session['role'] = user['username'], user['role']
                return redirect(url_for('index'))
        flash("فشل الدخول: تأكد من اسم المستخدم أو كلمة المرور")
    return render_ui('<div class="row justify-content-center"><div class="col-md-4 card p-4 mt-5 shadow"><h4 class="text-center mb-4">{{ L["login"] }}</h4><form method="POST"><input name="username" class="form-control mb-3" placeholder="{{ L[\'username\'] }}"><input type="password" name="password" class="form-control mb-3" placeholder="{{ L[\'password\'] }}"><button class="btn btn-primary w-100">{{ L[\'login\'] }}</button></form></div></div>')

@app.route('/add', methods=['POST'])
def add():
    if session.get('role') in ['admin', 'entry']:
        with get_db() as conn:
            try:
                conn.execute("INSERT INTO printers (name, serial, department, status, code, notes) VALUES (?,?,?,?,?,?)", 
                             (request.form['name'], request.form['serial'], request.form['dept'], request.form['status'], request.form.get('code', ''), request.form.get('notes', '')))
                conn.commit()
            except: flash("خطأ في الإضافة - تأكد من عدم تكرار الرقم التسلسلي")
    return redirect(url_for('index'))

@app.route('/edit/<int:pid>', methods=['GET', 'POST'])
def edit(pid):
    if session.get('role') not in ['admin', 'entry']: return redirect(url_for('index'))
    with get_db() as conn:
        if request.method == 'POST':
            try:
                conn.execute("UPDATE printers SET name=?, serial=?, department=?, status=?, code=?, notes=? WHERE id=?", 
                             (request.form['name'], request.form['serial'], request.form['dept'], request.form['status'], request.form.get('code', ''), request.form.get('notes', ''), pid))
                conn.commit()
            except:
                flash("خطأ في التعديل")
            return redirect(url_for('index'))
        printer = conn.execute("SELECT * FROM printers WHERE id=?", (pid,)).fetchone()
    return render_ui(EDIT_UI, printer=printer)

@app.route('/delete/<int:pid>')
def delete(pid):
    if session.get('role') == 'admin':
        with get_db() as conn:
            conn.execute("DELETE FROM printers WHERE id=?", (pid,))
            conn.commit()
    return redirect(url_for('index'))

@app.route('/set_lang/<lang>')
def set_lang(lang):
    if lang in ['ar', 'en']: session['lang'] = lang
    return redirect(request.referrer or url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=False)
