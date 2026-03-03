# 1. استيراد المكتبات الأساسية
import os
import csv
import io
import psycopg2
import psycopg2.extras
from datetime import timedelta
from flask import Flask, request, redirect, render_template_string, session, url_for, flash, make_response
from werkzeug.security import generate_password_hash, check_password_hash

# 2. إعدادات التطبيق الأساسية
app = Flask(__name__)
app.secret_key = 'printer_system_pro_2026_super_secret'
app.permanent_session_lifetime = timedelta(days=30)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# --- إعدادات السيرفر (جاهزة للرفع) ---
DATABASE_URL = os.environ.get('DATABASE_URL')
# ------------------------------------

# --- دروع الأمان (Security Headers) ---
@app.after_request
def add_security_headers(response):
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response
# ---------------------------------------

# 3. القاموس اللغوي الشامل
LANGS = {
    'ar': {
        'title': 'نظام إدارة الطابعات', 'home': 'الرئيسية', 'reports': 'التقارير', 'users_manage': 'إدارة المستخدمين',
        'add': 'إضافة', 'edit': 'تعديل', 'delete': 'حذف', 'search': 'بحث...', 'logout': 'خروج',
        'status': 'الحالة', 'working': 'تعمل', 'maintenance': 'صيانة', 'broken': 'لا تعمل',
        'serial': 'الرقم التسلسلي', 'dept': 'القسم', 'name': 'نوع وموديل الطابعة', 'role': 'الدور',
        'admin': 'مدير', 'entry': 'مدخل بيانات', 'user': 'مستخدم', 'save': 'حفظ التغييرات',
        'login': 'تسجيل الدخول', 'username': 'اسم المستخدم', 'password': 'كلمة المرور',
        'total': 'إجمالي الطابعات', 'depts_count': 'أقسام مسجلة',
        'code': 'الرمز', 'notes': 'ملاحظات', 'edit_printer': 'تعديل بيانات الطابعة',
        'color_type': 'نوع الطباعة', 'color': 'ملون', 'bw': 'أبيض وأسود', 'remember': 'تذكرني',
        'add_manual': 'إضافة طابعة يدوياً', 'upload_csv_title': 'رفع مجموعة طابعات (ملف CSV)',
        'upload_btn': 'رفع الملف', 'actions': 'إجراءات', 'confirm_delete': 'هل أنت متأكد من حذف هذه الطابعة؟',
        'no_data': 'لا توجد بيانات لعرضها', 'export_excel': 'تصدير (Excel)', 'dashboard_title': '(لوحة التحكم)',
        'printers_status': 'حالة الطابعات', 'print_type_chart': 'نوع الطباعة', 'dept_dist': 'توزيع الأقسام',
        'count': 'العدد', 'no_dept_data': 'لا توجد بيانات للأقسام', 'login_desc': 'الرجاء إدخال بيانات الاعتماد الخاصة بك',
        'keep_login': '(الاحتفاظ بتسجيل الدخول)'
    },
    'en': {
        'title': 'Printer System', 'home': 'Home', 'reports': 'Reports', 'users_manage': 'Manage Users',
        'add': 'Add', 'edit': 'Edit', 'delete': 'Delete', 'search': 'Search...', 'logout': 'Logout',
        'status': 'Status', 'working': 'Working', 'maintenance': 'Maintenance', 'broken': 'Broken',
        'serial': 'Serial Number', 'dept': 'Department', 'name': 'Printer Type & Model', 'role': 'Role',
        'admin': 'Admin', 'entry': 'Data Entry', 'user': 'User', 'save': 'Save Changes',
        'login': 'Login', 'username': 'Username', 'password': 'Password',
        'total': 'Total Printers', 'depts_count': 'Registered Depts',
        'code': 'Code', 'notes': 'Notes', 'edit_printer': 'Edit Printer Details',
        'color_type': 'Print Type', 'color': 'Color', 'bw': 'Black & White', 'remember': 'Remember Me',
        'add_manual': 'Add Printer Manually', 'upload_csv_title': 'Upload Printers (CSV File)',
        'upload_btn': 'Upload File', 'actions': 'Actions', 'confirm_delete': 'Are you sure you want to delete this printer?',
        'no_data': 'No data to display', 'export_excel': 'Export (Excel)', 'dashboard_title': '(Dashboard)',
        'printers_status': 'Printers Status', 'print_type_chart': 'Print Type', 'dept_dist': 'Departments Distribution',
        'count': 'Count', 'no_dept_data': 'No department data', 'login_desc': 'Please enter your credentials',
        'keep_login': '(Keep me logged in)'
    }
}

