# =====================================================================
# 1. استيراد المكتبات الأساسية
# =====================================================================
import os           
import csv          
import io           
import re           
import psycopg2     
import psycopg2.extras 
from datetime import timedelta 

from flask import Flask, request, redirect, render_template_string, session, url_for, flash, make_response, Response
from werkzeug.security import generate_password_hash, check_password_hash 
from flask_wtf.csrf import CSRFProtect, CSRFError 
from flask_limiter import Limiter 
from flask_limiter.util import get_remote_address 

# =====================================================================
# 2. إعدادات التطبيق الأساسية
# =====================================================================
app = Flask(__name__) 

app.secret_key = os.environ.get('SECRET_KEY', 'printer_system_pro_2026_super_secret_secured')
app.permanent_session_lifetime = timedelta(days=30) 
app.config['SESSION_COOKIE_HTTPONLY'] = True 
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax' 
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024 

csrf = CSRFProtect(app)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["1000 per day", "200 per hour"], 
    storage_uri="memory://"
)

DATABASE_URL = os.environ.get('DATABASE_URL', "postgresql://neondb_owner:npg_A4ogyrDlUT2h@ep-small-shadow-aieet5rw-pooler.c-4.us-east-1.aws.neon.tech/neondb?sslmode=require")

# =====================================================================
# 3. دوال الحماية الإضافية
# =====================================================================
@app.after_request
def add_security_headers(response):
    response.headers['X-Frame-Options'] = 'SAMEORIGIN' 
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response

@app.before_request
def verify_session_and_role():
    if request.endpoint in ['login', 'static'] or 'user' not in session:
        return
    
    conn = get_db_connection()
    if conn:
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT role FROM users WHERE username=%s", (session['user'],))
        user_in_db = cur.fetchone()
        cur.close()
        conn.close()

        if not user_in_db:
            session.clear()
            flash("تم إنهاء جلستك لأن الحساب لم يعد موجوداً.", "error")
            return redirect(url_for('login'))
        
        if user_in_db['role'] != session.get('role'):
            session['role'] = user_in_db['role']

@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    lang_code = session.get('lang', 'ar')
    if lang_code == 'ar':
        flash("انتهت صلاحية الصفحة لدواعي أمنية، يرجى المحاولة مرة أخرى.", "warning")
    else:
        flash("Session expired for security reasons, please try again.", "warning")
    return redirect(request.referrer or url_for('login'))

def log_activity(username, action, details):
    conn = get_db_connection()
    if conn:
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO activity_logs (username, action, details) VALUES (%s, %s, %s)", 
                        (username[:50], action[:50], details[:200]))
            conn.commit()
        except Exception: pass
        finally:
            cur.close()
            conn.close()

def is_strong_password(password):
    return len(password) >= 8 and re.search(r"\d", password) and re.search(r"[a-zA-Z]", password)

def sanitize_csv_field(val):
    val = str(val) if val else ""
    if val and val[0] in ('=', '+', '-', '@'):
        val = "'" + val
    return val

def sanitize_input(text, max_len=100):
    return str(text).strip()[:max_len] if text else ""

# =====================================================================
# 4. القاموس اللغوي 
# =====================================================================
LANGS = {
    'ar': {
        'title': 'نظام الطابعات', 'home': 'الرئيسية', 'reports': 'التقارير', 'users_manage': 'إدارة المستخدمين',
        'add': 'إضافة', 'edit': 'تعديل', 'delete': 'حذف', 'search': 'بحث...', 'logout_btn': 'تسجيل الخروج',
        'status': 'الحالة', 'working': 'تعمل', 'maintenance': 'صيانة', 'broken': 'لا تعمل',
        'serial': 'الرقم التسلسلي', 'dept': 'القسم', 'name': 'نوع وموديل الطابعة', 'role': 'الدور',
        'admin': 'مدير', 'entry': 'مدخل بيانات', 'user': 'مستخدم', 'save': 'حفظ التغييرات',
        'login': 'تسجيل الدخول', 'username': 'اسم المستخدم', 'password': 'كلمة المرور',
        'total': 'إجمالي الطابعات', 'depts_count': 'أقسام مسجلة',
        'code': 'الرمز', 'notes': 'ملاحظات', 'edit_printer': 'تعديل بيانات الطابعة',
        'color_type': 'نوع الطباعة', 'color': 'ملون', 'bw': 'أبيض وأسود', 'remember': 'تذكرني',
        'add_manual': 'إضافة طابعة يدوياً', 'upload_csv_title': 'رفع ملف طابعات (CSV)',
        'upload_btn': 'رفع الملف', 'actions': 'إجراءات', 'confirm_delete': 'هل أنت متأكد من الحذف؟',
        'no_data': 'لا توجد بيانات لعرضها', 'export_excel': 'تصدير (Excel)', 'dashboard_title': '(لوحة التحكم)',
        'printers_status': 'حالة الطابعات', 'print_type_chart': 'نوع الطباعة', 'dept_dist': 'توزيع الأقسام',
        'count': 'العدد', 'no_dept_data': 'لا توجد بيانات للأقسام',
        'confirm_delete_title': 'تأكيد الإجراء', 'confirm_delete_msg': 'هل أنت متأكد من حذف هذا السجل نهائياً؟', 
        'cancel': 'إلغاء', 'yes_delete': 'تأكيد الحذف', 'seq': 'ت', 
        'err_login': 'اسم المستخدم أو كلمة المرور غير صحيحة!', 'err_weak_pass': 'كلمة المرور ضعيفة (يجب أن تكون 8 أحرف وأرقام).',
        'forgot_pass': 'نسيت كلمة المرور؟', 'contact_admin': 'يرجى مراجعة مسؤول النظام (Admin) لإعادة تعيين كلمة المرور.',
        'edit_pass': 'تغيير الرمز', 'new_pass': 'كلمة المرور الجديدة', 'pass_changed': 'تم تغيير كلمة المرور بنجاح!',
        'admin_notice': 'إشعار النظام', 'edit_role': 'تعديل الصلاحية', 'new_role': 'الصلاحية', 'role_changed': 'تم التعديل بنجاح!',
        'audit_logs': 'سجل النظام', 'next': 'التالي', 'prev': 'السابق', 'page': 'صفحة',
        'login_box_title': 'تسجيل الدخول',
        'login_btn': 'دخول', 'footer_text': 'نظام الطابعات الإصدار 2.0 © 2026', 'ok_btn': 'حسناً'
    },
    'en': {
        'title': 'Printers System', 'home': 'Dashboard', 'reports': 'Reports', 'users_manage': 'Users',
        'add': 'Add', 'edit': 'Edit', 'delete': 'Delete', 'search': 'Search...', 'logout_btn': 'Logout',
        'status': 'Status', 'working': 'Working', 'maintenance': 'Maintenance', 'broken': 'Broken',
        'serial': 'Serial Number', 'dept': 'Department', 'name': 'Printer Model', 'role': 'Role',
        'admin': 'Admin', 'entry': 'Data Entry', 'user': 'User', 'save': 'Save Changes',
        'login': 'Login', 'username': 'Username', 'password': 'Password',
        'total': 'Total', 'depts_count': 'Departments',
        'code': 'Code', 'notes': 'Notes', 'edit_printer': 'Edit Printer',
        'color_type': 'Type', 'color': 'Color', 'bw': 'B&W', 'remember': 'Remember Me',
        'add_manual': 'Add Manually', 'upload_csv_title': 'Upload CSV',
        'upload_btn': 'Upload', 'actions': 'Actions', 'confirm_delete': 'Confirm Deletion?',
        'no_data': 'No data found', 'export_excel': 'Export Excel', 'dashboard_title': '',
        'printers_status': 'Status Overview', 'print_type_chart': 'Print Type', 'dept_dist': 'Departments',
        'count': 'Count', 'no_dept_data': 'No data', 
        'confirm_delete_title': 'Confirm Action', 'confirm_delete_msg': 'Are you sure you want to permanently delete this record?', 
        'cancel': 'Cancel', 'yes_delete': 'Confirm', 'seq': '#', 
        'err_login': 'Invalid credentials!', 'err_weak_pass': 'Password must be 8+ chars with letters & numbers.',
        'forgot_pass': 'Forgot Password?', 'contact_admin': 'Please contact the IT Admin to reset your password.',
        'edit_pass': 'Reset Pass', 'new_pass': 'New Password', 'pass_changed': 'Password updated!',
        'admin_notice': 'System Notice', 'edit_role': 'Change Role', 'new_role': 'Role', 'role_changed': 'Role updated!',
        'audit_logs': 'Audit Logs', 'next': 'Next', 'prev': 'Prev', 'page': 'Page',
        'login_box_title': 'Login',
        'login_btn': 'Login', 'footer_text': 'Printers System v2.0 © 2026', 'ok_btn': 'OK'
    }
}

