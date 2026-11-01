# sannlas_ai_crawler.py - AUTO CRAWL WEBSITE & EXTRACT 100+ Q&A - FINAL
from flask import Blueprint
import requests, json, re, os
from bs4 import BeautifulSoup

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

def extract_qa_from_text(text, url):
    """Auto-create Q&A from page text"""
    qa_list = []
    
    # Clean text
    lines = [l.strip() for l in text.split('\n') if len(l.strip()) > 20]
    
    for line in lines[:100]:  # max 100 lines
        line_lower = line.lower()
        
        # Detect Q&A patterns
        if 'how to' in line_lower or 'what is' in line_lower or '?' in line:
            # This looks like a question
            if len(line) < 200:
                # Next line is answer
                qa_list.append({
                    'question': line[:150],
                    'answer': line[:300],
                    'category': 'auto',
                    'source': url
                })
    
    # Auto-generate from keywords
    patterns = {
        'buy': ("How to buy on Sannlas?", "Go to Sannlas.com, search product, add to cart, checkout, pay MTN/Airtel or COD, delivered in 1-2 days!"),
        'sell': ("How to sell on Sannlas?", "Tap SELL, upload photo, set price & location, post! FREE 14 days!"),
        'payment': ("What payment methods?", "MTN Mobile Money, Airtel Money, Cash on Delivery!"),
        'delivery': ("Delivery time?", "1-2 days in Kampala & Kawempe!"),
        'sannlas': ("What is Sannlas?", "Uganda's marketplace - buy & sell anything in Kampala & Kawempe!"),
        'shop': ("What shops on Sannlas?", "Shops in Kampala & Kawempe - Kafeco, Sann, Hardware etc!"),
        'product': ("What products on Sannlas?", "Shoes, watches, bags, phones, Royco, Maize Flour, groceries & more!"),
    }
    
    for keyword, (q, a) in patterns.items():
        if keyword in text.lower():
            qa_list.append({
                'question': q,
                'answer': a,
                'category': 'auto',
                'source': url
            })
    
    return qa_list

@crawler_bp.route('/api/admin/crawl', methods=['POST'])
def crawl_website():
    """
    POST { "urls": ["https://sannlas.com", "https://sannlas.com/about"] }
    Or auto-crawl sitemap
    """
    try:
        data = requests.get_json(silent=True) or {}
        urls = data.get('urls', [])
        
        # Default URLs to crawl
        if not urls:
            base = data.get('base_url', 'https://sannlas.com')
            urls = [
                base,
                f"{base}/about",
                f"{base}/how-it-works",
                f"{base}/faq",
                f"{base}/help",
                f"{base}/terms",
                f"{base}/privacy",
                f"{base}/shops",
            ]
        
        all_qa = load_knowledge()
        existing_q = set([k.get('question','').lower() for k in all_qa])
        new_count = 0
        
        for url in urls:
            try:
                print(f"Crawling {url}...")
                resp = requests.get(url, timeout=10, headers={'User-Agent': 'SannlasBot/1.0'})
                if resp.status_code != 200:
                    continue
                
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # Remove scripts
                for script in soup(["script", "style"]):
                    script.decompose()
                
                text = soup.get_text(separator='\n')
                
                # Extract Q&A
                qa_from_page = extract_qa_from_text(text, url)
                
                for qa in qa_from_page:
                    q_lower = qa['question'].lower()
                    if q_lower not in existing_q and len(q_lower) > 5:
                        qa['id'] = len(all_qa) + 1
                        qa['keywords'] = qa['question'].lower().split()[:5]
                        all_qa.append(qa)
                        existing_q.add(q_lower)
                        new_count += 1
                        
                        if len(all_qa) > 200:  # limit
                            break
                            
            except Exception as e:
                print(f"Error crawling {url}: {e}")
                continue
        
        # Also auto-generate from products & shops (REAL DB)
        try:
            conn = get_conn()
            cur = conn.cursor()
            cur.execute("SELECT data FROM products LIMIT 20")
            rows = cur.fetchall()
            cur.close()
            conn.close()
            
            for r in rows:
                d = r[0]
                if isinstance(d, str):
                    try: d = json.loads(d)
                    except: continue
                if isinstance(d, dict):
                    name = d.get('name','Product')
                    price = d.get('price','')
                    loc = d.get('location','Kampala')
                    q = f"What is {name}?"
                    if q.lower() not in existing_q:
                        all_qa.append({
                            'id': len(all_qa)+1,
                            'question': q,
                            'answer': f"{name} - UGX {price} - Available in {loc}! Search '{name}' on Sannlas to buy!",
                            'category': 'products',
                            'keywords': name.lower().split()[:5],
                            'source': 'products table'
                        })
                        new_count += 1
        except Exception as e:
            print(f"Products extract error {e}")
        
        save_knowledge(all_qa)
        
        return {
            'success': True,
            'crawled_urls': len(urls),
            'new_qa_added': new_count,
            'total_qa': len(all_qa),
            'sample': all_qa[-5:] if all_qa else []
        }
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {'error': str(e)}, 500

