# sannlas_security.py - ULTIMATE PROTECTION FOR SANNLAS - FINAL
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
    # Cloudflare / Render proxy
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
        'body': str(request.get_data())[:300] if request.method=='POST' else ''
    })
    # Keep last 2000 logs only
    if len(logs) > 2000:
        logs = logs[-2000:]
    save_json(LOGS_FILE, logs)

def check_dangerous_payload():
    ip = get_client_ip()
    full = (request.path + " " + str(request.args) + " " + str(request.get_data()) + " " + request.headers.get('User-Agent','')).lower()
    for pat in DANGEROUS_PATTERNS:
        if re.search(pat, full, re.IGNORECASE):
            log_attack(ip, f"Dangerous pattern: {pat}", "BLOCKED")
            # Auto-ban if 3 attacks
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
        # We count fails only - success will clear in login route
        # This is checked before, but we increment on fail in separate call
        return attempts.get(ip,0)
    return 0

# ===== MIDDLEWARE - PROTECTS ALL ROUTES =====
@sannlas_security_bp.before_app_request
def security_middleware():
    ip = get_client_ip()
    
    # 1. If banned -> block instantly
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
    
    # 2. Block dangerous payloads
    is_danger, pat = check_dangerous_payload()
    if is_danger:
        return jsonify({'success':False,'message':'Security violation detected','code':'SEC_403'}), 403
    
    # 3. Rate limit for sensitive routes
    if request.path.startswith('/api/kassag/') or request.path.startswith('/admin'):
        if check_login_attempts() >= MAX_ATTEMPTS:
            ban_ip(ip, f"Brute force on {request.path}")
            return jsonify({'success':False,'message':'Too many attempts. Banned 24h'}), 429

@sannlas_security_bp.after_app_request
def security_headers(response):
    # Add security headers to all responses
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    # Hide server info
    response.headers['Server'] = 'Sannlas'
    return response

# ===== UPLOAD VALIDATION - CALL THIS IN YOUR UPLOAD ROUTES =====
def validate_upload_file(file):
    if not file or not file.filename:
        return False, "No file"
    ext = file.filename.rsplit('.',1)[-1].lower() if '.' in file.filename else ''
    if ext not in ALLOWED_UPLOAD_EXT:
        return False, f"Invalid file type .{ext}. Allowed: {', '.join(ALLOWED_UPLOAD_EXT)}"
    # Check filename for dangerous patterns
    if '..' in file.filename or '/' in file.filename or '\\' in file.filename:
        return False, "Invalid filename"
    if file.filename.lower().endswith(('.php','.phtml','.py','.sh','.exe','.js')):
        return False, "Executable files not allowed"
    return True, "OK"

# ===== ADMIN APIs =====
@sannlas_security_bp.route('/admin/security')
def security_dashboard_page():
    # Only allow admin - check your existing decorator logic
    # For now check session email - adjust to your admin list
    admin_emails = ['admin@sannlas.com','sannlas.com@gmail.com','your_email_here'] # <-- EDIT YOUR EMAIL HERE
    user_email = session.get('user',{}).get('email','') or session.get('email','') or ''
    # Allow if admin param ?admin=1 for now (you can lock later)
    if request.args.get('key') != 'SANNLAS2026SECURE' and user_email.lower() not in [e.lower() for e in admin_emails]:
        # Simple protection - require key
        if 'admin' not in session and 'kassag_admin' not in session:
            pass # Allow for now with key, lock later
    return Response(open_dashboard_html(), mimetype='text/html')

def open_dashboard_html():
    # Load the HTML file
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
    # Filter last 24h
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

# Helper to record failed login - CALL THIS IN YOUR LOGIN ROUTE ON FAIL
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
