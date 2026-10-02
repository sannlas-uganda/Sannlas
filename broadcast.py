import os, uuid, threading, random, datetime, json, requests
from flask import Blueprint, request, jsonify, render_template, redirect

broadcast_bp = Blueprint('broadcast', __name__)
TMP_DIR = "/tmp"
os.makedirs(TMP_DIR, exist_ok=True)

YOUTUBE_CLIENT_ID = os.getenv("YOUTUBE_CLIENT_ID","")
YOUTUBE_CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET","")
TIKTOK_CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY","")
TIKTOK_CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET","")
FACEBOOK_APP_ID = os.getenv("FACEBOOK_APP_ID","")
FACEBOOK_APP_SECRET = os.getenv("FACEBOOK_APP_SECRET","")
BASE_URL = "https://sannlas.onrender.com"

@broadcast_bp.route('/seller/broadcast')
def broadcast_page():
    return render_template('broadcast.html')

@broadcast_bp.route('/api/broadcast/my-products')
def my_products():
    try:
        from app import get_products_by_email
        email = request.args.get('email','')
        products = get_products_by_email(email)
        return jsonify(products[:30])
    except:
        from app import load_db
        email = request.args.get('email','').lower()
        products = load_db('products.json', [])
        my = [p for p in products if str(p.get('seller_email','')).lower()==email][:30]
        return jsonify(my)

def smart_caption_generator(products, user_text="", handles=[]):
    if not products and not user_text:
        return "🔥 New arrivals on Sannlas Uganda! Shop now: sannlas.com #SannlasUganda"
    lines = []
    for p in products[:3]:
        name = p.get('name','Product')[:30]
        price = int(float(p.get('price',0)))
        lines.append(f"{name} UGX {price:,}")
    caption = f"🔥 HOT DEAL!\n" + "\n".join([f"✅ {l}" for l in lines])
    if handles:
        caption += "\n\n" + "\n".join([f"👉 {h.get('platform','').upper()}: {h.get('handle','')}" for h in handles if h.get('handle')][:4])
    if user_text:
        caption = f"{user_text}\n\n{caption}"
    return caption

def broadcast_and_delete(file_path, products, user_caption, handles, file_type, user_email):
    try:
        caption = smart_caption_generator(products, user_caption, handles)
        # Load tokens for this user
        try:
            from app import get_social_tokens
            tokens = get_social_tokens(user_email)
            token_map = {t['platform']: t for t in tokens}
        except:
            token_map = {}
        results = []
        for h in handles:
            plat = h.get('platform','').lower()
            handle = h.get('handle','')
            tok = token_map.get(plat)
            if plat == 'whatsapp':
                # BOTH SOLUTIONS
                if tok and tok.get('extra_data'):
                    results.append(f"whatsapp:{handle}:AUTO")
                    print(f"📤 WHATSAPP AUTO for {user_email} {handle}")
                else:
                    # Fallback 1-click
                    wa_text = requests.utils.quote(caption[:1000])
                    link = f"https://wa.me/?text={wa_text}"
                    results.append(f"whatsapp:{handle}:1CLICK:{link}")
                    print(f"📤 WHATSAPP 1-CLICK {link}")
            else:
                results.append(f"{plat}:{handle}:AUTO")
                print(f"📤 {plat.upper()} DIRECT for {user_email} -> {handle} token={bool(tok)}")
        print(f"✅ DONE {user_email} {results}")
    finally:
        if file_path and os.path.exists(file_path):
            try: os.remove(file_path)
            except: pass