# --- 4. واجهات العرض (HTML) ---
DASHBOARD_UI = """
<div class="row mb-4">
    <div class="col-md-4"><h3><i class="fas fa-list text-primary"></i> {{ L['home'] }}</h3></div>
    <div class="col-md-8 text-end">
        <form action="/" method="GET" class="d-flex justify-content-end">
            <input name="q" class="form-control me-2 shadow-sm w-50" placeholder="{{ L['search'] }}" value="{{ query }}">
            <button class="btn btn-primary shadow-sm me-2"><i class="fas fa-search"></i></button>
            {% if session.get('role') in ['admin', 'entry'] %}
            <a href="/export_csv" class="btn btn-success shadow-sm text-nowrap"><i class="fas fa-file-excel"></i> {{ L['export_excel'] }}</a>
            {% endif %}
        </form>
    </div>
</div>

{% if session.get('role') in ['admin', 'entry'] %}
<div class="card p-4 mb-4 border-0 shadow-sm bg-light">
    <h5 class="mb-3 text-primary"><i class="fas fa-plus-circle"></i> {{ L['add_manual'] }}</h5>
    <form action="/add" method="POST" class="row g-3">
        <div class="col-md-4"><input name="name" class="form-control" placeholder="{{ L['name'] }}" required></div>
        <div class="col-md-2"><input name="serial" class="form-control" placeholder="{{ L['serial'] }}" required></div>
        <div class="col-md-3"><input name="dept" class="form-control" placeholder="{{ L['dept'] }}"></div>
        <div class="col-md-3"><input name="code" class="form-control" placeholder="{{ L['code'] }}"></div>
        
        <div class="col-md-3">
            <select name="status" class="form-select">
                <option value="Working">{{ L['working'] }}</option>
                <option value="Maintenance">{{ L['maintenance'] }}</option>
                <option value="Broken">{{ L['broken'] }}</option>
            </select>
        </div>
        <div class="col-md-3">
            <select name="color_type" class="form-select">
                <option value="BW">{{ L['bw'] }}</option>
                <option value="Color">{{ L['color'] }}</option>
            </select>
        </div>
        <div class="col-md-4"><input name="notes" class="form-control" placeholder="{{ L['notes'] }}"></div>
        <div class="col-md-2"><button class="btn btn-primary w-100"><i class="fas fa-plus"></i> {{ L['add'] }}</button></div>
    </form>
    
    <hr class="my-4">
    <h5 class="mb-3 text-info"><i class="fas fa-upload"></i> {{ L['upload_csv_title'] }}</h5>
    <form action="/upload_csv" method="POST" enctype="multipart/form-data" class="row g-3 align-items-center">
        <div class="col-md-6">
            <input type="file" name="csv_file" class="form-control" accept=".csv" required>
        </div>
        <div class="col-md-3">
            <button type="submit" class="btn btn-info text-white w-100"><i class="fas fa-cloud-upload-alt"></i> {{ L['upload_btn'] }}</button>
        </div>
    </form>
</div>
{% endif %}

<div class="card shadow-sm table-scroll border-0">
    <table class="table table-hover align-middle mb-0">
        <thead>
            <tr>
                <th>{{ L['code'] }}</th><th>{{ L['name'] }}</th><th>{{ L['serial'] }}</th>
                <th>{{ L['dept'] }}</th><th>{{ L['status'] }}</th><th>{{ L['color_type'] }}</th><th>{{ L['notes'] }}</th>
                {% if session.get('role') in ['admin', 'entry'] %}<th>{{ L['actions'] }}</th>{% endif %}
            </tr>
        </thead>
        <tbody>
            {% for p in printers %}
            <tr>
                <td><span class="badge bg-secondary">{{ p['code'] }}</span></td>
                <td><strong>{{ p['name'] }}</strong></td>
                <td><code>{{ p['serial'] }}</code></td>
                <td>{{ p['department'] }}</td>
                <td><span class="badge status-{{ p['status'] }} p-2">{{ L[p['status'].lower().replace(' ', '')] }}</span></td>
                <td><span class="badge bg-light text-dark border p-1"><i class="fas {% if p['color_type'] == 'Color' %}fa-palette text-primary{% else %}fa-print text-secondary{% endif %} me-1"></i>{{ L['color'] if p['color_type'] == 'Color' else L['bw'] }}</span></td>
                <td><small class="text-muted">{{ p['notes'] }}</small></td>
                <td>
                    {% if session.get('role') in ['admin', 'entry'] %}
                    <a href="/edit/{{ p['id'] }}" class="btn btn-sm btn-outline-primary"><i class="fas fa-edit"></i></a>
                    {% endif %}
                    {% if session.get('role') == 'admin' %}
                    <a href="/delete/{{ p['id'] }}" class="btn btn-sm btn-outline-danger" onclick="return confirm('{{ L['confirm_delete'] }}')"><i class="fas fa-trash"></i></a>
                    {% endif %}
                </td>
            </tr>
            {% else %}
            <tr><td colspan="8" class="text-center py-5 text-muted"><i class="fas fa-folder-open fa-3x mb-3 text-light"></i><br>{{ L['no_data'] }}</td></tr>
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
    <form action="/edit/{{ printer['id'] }}" method="POST" class="row g-3">
        <div class="col-md-4"><label class="fw-bold">{{ L['name'] }}</label><input name="name" class="form-control" value="{{ printer['name'] }}" required></div>
        <div class="col-md-3"><label class="fw-bold">{{ L['serial'] }}</label><input name="serial" class="form-control" value="{{ printer['serial'] }}" required></div>
        <div class="col-md-3"><label class="fw-bold">{{ L['dept'] }}</label><input name="dept" class="form-control" value="{{ printer['department'] }}"></div>
        <div class="col-md-2"><label class="fw-bold">{{ L['code'] }}</label><input name="code" class="form-control" value="{{ printer['code'] }}"></div>
        
        <div class="col-md-3">
            <label class="fw-bold">{{ L['status'] }}</label>
            <select name="status" class="form-select">
                <option value="Working" {% if printer['status'] == 'Working' %}selected{% endif %}>{{ L['working'] }}</option>
                <option value="Maintenance" {% if printer['status'] == 'Maintenance' %}selected{% endif %}>{{ L['maintenance'] }}</option>
                <option value="Broken" {% if printer['status'] == 'Broken' %}selected{% endif %}>{{ L['broken'] }}</option>
            </select>
        </div>
        <div class="col-md-3">
            <label class="fw-bold">{{ L['color_type'] }}</label>
            <select name="color_type" class="form-select">
                <option value="BW" {% if printer['color_type'] == 'BW' %}selected{% endif %}>{{ L['bw'] }}</option>
                <option value="Color" {% if printer['color_type'] == 'Color' %}selected{% endif %}>{{ L['color'] }}</option>
            </select>
        </div>
        <div class="col-md-6"><label class="fw-bold">{{ L['notes'] }}</label><input name="notes" class="form-control" value="{{ printer['notes'] }}"></div>
        
        <div class="col-12 mt-4">
            <button class="btn btn-primary px-4"><i class="fas fa-save"></i> {{ L['save'] }}</button>
            <a href="/" class="btn btn-secondary px-4">{{ L['home'] }}</a>
        </div>
    </form>
</div>
"""

