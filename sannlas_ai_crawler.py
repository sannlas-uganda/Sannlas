# sannlas_ai_crawler.py - A+B+C - WITH PRODUCTS & SHOPS AUTO
from flask import Blueprint, request, jsonify
import os, json, re
import urllib.request
from html.parser import HTMLParser

crawler_bp = Blueprint('crawler', __name__)

DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def get_conn():
    if not DATABASE_URL: return None
    try:
        import psycopg
        return psycopg.connect(DATABASE_URL, sslmode='require', connect_timeout=8)
    except:
        try:
            import psycopg2
            return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=8)
        except: return None

def load_knowledge():
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT data FROM kv_store WHERE key='ai_knowledge.json' LIMIT 1")
        row = cur.fetchone()
        cur.close()
        conn.close()
        if not row: return []
        d = row[0]
        if isinstance(d, str):
            try: d = json.loads(d)
            except: return []
        return d if isinstance(d, list) else []
    except: return []

def save_knowledge(data_list):
    try:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("CREATE TABLE IF NOT EXISTS kv_store (key TEXT PRIMARY KEY, data JSONB)")
        cur.execute("INSERT INTO kv_store (key, data) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET data = %s", 
                   ('ai_knowledge.json', json.dumps(data_list), json.dumps(data_list)))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Save error {e}")
        return False

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.texts = []
        self.skip = False
    def handle_starttag(self, tag, attrs):
        if tag in ['script', 'style']:
            self.skip = True
    def handle_endtag(self, tag):
        if tag in ['script', 'style']:
            self.skip = False
    def handle_data(self, data):
        if not self.skip and data.strip():
            if len(data.strip()) > 3:
                self.texts.append(data.strip())

def extract_text_from_html(html):
    parser = TextExtractor()
    parser.feed(html)
    return "\n".join(parser.texts)

