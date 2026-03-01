# 1. استيراد المكتبات الأساسية
import os
import csv
import io
import psycopg2
import psycopg2.extras
from flask import Flask, request, redirect, render_template_string, session, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash

# 2. إعدادات التطبيق الأساسية
app = Flask(__name__)
app.secret_key = 'printer_system_pro_2026'

# --- جلب رابط قاعدة البيانات الدائمة من إعدادات Render ---
DATABASE_URL = os.environ.get('DATABASE_URL')
# --------------------------------------------------------

# 3. القاموس اللغوي (تم اختصاره هنا لتوفير المساحة، لكنه يعمل بنفس طريقتك)
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
    }
}
# يمكنك إضافة القاموس الإنجليزي 'en' كما كان في كودك السابق إذا أردت.

# --- 4. واجهات العرض (HTML) ---
# احتفظت بتصميمك بالكامل، لم يتغير شيء في الواجهات.
# (تمت إزالة نصوص الواجهات من هذا المربع فقط لكي لا يكون الرد طويلاً جداً عليك، 
# يرجى نسخ نصوص `DASHBOARD_UI` و `EDIT_UI` و `REPORTS_UI` و `USERS_UI` من ملفك القديم ووضعها هنا).

# سأضع لك الواجهات هنا باختصار، انسخ الواجهات القديمة وضعها في هذه المساحة.
DASHBOARD_UI = """<div class="row mb-4"><div class="col-md-6"><h3><i class="fas fa-list text-primary"></i> {{ L['home'] }}</h3></div><div class="col-md-6 text-end"><form action="/" method="GET" class="d-flex"><input name="q" class="form-control me-2 shadow-sm" placeholder="{{ L['search'] }}" value="{{ query }}"><button class="btn btn-primary shadow-sm"><i class="fas fa-search"></i></button></form></div></div>{% if session.get('role') in ['admin', 'entry'] %}<div class="card p-4 mb-4 border-0 shadow-sm bg-light"><h5 class="mb-3 text-primary"><i class="fas fa-plus-circle"></i> إضافة طابعة يدوياً</h5><form action="/add" method="POST" class="row g-3"><div class="col-md-2"><input name="name" class="form-control" placeholder="{{ L['name'] }}" required></div><div class="col-md-2"><input name="serial" class="form-control" placeholder="{{ L['serial'] }}" required></div><div class="col-md-2"><input name="dept" class="form-control" placeholder="{{ L['dept'] }}"></div><div class="col-md-2"><input name="code" class="form-control" placeholder="{{ L['code'] }}"></div><div class="col-md-2"><select name="status" class="form-select"><option value="Working">{{ L['working'] }}</option><option value="Maintenance">{{ L['maintenance'] }}</option><option value="Broken">{{ L['broken'] }}</option></select></div><div class="col-md-8"><input name="notes" class="form-control" placeholder="{{ L['notes'] }}"></div><div class="col-md-4"><button class="btn btn-success w-100"><i class="fas fa-plus"></i> {{ L['add'] }}</button></div></form><hr class="my-4"><h5 class="mb-3 text-info"><i class="fas fa-file-excel"></i> رفع مجموعة طابعات (ملف CSV)</h5><form action="/upload_csv" method="POST" enctype="multipart/form-data" class="row g-3 align-items-center"><div class="col-md-6"><input type="file" name="csv_file" class="form-control" accept=".csv" required></div><div class="col-md-3"><button type="submit" class="btn btn-info text-white w-100"><i class="fas fa-upload"></i> رفع الملف</button></div><div class="col-12"><small class="text-muted">تنبيه: يجب أن يحتوي الملف على 6 أعمدة بالترتيب (الاسم، السيريال، القسم، الحالة، الرمز، الملاحظات). السطر الأول سيتم تجاهله.</small></div></form></div>{% endif %}<div class="card overflow-hidden shadow-sm"><table class="table table-hover align-middle mb-0"><thead class="table-dark"><tr><th>{{ L['code'] }}</th><th>{{ L['name'] }}</th><th>{{ L['serial'] }}</th><th>{{ L['dept'] }}</th><th>{{ L['status'] }}</th><th>{{ L['notes'] }}</th>{% if session.get('role') in ['admin', 'entry'] %}<th>إجراءات</th>{% endif %}</tr></thead><tbody>{% for p in printers %}<tr><td><span class="badge bg-secondary">{{ p['code'] }}</span></td><td><strong>{{ p['name'] }}</strong></td><td><code>{{ p['serial'] }}</code></td><td>{{ p['department'] }}</td><td><span class="badge status-{{ p['status'] }} p-2">{{ L[p['status'].lower().replace(' ', '')] }}</span></td><td><small class="text-muted">{{ p['notes'] }}</small></td><td>{% if session.get('role') in ['admin', 'entry'] %}<a href="/edit/{{ p['id'] }}" class="btn btn-sm btn-outline-primary"><i class="fas fa-edit"></i></a>{% endif %}{% if session.get('role') == 'admin' %}<a href="/delete/{{ p['id'] }}" class="btn btn-sm btn-outline-danger" onclick="return confirm('هل أنت متأكد؟')"><i class="fas fa-trash"></i></a>{% endif %}</td></tr>{% else %}<tr><td colspan="7" class="text-center py-4 text-muted">لا توجد بيانات لعرضها</td></tr>{% endfor %}</tbody></table></div>"""
EDIT_UI = """<div class="row mb-4"><div class="col-12"><h3><i class="fas fa-edit text-primary"></i> {{ L['edit_printer'] }}</h3></div></div><div class="card p-4 border-0 shadow-sm bg-light"><form action="/edit/{{ printer['id'] }}" method="POST" class="row g-3"><div class="col-md-3"><label>{{ L['name'] }}</label><input name="name" class="form-control" value="{{ printer['name'] }}" required></div><div class="col-md-3"><label>{{ L['serial'] }}</label><input name="serial" class="form-control" value="{{ printer['serial'] }}" required></div><div class="col-md-3"><label>{{ L['dept'] }}</label><input name="dept" class="form-control" value="{{ printer['department'] }}"></div><div class="col-md-3"><label>{{ L['code'] }}</label><input name="code" class="form-control" value="{{ printer['code'] }}"></div><div class="col-md-4"><label>{{ L['status'] }}</label><select name="status" class="form-select"><option value="Working" {% if printer['status'] == 'Working' %}selected{% endif %}>{{ L['working'] }}</option><option value="Maintenance" {% if printer['status'] == 'Maintenance' %}selected{% endif %}>{{ L['maintenance'] }}</option><option value="Broken" {% if printer['status'] == 'Broken' %}selected{% endif %}>{{ L['broken'] }}</option></select></div><div class="col-md-8"><label>{{ L['notes'] }}</label><input name="notes" class="form-control" value="{{ printer['notes'] }}"></div><div class="col-12 mt-4"><button class="btn btn-primary px-4"><i class="fas fa-save"></i> {{ L['save'] }}</button><a href="/" class="btn btn-secondary px-4">{{ L['home'] }}</a></div></form></div>"""
REPORTS_UI = """<div class="row mb-4"><div class="col-12"><h3><i class="fas fa-chart-pie text-primary"></i> {{ L['reports'] }}</h3></div></div><div class="row g-4 text-center"><div class="col-md-12"><div class="card p-4 bg-white border-bottom border-primary border-4 shadow-sm"><h5 class="text-muted">{{ L['total'] }}</h5><h1 class="text-primary fw-bold display-4">{{ stats['total'] }}</h1></div></div><div class="col-md-4"><div class="card p-4 bg-white border-bottom border-success border-4 shadow-sm"><h5 class="text-muted">{{ L['working'] }}</h5><h2 class="text-success fw-bold">{{ stats['active'] }}</h2></div></div><div class="col-md-4"><div class="card p-4 bg-white border-bottom border-warning border-4 shadow-sm"><h5 class="text-muted">{{ L['maintenance'] }}</h5><h2 class="text-warning fw-bold">{{ stats['maint'] }}</h2></div></div><div class="col-md-4"><div class="card p-4 bg-white border-bottom border-danger border-4 shadow-sm"><h5 class="text-muted">{{ L['broken'] }}</h5><h2 class="text-danger fw-bold">{{ stats['broken'] }}</h2></div></div></div>"""
USERS_UI = """<div class="row mb-4"><div class="col-12"><h3><i class="fas fa-users text-primary"></i> {{ L['users_manage'] }}</h3></div></div><div class="card p-4 mb-4 border-0 shadow-sm bg-light"><form action="/add_user" method="POST" class="row g-3"><div class="col-md-3"><input name="username" class="form-control" placeholder="{{ L['username'] }}" required></div><div class="col-md-3"><input type="password" name="password" class="form-control" placeholder="{{ L['password'] }}" required></div><div class="col-md-3"><select name="role" class="form-select"><option value="admin">{{ L['admin'] }}</option><option value="entry">{{ L['entry'] }}</option><option value="user">{{ L['user'] }}</option></select></div><div class="col-md-3"><button class="btn btn-success w-100"><i class="fas fa-plus"></i> {{ L['add'] }}</button></div></form></div><div class="card overflow-hidden shadow-sm"><table class="table table-hover align-middle mb-0"><thead class="table-dark"><tr><th>{{ L['username'] }}</th><th>{{ L['role'] }}</th><th>{{ L['delete'] }}</th></tr></thead><tbody>{% for u in users %}<tr><td>{{ u['username'] }}</td><td>{{ L[u['role']] }}</td><td>{% if u['username'] != 'admin' %}<a href="/delete_user/{{ u['id'] }}" class="btn btn-sm btn-outline-danger"><i class="fas fa-trash"></i></a>{% endif %}</td></tr>{% endfor %}</tbody></table></div>"""