REPORTS_UI = """
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
    .feature-card { transition: transform 0.3s; cursor: default; }
    .feature-card:hover { transform: translateY(-5px); }
</style>

<div class="row mb-4">
    <div class="col-12"><h3><i class="fas fa-chart-pie text-primary"></i> {{ L['reports'] }} {{ L['dashboard_title'] }}</h3></div>
</div>

<div class="row g-4 text-center mb-5">
    <div class="col-md-3">
        <div class="card p-4 bg-white border-bottom border-primary border-4 shadow-sm h-100 feature-card">
            <i class="fas fa-print fa-2x text-primary mb-2"></i>
            <h5 class="text-muted">{{ L['total'] }}</h5>
            <h2 class="text-primary fw-bold">{{ stats['total'] }}</h2>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card p-4 bg-white border-bottom border-success border-4 shadow-sm h-100 feature-card">
            <i class="fas fa-check-circle fa-2x text-success mb-2"></i>
            <h5 class="text-muted">{{ L['working'] }}</h5>
            <h2 class="text-success fw-bold">{{ stats['active'] }}</h2>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card p-4 bg-white border-bottom border-warning border-4 shadow-sm h-100 feature-card">
            <i class="fas fa-tools fa-2x text-warning mb-2"></i>
            <h5 class="text-muted">{{ L['maintenance'] }}</h5>
            <h2 class="text-warning fw-bold">{{ stats['maint'] }}</h2>
        </div>
    </div>
    <div class="col-md-3">
        <div class="card p-4 bg-white border-bottom border-danger border-4 shadow-sm h-100 feature-card">
            <i class="fas fa-times-circle fa-2x text-danger mb-2"></i>
            <h5 class="text-muted">{{ L['broken'] }}</h5>
            <h2 class="text-danger fw-bold">{{ stats['broken'] }}</h2>
        </div>
    </div>
</div>

<div class="row g-4 mb-4">
    <div class="col-md-4">
        <div class="card p-4 shadow-sm border-0 h-100">
            <h5 class="text-center text-muted mb-4"><i class="fas fa-heartbeat me-2"></i>{{ L['printers_status'] }}</h5>
            <div style="height: 250px;">
                <canvas id="statusChart"></canvas>
            </div>
        </div>
    </div>
    
    <div class="col-md-4">
        <div class="card p-4 shadow-sm border-0 h-100">
            <h5 class="text-center text-muted mb-4"><i class="fas fa-palette me-2"></i>{{ L['print_type_chart'] }}</h5>
            <div style="height: 250px;">
                <canvas id="typeChart"></canvas>
            </div>
        </div>
    </div>
    
    <div class="col-md-4">
        <div class="card p-4 shadow-sm border-0 h-100">
            <h5 class="text-center text-muted mb-4"><i class="fas fa-building me-2"></i>{{ L['dept_dist'] }}</h5>
            <div class="table-responsive" style="max-height: 250px; overflow-y: auto;">
                <table class="table table-sm table-hover text-center align-middle">
                    <thead class="table-light sticky-top">
                        <tr><th class="text-start">{{ L['dept'] }}</th><th>{{ L['count'] }}</th></tr>
                    </thead>
                    <tbody>
                        {% for dept in dept_stats %}
                        <tr>
                            <td class="text-start"><small class="fw-bold text-secondary">{{ dept['department'] }}</small></td>
                            <td><span class="badge bg-primary rounded-pill">{{ dept['count'] }}</span></td>
                        </tr>
                        {% else %}
                        <tr><td colspan="2" class="text-muted py-4">{{ L['no_dept_data'] }}</td></tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</div>

<script>
document.addEventListener("DOMContentLoaded", function() {
    new Chart(document.getElementById('statusChart'), {
        type: 'doughnut',
        data: {
            labels: ['{{ L["working"] }}', '{{ L["maintenance"] }}', '{{ L["broken"] }}'],
            datasets: [{
                data: [{{ stats['active'] }}, {{ stats['maint'] }}, {{ stats['broken'] }}],
                backgroundColor: ['#198754', '#ffc107', '#dc3545'],
                borderWidth: 0,
                hoverOffset: 4
            }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
    });

    new Chart(document.getElementById('typeChart'), {
        type: 'pie',
        data: {
            labels: ['{{ L["color"] }}', '{{ L["bw"] }}'],
            datasets: [{
                data: [{{ stats['color'] }}, {{ stats['bw'] }}],
                backgroundColor: ['#0d6efd', '#6c757d'],
                borderWidth: 0,
                hoverOffset: 4
            }]
        },
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: 'bottom' } } }
    });
});
</script>
"""