# =====================================================================
# 5. واجهات العرض (HTML) 
# =====================================================================
DASHBOARD_UI = """
<div class="d-flex justify-content-between align-items-center mb-3">
    <h4 class="fw-bold m-0" style="color: #1e3a8a;"><i class="fas fa-desktop me-2"></i> {{ L['home'] }}</h4>
    <form action="/" method="GET" class="d-flex gap-2 align-items-center" autocomplete="off">
        <div class="input-group input-group-sm border rounded" style="width: 350px; border-color: #1e3a8a !important;">
            <span class="input-group-text bg-white text-primary border-0"><i class="fas fa-search"></i></span>
            <input name="q" class="form-control border-0 shadow-none" placeholder="{{ L['search'] }}" value="{{ query }}" maxlength="50" autocomplete="off">
        </div>
        <button class="btn btn-sm text-white px-3 fw-bold" style="background-color: #1e3a8a;">{{ L['search'] }}</button>
        {% if session.get('role') in ['admin', 'entry'] %}
        <a href="/export_csv" class="btn btn-sm btn-success px-3 fw-bold"><i class="fas fa-file-excel me-1"></i> {{ L['export_excel'] }}</a>
        {% endif %}
    </form>
</div>

{% if session.get('role') in ['admin', 'entry'] %}
<div class="row gx-3 mb-3 flex-shrink-0">
    <div class="col-8">
        <div class="card border-0 shadow-sm h-100 rounded-1">
            <div class="card-header bg-white border-bottom-0 pt-3 pb-1 px-3">
                <h6 class="fw-bold mb-0" style="color: #1e3a8a;"><i class="fas fa-plus-square me-1"></i> {{ L['add_manual'] }}</h6>
            </div>
            <div class="card-body p-3">
                <form action="/add" method="POST" class="row g-2" autocomplete="off">
                    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
                    <div class="col-4"><input name="name" class="form-control form-control-sm bg-light" placeholder="{{ L['name'] }}" required maxlength="100" autocomplete="off"></div>
                    <div class="col-4"><input name="serial" class="form-control form-control-sm bg-light" placeholder="{{ L['serial'] }}" required maxlength="50" autocomplete="off"></div>
                    <div class="col-4"><input name="dept" class="form-control form-control-sm bg-light" placeholder="{{ L['dept'] }}" maxlength="100" autocomplete="off"></div>
                    
                    <div class="col-3"><input name="code" class="form-control form-control-sm bg-light" placeholder="{{ L['code'] }}" maxlength="50" autocomplete="off"></div>
                    <div class="col-3">
                        <select name="status" class="form-select form-select-sm bg-light">
                            <option value="Working">{{ L['working'] }}</option>
                            <option value="Maintenance">{{ L['maintenance'] }}</option>
                            <option value="Broken">{{ L['broken'] }}</option>
                        </select>
                    </div>
                    <div class="col-3">
                        <select name="color_type" class="form-select form-select-sm bg-light">
                            <option value="BW">{{ L['bw'] }}</option>
                            <option value="Color">{{ L['color'] }}</option>
                        </select>
                    </div>
                    <div class="col-3"><button class="btn btn-sm w-100 h-100 fw-bold text-white" style="background-color: #1e3a8a;">{{ L['add'] }}</button></div>
                    <div class="col-12"><input name="notes" class="form-control form-control-sm bg-light" placeholder="{{ L['notes'] }}" maxlength="250" autocomplete="off"></div>
                </form>
            </div>
        </div>
    </div>
    <div class="col-4">
        <div class="card border-0 shadow-sm h-100 rounded-1" style="background-color: #f1f5f9; border-left: 4px solid #1e3a8a !important;">
            <div class="card-body p-3 d-flex flex-column justify-content-center">
                <h6 class="fw-bold mb-3" style="color: #1e3a8a;"><i class="fas fa-file-csv me-1"></i> {{ L['upload_csv_title'] }}</h6>
                <form action="/upload_csv" method="POST" enctype="multipart/form-data">
                    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
                    <input type="file" name="csv_file" class="form-control form-control-sm mb-2 bg-white" accept=".csv" required>
                    <button type="submit" class="btn btn-sm w-100 fw-bold text-white" style="background-color: #3b82f6;"><i class="fas fa-upload me-1"></i> {{ L['upload_btn'] }}</button>
                </form>
            </div>
        </div>
    </div>
</div>
{% endif %}

<div class="card shadow-sm border-0 rounded-1 flex-grow-1 overflow-hidden d-flex flex-column">
    <div class="table-responsive flex-grow-1 custom-scrollbar">
        <table class="table table-hover table-striped align-middle mb-0" style="font-size: 0.85rem;">
            <thead class="table-dark" style="position: sticky; top: 0; z-index: 10;">
                <tr>
                    <th style="width: 5%; background-color: #1e3a8a;">{{ L['seq'] }}</th>
                    <th style="width: 10%; background-color: #1e3a8a;">{{ L['code'] }}</th>
                    <th style="width: 15%; background-color: #1e3a8a;">{{ L['name'] }}</th>
                    <th style="width: 15%; background-color: #1e3a8a;">{{ L['serial'] }}</th>
                    <th style="width: 20%; background-color: #1e3a8a;">{{ L['dept'] }}</th>
                    <th style="width: 10%; background-color: #1e3a8a;">{{ L['status'] }}</th>
                    <th style="width: 10%; background-color: #1e3a8a;">{{ L['color_type'] }}</th>
                    <th style="width: 10%; background-color: #1e3a8a;">{{ L['notes'] }}</th>
                    {% if session.get('role') in ['admin', 'entry'] %}<th style="width: 5%; background-color: #1e3a8a;">{{ L['actions'] }}</th>{% endif %}
                </tr>
            </thead>
            <tbody>
                {% for p in printers %}
                <tr>
                    <td class="text-center fw-bold text-muted">{{ loop.index + ((page - 1) * per_page) }}</td>
                    <td><span class="badge bg-secondary px-2 rounded-1">{{ p['code'] }}</span></td>
                    <td class="fw-bold text-dark">{{ p['name'] }}</td>
                    <td><span class="text-primary fw-bold" style="font-family: monospace;">{{ p['serial'] }}</span></td>
                    <td>{{ p['department'] }}</td>
                    <td><span class="badge status-{{ p['status'] }} px-2 py-1 rounded-1 w-100">{{ L[p['status'].lower().replace(' ', '')] }}</span></td>
                    <td><small class="fw-bold"><i class="fas {% if p['color_type'] == 'Color' %}fa-palette text-primary{% else %}fa-print text-secondary{% endif %} me-1"></i>{{ L['color'] if p['color_type'] == 'Color' else L['bw'] }}</small></td>
                    <td><small class="text-muted text-truncate d-inline-block" style="max-width: 150px;" title="{{ p['notes'] }}">{{ p['notes'] }}</small></td>
                    <td>
                        <div class="d-flex gap-1">
                        {% if session.get('role') in ['admin', 'entry'] %}
                        <a href="/edit/{{ p['id'] }}" class="btn btn-sm btn-light border py-0 px-2 text-primary" title="تعديل"><i class="fas fa-edit"></i></a>
                        {% endif %}
                        {% if session.get('role') == 'admin' %}
                        <button type="button" class="btn btn-sm btn-light border py-0 px-2 text-danger" title="حذف" onclick="showDeleteModal({{ p['id'] }})"><i class="fas fa-trash"></i></button>
                        {% endif %}
                        </div>
                    </td>
                </tr>
                {% else %}
                <tr><td colspan="9" class="text-center py-5 text-muted"><i class="fas fa-database fa-3x mb-3 text-light"></i><h6 class="fw-bold">{{ L['no_data'] }}</h6></td></tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    
    <div class="card-footer bg-white border-top p-2 d-flex justify-content-between align-items-center flex-shrink-0">
        {% if page > 1 %}
        <a href="/?q={{ query }}&page={{ page - 1 }}" class="btn btn-sm btn-outline-secondary fw-bold px-3"><i class="fas fa-chevron-right me-1"></i> {{ L['prev'] }}</a>
        {% else %}
        <button class="btn btn-sm btn-light text-muted fw-bold px-3 border" disabled><i class="fas fa-chevron-right me-1"></i> {{ L['prev'] }}</button>
        {% endif %}
        <span class="fw-bold text-muted small">{{ L['page'] }} <span class="badge text-white px-2 rounded-1" style="background-color: #1e3a8a;">{{ page }}</span></span>
        <a href="/?q={{ query }}&page={{ page + 1 }}" class="btn btn-sm btn-outline-secondary fw-bold px-3">{{ L['next'] }} <i class="fas fa-chevron-left ms-1"></i></a>
    </div>
</div>

<div class="modal fade" id="deleteModal" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered modal-sm">
    <div class="modal-content border-0 shadow rounded-2">
      <div class="modal-header bg-danger text-white border-0 py-2 rounded-top-2">
        <h6 class="modal-title fw-bold"><i class="fas fa-exclamation-triangle me-2"></i>{{ L['confirm_delete_title'] }}</h6>
        <button type="button" class="btn-close btn-close-white btn-sm" data-bs-dismiss="modal"></button>
      </div>
      <form id="deleteForm" method="POST" action="">
          <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
          <div class="modal-body text-center py-4">
            <p class="mb-0 text-dark fw-bold">{{ L['confirm_delete_msg'] }}</p>
          </div>
          <div class="modal-footer border-0 justify-content-center bg-light py-2 rounded-bottom-2">
            <button type="button" class="btn btn-sm btn-secondary px-4 fw-bold" data-bs-dismiss="modal">{{ L['cancel'] }}</button>
            <button type="submit" class="btn btn-sm btn-danger px-4 fw-bold">{{ L['yes_delete'] }}</button>
          </div>
      </form>
    </div>
  </div>
</div>
<script>function showDeleteModal(printerId) { document.getElementById('deleteForm').action = '/delete/' + printerId; var myModal = new bootstrap.Modal(document.getElementById('deleteModal')); myModal.show(); }</script>
"""