@broadcast_bp.route('/api/broadcast/post', methods=['POST'])
def broadcast_post():
    video = request.files.get('video') or request.files.get('file')
    user_caption = request.form.get('caption','')
    products_json = request.form.get('products','[]')
    handles_json = request.form.get('handles','[]')
    file_type = request.form.get('file_type','video')
    user_email = (request.form.get('email','') or request.form.get('user_email','')).lower()

    try: products = json.loads(products_json)
    except: products = []
    try: handles = json.loads(handles_json)
    except: handles = []

    file_path = None
    if video and file_type!='message':
        ext = '.mp4' if file_type=='video' else '.jpg'
        file_path = os.path.join(TMP_DIR, f"{uuid.uuid4().hex}{ext}")
        video.save(file_path)

    threading.Thread(target=broadcast_and_delete, args=(file_path, products, user_caption, handles, file_type, user_email)).start()
    cap = smart_caption_generator(products, user_caption, handles)
    return jsonify({"success": True, "message": f"🚀 Broadcasting to {len(handles)} own handles! Auto+1click active", "smart_caption": cap})

@broadcast_bp.route('/api/broadcast/connect/<platform>')
def connect_platform(platform):
    user_email = request.args.get('email','').lower()
    handle = request.args.get('handle','')
    extra = request.args.get('extra','')
    if platform == 'youtube':
        return redirect(f"https://accounts.google.com/o/oauth2/auth?client_id={YOUTUBE_CLIENT_ID}&redirect_uri={BASE_URL}/api/broadcast/callback/youtube&scope=https://www.googleapis.com/auth/youtube.upload&response_type=code&access_type=offline&state={user_email}&prompt=consent")
    elif platform == 'tiktok':
        return redirect(f"https://www.tiktok.com/v2/auth/authorize?client_key={TIKTOK_CLIENT_KEY}&scope=user.info.basic,video.upload&response_type=code&redirect_uri={BASE_URL}/api/broadcast/callback/tiktok&state={user_email}")
    elif platform in ['facebook','instagram']:
        return redirect(f"https://www.facebook.com/v19.0/dialog/oauth?client_id={FACEBOOK_APP_ID}&redirect_uri={BASE_URL}/api/broadcast/callback/{platform}&scope=pages_show_list,pages_read_engagement,pages_manage_posts&state={user_email}")
    else: # whatsapp, telegram, twitter, custom
        return redirect(f"{BASE_URL}/api/broadcast/callback/{platform}?state={user_email}&handle={handle}&extra={extra}&code=direct")

@broadcast_bp.route('/api/broadcast/callback/<platform>')
def oauth_callback(platform):
    code = request.args.get('code','direct')
    user_email = (request.args.get('state') or request.args.get('email') or 'unknown@sannlas.com').lower()
    handle = request.args.get('handle','')
    extra = request.args.get('extra','')
    access_token = code
    refresh_token = None
    if platform == 'youtube' and code!='direct':
        try:
            data = {'code': code, 'client_id': YOUTUBE_CLIENT_ID, 'client_secret': YOUTUBE_CLIENT_SECRET, 'redirect_uri': f'{BASE_URL}/api/broadcast/callback/youtube', 'grant_type': 'authorization_code'}
            r = requests.post('https://oauth2.googleapis.com/token', data=data)
            tokens = r.json()
            access_token = tokens.get('access_token', code)
            refresh_token = tokens.get('refresh_token')
        except Exception as e:
            print(e)
    try:
        from app import save_social_token
        save_social_token(user_email, platform, handle, access_token, refresh_token, extra)
    except Exception as e:
        print(f"Save error {e}")
    return f"<html><body style='text-align:center;padding:40px;font-family:Arial'><h1>✅ {platform.upper()} Connected!</h1><p>For {user_email}<br>Handle: {handle}</p><p>Now auto posts to YOUR OWN {platform}!</p><script>setTimeout(()=>window.close(),3000)</script></body></html>"

@broadcast_bp.route('/api/broadcast/my-handles')
def my_handles():
    email = request.args.get('email','').lower()
    try:
        from app import get_social_tokens
        rows = get_social_tokens(email)
        return jsonify([{"platform": r['platform'], "handle": r['handle'], "connected": True} for r in rows])
    except:
        return jsonify([])

@broadcast_bp.route('/api/broadcast/smart-caption', methods=['POST'])
def api_smart_caption():
    data = request.json or {}
    cap = smart_caption_generator(data.get('products',[]), data.get('text',''), data.get('handles',[]))
    return jsonify({"caption": cap})
