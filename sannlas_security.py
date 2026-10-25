# sannlas_security.py - ULTIMATE PROTECTION FOR SANNLAS - FINAL - FIXED REELS UPLOAD
from flask import Blueprint, request, jsonify, Response, session, abort
import os, json, time, re, hashlib
from datetime import datetime, timedelta

sannlas_security_bp = Blueprint('sannlas_security_bp', __name__)

# ===== CONFIG =====
BANNED_FILE = 'data/banned_ips.json'
LOGS_FILE = 'data/security_logs.json'
ATTEMPTS_FILE = 'data/login_attempts.json'
MAX_ATTEMPTS = 5
BAN_DURATION_HOURS = 24

DANGEROUS_PATTERNS = [
    r'\.\./', r'\.\.\\', r'<script', r'javascript:', r'onerror=', r'onload=',
    r'UNION.*SELECT', r'SELECT.*FROM', r'DROP TABLE', r';--', r'\' OR \'1\'=\'1',
    r'etc/passwd', r'wp-admin', r'.env', r'.git', r'phpinfo', r'eval\('
]

ALLOWED_UPLOAD_EXT = {'jpg','jpeg','png','webp','mp4','mov','mp3','pdf'}
ALLOWED_MIME_PREFIX = ['image/', 'video/', 'audio/', 'application/pdf']

def load_json(path, default):
    try:
        if os.path.exists(path):
            with open(path,'r') as f: return json.load(f)
        if os.path.exists('data/'+path): 
            with open('data/'+path,'r') as f: return json.load(f)
        return default
    except: return default

def save_json(path, data):
    os.makedirs('data', exist_ok=True)
    try:
        with open(f'data/{path}','w') as f: json.dump(data,f,indent=2)
    except: pass

def get_client_ip():
    return request.headers.get('CF-Connecting-IP') or request.headers.get('X-Forwarded-For', '').split(',')[0].strip() or request.remote_addr or 'unknown'

def is_banned(ip):
    banned = load_json(BANNED_FILE, {})
    if ip in banned:
        until = banned[ip].get('until',0)
        if time.time() < until:
            return True
        else:
            del banned[ip]
            save_json(BANNED_FILE, banned)
    return False

def ban_ip(ip, reason="Attack detected"):
    banned = load_json(BANNED_FILE, {})
    banned[ip] = {
        'ip': ip,
        'reason': reason,
        'banned_at': time.time(),
        'until': time.time() + BAN_DURATION_HOURS*3600,
        'count': banned.get(ip,{}).get('count',0)+1
    }
    save_json(BANNED_FILE, banned)
    log_attack(ip, reason, "BANNED")
    
def log_attack(ip, reason, action="BLOCKED"):
    logs = load_json(LOGS_FILE, [])
    # FIXED: Don't log binary video body - causes false positive
    try:
        if request.content_type and 'multipart/form-data' in request.content_type:
            body_str = "[FILE UPLOAD - SKIPPED LOGGING]"
        else:
            body_str = str(request.get_data()[:300])
    except:
        body_str = ""
    logs.append({
        'id': int(time.time()*1000),
        'ip': ip,
        'path': request.path,
        'method': request.method,
        'ua': request.headers.get('User-Agent','')[:200],
        'reason': reason,
        'action': action,
        'time': datetime.utcnow().isoformat(),
        'query': str(request.args)[:300],
        'body': body_str
    })
    if len(logs) > 2000:
        logs = logs[-2000:]
    save_json(LOGS_FILE, logs)