USERS_UI = """<div class="row mb-4"><div class="col-12"><h3><i class="fas fa-users text-primary"></i> {{ L['users_manage'] }}</h3></div></div><div class="card p-4 mb-4 border-0 shadow-sm bg-light"><form action="/add_user" method="POST" class="row g-3"><div class="col-md-3"><input name="username" class="form-control" placeholder="{{ L['username'] }}" required></div><div class="col-md-3"><input type="password" name="password" class="form-control" placeholder="{{ L['password'] }}" required></div><div class="col-md-3"><select name="role" class="form-select"><option value="admin">{{ L['admin'] }}</option><option value="entry">{{ L['entry'] }}</option><option value="user">{{ L['user'] }}</option></select></div><div class="col-md-3"><button class="btn btn-success w-100"><i class="fas fa-plus"></i> {{ L['add'] }}</button></div></form></div><div class="card overflow-hidden shadow-sm"><table class="table table-hover align-middle mb-0"><thead class="table-dark"><tr><th>{{ L['username'] }}</th><th>{{ L['role'] }}</th><th>{{ L['delete'] }}</th></tr></thead><tbody>{% for u in users %}<tr><td>{{ u['username'] }}</td><td>{{ L[u['role']] }}</td><td>{% if u['username'] != 'admin' %}<a href="/delete_user/{{ u['id'] }}" class="btn btn-sm btn-outline-danger"><i class="fas fa-trash"></i></a>{% endif %}</td></tr>{% endfor %}</tbody></table></div>"""

