# shop.py - SANNLAS SHOP CORE - FIXED - Live follower count
# Contains ONLY shop helpers + /api/shops that were in app.py
# shops.py + my_shop.py already handle the rest!
from flask import Blueprint, jsonify, request
import re, time, os, json
import psycopg2, psycopg2.extras

shop_bp = Blueprint('shop_bp', __name__)

DATABASE_URL = os.getenv('DATABASE_URL')

def get_conn_pg():
    url = DATABASE_URL
    if url and url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(url, sslmode='require')

# ===== HELPERS - Moved from app.py =====
def make_shop_slug(business):
    if not business: return 'shop'
    base = re.sub(r'[^a-z0-9]+', '-', business.lower()).strip('-')
    if not base: base = 'shop'
    return base[:50]

def get_biz_key(name):
    if not name: return ''
    return re.sub(r'[^a-z0-9]+', '', name.lower())

# ===== ✅ NEW - LIVE FOLLOWER COUNT - Use this in shops.py! =====
def get_live_follow_counts(shop_email, shop_slug=""):
    """
    Count followers LIVE from BOTH places, not from users.json (which is stale 0)
    - follows.json (kv_store)
    - sannlas_follows (Postgres - Reels follows)
    Returns: {'followers': int, 'following': int}
    """
    shop_email = (shop_email or '').lower().strip()
    shop_slug = (shop_slug or '').lower().strip()
    followers_set = set()
    following_set = set()

    # 1. From follows.json via app.load_db
    try:
        from app import load_db
        follows = load_db('follows.json', []) or []
        for f in follows:
            fe = (f.get('follower_email') or '').lower()
            te = (f.get('following_email') or '').lower()
            if shop_email and te == shop_email:
                if fe: followers_set.add(fe)
            if shop_email and fe == shop_email:
                if te: following_set.add(te)
            # Also match by slug if email missing
            if shop_slug and te == shop_slug:
                if fe: followers_set.add(fe)
    except Exception as e:
        print("get_live_follow_counts JSON fail:", e)

    # 2. From Postgres sannlas_follows
    try:
        conn = get_conn_pg(); cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS sannlas_follows (id BIGSERIAL PRIMARY KEY, follower_email TEXT, following_email TEXT, created TIMESTAMP DEFAULT NOW(), UNIQUE(follower_email, following_email))")
        conn.commit()
        if shop_email:
            cur.execute("SELECT follower_email FROM sannlas_follows WHERE LOWER(following_email)=%s", (shop_email,))
            for r in cur.fetchall():
                if r[0]: followers_set.add(r[0].lower())
            cur.execute("SELECT following_email FROM sannlas_follows WHERE LOWER(follower_email)=%s", (shop_email,))
            for r in cur.fetchall():
                if r[0]: following_set.add(r[0].lower())
        if shop_slug:
            cur.execute("SELECT follower_email FROM sannlas_follows WHERE LOWER(following_email)=%s", (shop_slug,))
            for r in cur.fetchall():
                if r[0]: followers_set.add(r[0].lower())
        cur.close(); conn.close()
    except Exception as e:
        print("get_live_follow_counts PG fail:", e)

    return {'followers': len(followers_set), 'following': len(following_set)}

def get_live_shop_stats(shop_email, shop_slug=""):
    """Followers + Following + Real Likes + Views - for shop page"""
    counts = get_live_follow_counts(shop_email, shop_slug)
    likes = 0; views = 0
    try:
        conn = get_conn_pg(); cur = conn.cursor()
        cur.execute("SELECT COALESCE(SUM(likes),0), COALESCE(SUM(views),0) FROM sannlas_reels WHERE LOWER(shop_slug)=%s OR LOWER(user_email)=%s", (shop_slug, shop_email))
        row = cur.fetchone()
        if row: likes, views = int(row[0] or 0), int(row[1] or 0)
        cur.close(); conn.close()
    except Exception as e:
        print("get_live_shop_stats fail:", e)
    return {'followers': counts['followers'], 'following': counts['following'], 'likes': likes, 'views': views, 'total_likes': likes, 'total_views': views}

def ensure_shop_for_user(user):
    # Lazy import to avoid circular import with app.py
    from app import load_db, save_db
    shops = load_db('shops.json', [])
    biz = (user.get('business') or '').strip()
    if not biz: biz = 'Shop'
    biz_key = get_biz_key(biz)
    slug = make_shop_slug(biz)
    email = (user.get('email') or '').lower()
    for s in shops:
        s_biz = s.get('business_name') or s.get('name') or ''
        if get_biz_key(s_biz) == biz_key and biz_key:
            s['shop_slug'] = slug
            s['slug'] = slug
            s['business_name'] = biz
            s['name'] = biz
            if email: s['owner_email'] = email
            if user.get('phone'): s['phone'] = user.get('phone')
            save_db('shops.json', shops)
            return s
    existing = next((s for s in shops if (s.get('shop_slug')==slug or s.get('slug')==slug)), None)
    if existing:
        existing['business_name'] = biz
        existing['name'] = biz
        existing['shop_slug'] = slug
        existing['slug'] = slug
        save_db('shops.json', shops)
        return existing
    existing2 = next((s for s in shops if s.get('user_id')==user.get('id')), None)
    if existing2:
        existing2['business_name'] = biz
        existing2['name'] = biz
        existing2['shop_slug'] = slug
        existing2['slug'] = slug
        save_db('shops.json', shops)
        return existing2
    shop = {"id": int(time.time()*1000),"user_id": user.get('id'),"business_name": biz,"name": biz,"shop_slug": slug,"slug": slug,"phone": user.get('phone',''),"owner_email": email,"location": "Kampala","description": "Welcome to " + biz + " shop!","logo_url": "","banner_url": "","verified": False,"total_products": 0,"product_count": 0,"created_at": time.time()}
    shops.append(shop)
    save_db('shops.json', shops)
    return shop

# ✅ NEW - API so frontend can get live count without Python template
@shop_bp.route('/api/shop/<slug>/live-stats')
def live_stats(slug):
    from app import load_db
    shops = load_db('shops.json', [])
    shop = next((s for s in shops if (s.get('shop_slug')==slug or s.get('slug')==slug)), None)
    email = (shop.get('owner_email') or shop.get('email') or '') if shop else ''
    stats = get_live_shop_stats(email, slug)
    stats['email'] = email
    stats['slug'] = slug
    return jsonify(stats)