EDIT_UI = """<div class="d-flex flex-column h-100"><div class="row mb-3"><div class="col-12"><h4 class="fw-bold" style="color: #1e3a8a;"><i class="fas fa-edit me-2"></i> {{ L['edit_printer'] }}</h4></div></div><div class="card p-4 border-0 shadow-sm bg-white rounded-1"><form action="/edit/{{ printer['id'] }}" method="POST" class="row g-3" autocomplete="off"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/><div class="col-md-4"><label class="fw-bold small text-muted mb-1">{{ L['name'] }}</label><input name="name" class="form-control" value="{{ printer['name'] }}" required maxlength="100" autocomplete="off"></div><div class="col-md-3"><label class="fw-bold small text-muted mb-1">{{ L['serial'] }}</label><input name="serial" class="form-control" value="{{ printer['serial'] }}" required maxlength="50" autocomplete="off"></div><div class="col-md-3"><label class="fw-bold small text-muted mb-1">{{ L['dept'] }}</label><input name="dept" class="form-control" value="{{ printer['department'] }}" maxlength="100" autocomplete="off"></div><div class="col-md-2"><label class="fw-bold small text-muted mb-1">{{ L['code'] }}</label><input name="code" class="form-control" value="{{ printer['code'] }}" maxlength="50" autocomplete="off"></div><div class="col-md-3"><label class="fw-bold small text-muted mb-1">{{ L['status'] }}</label><select name="status" class="form-select"><option value="Working" {% if printer['status'] == 'Working' %}selected{% endif %}>{{ L['working'] }}</option><option value="Maintenance" {% if printer['status'] == 'Maintenance' %}selected{% endif %}>{{ L['maintenance'] }}</option><option value="Broken" {% if printer['status'] == 'Broken' %}selected{% endif %}>{{ L['broken'] }}</option></select></div><div class="col-md-3"><label class="fw-bold small text-muted mb-1">{{ L['color_type'] }}</label><select name="color_type" class="form-select"><option value="BW" {% if printer['color_type'] == 'BW' %}selected{% endif %}>{{ L['bw'] }}</option><option value="Color" {% if printer['color_type'] == 'Color' %}selected{% endif %}>{{ L['color'] }}</option></select></div><div class="col-md-6"><label class="fw-bold small text-muted mb-1">{{ L['notes'] }}</label><input name="notes" class="form-control" value="{{ printer['notes'] }}" maxlength="250" autocomplete="off"></div><div class="col-12 mt-4 pt-3 border-top text-end"><a href="/" class="btn btn-light border px-4 fw-bold ms-2">{{ L['cancel'] }}</a><button class="btn px-4 fw-bold text-white" style="background-color: #1e3a8a;"><i class="fas fa-save me-1"></i> {{ L['save'] }}</button></div></form></div></div>"""