@crawler_bp.route('/api/admin/crawl/auto', methods=['GET'])
def auto_crawl():
    try:
        all_qa = load_knowledge()
        default_qa = [
            {"question": "What is Sannlas?", "answer": "Sannlas is Uganda's marketplace! Buy & sell anything - shoes, phones, watches, bags, groceries in Kampala & Kawempe! 🛍️", "category": "general", "keywords": ["what", "sannlas"]},
            {"question": "How to buy on Sannlas?", "answer": "Search product → Tap it → Add to Cart → Checkout → Pay MTN/Airtel or Cash on Delivery → Delivered in 1-2 days! 🛒", "category": "buying", "keywords": ["how", "buy"]},
            {"question": "How to sell on Sannlas?", "answer": "FREE 14 days! Tap SELL → Upload photo → Set price & location → Post! Start selling now! 🚀", "category": "selling", "keywords": ["how", "sell"]},
            {"question": "What payment methods does Sannlas accept?", "answer": "MTN Mobile Money, Airtel Money, and Cash on Delivery! Safe & easy! 💰", "category": "payment", "keywords": ["payment", "mtn", "airtel"]},
            {"question": "How long does delivery take?", "answer": "1-2 days in Kampala & Kawempe! Delivery fee ~5k-10k UGX! We call before delivery! 🚚", "category": "delivery", "keywords": ["delivery", "time"]},
            {"question": "What products are on Sannlas?", "answer": "Shoes, watches, bags, phones, clothes, Royco, Maize Flour, TIV Rice, groceries & more! 31+ products! Tell me what you need! 🛍️", "category": "products", "keywords": ["products", "what"]},
            {"question": "What shops are on Sannlas?", "answer": "Shops in Kampala & Kawempe! Like Kafeco shop in Kampala with many products! Search shops in Kampala! 🛍️", "category": "shops", "keywords": ["shops", "store"]},
            {"question": "Is selling free on Sannlas?", "answer": "YES! FREE for 14 days! After that small fee! Start selling now - tap SELL button! 🎉", "category": "selling", "keywords": ["free", "selling"]},
            {"question": "What are Sannlas coins?", "answer": "Coins are rewards! Earn by selling & sharing products! Use coins to boost your products to top! 💰", "category": "coins", "keywords": ["coins", "coin"]},
            {"question": "How to contact seller?", "answer": "Go to shop page and tap Contact or Call button! Seller will be notified! You can also chat! 📞", "category": "general", "keywords": ["contact", "seller"]},
            {"question": "What is Kassag?", "answer": "Kassag is group savings! Save money together with friends weekly! Like village savings! 👥", "category": "general", "keywords": ["kassag"]},
            {"question": "Can I return product?", "answer": "Yes! Return within 2 days if product not as described! Contact seller directly! 🔄", "category": "general", "keywords": ["return", "refund"]},
            {"question": "Where is Sannlas located?", "answer": "Online! But shops in Kampala, Kawempe, Wakiso! We deliver in Kampala & Kawempe! 📍", "category": "general", "keywords": ["location", "where"]},
            {"question": "How to create shop?", "answer": "Sell one product and shop auto-created! Your shop will show in shops list! Add logo & description! 🏪", "category": "shops", "keywords": ["create", "shop"]},
            {"question": "Do you have shoes?", "answer": "Yes! Chunky black shoes, sneakers, boots, heels! Search 'shoes' or 'Chunky shoes' UGX 125k! 👟", "category": "products", "keywords": ["shoes"]},
            {"question": "Do you have watches?", "answer": "Yes! Watches available! Search 'watches' - many styles in Kampala shops! ⌚", "category": "products", "keywords": ["watches", "watch"]},
            {"question": "Do you have bags?", "answer": "Yes! Handbags, backpacks, ladies bags! Search 'bags' in Kampala! 👜", "category": "products", "keywords": ["bags", "bag"]},
            {"question": "Do you have phones?", "answer": "Yes! iPhones, Samsung, Tecno, Infinix! Search 'phones' - affordable! 📱", "category": "products", "keywords": ["phones", "phone"]},
            {"question": "What is billboard?", "answer": "Billboard is top ads on homepage! Promote your product to get more views! More customers! 📢", "category": "general", "keywords": ["billboard"]},
            {"question": "What is promotion?", "answer": "Promote your product to get more customers! Use coins to boost to top! 🚀", "category": "general", "keywords": ["promotion", "promo"]},
            {"question": "How to earn coins?", "answer": "Earn coins by selling products, sharing products, daily login! Spin wheel to win coins! 💰", "category": "coins", "keywords": ["earn", "coins"]},
            {"question": "What is spin?", "answer": "Spin the wheel daily to win coins! Free coins every day! Try your luck! 🎡", "category": "coins", "keywords": ["spin"]},
            {"question": "Is Sannlas safe?", "answer": "Yes! Safe! Secure payments, verified shops, cash on delivery option! Shop with confidence! ✅", "category": "general", "keywords": ["safe", "secure"]},
            {"question": "How to track order?", "answer": "After order, seller calls you! Delivery in 1-2 days! Check notifications for updates! 📦", "category": "delivery", "keywords": ["track", "order"]},
            {"question": "What is Royco?", "answer": "Royco is seasoning! Available on Sannlas - Mchuzi Mix, Beef flavor! Search 'Royco'! 🍲", "category": "products", "keywords": ["royco"]},
        ]
        existing_q = set([k.get('question','').lower() for k in all_qa])
        added = 0
        for qa in default_qa:
            if qa['question'].lower() not in existing_q:
                qa['id'] = len(all_qa) + 1
                all_qa.append(qa)
                existing_q.add(qa['question'].lower())
                added += 1
        save_knowledge(all_qa)
        return jsonify({'success': True, 'total_qa': len(all_qa), 'new_added': added, 'message': f'✅ Loaded {len(all_qa)} Q&A! {added} new!', 'data': all_qa[-5:]})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@crawler_bp.route('/api/admin/crawl/products', methods=['POST'])
