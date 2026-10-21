import os, traceback, cloudinary, cloudinary.uploader, time, json
from flask import Blueprint, request, jsonify, render_template
import psycopg2

reels_bp = Blueprint('reels_bp', __name__)

cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET'),
    secure=True
)

def get_conn():
    DATABASE_URL = os.getenv('DATABASE_URL')
    return psycopg2.connect(DATABASE_URL, sslmode='require')

def ensure_reels_table():
    conn = get_conn(); cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS sannlas_reels (
      id BIGSERIAL PRIMARY KEY, 
      user_email TEXT, 
      user_name TEXT, 
      shop_name TEXT,
      shop_slug TEXT,
      caption TEXT,
      description TEXT,
      price TEXT,
      promo_link TEXT,
      location TEXT,
      hashtags TEXT,
      video_url TEXT, 
      product_link TEXT,
      product_id TEXT,
      likes INT DEFAULT 0, 
      created TIMESTAMP DEFAULT NOW())""")
    conn.commit()
    try:
        cur.execute("ALTER TABLE sannlas_reels ADD COLUMN IF NOT EXISTS shop_name TEXT")
        cur.execute("ALTER TABLE sannlas_reels ADD COLUMN IF NOT EXISTS shop_slug TEXT")
        cur.execute("ALTER TABLE sannlas_reels ADD COLUMN IF NOT EXISTS description TEXT")
        cur.execute("ALTER TABLE sannlas_reels ADD COLUMN IF NOT EXISTS price TEXT")
        cur.execute("ALTER TABLE sannlas_reels ADD COLUMN IF NOT EXISTS promo_link TEXT")
        cur.execute("ALTER TABLE sannlas_reels ADD COLUMN IF NOT EXISTS location TEXT")
        cur.execute("ALTER TABLE sannlas_reels ADD COLUMN IF NOT EXISTS hashtags TEXT")
        cur.execute("ALTER TABLE sannlas_reels ADD COLUMN IF NOT EXISTS product_id TEXT")
        conn.commit()
    except Exception as me:
        print("Migration error:", me)
    cur.close(); conn.close()

@reels_bp.route('/reels')
def reels_page():
    return render_template('reels.html')

@reels_bp.route('/api/sannlas/reels/feed')
def reels_feed():
    try:
        ensure_reels_table()
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT * FROM sannlas_reels ORDER BY id DESC LIMIT 100")
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        data = [dict(zip(cols, r)) for r in rows]

        # TRY TO GET REAL PRICE FROM PRODUCTS (JSONB)
        for reel in data:
            try:
                pid = str(reel.get('product_id') or '').strip()
                if pid:
                    cur.execute("SELECT data FROM products WHERE data->>'id' = %s OR id::text = %s LIMIT 1", (pid, pid))
                    prow = cur.fetchone()
                    if prow and prow[0]:
                        pdata = prow[0]
                        if isinstance(pdata, str):
                            pdata = json.loads(pdata)
                        reel['price'] = pdata.get('price') or reel.get('price') or 0
                        reel['product_name'] = pdata.get('name') or ''
                        reel['p_shop_slug'] = pdata.get('shop_slug') or ''
                        reel['buy_link'] = f"/product/{pid}"
                        reel['real_product_link'] = f"/shop/{pdata.get('shop_slug','')}?product={pid}"
                        reel['shop_link'] = f"/shop/{pdata.get('shop_slug','')}"
            except Exception as e:
                print(f"Product lookup fail {pid}: {e}")

        # FILL DEFAULTS FOR ALL REELS (OUTSIDE LOOP!)
        for reel in data:
            shop = reel.get('shop_name') or reel.get('user_name') or 'SANNLAS SHOP'
            reel['shop_name'] = shop
            if not reel.get('shop_slug'):
                reel['shop_slug'] = shop.lower().replace(' ','-')
            if not reel.get('shop_link'):
                reel['shop_link'] = f"/shop/{reel.get('shop_slug')}"
            if not reel.get('product_link'):
                reel['product_link'] = reel.get('promo_link') or f"/shop/{shop}"
            if not reel.get('buy_link'):
                reel['buy_link'] = reel.get('product_link')
            if not reel.get('price'):
                reel['price'] = 0

        cur.close(); conn.close()
        return jsonify(data)
    except Exception as e:
        print("FEED ERROR:", e)
        traceback.print_exc()
        return jsonify([])

@reels_bp.route('/api/sannlas/reels/upload', methods=['POST'])
def upload_reel():
    try:
        print("=== REELS UPLOAD START ===")
        video = request.files.get('video')
        if not video:
            return jsonify({'success':False, 'error':'No video file'}),400
        
        shop_name = request.form.get('shop_name') or request.form.get('business_name') or 'SANNLAS SHOP'
        shop_slug = (request.form.get('shop_slug') or shop_name).lower().replace(' ','-')
        description = request.form.get('description', '')
        caption = request.form.get('caption', description)
        price = request.form.get('price', '0')
        product_id = request.form.get('product_id', '')
        promo_link = request.form.get('promo_link', '') or request.form.get('product_link', '')
        product_link = promo_link or f"/product/{product_id}" if product_id else f"/shop/{shop_slug}"
        location = request.form.get('location', 'Uganda')
        hashtags = request.form.get('hashtags', '')
        user_email = request.form.get('user_email','anon')
        user_name = shop_name
        
        print(f"Uploading: Shop={shop_name}, ProductID={product_id}, Price={price}")
        result = cloudinary.uploader.upload(video, resource_type="video", folder="sannlas_reels", chunk_size=6000000, timeout=120)
        video_url = result.get('secure_url')
        
        conn = get_conn(); cur = conn.cursor()
        ensure_reels_table()
        
        # FIXED: 13 columns = 13 %s
        cur.execute("""
            INSERT INTO sannlas_reels 
            (user_email, user_name, shop_name, shop_slug, caption, description, price, promo_link, location, hashtags, video_url, product_link, product_id) 
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (user_email, user_name, shop_name, shop_slug, caption, description, price, promo_link, location, hashtags, video_url, product_link, product_id))
        conn.commit(); cur.close(); conn.close()
        print(f"DB SAVED OK")
        return jsonify({'success':True, 'url': video_url, 'shop_link': f'/shop/{shop_slug}'})
        
    except Exception as e:
        print("=== UPLOAD ERROR ===")
        traceback.print_exc()
        return jsonify({'success':False, 'error': str(e)}), 500

@reels_bp.route('/api/sannlas/reels/like/<int:rid>', methods=['POST'])
def like_reel(rid):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("UPDATE sannlas_reels SET likes = likes + 1 WHERE id=%s", (rid,))
        conn.commit(); cur.close(); conn.close()
        return jsonify({'success':True})
    except Exception as e:
        return jsonify({'success':False})
