import os, traceback, json, time, re
from flask import Blueprint, request, jsonify, render_template, send_from_directory
import psycopg2

reels_bp = Blueprint('reels_bp', __name__)

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

def ensure_reels_table():
    conn = get_conn(); cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS sannlas_reels (
      id BIGSERIAL PRIMARY KEY, 
      user_email TEXT, user_name TEXT, shop_name TEXT, shop_slug TEXT,
      caption TEXT, description TEXT, price TEXT, promo_link TEXT,
      location TEXT, hashtags TEXT, video_url TEXT, 
      product_link TEXT, product_id TEXT, likes INT DEFAULT 0, 
      created TIMESTAMP DEFAULT NOW())""")
    conn.commit()
    cur.close(); conn.close()

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

@reels_bp.route('/api/sannlas/reels/feed')
def reels_feed():
    try:
        ensure_reels_table()
        products_map = load_products_json()
        
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT * FROM sannlas_reels ORDER BY id DESC LIMIT 100")
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        data = [dict(zip(cols, r)) for r in rows]

        for reel in data:
            try:
                pid = str(reel.get('product_id') or '').strip()
                shop = reel.get('shop_name') or reel.get('user_name') or 'SANNLAS SHOP'
                slug = clean_slug(reel.get('shop_slug') or shop)
                
                reel['shop_name'] = shop
                reel['shop_slug'] = slug

                product_data = None
                if pid and pid in products_map:
                    product_data = products_map[pid]

                if product_data:
                    raw_coins = product_data.get('promo_coins') or product_data.get('promo_commission') or product_data.get('promo_comm') or 3
                    try:
                        promo_coins = int(float(str(raw_coins).strip()))
                    except:
                        promo_coins = 3
                else:
                    promo_coins = 3

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

        cur.close(); conn.close()
        return jsonify(data)
    except Exception as e:
        print("FEED ERROR:", e)
        traceback.print_exc()
        return jsonify([])

# ===== NEW: USER PROFILE API - TIKTOK STYLE =====
@reels_bp.route('/api/sannlas/reels/user/<shop_slug>')
def get_user_reels(shop_slug):
    try:
        ensure_reels_table()
        products_map = load_products_json()
        conn = get_conn(); cur = conn.cursor()
        
        # Clean the incoming slug too!
        incoming = clean_slug(shop_slug)
        
        cur.execute("SELECT * FROM sannlas_reels ORDER BY id DESC LIMIT 200")
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        all_data = [dict(zip(cols, r)) for r in rows]

        # Filter in Python to catch Sann%202 == sann-2
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

@reels_bp.route('/api/sannlas/reels/like/<int:rid>', methods=['POST'])
def like_reel(rid):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("UPDATE sannlas_reels SET likes = likes + 1 WHERE id=%s", (rid,))
        conn.commit(); cur.close(); conn.close()
        return jsonify({'success':True})
    except Exception as e:
        print("LIKE ERROR", e)
        return jsonify({'success':False})