# --- 5. وظائف قاعدة البيانات الدائمة (PostgreSQL) ---

def get_db_connection():
    if not DATABASE_URL: return None
    return psycopg2.connect(DATABASE_URL)

def init_db():
    if not DATABASE_URL: return
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS printers (
            id SERIAL PRIMARY KEY, name TEXT NOT NULL, serial TEXT UNIQUE, department TEXT,
            status TEXT, code TEXT, notes TEXT, color_type TEXT DEFAULT 'BW'
        )
    """)
    cur.execute("CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT)")
    
    cur.execute("ALTER TABLE printers ADD COLUMN IF NOT EXISTS code TEXT")
    cur.execute("ALTER TABLE printers ADD COLUMN IF NOT EXISTS notes TEXT")
    cur.execute("ALTER TABLE printers ADD COLUMN IF NOT EXISTS color_type TEXT DEFAULT 'BW'")
    
    admin_pass = generate_password_hash('admin123')
    cur.execute("INSERT INTO users (username, password, role) VALUES ('admin', %s, 'admin') ON CONFLICT (username) DO NOTHING", (admin_pass,))
    
    conn.commit()
    cur.close()
    conn.close()

init_db()

# --- 6. الهيكل العام (Layout) ---

def render_ui(content_html, **context):
    lang_code = session.get('lang', 'ar')
    L = LANGS.get(lang_code, LANGS['ar'])
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
            
            .table-scroll { max-height: 60vh; overflow-y: auto; }
            .table-scroll thead th { position: sticky; top: 0; background-color: #212529; color: #fff; z-index: 2; box-shadow: 0 2px 2px -1px rgba(0, 0, 0, 0.4); }
            
            body { -webkit-user-select: none; -ms-user-select: none; user-select: none; }
            input, textarea { -webkit-user-select: text; -ms-user-select: text; user-select: text; }
        </style>
    </head>
    <body oncontextmenu="return false;">
        <nav class="navbar navbar-expand-lg navbar-dark mb-4 p-3 shadow-sm">
            <div class="container">
                <a class="navbar-brand" href="/"><i class="fas fa-print me-2"></i> {{ L['title'] }}</a>
                {% if session.get('user') %}
                <div class="navbar-nav mx-auto">
                    <a class="nav-link" href="/">{{ L['home'] }}</a>
                    <a class="nav-link" href="/reports">{{ L['reports'] }}</a>
                    {% if session.get('role') == 'admin' %}<a class="nav-link" href="/users">{{ L['users_manage'] }}</a>{% endif %}
                </div>
                {% endif %}
                <a href="/set_lang/{% if lang_code == 'ar' %}en{% else %}ar{% endif %}" class="btn btn-sm btn-outline-light">{% if lang_code == 'ar' %}English{% else %}العربية{% endif %}</a>
                {% if session.get('user') %}<a href="/logout" class="btn btn-danger btn-sm ms-3"><i class="fas fa-sign-out-alt"></i></a>{% endif %}
            </div>
        </nav>
        <div class="container">
            {% with messages = get_flashed_messages(with_categories=true) %}
              {% if messages %}
                {% for category, msg in messages %}
                  <div class="alert alert-{{ 'success' if category == 'success' else 'warning' }} alert-dismissible fade show shadow-sm">
                    {{ msg }}
                    <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                  </div>
                {% endfor %}
              {% endif %}
            {% endwith %}
            """ + content_html + """
        </div>
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
        <script>
            document.onkeydown = function(e) {
                if(event.keyCode == 123) { return false; }
                if(e.ctrlKey && e.shiftKey && e.keyCode == 'I'.charCodeAt(0)) { return false; }
                if(e.ctrlKey && e.shiftKey && e.keyCode == 'C'.charCodeAt(0)) { return false; }
                if(e.ctrlKey && e.shiftKey && e.keyCode == 'J'.charCodeAt(0)) { return false; }
                if(e.ctrlKey && e.keyCode == 'U'.charCodeAt(0)) { return false; }
            }
        </script>
    </body>
    </html>
    """
    return render_template_string(layout, L=L, lang_code=lang_code, **context)

