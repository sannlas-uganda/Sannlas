import os, traceback, cloudinary, cloudinary.uploader, time
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

@reels_bp.route('/reels')
def reels_page():
    return render_template('reels.html')

@reels_bp.route('/api/sannlas/reels/feed')
def reels_feed():
    try:
        conn = get_conn(); cur = conn.cursor()
        # AUTO-ADD NEW COLUMNS IF NOT EXIST
        try:
            cur.execute("ALTER TABLE sannlas_reels ADD COLUMN IF NOT EXISTS shop_name TEXT")
            cur.execute("ALTER TABLE sannlas_reels ADD COLUMN IF NOT EXISTS description TEXT")
            cur.execute("ALTER TABLE sannlas_reels ADD COLUMN IF NOT EXISTS price TEXT")
            cur.execute("ALTER TABLE sannlas_reels ADD COLUMN IF NOT EXISTS promo_link TEXT")
            cur.execute("ALTER TABLE sannlas_reels ADD COLUMN IF NOT EXISTS location TEXT")
            cur.execute("ALTER TABLE sannlas_reels ADD COLUMN IF NOT EXISTS hashtags TEXT")
            cur.execute("ALTER TABLE sannlas_reels ADD COLUMN IF NOT EXISTS shop_slug TEXT")
            conn.commit()
        except:
            pass
        
        cur.execute("SELECT * FROM sannlas_reels ORDER BY id DESC LIMIT 100")
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        data = [dict(zip(cols, r)) for r in rows]
        
        # ADD SHOP LINK FOR STYLE 1
        for reel in data:
            shop = reel.get('shop_name') or reel.get('user_name') or 'SANNLAS SHOP'
            reel['shop_name'] = shop
            reel['shop_slug'] = reel.get('shop_slug') or shop
            reel['shop_link'] = f"/shop/{shop}"
            reel['user_name'] = shop
            # Keep backward compatible
            if not reel.get('product_link'):
                reel['product_link'] = reel.get('promo_link') or f"/shop/{shop}"
        
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
            return jsonify({'success':False, 'error':'No video file received'}),400
        
        print(f"File: {video.filename}")
        
        # ===== NEW - ALL YOUR UPLOAD FORM FIELDS =====
        shop_name = request.form.get('shop_name') or request.form.get('business_name') or request.form.get('shop_slug') or request.form.get('user_name') or 'SANNLAS SHOP'
        shop_slug = request.form.get('shop_slug') or shop_name
        description = request.form.get('description', '')
        caption = request.form.get('caption', description)
        price = request.form.get('price', '0')
        promo_link = request.form.get('promo_link', '') or request.form.get('product_link', '')
        product_link = promo_link or f"/shop/{shop_slug}"
        location = request.form.get('location', 'Uganda')
        hashtags = request.form.get('hashtags', '')
        user_email = request.form.get('user_email','anon')
        user_name = shop_name
        
        print(f"Shop: {shop_name}, Price: {price}, Promo: {promo_link}")
        print("Uploading to Cloudinary...")
        
        result = cloudinary.uploader.upload(
            video, 
            resource_type="video", 
            folder="sannlas_reels",
            chunk_size=6000000,
            timeout=120
        )
        video_url = result.get('secure_url')
        print("Cloudinary OK:", video_url)
        
        conn = get_conn(); cur = conn.cursor()
        
        # CREATE TABLE WITH ALL NEW COLUMNS
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
          likes INT DEFAULT 0, 
          created TIMESTAMP DEFAULT NOW())""")
        conn.commit()
        
        # AUTO-MIGRATE OLD TABLE
        try:
            cur.execute("ALTER TABLE sannlas_reels ADD COLUMN IF NOT EXISTS shop_name TEXT")
            cur.execute("ALTER TABLE sannlas_reels ADD COLUMN IF NOT EXISTS shop_slug TEXT")
            cur.execute("ALTER TABLE sannlas_reels ADD COLUMN IF NOT EXISTS description TEXT")
            cur.execute("ALTER TABLE sannlas_reels ADD COLUMN IF NOT EXISTS price TEXT")
            cur.execute("ALTER TABLE sannlas_reels ADD COLUMN IF NOT EXISTS promo_link TEXT")
            cur.execute("ALTER TABLE sannlas_reels ADD COLUMN IF NOT EXISTS location TEXT")
            cur.execute("ALTER TABLE sannlas_reels ADD COLUMN IF NOT EXISTS hashtags TEXT")
            conn.commit()
        except Exception as me:
            print("Migration error:", me)
        
        cur.execute("""
            INSERT INTO sannlas_reels 
            (user_email, user_name, shop_name, shop_slug, caption, description, price, promo_link, location, hashtags, video_url, product_link) 
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (user_email, user_name, shop_name, shop_slug, caption, description, price, promo_link, location, hashtags, video_url, product_link))
        conn.commit(); cur.close(); conn.close()
        print(f"DB SAVED OK - Shop: {shop_name}")
        return jsonify({'success':True, 'url': video_url, 'shop_name': shop_name, 'shop_link': f'/shop/{shop_name}'})
        
    except Exception as e:
        print("=== UPLOAD ERROR ===")
        traceback.print_exc()
        return jsonify({'success':False, 'error': str(e)}), 500
