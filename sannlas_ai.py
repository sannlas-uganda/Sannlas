from flask import Blueprint, request, jsonify
import os, json, requests
ai_bp = Blueprint('sannlas_ai', __name__)

DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def get_conn():
    if not DATABASE_URL:
        return None
    try:
        import psycopg
        return psycopg.connect(DATABASE_URL, sslmode='require', connect_timeout=10)
    except:
        try:
            import psycopg2
            return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=10)
        except:
            return None

def search_products(query, limit=6):
    """Search REAL products from your DB"""
    if not DATABASE_URL:
        return []
    try:
        conn = get_conn()
        if not conn:
            return []
        cur = conn.cursor()
        # Try JSON search
        try:
            cur.execute("""
                SELECT data FROM products 
                WHERE LOWER(data::text) LIKE %s 
                ORDER BY id DESC LIMIT %s
            """, (f"%{query.lower()}%", limit))
        except:
            cur.execute("SELECT data FROM products ORDER BY id DESC LIMIT %s", (limit,))
        
        rows = cur.fetchall()
        cur.close()
        conn.close()
        
        products = []
        for r in rows:
            d = r[0]
            if isinstance(d, str):
                try: d = json.loads(d)
                except: continue
            if isinstance(d, dict):
                products.append(d)
        return products
    except Exception as e:
        print(f"DB search error: {e}")
        return []

def get_stats():
    try:
        conn = get_conn()
        if not conn:
            return {"shops": "many", "products": "1000+"}
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM products")
        p_count = cur.fetchone()[0]
        try:
            cur.execute("SELECT COUNT(*) FROM shops")
            s_count = cur.fetchone()[0]
        except:
            s_count = 50
        cur.close()
        conn.close()
        return {"shops": s_count, "products": p_count}
    except:
        return {"shops": 100, "products": 500}

