# sannlas_reels.py - SANNLAS REELS MODULE (Separate from KASSAG)
import os
import cloudinary.uploader
from flask import Blueprint, request, jsonify, render_template
import psycopg2

reels_bp = Blueprint('reels', __name__)
DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("NEON_DATABASE_URL")

def get_conn():
    try:
        import psycopg
        return psycopg.connect(DATABASE_URL, sslmode='require', connect_timeout=10)
    except:
        return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=10)

@reels_bp.route('/reels')
def reels_page():
    return render_template('reels.html')

@reels_bp.route('/api/sannlas/reels/upload', methods=['POST'])
def upload_reel():
    try:
        video = request.files.get('video')
        if not video: return jsonify({'success':False, 'error':'No video'}),400
        caption = request.form.get('caption','')
        user_email = request.form.get('user_email','anonymous')
        user_name = request.form.get('user_name','User')
        product_link = request.form.get('product_link','')
        result = cloudinary.uploader.upload(video, resource_type="video", folder="sannlas_reels", chunk_size=6000000)
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS sannlas_reels (
          id BIGSERIAL PRIMARY KEY, user_email TEXT, user_name TEXT, caption TEXT,
          video_url TEXT NOT NULL, product_link TEXT, likes INT DEFAULT 0, created TIMESTAMP DEFAULT NOW())""")
        conn.commit()
        cur.execute("INSERT INTO sannlas_reels (user_email, user_name, caption, video_url, product_link) VALUES (%s,%s,%s,%s,%s)",
                    (user_email, user_name, caption, result['secure_url'], product_link))
        conn.commit(); cur.close(); conn.close()
        return jsonify({'success':True, 'url': result['secure_url']})
    except Exception as e:
        return jsonify({'success':False, 'error': str(e)}),500

@reels_bp.route('/api/sannlas/reels/feed')
def feed_reels():
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT id, user_email, user_name, caption, video_url, product_link, likes FROM sannlas_reels ORDER BY created DESC LIMIT 50")
        rows = cur.fetchall(); cur.close(); conn.close()
        return jsonify([{"id":r[0], "user_email":r[1], "user_name":r[2], "caption":r[3], "video_url":r[4], "product_link":r[5], "likes":r[6]} for r in rows])
    except: return jsonify([])

@reels_bp.route('/api/sannlas/reels/like/<int:reel_id>', methods=['POST'])
def like_reel(reel_id):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("UPDATE sannlas_reels SET likes = likes + 1 WHERE id=%s", (reel_id,))
        conn.commit(); cur.close(); conn.close()
        return jsonify({'success':True})
    except: return jsonify({'success':False}),500# sannlas_reels.py - SANNLAS REELS MODULE (Separate from KASSAG)
import os
import cloudinary.uploader
from flask import Blueprint, request, jsonify, render_template
import psycopg2

reels_bp = Blueprint('reels', __name__)
DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("NEON_DATABASE_URL")

def get_conn():
    try:
        import psycopg
        return psycopg.connect(DATABASE_URL, sslmode='require', connect_timeout=10)
    except:
        return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=10)

@reels_bp.route('/reels')
def reels_page():
    return render_template('reels.html')

@reels_bp.route('/api/sannlas/reels/upload', methods=['POST'])
def upload_reel():
    try:
        video = request.files.get('video')
        if not video: return jsonify({'success':False, 'error':'No video'}),400
        caption = request.form.get('caption','')
        user_email = request.form.get('user_email','anonymous')
        user_name = request.form.get('user_name','User')
        product_link = request.form.get('product_link','')
        result = cloudinary.uploader.upload(video, resource_type="video", folder="sannlas_reels", chunk_size=6000000)
        conn = get_conn(); cur = conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS sannlas_reels (
          id BIGSERIAL PRIMARY KEY, user_email TEXT, user_name TEXT, caption TEXT,
          video_url TEXT NOT NULL, product_link TEXT, likes INT DEFAULT 0, created TIMESTAMP DEFAULT NOW())""")
        conn.commit()
        cur.execute("INSERT INTO sannlas_reels (user_email, user_name, caption, video_url, product_link) VALUES (%s,%s,%s,%s,%s)",
                    (user_email, user_name, caption, result['secure_url'], product_link))
        conn.commit(); cur.close(); conn.close()
        return jsonify({'success':True, 'url': result['secure_url']})
    except Exception as e:
        return jsonify({'success':False, 'error': str(e)}),500

@reels_bp.route('/api/sannlas/reels/feed')
def feed_reels():
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("SELECT id, user_email, user_name, caption, video_url, product_link, likes FROM sannlas_reels ORDER BY created DESC LIMIT 50")
        rows = cur.fetchall(); cur.close(); conn.close()
        return jsonify([{"id":r[0], "user_email":r[1], "user_name":r[2], "caption":r[3], "video_url":r[4], "product_link":r[5], "likes":r[6]} for r in rows])
    except: return jsonify([])

@reels_bp.route('/api/sannlas/reels/like/<int:reel_id>', methods=['POST'])
def like_reel(reel_id):
    try:
        conn = get_conn(); cur = conn.cursor()
        cur.execute("UPDATE sannlas_reels SET likes = likes + 1 WHERE id=%s", (reel_id,))
        conn.commit(); cur.close(); conn.close()
        return jsonify({'success':True})
    except: return jsonify({'success':False}),500