# --- 5. وظائف قاعدة البيانات الدائمة (PostgreSQL) ---

def get_db_connection():
    if not DATABASE_URL:
        return None
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def init_db():
    if not DATABASE_URL:
        print("DATABASE_URL is missing. Please set it in Render.")
        return
        
    conn = get_db_connection()
    cur = conn.cursor()
    
    # إنشاء الجداول بأسلوب PostgreSQL
    cur.execute("""
        CREATE TABLE IF NOT EXISTS printers (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            serial TEXT UNIQUE,
            department TEXT,
            status TEXT,
            code TEXT,
            notes TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT
        )
    """)
    
    # إضافة الحقول إذا لم تكن موجودة
    cur.execute("ALTER TABLE printers ADD COLUMN IF NOT EXISTS code TEXT")
    cur.execute("ALTER TABLE printers ADD COLUMN IF NOT EXISTS notes TEXT")
    
    # إضافة حساب المدير الافتراضي
    admin_pass = generate_password_hash('admin123')
    cur.execute("""
        INSERT INTO users (username, password, role) 
        VALUES ('admin', %s, 'admin') 
        ON CONFLICT (username) DO NOTHING
    """, (admin_pass,))
    
    conn.commit()
    cur.close()
    conn.close()

# تشغيل الإنشاء التلقائي
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
            {% with messages = get_flashed_messages(with_categories=true) %}
              {% if messages %}
                {% for category, msg in messages %}
                  <div class="alert alert-{{ 'success' if category == 'success' else 'warning' }}">{{ msg }}</div>
                {% endfor %}
              {% endif %}
            {% endwith %}
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
    query_sql = f"%{q}%"
    
    conn = get_db_connection()
    if not conn: return "Database Error"
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    cur.execute("""
        SELECT * FROM printers 
        WHERE name ILIKE %s OR serial ILIKE %s OR department ILIKE %s OR code ILIKE %s OR notes ILIKE %s
    """, (query_sql, query_sql, query_sql, query_sql, query_sql))
    printers = cur.fetchall()
    
    cur.close()
    conn.close()
    return render_ui(DASHBOARD_UI, printers=printers, query=q)