REPORTS_UI = """
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
    .stat-card { transition: transform 0.2s ease, box-shadow 0.2s ease; border-radius: 12px; border: 1px solid #e2e8f0; }
    .stat-card:hover { transform: translateY(-4px); box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05) !important; }
    .stat-icon-wrap { width: 64px; height: 64px; display: flex; align-items: center; justify-content: center; border-radius: 16px; }
</style>

<div class="d-flex flex-column h-100 pe-2">
    <div class="row mb-4">
        <div class="col-12">
            <h4 class="fw-bolder m-0" style="color: #1e3a8a;"><i class="fas fa-chart-line me-2"></i> {{ L['reports'] }}</h4>
            <p class="text-muted small mt-1 mb-0">نظرة عامة تحليلية ومؤشرات الأداء</p>
        </div>
    </div>
    
    <div class="row g-4 mb-4 flex-shrink-0">
        <div class="col-xl-3 col-md-6">
            <div class="card stat-card bg-white h-100 border-0 shadow-sm" style="border-bottom: 4px solid #3b82f6 !important;">
                <div class="card-body p-4 d-flex align-items-center justify-content-between">
                    <div>
                        <h6 class="text-muted fw-bold mb-1">{{ L['total'] }}</h6>
                        <h2 class="fw-black mb-0 text-dark" style="font-size: 2.5rem; letter-spacing: -1px;">{{ stats['total'] }}</h2>
                    </div>
                    <div class="stat-icon-wrap bg-primary bg-opacity-10 text-primary">
                        <i class="fas fa-print fa-2x"></i>
                    </div>
                </div>
            </div>
        </div>
        <div class="col-xl-3 col-md-6">
            <div class="card stat-card bg-white h-100 border-0 shadow-sm" style="border-bottom: 4px solid #10b981 !important;">
                <div class="card-body p-4 d-flex align-items-center justify-content-between">
                    <div>
                        <h6 class="text-muted fw-bold mb-1">{{ L['working'] }}</h6>
                        <h2 class="fw-black mb-0 text-dark" style="font-size: 2.5rem; letter-spacing: -1px;">{{ stats['active'] }}</h2>
                    </div>
                    <div class="stat-icon-wrap bg-success bg-opacity-10 text-success">
                        <i class="fas fa-check-circle fa-2x"></i>
                    </div>
                </div>
            </div>
        </div>
        <div class="col-xl-3 col-md-6">
            <div class="card stat-card bg-white h-100 border-0 shadow-sm" style="border-bottom: 4px solid #f59e0b !important;">
                <div class="card-body p-4 d-flex align-items-center justify-content-between">
                    <div>
                        <h6 class="text-muted fw-bold mb-1">{{ L['maintenance'] }}</h6>
                        <h2 class="fw-black mb-0 text-dark" style="font-size: 2.5rem; letter-spacing: -1px;">{{ stats['maint'] }}</h2>
                    </div>
                    <div class="stat-icon-wrap bg-warning bg-opacity-10 text-warning">
                        <i class="fas fa-tools fa-2x"></i>
                    </div>
                </div>
            </div>
        </div>
        <div class="col-xl-3 col-md-6">
            <div class="card stat-card bg-white h-100 border-0 shadow-sm" style="border-bottom: 4px solid #ef4444 !important;">
                <div class="card-body p-4 d-flex align-items-center justify-content-between">
                    <div>
                        <h6 class="text-muted fw-bold mb-1">{{ L['broken'] }}</h6>
                        <h2 class="fw-black mb-0 text-dark" style="font-size: 2.5rem; letter-spacing: -1px;">{{ stats['broken'] }}</h2>
                    </div>
                    <div class="stat-icon-wrap bg-danger bg-opacity-10 text-danger">
                        <i class="fas fa-times-circle fa-2x"></i>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <div class="row g-4 flex-grow-1 pb-3">
        <div class="col-lg-4 d-flex flex-column">
            <div class="card border-0 shadow-sm rounded-4 flex-grow-1 d-flex flex-column h-100">
                <div class="card-header bg-white border-0 pt-4 pb-0 px-4">
                    <h6 class="fw-bold mb-0 text-dark"><i class="fas fa-chart-pie me-2 text-primary"></i> {{ L['printers_status'] }}</h6>
                </div>
                <div class="card-body p-4 d-flex justify-content-center align-items-center flex-grow-1">
                    <div style="height: 100%; width: 100%; min-height: 250px; max-height: 300px; position: relative;">
                        <canvas id="statusChart"></canvas>
                    </div>
                </div>
            </div>
        </div>
        <div class="col-lg-4 d-flex flex-column">
            <div class="card border-0 shadow-sm rounded-4 flex-grow-1 d-flex flex-column h-100">
                <div class="card-header bg-white border-0 pt-4 pb-0 px-4">
                    <h6 class="fw-bold mb-0 text-dark"><i class="fas fa-palette me-2 text-primary"></i> {{ L['print_type_chart'] }}</h6>
                </div>
                <div class="card-body p-4 d-flex justify-content-center align-items-center flex-grow-1">
                    <div style="height: 100%; width: 100%; min-height: 250px; max-height: 300px; position: relative;">
                        <canvas id="typeChart"></canvas>
                    </div>
                </div>
            </div>
        </div>
        <div class="col-lg-4 d-flex flex-column">
            <div class="card border-0 shadow-sm rounded-4 flex-grow-1 d-flex flex-column overflow-hidden h-100">
                <div class="card-header bg-white border-bottom pt-4 pb-3 px-4 shadow-sm" style="z-index: 2;">
                    <h6 class="fw-bold mb-0 text-dark"><i class="fas fa-building me-2 text-primary"></i> {{ L['dept_dist'] }}</h6>
                </div>
                <div class="card-body p-0 flex-grow-1 custom-scrollbar overflow-auto" style="height: 0; min-height: 250px;">
                    <table class="table table-hover align-middle mb-0 text-center" style="font-size: 0.9rem;">
                        <thead class="table-light" style="position: sticky; top: 0; z-index: 1;">
                            <tr>
                                <th class="text-start px-4 py-3 text-muted fw-bold border-bottom-0">{{ L['dept'] }}</th>
                                <th class="py-3 text-muted fw-bold border-bottom-0" style="width: 100px;">{{ L['count'] }}</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for dept in dept_stats %}
                            <tr>
                                <td class="text-start px-4 fw-bold text-dark border-light">{{ dept['department'] }}</td>
                                <td class="border-light"><span class="badge bg-primary bg-opacity-10 text-primary rounded-pill px-3 py-2 fw-bold shadow-sm">{{ dept['count'] }}</span></td>
                            </tr>
                            {% else %}
                            <tr><td colspan="2" class="text-muted py-5 border-0">{{ L['no_dept_data'] }}</td></tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
document.addEventListener("DOMContentLoaded", function() { 
    Chart.defaults.font.family = 'Tajawal';
    Chart.defaults.color = '#64748b';
    Chart.defaults.font.size = 13;
    
    const commonOptions = {
        responsive: true, 
        maintainAspectRatio: false, 
        cutout: '75%',
        layout: { padding: 10 },
        plugins: { 
            legend: { position: 'bottom', labels: { padding: 20, usePointStyle: true, pointStyle: 'circle' } },
            tooltip: { backgroundColor: 'rgba(15, 23, 42, 0.9)', padding: 12, cornerRadius: 8, titleFont: { size: 14 }, bodyFont: { size: 14 } }
        }
    };
    
    new Chart(document.getElementById('statusChart'), { 
        type: 'doughnut', 
        data: { 
            labels: ['{{ L["working"] }}', '{{ L["maintenance"] }}', '{{ L["broken"] }}'], 
            datasets: [{ 
                data: [{{ stats['active'] }}, {{ stats['maint'] }}, {{ stats['broken'] }}], 
                backgroundColor: ['#10b981', '#f59e0b', '#ef4444'], 
                borderWidth: 0, hoverOffset: 8, borderRadius: 5
            }] 
        }, 
        options: commonOptions 
    }); 
    
    new Chart(document.getElementById('typeChart'), { 
        type: 'doughnut', 
        data: { 
            labels: ['{{ L["color"] }}', '{{ L["bw"] }}'], 
            datasets: [{ 
                data: [{{ stats['color'] }}, {{ stats['bw'] }}], 
                backgroundColor: ['#3b82f6', '#94a3b8'], 
                borderWidth: 0, hoverOffset: 8, borderRadius: 5
            }] 
        }, 
        options: commonOptions 
    }); 
});
</script>
"""