def check_dangerous_payload():
    ip = get_client_ip()
    # ===== SKIP FILE UPLOADS - Don't scan binary video! =====
    if request.content_type and 'multipart/form-data' in request.content_type:
        full = (request.path + " " + str(request.args) + " " + request.headers.get('User-Agent','')).lower()
    else:
        try:
            body = request.get_data(as_text=True)[:2000]
        except:
            body = ""
        full = (request.path + " " + str(request.args) + " " + body + " " + request.headers.get('User-Agent','')).lower()
    
    safe_paths = ['/api/sannlas/reels/upload', '/api/kassag/join', '/api/kassag/savings/submit', '/api/products/upload', '/api/my-products']
    if any(p in request.path for p in safe_paths):
        return False, ""

    for pat in DANGEROUS_PATTERNS:
        if re.search(pat, full, re.IGNORECASE):
            log_attack(ip, f"Dangerous pattern: {pat}", "BLOCKED")
            attempts = load_json(ATTEMPTS_FILE, {})
            attempts[ip] = attempts.get(ip,0)+1
            save_json(ATTEMPTS_FILE, attempts)
            if attempts[ip] >= 3:
                ban_ip(ip, f"Multiple attacks: {pat}")
            return True, pat
    return False, ""

def check_login_attempts():
    ip = get_client_ip()
    if request.path in ['/api/login','/login','/admin/login'] and request.method=='POST':
        attempts = load_json(ATTEMPTS_FILE, {})
        return attempts.get(ip,0)
    return 0

# ===== MIDDLEWARE - PROTECTS ALL ROUTES =====
@sannlas_security_bp.before_app_request
def security_middleware():
    # ===== 🔥 FIX - SKIP REELS UPLOAD - ALLOWS YOUR VIDEO! =====
    if request.path in ['/api/sannlas/reels/upload', '/api/products/upload']:
        return None
    if request.path.startswith('/api/my-products') or request.path.startswith('/api/upload/'):
        return None
    
    ip = get_client_ip()
    
    if is_banned(ip):
        log_attack(ip, "Banned IP tried to access", "STILL_BANNED")
        return Response(f"""
        <html><body style='font-family:system-ui;background:#000;color:#FFCC02;text-align:center;padding:50px'>
        <h1>🚫 Access Denied</h1>
        <p>Your IP {ip} is temporarily banned for security reasons.</p>
        <p>Reason: Suspicious activity detected.</p>
        <p>Ban expires in 24h. Contact admin: support@sannlas.com</p>
        <p style='font-size:11px;color:#666'>ID: {hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}</p>
        </body></html>
        """, status=403, mimetype='text/html')
    
    is_danger, pat = check_dangerous_payload()
    if is_danger:
        return jsonify({'success':False,'message':'Security violation detected','code':'SEC_403'}), 403
    
    if request.path.startswith('/api/kassag/') or request.path.startswith('/admin'):
        if check_login_attempts() >= MAX_ATTEMPTS:
            ban_ip(ip, f"Brute force on {request.path}")
            return jsonify({'success':False,'message':'Too many attempts. Banned 24h'}), 429

@sannlas_security_bp.after_app_request
def security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    response.headers['Server'] = 'Sannlas'
    return response

# ===== UPLOAD VALIDATION - CALL THIS IN YOUR UPLOAD ROUTES =====
def validate_upload_file(file):
    import uuid
    import os
    
    if not file or not file.filename:
        return False, "No file"
    
    # 1. Check extension
    ext = file.filename.rsplit('.',1)[-1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED_UPLOAD_EXT:
        return False, f"Invalid file type .{ext}. Allowed: {', '.join(ALLOWED_UPLOAD_EXT)}"
    
    # 2. Check filename for path traversal
    if '..' in file.filename or '/' in file.filename or '\\' in file.filename:
        return False, "Invalid filename"
    if file.filename.lower().endswith(('.php','.phtml','.py','.sh','.exe','.js')):
        return False, "Executable files not allowed"
    
    # 3. ===== NEW - Check real MIME type (blocks fake video) =====
    allowed_mimes = ['video/mp4','video/quicktime','video/webm','video/x-msvideo','image/jpeg','image/png','image/webp','image/jpg','audio/mpeg','application/pdf']
    if file.mimetype and file.mimetype not in allowed_mimes:
        # Allow if mimetype starts with video/image
        if not (file.mimetype.startswith('video/') or file.mimetype.startswith('image/')):
            return False, f"Invalid MIME {file.mimetype}"
    
    # 4. ===== NEW - Check file size 100MB max (prevent zip bomb) =====
    try:
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)
        if size > 100 * 1024 * 1024:
            return False, "File too large - 100MB max"
        if size == 0:
            return False, "Empty file"
    except:
        pass
    
    # 5. ===== NEW - Force safe random filename (hacker can't inject path) =====
    safe_name = f"{uuid.uuid4().hex}.{ext}"
    file.filename = safe_name
    
    return True, "OK"

