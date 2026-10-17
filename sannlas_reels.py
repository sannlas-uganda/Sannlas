import os, traceback, cloudinary, cloudinary.uploader
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
        cur.execute("SELECT id, user_email, user_name, caption, video_url, product_link, likes, created FROM sannlas_reels ORDER BY id DESC LIMIT 100")
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]
        data = [dict(zip(cols, r)) for r in rows]
        cur.close(); conn.close()
        return jsonify(data)
    except Exception as e:
        print("FEED ERROR:", e)
        return jsonify([])

@reels_bp.route('/api/sannlas/reels/upload', methods=['POST'])
def upload_reel():
    try:
        print("=== REELS UPLOAD START ===")
        video = request.files.get('video')
        if not video:
            return jsonify({'success':False, 'error':'No video file received'}),400
        
        print(f"File: {video.filename}, Content-Type: {video.content_type}")
        
        caption = request.form.get('caption','')
        user_email = request.form.get('user_email','anon')
        user_name = request.form.get('user_name','User')
        product_link = request.form.get('product_link','')
        
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
        cur.execute("""CREATE TABLE IF NOT EXISTS sannlas_reels (
          id BIGSERIAL PRIMARY KEY, user_email TEXT, user_name TEXT, caption TEXT,
          video_url TEXT, product_link TEXT, likes INT DEFAULT 0, created TIMESTAMP DEFAULT NOW())""")
        conn.commit()
        cur.execute("INSERT INTO sannlas_reels (user_email, user_name, caption, video_url, product_link) VALUES (%s,%s,%s,%s,%s)",
                    (user_email, user_name, caption, video_url, product_link))
        conn.commit(); cur.close(); conn.close()
        print("DB SAVED OK")
        return jsonify({'success':True, 'url': video_url})
        
    except Exception as e:
        print("=== UPLOAD ERROR ===")
        traceback.print_exc()
        return jsonify({'success':False, 'error': str(e)}), 500