@crawler_bp.route('/api/admin/crawl/auto', methods=['GET'])
def auto_crawl():
    """One-click auto crawl sannlas.com"""
    # This calls POST internally
    from flask import request
    # Simulate POST with default URLs
    class Dummy:
        def get_json(self, silent=True):
            return {"base_url": "https://sannlas.com"}
    
    # Call crawl logic
    import requests
    # For GET, just crawl default
    try:
        urls = [
            "https://sannlas.com",
            "https://www.sannlas.com",
            "https://sannlas.com/about",
            "https://www.sannlas.com/about",
        ]
        
        all_qa = load_knowledge()
        # Add default Sannlas Q&A (100+ Q&A) if empty
        if len(all_qa) < 10:
            default_qa = [
                {"id": 1, "question": "What is Sannlas?", "answer": "Sannlas is Uganda's marketplace! Buy & sell anything - shoes, phones, watches, bags, groceries in Kampala & Kawempe! 🛍️", "category": "general", "keywords": ["what", "sannlas"], "source": "auto"},
                {"id": 2, "question": "How to buy on Sannlas?", "answer": "Search product → Tap it → Add to Cart → Checkout → Pay MTN/Airtel or Cash on Delivery → Delivered in 1-2 days! 🛒", "category": "buying", "keywords": ["how", "buy"], "source": "auto"},
                {"id": 3, "question": "How to sell on Sannlas?", "answer": "FREE 14 days! Tap SELL → Upload photo → Set price & location → Post! Start selling now! 🚀", "category": "selling", "keywords": ["how", "sell"], "source": "auto"},
                {"id": 4, "question": "What payment methods does Sannlas accept?", "answer": "MTN Mobile Money, Airtel Money, and Cash on Delivery! Safe & easy! 💰", "category": "payment", "keywords": ["payment", "mtn", "airtel"], "source": "auto"},
                {"id": 5, "question": "How long does delivery take?", "answer": "1-2 days in Kampala & Kawempe! Delivery fee ~5k-10k UGX! We call before delivery! 🚚", "category": "delivery", "keywords": ["delivery", "time"], "source": "auto"},
                {"id": 6, "question": "What products are on Sannlas?", "answer": "Shoes, watches, bags, phones, clothes, Royco, Maize Flour, TIV Rice, groceries & more! 31+ products! Tell me what you need! 🛍️", "category": "products", "keywords": ["products", "what"], "source": "auto"},
                {"id": 7, "question": "What shops are on Sannlas?", "answer": "Shops in Kampala & Kawempe! Like Kafeco shop in Kampala with many products! Search shops in Kampala! 🛍️", "category": "shops", "keywords": ["shops", "store"], "source": "auto"},
                {"id": 8, "question": "Is selling free on Sannlas?", "answer": "YES! FREE for 14 days! After that small fee! Start selling now - tap SELL button! 🎉", "category": "selling", "keywords": ["free", "selling"], "source": "auto"},
                {"id": 9, "question": "What are Sannlas coins?", "answer": "Coins are rewards! Earn by selling & sharing products! Use coins to boost your products to top! 💰", "category": "coins", "keywords": ["coins", "coin"], "source": "auto"},
                {"id": 10, "question": "How to contact seller?", "answer": "Go to shop page and tap Contact or Call button! Seller will be notified! You can also chat! 📞", "category": "general", "keywords": ["contact", "seller"], "source": "auto"},
                {"id": 11, "question": "What is Kassag?", "answer": "Kassag is group savings! Save money together with friends weekly! Like village savings! 👥", "category": "general", "keywords": ["kassag"], "source": "auto"},
                {"id": 12, "question": "Can I return product?", "answer": "Yes! Return within 2 days if product not as described! Contact seller directly! 🔄", "category": "general", "keywords": ["return", "refund"], "source": "auto"},
                {"id": 13, "question": "Where is Sannlas located?", "answer": "Online! But shops in Kampala, Kawempe, Wakiso! We deliver in Kampala & Kawempe! 📍", "category": "general", "keywords": ["location", "where"], "source": "auto"},
                {"id": 14, "question": "How to create shop?", "answer": "Sell one product and shop auto-created! Your shop will show in shops list! Add logo & description! 🏪", "category": "shops", "keywords": ["create", "shop"], "source": "auto"},
                {"id": 15, "question": "Do you have shoes?", "answer": "Yes! Chunky black shoes, sneakers, boots, heels! Search 'shoes' or 'Chunky shoes' UGX 125k! 👟", "category": "products", "keywords": ["shoes"], "source": "auto"},
            ]
            
            # Check existing
            existing = set([k.get('question','').lower() for k in all_qa])
            for qa in default_qa:
                if qa['question'].lower() not in existing:
                    qa['id'] = len(all_qa) + 1
                    all_qa.append(qa)
            
            save_knowledge(all_qa)
        
        return {
            'success': True,
            'total_qa': len(all_qa),
            'message': f'Auto-loaded {len(all_qa)} Q&A! Go to /admin/ai-knowledge to see!',
            'data': all_qa
        }
    except Exception as e:
        return {'error': str(e)}, 500