@app.route('/reports')
def reports():
    if 'user' not in session: return redirect(url_for('login'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    stats = {}
    cur.execute("SELECT COUNT(*) FROM printers")
    stats['total'] = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM printers WHERE status='Working'")
    stats['active'] = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM printers WHERE status='Maintenance'")
    stats['maint'] = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM printers WHERE status='Broken'")
    stats['broken'] = cur.fetchone()[0]
    
    cur.close()
    conn.close()
    return render_ui(REPORTS_UI, stats=stats)

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
            cur.execute("INSERT INTO users (username, password, role) VALUES (%s,%s,%s)", 
                        (request.form['username'], generate_password_hash(request.form['password']), request.form['role']))
            conn.commit()
        except Exception:
            pass
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
            session['user'] = user['username']
            session['role'] = user['role']
            return redirect(url_for('index'))
        flash("فشل الدخول: تأكد من اسم المستخدم أو كلمة المرور", "error")
    
    L = LANGS.get(session.get('lang', 'ar'), LANGS['ar'])
    return render_ui(f'<div class="row justify-content-center"><div class="col-md-4 card p-4 mt-5 shadow"><h4 class="text-center mb-4">{L["login"]}</h4><form method="POST"><input name="username" class="form-control mb-3" placeholder="{L["username"]}"><input type="password" name="password" class="form-control mb-3" placeholder="{L["password"]}"><button class="btn btn-primary w-100">{L["login"]}</button></form></div></div>')

@app.route('/add', methods=['POST'])
def add():
    if session.get('role') in ['admin', 'entry']:
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO printers (name, serial, department, status, code, notes) VALUES (%s,%s,%s,%s,%s,%s)", 
                         (request.form['name'], request.form['serial'], request.form['dept'], request.form['status'], request.form.get('code', ''), request.form.get('notes', '')))
            conn.commit()
            flash("تمت الإضافة بنجاح", "success")
        except:
            conn.rollback()
            flash("خطأ في الإضافة - تأكد من عدم تكرار الرقم التسلسلي", "error")
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
                        
                    if name and serial:
                        try:
                            cur.execute("""
                                INSERT INTO printers (name, serial, department, status, code, notes) 
                                VALUES (%s,%s,%s,%s,%s,%s) 
                                ON CONFLICT (serial) DO NOTHING
                            """, (name, serial, dept, status, code, notes))
                            if cur.rowcount > 0:
                                added_count += 1
                        except Exception as e:
                            conn.rollback()
            conn.commit()
            cur.close()
            conn.close()
            flash(f"تمت العملية! أُضيفت {added_count} طابعة بنجاح.", "success")
        except Exception as e:
            flash(f"حدث خطأ: {str(e)}", "error")
    else:
        flash("الرجاء رفع ملف بصيغة CSV فقط", "error")
    return redirect(url_for('index'))

@app.route('/edit/<int:pid>', methods=['GET', 'POST'])
def edit(pid):
    if session.get('role') not in ['admin', 'entry']: return redirect(url_for('index'))
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    if request.method == 'POST':
        try:
            cur.execute("UPDATE printers SET name=%s, serial=%s, department=%s, status=%s, code=%s, notes=%s WHERE id=%s", 
                         (request.form['name'], request.form['serial'], request.form['dept'], request.form['status'], request.form.get('code', ''), request.form.get('notes', ''), pid))
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