# ---------------------------------------------------------------------
# التعديل الجديد: واجهة إدارة المستخدمين الاحترافية (Modern Users UI)
# ---------------------------------------------------------------------
USERS_UI = """
<style>
    /* تصميم أزرار الإجراءات الاحترافية */
    .action-btn { width: 34px; height: 34px; display: inline-flex; align-items: center; justify-content: center; border-radius: 8px; transition: all 0.2s ease; border: none; text-decoration: none; cursor: pointer;}
    .action-btn:hover { transform: translateY(-2px); box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06); }
    .btn-edit-pass { background-color: rgba(59, 130, 246, 0.1); color: #3b82f6; }
    .btn-edit-pass:hover { background-color: #3b82f6; color: white; }
    .btn-edit-role { background-color: rgba(245, 158, 11, 0.1); color: #f59e0b; }
    .btn-edit-role:hover { background-color: #f59e0b; color: white; }
    .btn-delete-user { background-color: rgba(239, 68, 68, 0.1); color: #ef4444; }
    .btn-delete-user:hover { background-color: #ef4444; color: white; }
</style>

<div class="d-flex flex-column h-100">
    <div class="row mb-4 align-items-center">
        <div class="col-md-8">
            <h4 class="fw-bolder m-0" style="color: #1e3a8a;"><i class="fas fa-users-cog me-2"></i> {{ L['users_manage'] }}</h4>
            <p class="text-muted small mt-1 mb-0">إدارة الصلاحيات وحسابات موظفي النظام</p>
        </div>
        <div class="col-md-4 text-end">
            <a href="/audit" class="btn btn-light bg-white border-0 shadow-sm fw-bold rounded-pill px-4 text-primary">
                <i class="fas fa-clipboard-list me-2"></i> {{ L['audit_logs'] }}
            </a>
        </div>
    </div>

    <div class="card border-0 shadow-sm rounded-4 mb-4 flex-shrink-0">
        <div class="card-header bg-white border-bottom-0 pt-4 pb-2 px-4">
            <h6 class="fw-bold mb-0 text-dark"><i class="fas fa-user-plus me-2 text-primary"></i> إضافة مستخدم جديد</h6>
        </div>
        <div class="card-body px-4 pb-4 pt-2">
            <form action="/add_user" method="POST" class="row g-3 align-items-end" autocomplete="off">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
                <div class="col-md-3">
                    <label class="small fw-bold text-muted mb-1">{{ L['username'] }}</label>
                    <div class="input-group">
                        <span class="input-group-text bg-light border-end-0 text-muted"><i class="fas fa-user"></i></span>
                        <input name="username" class="form-control border-start-0 bg-light" required autocomplete="off" maxlength="30">
                    </div>
                </div>
                <div class="col-md-3">
                    <label class="small fw-bold text-muted mb-1">{{ L['password'] }}</label>
                    <div class="input-group">
                        <span class="input-group-text bg-light border-end-0 text-muted"><i class="fas fa-lock"></i></span>
                        <input type="password" name="password" class="form-control border-start-0 bg-light" required autocomplete="new-password" maxlength="50">
                    </div>
                </div>
                <div class="col-md-3">
                    <label class="small fw-bold text-muted mb-1">{{ L['role'] }}</label>
                    <div class="input-group">
                        <span class="input-group-text bg-light border-end-0 text-muted"><i class="fas fa-user-shield"></i></span>
                        <select name="role" class="form-select border-start-0 bg-light">
                            <option value="admin">{{ L['admin'] }}</option>
                            <option value="entry">{{ L['entry'] }}</option>
                            <option value="user">{{ L['user'] }}</option>
                        </select>
                    </div>
                </div>
                <div class="col-md-3">
                    <button class="btn text-white w-100 fw-bold rounded-3 shadow-sm" style="background-color: #1e3a8a; height: 38px;">
                        {{ L['add'] }}
                    </button>
                </div>
            </form>
        </div>
    </div>

    <div class="card shadow-sm border-0 rounded-4 flex-grow-1 overflow-hidden d-flex flex-column">
        <div class="table-responsive flex-grow-1 custom-scrollbar">
            <table class="table table-hover align-middle mb-0">
                <thead class="table-light" style="position: sticky; top: 0; z-index: 10;">
                    <tr>
                        <th class="px-4 py-3 text-muted fw-bold border-bottom-0">{{ L['username'] }}</th>
                        <th class="py-3 text-muted fw-bold border-bottom-0">{{ L['role'] }}</th>
                        <th class="py-3 text-center text-muted fw-bold border-bottom-0" style="width: 180px;">{{ L['actions'] }}</th>
                    </tr>
                </thead>
                <tbody>
                    {% for u in users %}
                    <tr>
                        <td class="fw-bold px-4 text-dark py-3 border-light">
                            <div class="d-flex align-items-center">
                                <div class="bg-primary bg-opacity-10 text-primary rounded-circle d-flex align-items-center justify-content-center me-3" style="width: 35px; height: 35px;">
                                    <i class="fas fa-user"></i>
                                </div>
                                <span>{{ u['username'] }}</span>
                            </div>
                        </td>
                        <td class="border-light">
                            {% set role_color = 'danger' if u['role'] == 'admin' else ('success' if u['role'] == 'entry' else 'secondary') %}
                            <span class="badge bg-{{ role_color }} bg-opacity-10 text-{{ role_color }} px-3 py-2 rounded-pill fw-bold border border-{{ role_color }} border-opacity-25">
                                <i class="fas {% if u['role'] == 'admin' %}fa-crown{% elif u['role'] == 'entry' %}fa-keyboard{% else %}fa-user{% endif %} me-1"></i> {{ L[u['role']] }}
                            </span>
                        </td>
                        <td class="text-center border-light">
                            <div class="d-flex justify-content-center gap-2">
                                <button type="button" class="action-btn btn-edit-pass" onclick="showEditPassModal({{ u['id'] }}, '{{ u['username'] }}')" title="{{ L['edit_pass'] }}">
                                    <i class="fas fa-key"></i>
                                </button>
                                {% if u['username'] != 'admin' %}
                                <button type="button" class="action-btn btn-edit-role" onclick="showEditRoleModal({{ u['id'] }}, '{{ u['username'] }}', '{{ u['role'] }}')" title="{{ L['edit_role'] }}">
                                    <i class="fas fa-user-tag"></i>
                                </button>
                                <button type="button" class="action-btn btn-delete-user" onclick="showDeleteUserModal({{ u['id'] }})" title="{{ L['delete'] }}">
                                    <i class="fas fa-trash-alt"></i>
                                </button>
                                {% endif %}
                            </div>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</div>

<div class="modal fade" id="deleteUserModal" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered modal-sm">
    <div class="modal-content border-0 shadow rounded-4">
      <div class="modal-header border-0 pb-0 justify-content-center mt-3">
        <div class="bg-danger bg-opacity-10 text-danger rounded-circle d-flex align-items-center justify-content-center" style="width: 60px; height: 60px;">
            <i class="fas fa-exclamation-triangle fa-2x"></i>
        </div>
      </div>
      <form id="deleteUserForm" method="POST" action="">
          <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
          <div class="modal-body text-center py-4">
            <h6 class="fw-bold text-dark mb-2">{{ L['confirm_delete_title'] }}</h6>
            <p class="mb-0 text-muted small">هل أنت متأكد من حذف هذا الحساب نهائياً؟ لا يمكن التراجع عن هذا الإجراء.</p>
          </div>
          <div class="modal-footer border-0 justify-content-center bg-light py-3 rounded-bottom-4">
            <button type="button" class="btn btn-light shadow-sm px-4 fw-bold text-muted border" data-bs-dismiss="modal">{{ L['cancel'] }}</button>
            <button type="submit" class="btn btn-danger shadow-sm px-4 fw-bold">{{ L['yes_delete'] }}</button>
          </div>
      </form>
    </div>
  </div>
</div>

<div class="modal fade" id="editPassModal" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered modal-sm">
    <div class="modal-content border-0 shadow rounded-4">
      <div class="modal-header border-0 pb-0 justify-content-center mt-3">
        <div class="bg-primary bg-opacity-10 text-primary rounded-circle d-flex align-items-center justify-content-center" style="width: 60px; height: 60px;">
            <i class="fas fa-key fa-2x"></i>
        </div>
      </div>
      <form action="/edit_user_password" method="POST" autocomplete="off">
          <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
          <div class="modal-body py-3 px-4">
            <input type="hidden" name="user_id" id="editPassUserId">
            <div class="text-center mb-3">
                <h6 class="fw-bold text-dark mb-0">{{ L['edit_pass'] }}</h6>
                <small class="text-primary fw-bold" id="editPassUsername"></small>
            </div>
            <div>
                <label class="form-label fw-bold small text-muted">{{ L['new_pass'] }}</label>
                <input type="password" name="new_password" class="form-control bg-light" required autocomplete="new-password" maxlength="50">
            </div>
          </div>
          <div class="modal-footer border-0 justify-content-center bg-light py-3 rounded-bottom-4">
            <button type="button" class="btn btn-light shadow-sm px-3 fw-bold text-muted border" data-bs-dismiss="modal">{{ L['cancel'] }}</button>
            <button type="submit" class="btn text-white shadow-sm px-4 fw-bold" style="background-color: #1e3a8a;">{{ L['save'] }}</button>
          </div>
      </form>
    </div>
  </div>
</div>

<div class="modal fade" id="editRoleModal" tabindex="-1" aria-hidden="true">
  <div class="modal-dialog modal-dialog-centered modal-sm">
    <div class="modal-content border-0 shadow rounded-4">
      <div class="modal-header border-0 pb-0 justify-content-center mt-3">
        <div class="bg-warning bg-opacity-10 text-warning rounded-circle d-flex align-items-center justify-content-center" style="width: 60px; height: 60px;">
            <i class="fas fa-user-shield fa-2x"></i>
        </div>
      </div>
      <form action="/edit_user_role" method="POST">
          <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
          <div class="modal-body py-3 px-4">
            <input type="hidden" name="user_id" id="editRoleUserId">
            <div class="text-center mb-3">
                <h6 class="fw-bold text-dark mb-0">{{ L['edit_role'] }}</h6>
                <small class="text-warning fw-bold" id="editRoleUsername"></small>
            </div>
            <div>
                <label class="form-label fw-bold small text-muted">{{ L['new_role'] }}</label>
                <select name="new_role" id="editRoleSelect" class="form-select bg-light">
                    <option value="admin">{{ L['admin'] }}</option>
                    <option value="entry">{{ L['entry'] }}</option>
                    <option value="user">{{ L['user'] }}</option>
                </select>
            </div>
          </div>
          <div class="modal-footer border-0 justify-content-center bg-light py-3 rounded-bottom-4">
            <button type="button" class="btn btn-light shadow-sm px-3 fw-bold text-muted border" data-bs-dismiss="modal">{{ L['cancel'] }}</button>
            <button type="submit" class="btn btn-warning text-dark shadow-sm px-4 fw-bold">{{ L['save'] }}</button>
          </div>
      </form>
    </div>
  </div>
</div>

<script>
function showDeleteUserModal(userId) { 
    document.getElementById('deleteUserForm').action = '/delete_user/' + userId; 
    var myModal = new bootstrap.Modal(document.getElementById('deleteUserModal')); 
    myModal.show(); 
} 
function showEditPassModal(userId, username) { 
    document.getElementById('editPassUserId').value = userId; 
    document.getElementById('editPassUsername').innerText = '@' + username; 
    var myModal = new bootstrap.Modal(document.getElementById('editPassModal')); 
    myModal.show(); 
} 
function showEditRoleModal(userId, username, currentRole) { 
    document.getElementById('editRoleUserId').value = userId; 
    document.getElementById('editRoleUsername').innerText = '@' + username; 
    document.getElementById('editRoleSelect').value = currentRole; 
    var myModal = new bootstrap.Modal(document.getElementById('editRoleModal')); 
    myModal.show(); 
}
</script>
"""