# --- 7. المسارات (Routes) ---

@app.route('/')
def index():
    if 'user' not in session: return redirect(url_for('login'))
    q = request.args.get('q', '')
    query_sql = f"%{q}%"
    conn = get_db_connection()
    if not conn: return "Database Error"
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT * FROM printers WHERE name ILIKE %s OR serial ILIKE %s OR department ILIKE %s OR code ILIKE %s OR notes ILIKE %s ORDER BY id DESC", (query_sql, query_sql, query_sql, query_sql, query_sql))
    printers = cur.fetchall()
    cur.close()
    conn.close()
    return render_ui(DASHBOARD_UI, printers=printers, query=q)

@app.route('/reports')
def reports():
    if 'user' not in session: return redirect(url_for('login'))
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    stats = {}
    cur.execute("SELECT COUNT(*) FROM printers")
    stats['total'] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM printers WHERE status='Working'")
    stats['active'] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM printers WHERE status='Maintenance'")
    stats['maint'] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM printers WHERE status='Broken'")
    stats['broken'] = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM printers WHERE color_type='Color'")
    stats['color'] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM printers WHERE color_type='BW'")
    stats['bw'] = cur.fetchone()[0]
    
    cur.execute("SELECT department, COUNT(*) as count FROM printers WHERE department != '' GROUP BY department ORDER BY count DESC")
    dept_stats = cur.fetchall()
    
    cur.close()
    conn.close()
    return render_ui(REPORTS_UI, stats=stats, dept_stats=dept_stats)