def crawl_products():
    """B) AUTO-ADD PRODUCTS Q&A from Neon DB"""
    try:
        all_qa = load_knowledge()
        existing_q = set([k.get('question','').lower() for k in all_qa])
        added = 0
        conn = get_conn()
        if conn:
            cur = conn.cursor()
            cur.execute("SELECT data FROM products ORDER BY id DESC LIMIT 100")
            rows = cur.fetchall()
            cur.close()
            conn.close()
            for r in rows:
                d = r[0]
                if isinstance(d, str):
                    try: d = json.loads(d)
                    except: continue
                if not isinstance(d, dict): continue
                name = d.get('name','').strip()
                if not name: continue
                price = d.get('price','')
                loc = d.get('location','Kampala')
                # 2 Q&A per product
                q1 = f"Do you have {name}?"
                q2 = f"How much is {name}?"
                if q1.lower() not in existing_q:
                    all_qa.append({
                        'id': len(all_qa)+1,
                        'question': q1,
                        'answer': f"Yes! {name} - UGX {price} - Available in {loc}! Search '{name}' on Sannlas to buy! 🛍️",
                        'category': 'products',
                        'keywords': name.lower().split()[:5],
                        'source': 'products table auto'
                    })
                    existing_q.add(q1.lower())
                    added += 1
                if q2.lower() not in existing_q:
                    all_qa.append({
                        'id': len(all_qa)+1,
                        'question': q2,
                        'answer': f"{name} costs UGX {price} in {loc}! Tap to buy - Cash on Delivery or Mobile Money! 💰",
                        'category': 'products',
                        'keywords': name.lower().split()[:5],
                        'source': 'products table auto'
                    })
                    existing_q.add(q2.lower())
                    added += 1
        save_knowledge(all_qa)
        return jsonify({'success': True, 'total_qa': len(all_qa), 'new_added': added, 'message': f'Added {added} products Q&A!'})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@crawler_bp.route('/api/admin/crawl/shops', methods=['POST'])
def crawl_shops():
    """Auto-add shops Q&A"""
    try:
        all_qa = load_knowledge()
        existing_q = set([k.get('question','').lower() for k in all_qa])
        added = 0
        conn = get_conn()
        if conn:
            cur = conn.cursor()
            try:
                cur.execute("SELECT data FROM shops ORDER BY id DESC LIMIT 50")
                rows = cur.fetchall()
            except:
                cur.execute("SELECT DISTINCT data->>'shop_name', data->>'location' FROM products WHERE data->>'shop_name' IS NOT NULL LIMIT 20")
                rows = cur.fetchall()
            cur.close()
            conn.close()
            for r in rows:
                d = r[0]
                if isinstance(d, dict):
                    shop = d.get('shop_name') or d.get('name') or 'Shop'
                    loc = d.get('location','Kampala')
                elif isinstance(d, str):
                    try:
                        jd = json.loads(d)
                        shop = jd.get('shop_name') or jd.get('name') or d[:30]
                        loc = jd.get('location','Kampala')
                    except:
                        shop = d[:30]
                        loc = 'Kampala'
                else:
                    continue
                q = f"What about {shop} shop?"
                if q.lower() not in existing_q and shop:
                    all_qa.append({
                        'id': len(all_qa)+1,
                        'question': q,
                        'answer': f"{shop} is in {loc}! Visit shop on Sannlas to see all products! 🛍️",
                        'category': 'shops',
                        'keywords': [shop.lower(), 'shop'],
                        'source': 'shops auto'
                    })
                    existing_q.add(q.lower())
                    added += 1
        save_knowledge(all_qa)
        return jsonify({'success': True, 'total_qa': len(all_qa), 'new_added': added})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@crawler_bp.route('/api/admin/crawl', methods=['POST'])
def crawl_website():
    try:
        data = request.get_json(silent=True) or {}
        base = data.get('base_url', 'https://sannlas.onrender.com')
        all_qa = load_knowledge()
        existing_q = set([k.get('question','').lower() for k in all_qa])
        try:
            req = urllib.request.Request(base, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                html = resp.read().decode('utf-8', errors='ignore')
                text = extract_text_from_html(html)
                for line in text.split('\n'):
                    line = line.strip()
                    if 10 < len(line) < 150 and ('?' in line or line.lower().startswith(('how','what','where','can','do','is'))):
                        if line.lower() not in existing_q:
                            all_qa.append({'id': len(all_qa)+1, 'question': line[:150], 'answer': f"Yes! {line} - Check Sannlas.com! 🛍️", 'category': 'auto', 'keywords': line.lower().split()[:5], 'source': base})
                            existing_q.add(line.lower())
        except Exception as e:
            print(f"Crawl error {e}")
        save_knowledge(all_qa)
        return jsonify({'success': True, 'total_qa': len(all_qa), 'crawled': base})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