AUDIT_UI = """<div class="d-flex flex-column h-100"><div class="row mb-3"><div class="col-12"><h4 class="fw-bold" style="color: #1e3a8a;"><i class="fas fa-clipboard-check me-2"></i> {{ L['audit_logs'] }}</h4></div></div><div class="card shadow-sm border-0 rounded-1 flex-grow-1 overflow-hidden d-flex flex-column"><div class="table-responsive flex-grow-1 custom-scrollbar"><table class="table table-striped table-hover align-middle mb-0"><thead class="table-dark" style="position: sticky; top: 0; z-index: 10;"><tr><th style="background-color: #1e3a8a; width: 20%;" class="px-4">{{ L['username'] }}</th><th style="background-color: #1e3a8a; width: 20%;">{{ L['actions'] }}</th><th style="background-color: #1e3a8a; width: 40%;">التفاصيل</th><th style="background-color: #1e3a8a; width: 20%;">الوقت</th></tr></thead><tbody>{% for log in logs %}<tr><td class="fw-bold px-4">{{ log['username'] }}</td><td><span class="badge border text-dark bg-light px-2 py-1"><i class="fas fa-angle-left me-1 text-primary"></i> {{ log['action'] }}</span></td><td class="text-muted"><small>{{ log['details'] }}</small></td><td dir="ltr"><span class="badge bg-secondary text-white font-monospace">{{ log['timestamp'] }}</span></td></tr>{% else %}<tr><td colspan="4" class="text-center py-5 text-muted"><i class="fas fa-check-circle fa-3x mb-3 text-light"></i><br><span class="fw-bold">{{ L['no_data'] }}</span></td></tr>{% endfor %}</tbody></table></div></div></div>"""

# =====================================================================
# 5. وظائف قاعدة البيانات
# =====================================================================
def get_db_connection():
    if not DATABASE_URL: return None
    return psycopg2.connect(DATABASE_URL)

def init_db():
    if not DATABASE_URL: return
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS printers (id SERIAL PRIMARY KEY, name TEXT NOT NULL, serial TEXT UNIQUE, department TEXT, status TEXT, code TEXT, notes TEXT, color_type TEXT DEFAULT 'BW')""")
    cur.execute("CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, username TEXT UNIQUE, password TEXT, role TEXT)")
    cur.execute("""CREATE TABLE IF NOT EXISTS activity_logs (id SERIAL PRIMARY KEY, username TEXT, action TEXT, details TEXT, timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    
    cur.execute("ALTER TABLE printers ADD COLUMN IF NOT EXISTS code TEXT")
    cur.execute("ALTER TABLE printers ADD COLUMN IF NOT EXISTS notes TEXT")
    cur.execute("ALTER TABLE printers ADD COLUMN IF NOT EXISTS color_type TEXT DEFAULT 'BW'")
    
    admin_pass = generate_password_hash('admin123P')
    cur.execute("INSERT INTO users (username, password, role) VALUES ('admin', %s, 'admin') ON CONFLICT (username) DO NOTHING", (admin_pass,))
    conn.commit()
    cur.close()
    conn.close()

init_db()

# =====================================================================
# 6. الهيكل العام والـ CSS
# =====================================================================
def render_ui(content_html, **context):
    lang_code = session.get('lang', 'ar')
    L = LANGS.get(lang_code, LANGS['ar'])
    layout = """
    <!DOCTYPE html>
    <html lang="{{ lang_code }}" dir="{{ 'rtl' if lang_code == 'ar' else 'ltr' }}">
    <head>
        <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
        <title>{{ L['title'] }}</title>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700;800&display=swap" rel="stylesheet">
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap{% if lang_code == 'ar' %}.rtl{% endif %}.min.css">
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css">
        <style>
            body, html { height: 100vh; overflow: hidden; margin: 0; background-color: #eef2f6; } 
            body { font-family: 'Tajawal', sans-serif; display: flex; flex-direction: column; } 
            
            .navbar { flex-shrink: 0; background-color: #1e3a8a; border-bottom: 3px solid #facc15; box-shadow: 0 2px 4px rgba(0,0,0,0.1); z-index: 1000;} 
            .navbar-brand { font-weight: 800; letter-spacing: 0.5px; }
            
            .main-wrapper { flex: 1; display: flex; flex-direction: column; overflow: hidden; padding: 15px; } 
            
            .form-control, .form-select { border-radius: 4px; border: 1px solid #ced4da; font-size: 0.9rem;}
            .form-control:focus, .form-select:focus { border-color: #1e3a8a; box-shadow: 0 0 0 2px rgba(30, 58, 138, 0.15); }
            .btn { border-radius: 4px; font-weight: 700; letter-spacing: 0.2px; }
            
            .btn-logout { background-color: rgba(255,255,255,0.1); color: #fff; border: 1px solid rgba(255,255,255,0.2); transition: all 0.3s ease;}
            .btn-logout:hover { background-color: #dc2626; color: #fff; border-color: #dc2626; box-shadow: 0 2px 4px rgba(0,0,0,0.2);}

            .custom-scrollbar::-webkit-scrollbar { width: 12px; height: 12px; }
            .custom-scrollbar::-webkit-scrollbar-track { background: #f8f9fa; border-left: 1px solid #e9ecef; }
            .custom-scrollbar::-webkit-scrollbar-thumb { background-color: #1e3a8a; border: 2px solid #f8f9fa; border-radius: 6px; }
            .custom-scrollbar::-webkit-scrollbar-thumb:hover { background-color: #172554; }

            .status-Working { color: #059669; background-color: #ecfdf5; border: 1px solid #a7f3d0; } 
            .status-Maintenance { color: #d97706; background-color: #fffbeb; border: 1px solid #fde68a; } 
            .status-Broken { color: #dc2626; background-color: #fef2f2; border: 1px solid #fecaca; } 
            
            .login-container { display: flex; height: 100vh; width: 100vw; }
            .login-brand { flex: 1; background: linear-gradient(135deg, #1e3a8a 0%, #172554 100%); color: white; display: flex; flex-direction: column; justify-content: center; align-items: center; padding: 40px; text-align: center;}
            .login-form-area { flex: 1; display: flex; flex-direction: column; justify-content: center; align-items: center; background: #ffffff; position: relative;}
            .login-box { width: 100%; max-width: 400px; padding: 20px; }
            
            table th { font-weight: 700; font-size: 0.85rem; letter-spacing: 0.5px; }
            body { -webkit-user-select: none; -ms-user-select: none; user-select: none; } 
            input, textarea { -webkit-user-select: text; -ms-user-select: text; user-select: text; }
        </style>
    </head>
    <body>
        {% if request.endpoint != 'login' %}
        <nav class="navbar navbar-expand-lg navbar-dark p-2">
            <div class="container-fluid px-4">
                <a class="navbar-brand fs-5" href="/"><i class="fas fa-print text-warning me-2"></i> {{ L['title'] }}</a>
                {% if session.get('user') %}
                <div class="navbar-nav mx-auto d-flex gap-2">
                    <a class="nav-link text-white fw-bold px-3 py-1 rounded" href="/">{{ L['home'] }}</a>
                    <a class="nav-link text-white fw-bold px-3 py-1 rounded" href="/reports">{{ L['reports'] }}</a>
                    {% if session.get('role') == 'admin' %}<a class="nav-link text-warning fw-bold px-3 py-1 rounded" href="/users">{{ L['users_manage'] }}</a>{% endif %}
                </div>
                {% endif %}
                <div class="d-flex align-items-center gap-3">
                    <a href="/set_lang/{% if lang_code == 'ar' %}en{% else %}ar{% endif %}" class="text-white text-decoration-none fw-bold small"><i class="fas fa-globe me-1"></i> {% if lang_code == 'ar' %}English{% else %}عربي{% endif %}</a>
                    {% if session.get('user') %}
                    <a href="/logout" class="btn btn-sm btn-logout px-3 fw-bold rounded-2"><i class="fas fa-sign-out-alt me-1"></i> {{ L['logout_btn'] }}</a>
                    {% endif %}
                </div>
            </div>
        </nav>
        <div class="container-fluid main-wrapper">
            <div class="flex-shrink-0">
                {% with messages = get_flashed_messages(with_categories=true) %}
                  {% if messages %}
                    {% for category, msg in messages %}
                      <div class="alert alert-{{ 'success' if category == 'success' else 'warning' }} alert-dismissible fade show shadow-sm rounded-1 fw-bold py-2 border-0 border-start border-4 border-{{ 'success' if category == 'success' else 'warning' }}">
                        {{ msg }}<button type="button" class="btn-close btn-sm" data-bs-dismiss="alert"></button>
                      </div>
                    {% endfor %}
                  {% endif %}
                {% endwith %}
            </div>
            """ + content_html + """
        </div>
        {% else %}
        """ + content_html + """
        {% endif %}
        <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    </body>
    </html>
    """
    return render_template_string(layout, L=L, lang_code=lang_code, **context)

# =====================================================================
# 7. المسارات (Routes)
# =====================================================================
@app.route('/')
def index():
    if 'user' not in session: return redirect(url_for('login'))
    page = request.args.get('page', 1, type=int)
    per_page = 50
    offset = (page - 1) * per_page
    q = sanitize_input(request.args.get('q', ''))
    query_sql = f"%{q}%"
    
    conn = get_db_connection()
    if not conn: return "Database Error"
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT * FROM printers WHERE name ILIKE %s OR serial ILIKE %s OR department ILIKE %s OR code ILIKE %s OR notes ILIKE %s ORDER BY id DESC LIMIT %s OFFSET %s", (query_sql, query_sql, query_sql, query_sql, query_sql, per_page, offset))
    printers = cur.fetchall()
    cur.close()
    conn.close()
    return render_ui(DASHBOARD_UI, printers=printers, query=q, page=page, per_page=per_page)

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
    cur.execute("SELECT * FROM users ORDER BY id")
    users_list = cur.fetchall()
    cur.close()
    conn.close()
    return render_ui(USERS_UI, users=users_list)

@app.route('/audit')
def audit():
    if session.get('role') != 'admin': return redirect(url_for('index'))
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("SELECT * FROM activity_logs ORDER BY id DESC LIMIT 200")
    logs = cur.fetchall()
    cur.close()
    conn.close()
    return render_ui(AUDIT_UI, logs=logs)

@app.route('/add_user', methods=['POST'])
def add_user():
    if session.get('role') == 'admin':
        L = LANGS.get(session.get('lang', 'ar'), LANGS['ar'])
        password = request.form['password']
        if not is_strong_password(password):
            flash(L['err_weak_pass'], "error")
            return redirect(url_for('users'))
        username = sanitize_input(request.form['username'], 30)
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO users (username, password, role) VALUES (%s,%s,%s)", 
                        (username, generate_password_hash(password), request.form['role']))
            conn.commit()
            log_activity(session['user'], 'إضافة مستخدم', f"تمت إضافة المستخدم: {username}")
        except Exception: 
            flash("خطأ: ربما اسم المستخدم موجود مسبقاً", "error")
        cur.close()
        conn.close()
    return redirect(url_for('users'))

