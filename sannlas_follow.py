# sannlas_follow.py - FIXED - Counts from BOTH follows.json + Postgres sannlas_follows
# Fixes: 0 Followers bug, hardcoded 70 likes / 1736 views, slug vs email mismatch
from flask import Blueprint, Response, request, jsonify
import os, json, time, re
import psycopg2, psycopg2.extras

sannlas_follow_bp = Blueprint('sannlas_follow_bp', __name__)

DATABASE_URL = os.getenv('DATABASE_URL')

def get_conn():
    url = DATABASE_URL
    if url and url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(url, sslmode='require')

def ensure_follows_table():
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS sannlas_follows (
            id BIGSERIAL PRIMARY KEY, follower_email TEXT, following_email TEXT,
            created TIMESTAMP DEFAULT NOW(), UNIQUE(follower_email, following_email))""")
        conn.commit(); cur.close(); conn.close()
    except Exception as e:
        print("ensure_follows_table fail:", e)

def load_db(file, default):
    try:
        if DATABASE_URL:
            conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT data FROM kv_store WHERE key=%s", (file,))
            row = cur.fetchone(); cur.close(); conn.close()
            if not row: return default
            d = row['data']
            if isinstance(d,str):
                try: d=json.loads(d)
                except: pass
            return d
        if os.path.exists(f'data/{file}'):
            return json.load(open(f'data/{file}'))
        return default
    except Exception as e:
        print(f"load_db {file} error:", e)
        return default

def save_db(file, data):
    try:
        if DATABASE_URL:
            conn = get_conn(); cur = conn.cursor()
            cur.execute("CREATE TABLE IF NOT EXISTS kv_store (key TEXT PRIMARY KEY, data JSONB NOT NULL)")
            cur.execute("INSERT INTO kv_store (key, data) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET data = EXCLUDED.data", (file, json.dumps(data)))
            conn.commit(); cur.close(); conn.close()
            return
        os.makedirs('data', exist_ok=True)
        json.dump(data, open(f'data/{file}','w'), indent=2)
    except Exception as e:
        print(f"save_db {file} error:", e)

def get_users(): return load_db('users.json', [])
def get_follows(): return load_db('follows.json', [])
def save_follows(data): save_db('follows.json', data)

def clean_slug(s):
    if not s: return 'shop'
    return re.sub(r'[^a-z0-9]+', '-', str(s).lower()).strip('-')

def find_shop_email(target_slug_raw):
    target_slug_raw = (target_slug_raw or '').strip()
    target_slug = clean_slug(target_slug_raw)
    target_lower = target_slug_raw.lower()
    users = get_users()
    shops = load_db('shops.json', [])
    products = load_db('products.json', [])

    if '@' in target_lower:
        return target_lower

    # 1. Search shops.json - contains match (sann in sannlas)
    for s in shops:
        slug = clean_slug(s.get('shop_slug') or s.get('slug') or '')
        biz = (s.get('business_name') or s.get('name') or '').lower()
        biz_slug = clean_slug(biz)
        if target_slug == slug or target_slug in biz_slug or biz_slug in target_slug or target_lower in biz or biz in target_lower or target_slug in slug or slug in target_slug:
            em = (s.get('owner_email') or s.get('email') or '').lower()
            if em: return em

    # 2. Search users.json - business contains
    for u in users:
        biz = (u.get('business') or '').lower()
        biz_slug = clean_slug(biz)
        shop_slug = clean_slug(u.get('shop_slug') or '')
        if target_slug == biz_slug or target_slug == shop_slug or target_slug in biz_slug or biz_slug in target_slug or target_lower in biz or biz in target_lower:
            em = (u.get('email') or '').lower()
            if em: return em

    # 3. Search products to get owner
    for p in products:
        ps = clean_slug(p.get('shop_slug') or '')
        pb = (p.get('business') or '').lower()
        if ps == target_slug or target_slug in ps or target_lower in pb:
            em = (p.get('seller_email') or p.get('owner_email') or '').lower()
            if em: return em

    # 4. ✅ NEW - Search sannlas_reels Postgres table - shop_slug -> user_email
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT user_email FROM sannlas_reels WHERE LOWER(shop_slug)=%s OR LOWER(shop_name)=%s LIMIT 1", (target_slug, target_lower))
        row = cur.fetchone()
        cur.close(); conn.close()
        if row and row[0] and '@' in str(row[0]):
            return str(row[0]).lower().strip()
    except Exception as e:
        print("find_shop_email PG fail:", e)

    return target_lower

def get_follow_html():
    try:
        if os.path.exists('templates/follow.html'):
            return open('templates/follow.html', encoding='utf-8').read()
        if os.path.exists('follow.html'):
            return open('follow.html', encoding='utf-8').read()
    except: pass
    return "<h1>Follow page - put follow.html in templates/</h1>"

@sannlas_follow_bp.route('/follow')
def follow_page():
    return Response(get_follow_html(), mimetype='text/html')

@sannlas_follow_bp.route('/api/follow/stats')
def follow_stats():
    email = request.args.get('email','').lower().strip()
    phone = request.args.get('phone','').strip()
    users = get_users()
    follows = get_follows()
    me = next((u for u in users if (email and str(u.get('email','')).lower()==email) or (phone and str(u.get('phone',''))==phone)), None)
    my_email = (me.get('email','').lower() if me else email)
    my_followers_emails = [f['follower_email'].lower() for f in follows if f.get('following_email','').lower()==my_email]
    my_following_emails = [f['following_email'].lower() for f in follows if f.get('follower_email','').lower()==my_email]
    # ✅ Also add Postgres followers
    try:
        ensure_follows_table()
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT follower_email FROM sannlas_follows WHERE LOWER(following_email)=%s", (my_email,))
        for r in cur.fetchall():
            if r[0] and r[0].lower() not in my_followers_emails:
                my_followers_emails.append(r[0].lower())
        cur.execute("SELECT following_email FROM sannlas_follows WHERE LOWER(follower_email)=%s", (my_email,))
        for r in cur.fetchall():
            if r[0] and r[0].lower() not in my_following_emails:
                my_following_emails.append(r[0].lower())
        cur.close(); conn.close()
    except Exception as e:
        print("follow_stats PG fail:", e)
    def enrich(email_list):
        result=[]
        for em in email_list:
            u = next((x for x in users if str(x.get('email','')).lower()==em), None)
            if u:
                f_count = len([f for f in follows if f.get('following_email','').lower()==em])
                is_following = em in my_following_emails
                result.append({'email': u.get('email'),'business': u.get('business',''),'phone': u.get('phone',''),'followers': f_count,'is_following': is_following})
        return result
    return jsonify({'followers': len(my_followers_emails),'following': len(my_following_emails),'followers_list': enrich(my_followers_emails),'following_list': enrich(my_following_emails),'discover': [],'total_users': len(users)})

@sannlas_follow_bp.route('/api/user/follow-count/<shop_slug>')
def user_follow_count(shop_slug):
    follows = get_follows()
    target_email = find_shop_email(shop_slug)
    followers_json = [f for f in follows if f.get('following_email','').lower() == target_email]
    following_json = [f for f in follows if f.get('follower_email','').lower() == target_email]
    # ✅ FIX - ALSO count from Postgres sannlas_follows (Reels follows!)
    pg_follower_emails = set()
    following_pg = 0
    try:
        ensure_follows_table()
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT follower_email FROM sannlas_follows WHERE LOWER(following_email)=%s OR LOWER(following_email)=%s", (target_email, shop_slug.lower()))
        for r in cur.fetchall():
            if r[0]: pg_follower_emails.add(r[0].lower())
        cur.execute("SELECT COUNT(*) FROM sannlas_follows WHERE LOWER(follower_email)=%s", (target_email,))
        row = cur.fetchone()
        following_pg = row[0] or 0 if row else 0
        cur.close(); conn.close()
    except Exception as e:
        print("follow-count PG fail:", e)
    all_followers = set([f.get('follower_email','').lower() for f in followers_json]) | pg_follower_emails
    followers = len(all_followers)
    following = len(set([f.get('following_email','').lower() for f in following_json])) + following_pg
    if '@' not in target_email:
        print(f"⚠️ FOLLOW-COUNT: No email found for slug {shop_slug}, got {target_email} - check shops.json owner_email!")
    return jsonify({'followers': followers, 'following': following, 'email': target_email, 'slug': shop_slug})

@sannlas_follow_bp.route('/api/shop/<slug>/stats')
def shop_stats_override(slug):
    # ✅ FIX - No more hardcoded 70 / 1736! Use real counts
    r = user_follow_count(slug)
    d = r.get_json()
    likes = 0; views = 0
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT COALESCE(SUM(likes),0), COALESCE(SUM(views),0) FROM sannlas_reels WHERE LOWER(shop_slug)=%s OR LOWER(user_email)=%s", (slug.lower(), (d.get('email') or '').lower()))
        row = cur.fetchone()
        if row: likes, views = int(row[0] or 0), int(row[1] or 0)
        cur.close(); conn.close()
    except Exception as e:
        print("shop stats fail:", e)
    return jsonify({'followers': d['followers'],'following': d['following'],'follower_count': d['followers'],'following_count': d['following'],'total_likes': likes,'likes': likes,'total_views': views,'views': views,'email': d.get('email')})

@sannlas_follow_bp.route('/api/follow', methods=['POST'])
def follow_user():
    data = request.get_json() or {}
    my_email = (data.get('email','') or '').lower().strip()
    target_email = (data.get('target_email','') or '').lower().strip()
    target_shop_raw = (data.get('target_shop','') or '').lower().strip()
    if not target_email and target_shop_raw:
        target_email = find_shop_email(target_shop_raw)
    if not target_email or '@' not in target_email:
        return jsonify({"success": False, "message": f"user not found - {target_shop_raw}"}), 404
    if my_email == target_email:
        return jsonify({"success": False, "message": "Can't follow yourself"}), 400
    follows = get_follows()
    for f in follows:
        if f.get('follower_email','').lower() == my_email and f.get('following_email','').lower() == target_email:
            # Already in JSON - also ensure in PG
            try:
                ensure_follows_table()
                conn = get_conn(); cur = conn.cursor()
                cur.execute("INSERT INTO sannlas_follows (follower_email, following_email) VALUES (%s,%s) ON CONFLICT DO NOTHING", (my_email, target_email))
                conn.commit(); cur.close(); conn.close()
            except: pass
            return jsonify({"success": True, "message": "Already following", "followers": len([x for x in follows if x.get('following_email','').lower()==target_email])})
    follows.append({"follower_email": my_email, "following_email": target_email, "created_at": time.time()})
    save_follows(follows)
    # ✅ FIX - Also save to Postgres so Reels + Shop agree!
    try:
        ensure_follows_table()
        conn = get_conn(); cur = conn.cursor()
        cur.execute("INSERT INTO sannlas_follows (follower_email, following_email) VALUES (%s,%s) ON CONFLICT DO NOTHING", (my_email, target_email))
        conn.commit(); cur.close(); conn.close()
    except Exception as e:
        print("PG follow save fail:", e)
    users = get_users()
    for u in users:
        if str(u.get('email','')).lower()==target_email:
            u['followers'] = int(u.get('followers',0)) + 1
            break
    save_db('users.json', users)
    # ✅ New count = JSON + PG merged
    new_count = len(set([x.get('follower_email','').lower() for x in get_follows() if x.get('following_email','').lower()==target_email]))
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT COUNT(DISTINCT follower_email) FROM sannlas_follows WHERE LOWER(following_email)=%s", (target_email,))
        pg_c = cur.fetchone()[0] or 0
        cur.close(); conn.close()
        new_count = max(new_count, pg_c)
    except: pass
    return jsonify({"success": True, "message": "Followed!", "followers": new_count})

@sannlas_follow_bp.route('/api/unfollow', methods=['POST'])
def api_unfollow():
    data = request.json or {}
    email = data.get('email','').lower().strip()
    target = data.get('target_email','').lower().strip()
    if '@' not in target:
        target = find_shop_email(target)
    follows = get_follows()
    before = len(follows)
    follows = [f for f in follows if not (f.get('follower_email','').lower()==email and f.get('following_email','').lower()==target)]
    if before==len(follows):
        # Not in JSON - try PG only
        try:
            conn = get_conn(); cur = conn.cursor()
            cur.execute("DELETE FROM sannlas_follows WHERE LOWER(follower_email)=%s AND LOWER(following_email)=%s", (email, target))
            deleted = cur.rowcount
            conn.commit(); cur.close(); conn.close()
            if deleted and deleted > 0:
                return jsonify({'success':True,'message':'Unfollowed!','followers':0})
        except: pass
        return jsonify({'success':False,'message':'Not following!'}),400
    save_follows(follows)
    # ✅ Also delete from PG
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("DELETE FROM sannlas_follows WHERE LOWER(follower_email)=%s AND LOWER(following_email)=%s", (email, target))
        conn.commit(); cur.close(); conn.close()
    except Exception as e:
        print("PG unfollow fail:", e)
    users = get_users()
    for u in users:
        if str(u.get('email','')).lower()==target:
            u['followers'] = max(0, int(u.get('followers',0)) - 1)
            break
    save_db('users.json', users)
    new_count = len([x for x in follows if x.get('following_email','').lower()==target])
    return jsonify({'success':True,'message':'Unfollowed!','followers':new_count})

@sannlas_follow_bp.route('/api/follow/check')
def api_follow_check():
    email = request.args.get('email','').lower()
    target = request.args.get('target','').lower()
    if '@' not in target:
        target = find_shop_email(target)
    follows = get_follows()
    is_following = any(f.get('follower_email','').lower()==email and f.get('following_email','').lower()==target for f in follows)
    if not is_following:
        try:
            conn = get_conn(); cur = conn.cursor()
            cur.execute("SELECT 1 FROM sannlas_follows WHERE LOWER(follower_email)=%s AND LOWER(following_email)=%s LIMIT 1", (email, target))
            if cur.fetchone(): is_following = True
            cur.close(); conn.close()
        except: pass
    return jsonify({'is_following': is_following, 'email': target})
