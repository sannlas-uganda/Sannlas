# shop.py - SANNLAS SHOP CORE - Extracted from app.py
# Contains ONLY shop helpers + /api/shops that were in app.py
# shops.py + my_shop.py already handle the rest!
from flask import Blueprint, jsonify, request
import re, time

shop_bp = Blueprint('shop_bp', __name__)

# ===== HELPERS - Moved from app.py =====
def make_shop_slug(business):
    if not business: return 'shop'
    base = re.sub(r'[^a-z0-9]+', '-', business.lower()).strip('-')
    if not base: base = 'shop'
    return base[:50]

def get_biz_key(name):
    if not name: return ''
    return re.sub(r'[^a-z0-9]+', '', name.lower())

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

# ===== /api/shops - Moved from app.py =====
@shop_bp.route('/api/shops')
def list_shops():
    from app import load_db, get_conn, DATABASE_URL
    import json, os
    try:
        shops = load_db('shops.json', [])
        if DATABASE_URL:
            try:
                conn = get_conn()
                cur = conn.cursor()
                cur.execute("SELECT data->>'shop_slug' as slug, COUNT(*) as cnt FROM products WHERE data->>'shop_slug' IS NOT NULL GROUP BY slug")
                rows = cur.fetchall()
                counts = {}
                for r in rows:
                    if isinstance(r, dict):
                        counts[r['slug']] = int(r['cnt'])
                    else:
                        counts[str(r[0])] = int(r[1])
                cur.close()
                conn.close()
            except Exception as e:
                print("shops fast count error:", e)
                counts = {}
                try: conn.close()
                except: pass
        else:
            try:
                path = 'data/products.json'
                if os.path.exists(path):
                    data = json.load(open(path))
                    counts = {}
                    for p in data:
                        slug = p.get('shop_slug')
                        if slug:
                            counts[slug] = counts.get(slug, 0) + 1
                else:
                    counts = {}
            except:
                counts = {}
        for s in shops:
            slug = s.get('shop_slug')
            s['total_products'] = counts.get(slug, 0)
        filtered = [s for s in shops if s.get('total_products',0)>0]
        if not filtered:
            filtered = shops[:50]
        return jsonify(sorted(filtered, key=lambda x: x.get('total_products',0), reverse=True)[:100])
    except Exception as e:
        print("SHOPS ERROR:", e)
        try:
            shops = load_db('shops.json', [])[:50]
            return jsonify(shops)
        except:
            return jsonify([])