@app.route('/edit_user_password', methods=['POST'])
def edit_user_password():
    if session.get('role') == 'admin':
        L = LANGS.get(session.get('lang', 'ar'), LANGS['ar'])
        user_id = request.form.get('user_id')
        new_password = request.form.get('new_password')
        if not is_strong_password(new_password):
            flash(L['err_weak_pass'], "error")
            return redirect(url_for('users'))
        if user_id and new_password:
            conn = get_db_connection()
            cur = conn.cursor()
            try:
                cur.execute("UPDATE users SET password=%s WHERE id=%s", (generate_password_hash(new_password), user_id))
                conn.commit()
                log_activity(session['user'], 'تغيير كلمة مرور', f"تم تغيير كلمة المرور للمستخدم رقم: {user_id}")
                flash(L['pass_changed'], "success")
            except Exception:
                conn.rollback()
            cur.close()
            conn.close()
    return redirect(url_for('users'))

@app.route('/edit_user_role', methods=['POST'])
def edit_user_role():
    if session.get('role') == 'admin':
        L = LANGS.get(session.get('lang', 'ar'), LANGS['ar'])
        user_id = request.form.get('user_id')
        new_role = request.form.get('new_role')
        if user_id and new_role in ['admin', 'entry', 'user']:
            conn = get_db_connection()
            cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            try:
                cur.execute("SELECT username FROM users WHERE id=%s", (user_id,))
                target_user = cur.fetchone()
                if target_user and target_user['username'] == 'admin':
                    flash("لا يمكن تعديل صلاحيات مدير النظام الأساسي", "error")
                else:
                    cur.execute("UPDATE users SET role=%s WHERE id=%s", (new_role, user_id))
                    conn.commit()
                    log_activity(session['user'], 'تعديل صلاحية', f"تغيير صلاحية المستخدم {user_id} إلى {new_role}")
                    flash(L['role_changed'], "success")
            except Exception:
                conn.rollback()
            cur.close()
            conn.close()
    return redirect(url_for('users'))

@app.route('/delete_user/<int:uid>', methods=['POST'])
def delete_user(uid):
    if session.get('role') == 'admin':
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM users WHERE id=%s AND username!='admin'", (uid,))
        conn.commit()
        log_activity(session['user'], 'حذف مستخدم', f"تم حذف المستخدم رقم: {uid}")
        cur.close()
        conn.close()
    return redirect(url_for('users'))

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute", error_message="تم تجاوز الحد المسموح به. يرجى الانتظار قليلاً.")
def login():
    lang_code = session.get('lang', 'ar')
    L = LANGS.get(lang_code, LANGS['ar'])
    
    if request.method == 'POST':
        username = sanitize_input(request.form['username'], 30)
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if not user or not check_password_hash(user['password'], request.form['password']):
            log_activity(username, 'فشل تسجيل دخول', 'محاولة فاشلة')
            flash(L['err_login'], "error")
        else:
            session.permanent = bool(request.form.get('remember'))
            session['user'] = user['username']
            session['role'] = user['role']
            log_activity(user['username'], 'تسجيل دخول ناجح', 'دخول إلى النظام')
            return redirect(url_for('index'))
            
    login_html = f"""
    <div class="login-container">
        <div class="login-brand d-none d-md-flex position-relative overflow-hidden">
            <i class="fas fa-desktop position-absolute text-white" style="font-size: 300px; opacity: 0.05; right: -50px; bottom: -50px;"></i>
            <div class="text-center position-relative z-1">
                <i class="fas fa-print fa-5x text-warning mb-4"></i>
                <h1 class="fw-bold mb-3">{L['title']}</h1>
            </div>
        </div>
        <div class="login-form-area bg-light">
            <div class="position-absolute p-4 z-3" style="top: 0; {'left: 0;' if lang_code == 'ar' else 'right: 0;'}">
                <a href="/set_lang/{'en' if lang_code == 'ar' else 'ar'}" class="btn btn-sm bg-white shadow-sm fw-bold rounded-pill px-3" style="color: #1e3a8a; border: 2px solid #1e3a8a;">
                    <i class="fas fa-globe me-1"></i> {'English' if lang_code == 'ar' else 'عربي'}
                </a>
            </div>
            
            <div class="login-box mt-4">
                {{% with messages = get_flashed_messages(with_categories=true) %}}
                  {{% if messages %}}
                    {{% for category, msg in messages %}}
                      <div class="alert alert-{{{{ 'success' if category == 'success' else 'danger' }}}} alert-dismissible fade show shadow-sm rounded-1 fw-bold small text-center border-0 border-start border-4 border-{{{{ 'success' if category == 'success' else 'danger' }}}}">
                        {{{{ msg }}}}
                        <button type="button" class="btn-close btn-sm" data-bs-dismiss="alert"></button>
                      </div>
                    {{% endfor %}}
                  {{% endif %}}
                {{% endwith %}}
                
                <div class="text-center mb-4 d-md-none">
                    <i class="fas fa-print fa-3x text-primary mb-2"></i>
                    <h4 class="fw-bold" style="color: #1e3a8a;">{L['title']}</h4>
                </div>
                <div class="card border-0 shadow-sm rounded-2">
                    <div class="card-body p-4">
                        <h5 class="fw-bold text-dark mb-4 text-center">{L['login_box_title']}</h5>
                        <form method="POST" autocomplete="off">
                            <input type="hidden" name="csrf_token" value="{{{{ csrf_token() }}}}" />
                            <div class="mb-3">
                                <label class="form-label fw-bold text-muted small">{L['username']}</label>
                                <div class="input-group">
                                    <span class="input-group-text bg-white border-end-0"><i class="fas fa-user text-muted"></i></span>
                                    <input type="text" name="username" class="form-control border-start-0 ps-0" required autocomplete="off">
                                </div>
                            </div>
                            <div class="mb-3">
                                <label class="form-label fw-bold text-muted small">{L['password']}</label>
                                <div class="input-group">
                                    <span class="input-group-text bg-white border-end-0"><i class="fas fa-lock text-muted"></i></span>
                                    <input type="password" name="password" class="form-control border-start-0 ps-0" required autocomplete="new-password">
                                </div>
                            </div>
                            <div class="d-flex justify-content-between align-items-center mb-4">
                                <div class="form-check">
                                    <input class="form-check-input border-secondary" type="checkbox" name="remember" id="remember" checked>
                                    <label class="form-check-label text-muted fw-bold small" for="remember">{L['remember']}</label>
                                </div>
                                <a href="#" data-bs-toggle="modal" data-bs-target="#forgotPassModal" class="text-decoration-none small fw-bold" style="color: #1e3a8a;">{L['forgot_pass']}</a>
                            </div>
                            <button class="btn w-100 py-2 fs-6 fw-bold text-white shadow-sm" style="background-color: #1e3a8a;">{L['login_btn']} <i class="fas {'fa-arrow-left' if lang_code == 'ar' else 'fa-arrow-right'} ms-1"></i></button>
                        </form>
                    </div>
                </div>
                <div class="text-center mt-4">
                    <small class="text-muted fw-bold">{L['footer_text']}</small>
                </div>
            </div>
        </div>
    </div>

    <div class="modal fade" id="forgotPassModal" tabindex="-1" aria-hidden="true">
      <div class="modal-dialog modal-dialog-centered modal-sm">
        <div class="modal-content border-0 shadow rounded-2">
          <div class="modal-header text-white border-0 py-2 rounded-top-2" style="background-color: #1e3a8a;">
            <h6 class="modal-title fw-bold"><i class="fas fa-info-circle me-2"></i>{L['admin_notice']}</h6>
            <button type="button" class="btn-close btn-close-white btn-sm" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body text-center py-4">
            <i class="fas fa-user-shield fa-3x mb-3" style="color: #1e3a8a;"></i>
            <p class="mb-0 text-dark fw-bold small">{L['contact_admin']}</p>
          </div>
          <div class="modal-footer border-0 justify-content-center bg-light py-2">
            <button type="button" class="btn btn-sm text-white px-4 fw-bold" style="background-color: #1e3a8a;" data-bs-dismiss="modal">{L['ok_btn']}</button>
          </div>
        </div>
      </div>
    </div>
    """
    return render_ui(login_html)