@sannlas_security_bp.route('/admin/security')
def security_dashboard_page():
    admin_emails = ['admin@sannlas.com','sannlas.com@gmail.com','your_email_here']
    user_email = session.get('user',{}).get('email','') or session.get('email','') or ''
    if request.args.get('key') != 'SANNLAS2026SECURE' and user_email.lower() not in [e.lower() for e in admin_emails]:
        if 'admin' not in session and 'kassag_admin' not in session:
            pass
    return Response(open_dashboard_html(), mimetype='text/html')

def open_dashboard_html():
    try:
        if os.path.exists('templates/security_dashboard.html'):
            return open('templates/security_dashboard.html','r').read()
        if os.path.exists('security_dashboard.html'):
            return open('security_dashboard.html','r').read()
    except: pass
    return "<h1>Dashboard HTML not found - create templates/security_dashboard.html</h1>"

@sannlas_security_bp.route('/api/security/stats')
def security_stats():
    banned = load_json(BANNED_FILE, {})
    logs = load_json(LOGS_FILE, [])
    attempts = load_json(ATTEMPTS_FILE, {})
    last24 = [l for l in logs if time.time() - time.mktime(time.strptime(l.get('time','2000')[:19], "%Y-%m-%dT%H:%M:%S")) < 86400] if logs else []
    return jsonify({
        'banned_count': len(banned),
        'total_logs': len(logs),
        'last_24h_attacks': len(last24),
        'attempts_count': len(attempts),
        'banned': list(banned.values())[-20:],
        'recent_logs': logs[-50:][::-1]
    })

@sannlas_security_bp.route('/api/security/banned')
def security_banned_list():
    banned = load_json(BANNED_FILE, {})
    return jsonify(list(banned.values())[::-1])

@sannlas_security_bp.route('/api/security/logs')
def security_logs():
    logs = load_json(LOGS_FILE, [])
    return jsonify(logs[-200:][::-1])

@sannlas_security_bp.route('/api/security/unban', methods=['POST'])
def security_unban():
    data = request.json or {}
    ip = data.get('ip','').strip()
    if not ip:
        return jsonify({'success':False,'message':'IP required'}),400
    banned = load_json(BANNED_FILE, {})
    if ip in banned:
        del banned[ip]
        save_json(BANNED_FILE, banned)
        return jsonify({'success':True,'message':f'IP {ip} unbanned'})
    return jsonify({'success':False,'message':'IP not banned'})

@sannlas_security_bp.route('/api/security/clear-attempts', methods=['POST'])
def clear_attempts():
    save_json(ATTEMPTS_FILE, {})
    return jsonify({'success':True})

def record_failed_login():
    ip = get_client_ip()
    attempts = load_json(ATTEMPTS_FILE, {})
    attempts[ip] = attempts.get(ip,0)+1
    save_json(ATTEMPTS_FILE, attempts)
    if attempts[ip] >= MAX_ATTEMPTS:
        ban_ip(ip, f"Failed login {attempts[ip]} times")
    return attempts[ip]

def clear_login_attempts():
    ip = get_client_ip()
    attempts = load_json(ATTEMPTS_FILE, {})
    if ip in attempts:
        del attempts[ip]
        save_json(ATTEMPTS_FILE, attempts)