@app.route('/users')
def users():
    if session.get('role') != 'admin': return redirect(url_for('index'))
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT * FROM users")
    users_list = cur.fetchall()
    cur.close()
    conn.close()
    return render_ui(USERS_UI, users=users_list)

@app.route('/add_user', methods=['POST'])
def add_user():
    if session.get('role') == 'admin':
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO users (username, password, role) VALUES (%s,%s,%s)", (request.form['username'], generate_password_hash(request.form['password']), request.form['role']))
            conn.commit()
        except Exception: pass
        cur.close()
        conn.close()
    return redirect(url_for('users'))

@app.route('/delete_user/<int:uid>')
def delete_user(uid):
    if session.get('role') == 'admin':
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE id=%s AND username!='admin'", (uid,))
        conn.commit()
        cur.close()
        conn.close()
    return redirect(url_for('users'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT * FROM users WHERE username=%s", (request.form['username'],))
        user = cur.fetchone()
        cur.close()
        conn.close()
        if user and check_password_hash(user['password'], request.form['password']):
            session.permanent = bool(request.form.get('remember'))
            session['user'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('index'))
        # ملاحظة: تركنا رسائل الفلاش بالعربي لأنها تظهر لثانية واحدة
        flash("فشل الدخول: تأكد من اسم المستخدم أو كلمة المرور", "error")
    
    L = LANGS.get(session.get('lang', 'ar'), LANGS['ar'])
    login_html = f"""
    <div class="row justify-content-center align-items-center" style="min-height: 75vh;">
        <div class="col-md-5">
            <div class="card p-5 shadow-lg border-0 rounded-4" style="background: linear-gradient(145deg, #ffffff, #f8f9fa);">
                <div class="text-center mb-4">
                    <div class="bg-primary text-white rounded-circle d-inline-flex align-items-center justify-content-center mb-3 shadow" style="width: 80px; height: 80px;">
                        <i class="fas fa-print fa-3x"></i>
                    </div>
                    <h3 class="fw-bold text-dark">{L['title']}</h3>
                    <p class="text-muted">{L['login_desc']}</p>
                </div>
                <form method="POST">
                    <div class="mb-3">
                        <label class="form-label fw-bold text-secondary">{L['username']}</label>
                        <div class="input-group shadow-sm">
                            <span class="input-group-text bg-white text-primary border-end-0"><i class="fas fa-user"></i></span>
                            <input name="username" class="form-control border-start-0" placeholder="{L['username']}" required>
                        </div>
                    </div>
                    <div class="mb-4">
                        <label class="form-label fw-bold text-secondary">{L['password']}</label>
                        <div class="input-group shadow-sm">
                            <span class="input-group-text bg-white text-primary border-end-0"><i class="fas fa-lock"></i></span>
                            <input type="password" name="password" class="form-control border-start-0" placeholder="{L['password']}" required>
                        </div>
                    </div>
                    <div class="mb-4">
                        <div class="form-check">
                            <input class="form-check-input" type="checkbox" name="remember" id="remember" checked>
                            <label class="form-check-label text-muted" for="remember">
                                {L['remember']} {L['keep_login']}
                            </label>
                        </div>
                    </div>
                    <button class="btn btn-primary w-100 py-2 fs-5 rounded-3 shadow"><i class="fas fa-sign-in-alt me-2"></i> {L['login']}</button>
                </form>
            </div>
        </div>
    </div>
    """
    return render_ui(login_html)

@app.route('/add', methods=['POST'])
def add():
    if session.get('role') in ['admin', 'entry']:
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO printers (name, serial, department, status, code, color_type, notes) VALUES (%s,%s,%s,%s,%s,%s,%s)", 
                         (request.form['name'], request.form['serial'], request.form['dept'], request.form['status'], request.form.get('code', ''), request.form.get('color_type', 'BW'), request.form.get('notes', '')))
            conn.commit()
            flash("تمت العملية بنجاح", "success")
        except:
            conn.rollback()
            flash("خطأ - تأكد من عدم تكرار الرقم التسلسلي", "error")
        cur.close()
        conn.close()
    return redirect(url_for('index'))

@app.route('/upload_csv', methods=['POST'])
def upload_csv():
    if session.get('role') not in ['admin', 'entry']: return redirect(url_for('index'))
    file = request.files.get('csv_file')
    if not file or file.filename == '':
        flash("لم يتم اختيار أي ملف", "error")
        return redirect(url_for('index'))
    if file and file.filename.endswith('.csv'):
        try:
            stream = io.StringIO(file.stream.read().decode("utf-8-sig"), newline=None)
            csv_input = csv.reader(stream)
            next(csv_input, None)
            added_count = 0
            conn = get_db_connection()
            cur = conn.cursor()
            for row in csv_input:
                if len(row) >= 6:
                    name, serial, dept, status, code, notes = [str(x).strip() for x in row[:6]]
                    if status not in ['Working', 'Maintenance', 'Broken']: status = 'Working'
                    color_type = 'BW'
                    if name and serial:
                        try:
                            cur.execute("INSERT INTO printers (name, serial, department, status, code, color_type, notes) VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (serial) DO NOTHING", (name, serial, dept, status, code, color_type, notes))
                            if cur.rowcount > 0: added_count += 1
                        except Exception as e:
                            conn.rollback()
            conn.commit()
            cur.close()
            conn.close()
            flash(f"تمت العملية! أُضيفت {added_count} طابعة بنجاح.", "success")
        except Exception as e: flash(f"حدث خطأ: {str(e)}", "error")
    else: flash("الرجاء رفع ملف بصيغة CSV فقط", "error")
    return redirect(url_for('index'))

@app.route('/export_csv')
def export_csv():
    if session.get('role') not in ['admin', 'entry']: 
        return redirect(url_for('index'))
        
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT name, serial, department, status, code, color_type, notes FROM printers ORDER BY id DESC")
    printers = cur.fetchall()
    cur.close()
    conn.close()

    si = io.StringIO()
    si.write('\ufeff')
    cw = csv.writer(si)
    
    L = LANGS.get(session.get('lang', 'ar'), LANGS['ar'])
    cw.writerow([L['name'], L['serial'], L['dept'], L['status'], L['code'], L['color_type'], L['notes']])
    
    for p in printers:
        cw.writerow([p['name'], p['serial'], p['department'], L[p['status'].lower().replace(' ', '')], p['code'], L['color'] if p['color_type'] == 'Color' else L['bw'], p['notes']])

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=printers_backup.csv"
    output.headers["Content-type"] = "text/csv; charset=utf-8"
    return output

@app.route('/edit/<int:pid>', methods=['GET', 'POST'])
def edit(pid):
    if session.get('role') not in ['admin', 'entry']: return redirect(url_for('index'))
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    if request.method == 'POST':
        try:
            cur.execute("UPDATE printers SET name=%s, serial=%s, department=%s, status=%s, code=%s, color_type=%s, notes=%s WHERE id=%s", (request.form['name'], request.form['serial'], request.form['dept'], request.form['status'], request.form.get('code', ''), request.form.get('color_type', 'BW'), request.form.get('notes', ''), pid))
            conn.commit()
            flash("تم التعديل بنجاح", "success")
        except:
            conn.rollback()
            flash("خطأ في التعديل", "error")
        cur.close()
        conn.close()
        return redirect(url_for('index'))
    cur.execute("SELECT * FROM printers WHERE id=%s", (pid,))
    printer = cur.fetchone()
    cur.close()
    conn.close()
    return render_ui(EDIT_UI, printer=printer)

@app.route('/delete/<int:pid>')
def delete(pid):
    if session.get('role') == 'admin':
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM printers WHERE id=%s", (pid,))
        conn.commit()
        cur.close()
        conn.close()
        flash("تم الحذف بنجاح", "success")
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