@app.route('/add', methods=['POST'])
def add():
    if session.get('role') in ['admin', 'entry']:
        name = sanitize_input(request.form['name'], 100)
        serial = sanitize_input(request.form['serial'], 50)
        dept = sanitize_input(request.form['dept'], 100)
        code = sanitize_input(request.form.get('code', ''), 50)
        notes = sanitize_input(request.form.get('notes', ''), 250)
        
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO printers (name, serial, department, status, code, color_type, notes) VALUES (%s,%s,%s,%s,%s,%s,%s)", 
                         (name, serial, dept, request.form['status'], code, request.form.get('color_type', 'BW'), notes))
            conn.commit()
            log_activity(session['user'], 'إضافة طابعة', f"تمت إضافة طابعة سيريال: {serial}")
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
                    name = sanitize_input(row[0], 100)
                    serial = sanitize_input(row[1], 50)
                    dept = sanitize_input(row[2], 100)
                    status = sanitize_input(row[3], 20)
                    code = sanitize_input(row[4], 50)
                    
                    if len(row) >= 7:
                        color_val = sanitize_input(row[5], 20)
                        notes = sanitize_input(row[6], 250)
                    else:
                        color_val = 'BW'
                        notes = sanitize_input(row[5], 250)
                    
                    if status not in ['Working', 'Maintenance', 'Broken']: status = 'Working'
                    
                    color_type = 'Color' if color_val in ['Color', 'ملون'] else 'BW'
                    
                    if name and serial:
                        try:
                            cur.execute("INSERT INTO printers (name, serial, department, status, code, color_type, notes) VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (serial) DO NOTHING", (name, serial, dept, status, code, color_type, notes))
                            if cur.rowcount > 0: added_count += 1
                        except Exception: conn.rollback()
            conn.commit()
            log_activity(session['user'], 'رفع ملف CSV', f"تم استيراد {added_count} طابعة بنجاح")
            cur.close()
            conn.close()
            flash(f"تمت العملية! أُضيفت {added_count} طابعة بنجاح.", "success")
        except Exception: flash("حدث خطأ تقني، يرجى التأكد من صيغة الملف والمحاولة لاحقاً.", "error")
    else: flash("الرجاء رفع ملف بصيغة CSV فقط", "error")
    return redirect(url_for('index'))

@app.route('/export_csv')
def export_csv():
    if session.get('role') not in ['admin', 'entry']: 
        return redirect(url_for('index'))

    L = LANGS.get(session.get('lang', 'ar'), LANGS['ar'])

    def generate():
        yield '\ufeff' 
        si = io.StringIO()
        cw = csv.writer(si)
        cw.writerow([L['name'], L['serial'], L['dept'], L['status'], L['code'], L['color_type'], L['notes']])
        yield si.getvalue()
        si.seek(0); si.truncate(0)

        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cur.execute("SELECT name, serial, department, status, code, color_type, notes FROM printers ORDER BY id DESC")
        
        while True:
            rows = cur.fetchmany(100)
            if not rows: break
            for p in rows:
                status_localized = L[p['status'].lower().replace(' ', '')]
                color_localized = L['color'] if p['color_type'] == 'Color' else L['bw']
                
                row_data = [
                    sanitize_csv_field(p['name']), sanitize_csv_field(p['serial']), 
                    sanitize_csv_field(p['department']), sanitize_csv_field(status_localized), 
                    sanitize_csv_field(p['code']), sanitize_csv_field(color_localized), 
                    sanitize_csv_field(p['notes'])
                ]
                cw.writerow(row_data)
            yield si.getvalue()
            si.seek(0); si.truncate(0)

        cur.close()
        conn.close()

    log_activity(session['user'], 'تصدير بيانات', 'تصدير الطابعات إلى CSV')
    return Response(generate(), mimetype='text/csv', headers={"Content-Disposition": "attachment; filename=printers_backup.csv"})

@app.route('/edit/<int:pid>', methods=['GET', 'POST'])
def edit(pid):
    if session.get('role') not in ['admin', 'entry']: return redirect(url_for('index'))
    conn = get_db_connection()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    if request.method == 'POST':
        name = sanitize_input(request.form['name'], 100)
        serial = sanitize_input(request.form['serial'], 50)
        dept = sanitize_input(request.form['dept'], 100)
        code = sanitize_input(request.form.get('code', ''), 50)
        notes = sanitize_input(request.form.get('notes', ''), 250)
        
        try:
            cur.execute("UPDATE printers SET name=%s, serial=%s, department=%s, status=%s, code=%s, color_type=%s, notes=%s WHERE id=%s", 
                        (name, serial, dept, request.form['status'], code, request.form.get('color_type', 'BW'), notes, pid))
            conn.commit()
            log_activity(session['user'], 'تعديل طابعة', f"تم تعديل بيانات الطابعة رقم: {pid}")
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

@app.route('/delete/<int:pid>', methods=['POST'])
def delete(pid):
    if session.get('role') == 'admin':
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM printers WHERE id=%s", (pid,))
        conn.commit()
        log_activity(session['user'], 'حذف طابعة', f"تم حذف الطابعة رقم: {pid}")
        cur.close()
        conn.close()
    return redirect(url_for('index'))

@app.route('/set_lang/<lang>')
def set_lang(lang):
    if lang in ['ar', 'en']: session['lang'] = lang
    return redirect(request.referrer or url_for('index'))

@app.route('/logout')
def logout():
    log_activity(session.get('user', 'غير معروف'), 'تسجيل خروج', 'خروج من النظام')
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0')