@ai_bp.route('/api/ai/chat', methods=['POST','OPTIONS','GET'])
def ai_chat():
    if request.method != 'POST':
        return jsonify({'ok': True})
    
    try:
        data = request.get_json(silent=True) or {}
        user_msg = (data.get('message') or '').strip()
        msg_lower = user_msg.lower()
        
        if not user_msg:
            return jsonify({'reply': 'Hi Boss! 👋 I am Sannlas AI! What do you want to buy today?', 'products': []})

        # ===== SMART LOCAL AI - NO GROQ NEEDED =====
        products = []
        reply = ""
        stats = get_stats()

        # Question types
        if any(k in msg_lower for k in ['how many shops', 'shops are', 'number of shop']):
            reply = f"Boss! 🛍️ Sannlas has {stats['shops']} active shops and {stats['products']} products! All across Uganda - Kampala, Wakiso, Mukono! Want to see shops? Type 'shops in Kampala' 👑"
        
        elif any(k in msg_lower for k in ['how to buy', 'how can i buy', 'buy on sannlas', 'how to order']):
            reply = "Kale Boss! Buying on Sannlas is easy! 🛒\n1. Find product you like\n2. Tap it → Add to Cart\n3. Checkout → Pay with MTN/Airtel Money or Cash on Delivery\n4. We deliver to you! 🚚\nWhat do you want to buy? Tell me e.g. 'watches under 100k'"
        
        elif any(k in msg_lower for k in ['how to sell', 'how can i sell', 'sell on sannlas', 'become seller']):
            reply = "Boss, selling on Sannlas is FREE! 🚀\n1. Tap SELL button (bottom)\n2. Upload photo, set price UGX, location\n3. Post! Customers will call you!\nNo commission for now! Start today - what do you want to sell?"
        
        elif any(k in msg_lower for k in ['watch', 'watches']):
            products = search_products('watch', 5)
            if products:
                reply = f"Yes Boss! I found {len(products)} watches for you! ⌚ Prices from UGX {min([p.get('price',0) for p in products])} ! Check below 👇"
            else:
                reply = "⌚ Watches! Boss we have smart watches, Rolex, casual watches from 20k UGX! Search 'watch' in app or tell me your budget e.g. 'watches under 50k'!"
        
        elif any(k in msg_lower for k in ['bag', 'bags']):
            products = search_products('bag', 5)
            if products:
                reply = f"👜 Found {len(products)} bags Boss! Ladies bags, school bags, travel bags! From UGX {min([p.get('price',0) for p in products if p.get('price')], default=15000)} ! See below!"
            else:
                reply = "👜 Bags! We have ladies handbags, backpacks, traveling bags from 15k UGX! What type you want?"
        
        elif any(k in msg_lower for k in ['shoe', 'shoes']):
            products = search_products('shoe', 5)
            reply = f"👟 Shoes Boss! Sneakers, heels, sandals available! I found {len(products)} for you!" if products else "👟 Shoes! Nike, Adidas, heels, flats from 30k UGX! What size?"
        
        elif any(k in msg_lower for k in ['phone', 'iphone', 'samsung']):
            products = search_products('phone' if 'phone' in msg_lower else 'iphone', 5)
            reply = f"📱 Phones! iPhones, Samsung, Tecno! Found {len(products)} deals for you Boss!" if products else "📱 Phones! iPhones from 500k, Samsung, Tecno from 200k! What phone you want?"
        
        elif any(k in msg_lower for k in ['dress', 'cloth', 'shirt']):
            products = search_products('dress', 5)
            reply = f"👗 Fashion! Found {len(products)} dresses/clothes for you Boss!" if products else "👗 Fashion! Dresses, shirts, kitenge from 20k UGX!"
        
        elif any(k in msg_lower for k in ['hi', 'hello', 'hey', 'kale']):
            reply = f"Hi Boss! 👋 I'm Sannlas AI - Uganda's shopping assistant! 🛍️\n\nWe have {stats['products']} products in {stats['shops']} shops!\n\nAsk me:\n• 'Find watches under 100k'\n• 'Bags in Kampala'\n• 'How to sell on Sannlas?'\n\nWhat do you want today?"
        
        else:
            # General search
            products = search_products(msg_lower.split()[0] if msg_lower.split() else 'a', 5)
            if products:
                reply = f"Boss! 🔍 I searched '{user_msg}' - found {len(products)} products for you! Prices in UGX, all in Uganda! Check below 👇"
            else:
                # Try Groq as last resort
                try:
                    key = os.environ.get('GROQ_API_KEY','').strip()
                    if key:
                        r = requests.post(
                            "https://api.groq.com/openai/v1/chat/completions",
                            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                            json={
                                "model": "llama3-8b-8192",
                                "messages": [
                                    {"role": "system", "content": "You are Sannlas AI Uganda shopping assistant. Short friendly answer, call user Boss."},
                                    {"role": "user", "content": user_msg}
                                ],
                                "max_tokens": 150
                            },
                            timeout=8
                        )
                        if r.status_code == 200:
                            reply = r.json()['choices'][0]['message']['content']
                        else:
                            reply = f"Hey Boss! 👋 On Sannlas you can find '{user_msg}'! We have {stats['products']} products! Try searching in app or ask 'how to buy on Sannlas?' 🛍️"
                    else:
                        reply = f"Hey Boss! 👋 You want '{user_msg}'? On Sannlas.com you can find everything in Uganda! Search it in app or tell me more! 🧠"
                except:
                    reply = f"Boss! I can help you find '{user_msg}' on Sannlas! 🛍️ We have {stats['products']} products! What budget you have?"

        return jsonify({'reply': reply, 'products': products[:6]})

    except Exception as e:
        print(f"AI ERROR: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'reply': "Kale Boss! I'm Sannlas AI 🧠 Ask me about watches, bags, phones, shops in Uganda! What do you want to buy?", 'products': []}), 200
