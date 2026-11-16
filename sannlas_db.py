# sannlas_db.py - YOUR OWN DATABASE - Step 1: Products only
import sqlite3, os, json, time

DB_FILE = "sannlas.db"

def get_sannlas_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_sannlas_db():
    conn = get_sannlas_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
        name TEXT,
        price INTEGER DEFAULT 0,
        original_price INTEGER DEFAULT 0,
        business TEXT,
        location TEXT,
        phone TEXT,
        seller_email TEXT,
        description TEXT,
        image TEXT,
        images_json TEXT,
        main_category TEXT,
        smart_keywords TEXT,
        stock INTEGER DEFAULT 10,
        sold INTEGER DEFAULT 0,
        rating REAL DEFAULT 5,
        shop_id INTEGER,
        shop_slug TEXT,
        promo_commission INTEGER DEFAULT 3,
        created REAL
    )''')
    conn.commit()
    conn.close()
    print("✅ sannlas.db - products table ready!")

# --- ADD / DELETE / EDIT - You asked Boss! ---
def add_product_db(p):
    conn = get_sannlas_db()
    conn.execute('''INSERT OR REPLACE INTO products
        (id, name, price, original_price, business, location, phone, seller_email,
         description, image, images_json, main_category, smart_keywords,
         stock, sold, rating, shop_id, shop_slug, promo_commission, created)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
        (p.get('id', int(time.time()*1000)), p.get('name'), p.get('price',0),
         p.get('original_price', p.get('price',0)), p.get('business'),
         p.get('location'), p.get('phone'), p.get('seller_email'),
         p.get('description',''), p.get('image',''),
         json.dumps(p.get('images',[])), p.get('main_category'),
         p.get('smart_keywords',''), p.get('stock',10), p.get('sold',0),
         p.get('rating',5), p.get('shop_id'), p.get('shop_slug'),
         p.get('promo_commission',3), p.get('created', time.time())))
    conn.commit(); conn.close()

def delete_product_db(pid):
    conn = get_sannlas_db()
    conn.execute("DELETE FROM products WHERE id=?", (pid,))
    conn.commit(); conn.close()

def get_all_products_db():
    conn = get_sannlas_db()
    rows = conn.execute("SELECT * FROM products ORDER BY created DESC").fetchall()
    conn.close()
    out=[]
    for r in rows:
        d=dict(r)
        try: d['images']=json.loads(d['images_json'] or '[]')
        except: d['images']=[d.get('image','')]
        d['reviews']=[]
        out.append(d)
    return out

if __name__ == "__main__":
    init_sannlas_db()
