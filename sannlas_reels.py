import os, traceback, json, time, re, math, random
from flask import Blueprint, request, jsonify, render_template, send_from_directory
from datetime import datetime, timezone
import psycopg2

reels_bp = Blueprint('reels_bp', __name__)

# ✅ CACHE AT TOP
_feed_cache = {'data': [], 'time': 0, 'followed': {}, 'liked': {}, 'key': ''}

# ============================================================
# 1. HELPERS
# ============================================================

def get_conn():
    DATABASE_URL = os.getenv('DATABASE_URL')
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def clean_slug(raw_name):
    if not raw_name:
        return 'shop'
    raw = str(raw_name).strip()
    raw = raw.replace('%20',' ').replace('%2',' ')
    slug = re.sub(r'[^a-z0-9]+', '-', raw.lower()).strip('-')
    return slug or 'shop'

def load_products_json():
    try:
        for path in ['data/products.json', 'products.json']:
            if os.path.exists(path):
                with open(path, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return {str(p.get('id')): p for p in data}
    except Exception as e:
        print("Load products.json fail:", e)
    return {}

def load_shops_map():
    shops_data = []
    users_data = []
    for path in ['data/shops.json', 'shops.json']:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    shops_data = json.load(f)
                    break
            except: pass
    for path in ['data/users.json', 'users.json']:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    users_data = json.load(f)
                    break
            except: pass
    m = {}
    try:
        for s in shops_data:
            if not isinstance(s, dict): continue
            slug = clean_slug(s.get('shop_slug') or s.get('slug') or s.get('business_name') or '')
            name = (s.get('business_name') or s.get('name') or '').lower().strip()
            email = (s.get('owner_email') or s.get('email') or '').lower().strip()
            if slug: m[slug] = s
            if name: m[name] = s
            if email: m[email] = s
            if email and not s.get('email'):
                s['email'] = email
                s['owner_email'] = email
        for u in users_data:
            if not isinstance(u, dict): continue
            u_email = (u.get('email') or '').lower().strip()
            u_business = (u.get('business') or u.get('shop_name') or '').lower().strip()
            u_slug = clean_slug(u_business)
            if u_email:
                if u_slug in m:
                    if not m[u_slug].get('email'):
                        m[u_slug]['email'] = u_email
                        m[u_slug]['owner_email'] = u_email
                if u_business in m:
                    if not m[u_business].get('email'):
                        m[u_business]['email'] = u_email
                        m[u_business]['owner_email'] = u_email
                if u_business not in m:
                    m[u_business] = {'email': u_email, 'owner_email': u_email, 'business_name': u.get('business')}
                if u_slug not in m:
                    m[u_slug] = {'email': u_email, 'owner_email': u_email, 'business_name': u.get('business')}
    except Exception as e:
        print("load_shops_map error:", e)
    return m

def ensure_reels_table():
    conn = get_conn(); cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS sannlas_reels (
      id BIGSERIAL PRIMARY KEY, 
      user_email TEXT, user_name TEXT, shop_name TEXT, shop_slug TEXT,
      caption TEXT, description TEXT, price TEXT, promo_link TEXT,
      location TEXT, hashtags TEXT, video_url TEXT, 
      product_link TEXT, product_id TEXT, likes INT DEFAULT 0, 
      created TIMESTAMP DEFAULT NOW())""")
    for col, dtype in [
        ('views','INT DEFAULT 0'),
        ('shares','INT DEFAULT 0'),
        ('comments_count','INT DEFAULT 0'),
        ('saves','INT DEFAULT 0'),
        ('category','TEXT DEFAULT \'\''),
        ('duration','FLOAT DEFAULT 0'),
        ('score','FLOAT DEFAULT 0'),
    ]:
        try: cur.execute(f"ALTER TABLE sannlas_reels ADD COLUMN IF NOT EXISTS {col} {dtype}")
        except: pass
    cur.execute("""CREATE TABLE IF NOT EXISTS sannlas_reel_interactions (
        id BIGSERIAL PRIMARY KEY, reel_id BIGINT, user_email TEXT,
        action TEXT, watch_time FLOAT DEFAULT 0, created TIMESTAMP DEFAULT NOW())""")
    cur.execute("""CREATE TABLE IF NOT EXISTS sannlas_follows (
        id BIGSERIAL PRIMARY KEY, follower_email TEXT, following_email TEXT,
        created TIMESTAMP DEFAULT NOW(), UNIQUE(follower_email, following_email))""")
    conn.commit(); cur.close(); conn.close()

# ============================================================
# 2. 🧠 ALGORITHM - NEW = MAJOR!
# ============================================================

def calc_reel_score(reel, viewer_email='', followed_set=None, liked_categories=None):
    likes = int(reel.get('likes') or 0)
    views = int(reel.get('views') or 0)
    comments = int(reel.get('comments_count') or 0)
    shares = int(reel.get('shares') or 0)
    saves = int(reel.get('saves') or 0)
    created = reel.get('created')
    try:
        if isinstance(created, str):
            created = datetime.fromisoformat(created.replace('Z','+00:00'))
        if created and created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        hours = (datetime.now(timezone.utc) - created).total_seconds() / 3600 if created else 9999
    except:
        hours = 9999
    if hours < 1:
        fresh = 100000
    elif hours < 6:
        fresh = 50000
    elif hours < 24:
        fresh = 20000
    elif hours < 72:
        fresh = 5000
    elif hours < 168:
        fresh = 1000
    else:
        fresh = 0
    engagement = (likes*3) + (comments*5) + (shares*10) + (saves*8) + (views*0.5)
    engagement = min(engagement, 999)
    personal = 0
    if followed_set and (reel.get('user_email') or '').lower() in followed_set:
        personal += 50
    if liked_categories:
        cat = (reel.get('category') or '').lower()
        if cat in liked_categories:
            personal += 30
    new_seller = 0
    if views < 20 and hours < 24:
        new_seller = 20
    score = fresh + engagement + personal + new_seller
    score += random.uniform(0, 5)
    return round(score, 2)

# ============================================================
# 3. PAGES
# ============================================================

@reels_bp.route('/reels')
@reels_bp.route('/reels.html')
def reels_page():
    try:
        return render_template('reels.html')
    except:
        try:
            return send_from_directory('.', 'reels.html')
        except:
            return send_from_directory('templates', 'reels.html')

@reels_bp.route('/profile/<shop_slug>')
@reels_bp.route('/@<shop_slug>')
@reels_bp.route('/reels/user/<shop_slug>')
@reels_bp.route('/user/<shop_slug>')
def user_profile_page(shop_slug):
    try:
        return render_template('user_profile.html', shop_slug=shop_slug)
    except:
        try:
            return send_from_directory('templates', 'user_profile.html')
        except:
            return f"Create templates/user_profile.html first for @{shop_slug}", 404

# ============================================================
# 4. FEED
# ============================================================

@reels_bp.route('/api/sannlas/reels/feed')
def reels_feed():
    try:
        products_map = load_products_json()
        shops_map = load_shops_map()
        viewer_email = (request.args.get('user_email') or request.args.get('email') or '').lower().strip()
        page = int(request.args.get('page') or 1)
        limit = int(request.args.get('limit') or 20)
        now = time.time()
        cache_key = viewer_email or 'guest'
        use_cache = (now - _feed_cache.get('time', 0) < 10 and _feed_cache.get('key') == cache_key and _feed_cache.get('data'))
        if use_cache:
            final = _feed_cache['data']
            followed_set = _feed_cache.get('followed', set())
        else:
            conn = get_conn(); cur = conn.cursor()
            followed_set = set()
            liked_categories = set()
            if viewer_email:
                try:
                    cur.execute("SELECT following_email FROM sannlas_follows WHERE follower_email=%s", (viewer_email,))
                    followed_set = set([r[0].lower() for r in cur.fetchall() if r[0]])
                    cur.execute("""SELECT r.category FROM sannlas_reel_interactions i
                                   JOIN sannlas_reels r ON r.id=i.reel_id
                                   WHERE i.user_email=%s AND i.action IN ('like','save','share')
                                   GROUP BY r.category ORDER BY COUNT(*) DESC LIMIT 3""", (viewer_email,))
                    liked_categories = set([r[0].lower() for r in cur.fetchall() if r[0]])
                except: pass
            cur.execute("SELECT id, user_email, user_name, shop_name, shop_slug, caption, description, product_id, video_url, likes, views, shares, comments_count, saves, category, created FROM sannlas_reels ORDER BY id DESC LIMIT 300")
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
            data = [dict(zip(cols, r)) for r in rows]
            cur.close(); conn.close()
            scored = []
            for reel in data:
                reel['algo_score'] = calc_reel_score(reel, viewer_email, followed_set, liked_categories)
                scored.append(reel)
            scored.sort(key=lambda x: x['algo_score'], reverse=True)
            final = []
            last_shop = ''
            skipped = []
            for idx, r in enumerate(scored):
                shop = r.get('shop_slug') or ''
                if idx < 3:
                    final.append(r); last_shop = shop; continue
                if shop == last_shop and len(final) < 20:
                    skipped.append(r); continue
                final.append(r); last_shop = shop
            final.extend(skipped)
            _feed_cache['data'] = final
            _feed_cache['time'] = now
            _feed_cache['key'] = cache_key
            _feed_cache['followed'] = followed_set
        start = (page-1)*limit
        page_data = final[start:start+limit]
        for reel in page_data:
            try:
                pid = str(reel.get('product_id') or '').strip()
                shop = reel.get('shop_name') or reel.get('user_name') or 'SANNLAS SHOP'
                slug = clean_slug(reel.get('shop_slug') or shop)
                reel['shop_name'] = shop
                reel['shop_slug'] = slug
                shop_obj = shops_map.get(slug) or shops_map.get(shop.lower()) or {}
                reel['shop_logo'] = shop_obj.get('logo','')
                reel['shop_profile_url'] = f"/shop/{slug}"
                db_email = reel.get('user_email') or ''
                shop_email = shop_obj.get('email') or shop_obj.get('owner_email') or ''
                final_email = (db_email or shop_email or '').lower().strip()
                reel['user_email'] = final_email
                reel['shop_email'] = final_email
                reel['email'] = final_email
                reel['user_id'] = final_email or slug
                reel['shop_id'] = final_email or slug
                reel['is_following'] = final_email in followed_set
                reel['category'] = reel.get('category') or ''
                reel['views'] = int(reel.get('views') or 0)
                reel['shares'] = int(reel.get('shares') or 0)
                reel['comments_count'] = int(reel.get('comments_count') or 0)
                product_data = products_map.get(pid) if pid else None
                if product_data:
                    raw_coins = product_data.get('promo_coins') or product_data.get('promo_commission') or 3
                    try: promo_coins = int(float(str(raw_coins).strip()))
                    except: promo_coins = 3
                else: promo_coins = 3
                ugx = promo_coins * 599
                reel['promo_coins'] = promo_coins
                reel['promo_commission'] = promo_coins
                reel['promo_commission_ugx'] = ugx
                reel['earn_amount'] = ugx
                reel['earn_amount_formatted'] = f"{ugx:,}"
                if pid:
                    reel['promote_link'] = f"/promotion/{pid}?commission={promo_coins}&from=reels"
                    reel['product_link'] = f"/product/{pid}"
                    reel['buy_link'] = f"/product/{pid}"
                else:
                    reel['promote_link'] = f"/shop/{slug}"
                    reel['product_link'] = f"/shop/{slug}"
                    reel['buy_link'] = f"/shop/{slug}"
            except Exception as e:
                print(f"Reel fail {reel.get('id')}: {e}")
        return jsonify(page_data)
    except Exception as e:
        print("FEED ERROR:", e)
        traceback.print_exc()
        return jsonify([])

# ============================================================
# 5. USER REELS
# ============================================================

@reels_bp.route('/api/sannlas/reels/user/<shop_slug>')
def get_user_reels(shop_slug):
    try:
        ensure_reels_table()
        products_map = load_products_json()
        shops_map = load_shops_map()
        conn = get_conn(); cur = conn.cursor()
        incoming = clean_slug(shop_slug)
        cur.execute("SELECT * FROM sannlas_reels ORDER BY id DESC LIMIT 200")
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        all_data = [dict(zip(cols, r)) for r in rows]
        filtered = []
        for r in all_data:
            db_slug = clean_slug(r.get('shop_slug') or '')
            db_name = clean_slug(r.get('shop_name') or '')
            db_user = clean_slug(r.get('user_name') or '')
            if incoming in [db_slug, db_name, db_user] or db_slug == incoming or incoming in db_slug or db_slug in incoming:
                filtered.append(r)
        data = filtered
        for reel in data:
            pid = str(reel.get('product_id') or '').strip()
            shop = reel.get('shop_name') or reel.get('user_name') or 'SANNLAS SHOP'
            slug = clean_slug(reel.get('shop_slug') or shop)
            reel['shop_name'] = shop
            reel['shop_slug'] = slug
            shop_obj = shops_map.get(slug) or {}
            reel['shop_logo'] = shop_obj.get('logo','')
            reel['shop_profile_url'] = f"/shop/{slug}"
            db_email = reel.get('user_email') or ''
            shop_email = shop_obj.get('email') or ''
            final_email = (db_email or shop_email or '').lower().strip()
            reel['user_email'] = final_email
            reel['shop_email'] = final_email
            reel['email'] = final_email
            reel['user_id'] = final_email or slug
            reel['shop_id'] = final_email or slug
            raw_coins = 3
            if pid and pid in products_map:
                pd = products_map[pid]
                raw_coins = pd.get('promo_coins') or pd.get('promo_commission') or 3
            try:
                promo_coins = int(float(str(raw_coins).strip()))
            except:
                promo_coins = 3
            ugx = promo_coins * 599
            reel['promo_coins'] = promo_coins
            reel['earn_amount'] = ugx
            reel['earn_amount_formatted'] = f"{ugx:,}"
            reel['promote_link'] = f"/promotion/{pid}?commission={promo_coins}&from=reels" if pid else f"/shop/{slug}"
        cur.close(); conn.close()
        return jsonify(data)
    except Exception as e:
        print("USER REELS ERROR:", e)
        traceback.print_exc()
        return jsonify([])

# ============================================================
# 6. 🔥 OPTION 2 - DIRECT UPLOAD TO CLOUDINARY!
# ============================================================

@reels_bp.route('/api/cloudinary-signature')
def cloudinary_signature():
    try:
        import cloudinary.utils
        ts = int(time.time())
        # Sign ONLY timestamp + folder - safe!
        params = {'timestamp': ts, 'folder': 'sannlas_reels'}
        sig = cloudinary.utils.api_sign_request(params, os.getenv('CLOUDINARY_API_SECRET'))
        return jsonify({
            'signature': sig,
            'timestamp': ts,
            'api_key': os.getenv('CLOUDINARY_API_KEY'),
            'cloud_name': os.getenv('CLOUDINARY_CLOUD_NAME'),
            'folder': 'sannlas_reels'
        })
    except Exception as e:
        print("SIG ERROR:", e)
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@reels_bp.route('/api/sannlas/reels/save-url', methods=['POST'])
def save_reel_url():
    try:
        ensure_reels_table()
        d = request.get_json(silent=True) or {}
        video_url = (d.get('video_url') or d.get('url') or '').strip()
        if not video_url:
            return jsonify({'success': False, 'error': 'video_url missing'}), 400
        user_email = (d.get('user_email') or d.get('email') or '').lower().strip()
        if not user_email:
            return jsonify({'success': False, 'error': 'login first!'}), 400
        user_name = d.get('user_name') or (user_email.split('@')[0] if user_email else 'SANNLAS USER')
        shop_name = d.get('shop_name') or user_name or 'SANNLAS SHOP'
        shop_slug = clean_slug(d.get('shop_slug') or shop_name)
        caption = d.get('caption') or d.get('product_name') or 'New Reel 🔥'
        product_id = d.get('product_id') or ''
        category = d.get('category') or ''
        hashtags = d.get('hashtags') or ''
        location = d.get('location') or ''
        price = str(d.get('price') or '')
        promo_link = d.get('promo_link') or ''
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("INSERT INTO sannlas_reels (user_email, user_name, shop_name, shop_slug, caption, description, product_id, video_url, likes, category, hashtags, location, price, promo_link, product_link) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,0,%s,%s,%s,%s,%s,%s) RETURNING id", (user_email, user_name, shop_name, shop_slug, caption, caption, product_id, video_url, category, hashtags, location, price, promo_link, promo_link))
        new_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        _feed_cache['data'] = []
        _feed_cache['time'] = 0
        return jsonify({'success': True, 'id': new_id, 'video_url': video_url})
    except Exception as e:
        print("SAVE-URL ERROR:", e)
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500
        
# OLD upload kept as FALLBACK if direct fails - but NOT used by new frontend
@reels_bp.route('/api/sannlas/reels/upload', methods=['POST'])
def upload_reel_old():
    return jsonify({'success': False, 'error': 'Use direct upload - /api/cloudinary-signature + /api/sannlas/reels/save-url'}), 400

# ============================================================
# 7. INTERACTIONS
# ============================================================

@reels_bp.route('/api/sannlas/reels/like/<int:rid>', methods=['POST'])
def like_reel(rid):
    try:
        d = request.get_json(silent=True) or {}
        email = (d.get('user_email') or '').lower().strip()
        conn = get_conn(); cur = conn.cursor()
        cur.execute("UPDATE sannlas_reels SET likes = likes + 1 WHERE id=%s", (rid,))
        if email:
            cur.execute("INSERT INTO sannlas_reel_interactions (reel_id, user_email, action) VALUES (%s,%s,'like')", (rid, email))
        conn.commit(); cur.close(); conn.close()
        return jsonify({'success':True})
    except Exception as e:
        print("LIKE ERROR", e); return jsonify({'success':False})

@reels_bp.route('/api/sannlas/reels/view/<int:rid>', methods=['POST'])
def view_reel(rid):
    try:
        d = request.get_json(silent=True) or {}
        email = (d.get('user_email') or '').lower().strip()
        watch = float(d.get('watch_time') or 0)
        ensure_reels_table()
        conn = get_conn(); cur = conn.cursor()
        cur.execute("UPDATE sannlas_reels SET views = views + 1 WHERE id=%s", (rid,))
        if email:
            cur.execute("INSERT INTO sannlas_reel_interactions (reel_id, user_email, action, watch_time) VALUES (%s,%s,'view',%s)", (rid, email, watch))
        conn.commit(); cur.close(); conn.close()
        return jsonify({'success':True})
    except Exception as e:
        print("VIEW ERROR", e); return jsonify({'success':False})

@reels_bp.route('/api/sannlas/reels/share/<int:rid>', methods=['POST'])
def share_reel(rid):
    try:
        d = request.get_json(silent=True) or {}
        email = (d.get('user_email') or '').lower().strip()
        conn = get_conn(); cur = conn.cursor()
        cur.execute("UPDATE sannlas_reels SET shares = shares + 1 WHERE id=%s", (rid,))
        if email: cur.execute("INSERT INTO sannlas_reel_interactions (reel_id, user_email, action) VALUES (%s,%s,'share')", (rid, email))
        conn.commit(); cur.close(); conn.close()
        return jsonify({'success':True})
    except Exception as e:
        print("SHARE ERROR", e); return jsonify({'success':False})

@reels_bp.route('/api/sannlas/reels/save/<int:rid>', methods=['POST'])
def save_reel(rid):
    try:
        d = request.get_json(silent=True) or {}
        email = (d.get('user_email') or '').lower().strip()
        conn = get_conn(); cur = conn.cursor()
        cur.execute("UPDATE sannlas_reels SET saves = saves + 1 WHERE id=%s", (rid,))
        if email: cur.execute("INSERT INTO sannlas_reel_interactions (reel_id, user_email, action) VALUES (%s,%s,'save')", (rid, email))
        conn.commit(); cur.close(); conn.close()
        return jsonify({'success':True})
    except Exception as e:
        print("SAVE ERROR", e); return jsonify({'success':False})

@reels_bp.route('/api/sannlas/reels/follow', methods=['POST'])
def follow_shop():
    try:
        d = request.get_json(silent=True) or {}
        follower = (d.get('follower_email') or d.get('user_email') or '').lower().strip()
        following = (d.get('following_email') or d.get('shop_email') or '').lower().strip()
        if not follower or not following: return jsonify({'success':False, 'error':'missing emails'})
        ensure_reels_table()
        conn = get_conn(); cur = conn.cursor()
        cur.execute("INSERT INTO sannlas_follows (follower_email, following_email) VALUES (%s,%s) ON CONFLICT DO NOTHING", (follower, following))
        conn.commit(); cur.close(); conn.close()
        return jsonify({'success':True, 'following':True})
    except Exception as e:
        print("FOLLOW ERROR", e); return jsonify({'success':False})

# ============================================================
# 8. FIX OLD REELS EMAILS
# ============================================================

@reels_bp.route('/fix-old-reels-emails')
def fix_old_reels():
    try:
        shops_map = load_shops_map()
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT id, shop_name, shop_slug, user_email FROM sannlas_reels")
        rows = cur.fetchall()
        fixed = 0
        for r in rows:
            rid, shop_name, shop_slug, user_email = r
            if user_email and '@' in str(user_email): 
                continue
            slug = clean_slug(shop_slug or shop_name)
            shop_obj = shops_map.get(slug) or shops_map.get((shop_name or '').lower()) or {}
            email = (shop_obj.get('email') or shop_obj.get('owner_email') or '').lower().strip()
            if email:
                cur.execute("UPDATE sannlas_reels SET user_email=%s WHERE id=%s", (email, rid))
                fixed += 1
        conn.commit()
        cur.close(); conn.close()
        return f"Fixed {fixed} reels with emails! Now + button will work!"
    except Exception as e:
        traceback.print_exc()
        return f"Error: {e}", 500
