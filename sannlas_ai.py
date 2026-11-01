# sannlas_ai.py - SANNLAS AI BRAIN - FREE Groq
from flask import Blueprint, request, jsonify
import os, json, requests
from datetime import datetime

ai_bp = Blueprint('ai_bp', __name__)

DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

def get_conn():
    if not DATABASE_URL:
        raise Exception("No DATABASE_URL")
    try:
        import psycopg
        return psycopg.connect(DATABASE_URL, sslmode='require', connect_timeout=10)
    except:
        import psycopg2
        return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=10)

def load_db(file, default):
    try:
        if DATABASE_URL:
            conn = get_conn()
            try:
                from psycopg.rows import dict_row
                cur = conn.cursor(row_factory=dict_row)
                if file == 'products.json':
                    cur.execute("SELECT data FROM products ORDER BY id ASC LIMIT 100")
                    rows = cur.fetchall(); cur.close(); conn.close()
                    result=[]
                    for r in rows:
                        d=r['data']
                        if isinstance(d,str):
                            try: d=json.loads(d)
                            except: pass
                        result.append(d)
                    return result
                else:
                    cur.execute("SELECT data FROM kv_store WHERE key=%s", (file,))
                    row = cur.fetchone(); cur.close(); conn.close()
                    if not row: return default
                    d=row['data']
                    if isinstance(d,str):
                        try: d=json.loads(d)
                        except: pass
                    return d
            except:
                import psycopg2.extras
                cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
                cur.execute("SELECT data FROM products ORDER BY id ASC LIMIT 100")
                rows = cur.fetchall(); cur.close(); conn.close()
                return [r['data'] if not isinstance(r['data'],str) else json.loads(r['data']) for r in rows]
        else:
            return default
    except:
        return default

def get_sannlas_context():
    try:
        products = load_db('products.json', [])[:25]
        prod_text = "\n".join([f"- {p.get('name','')} | UGX {p.get('price',0)} | Shop: {p.get('business','')} | {p.get('location','Kampala')}" for p in products[:15]])
        return f"""
You are SANNLAS AI - Official AI for Sannlas.com
Uganda's #1 Shopping + Reels App (TikTok + Jumia)

CURRENT PRODUCTS:
{prod_text}

YOUR STYLE:
- Friendly Ugandan, call user Boss, use Kale, Ssebo sometimes
- Short answers (2-3 lines) for mobile
- If user wants to buy, mention product + price
- If user asks how to sell, explain Sannlas is FREE to open shop
- Never say you are Groq or ChatGPT, you are Sannlas AI built by Sannlas team
- Currency UGX, Location Uganda
"""
    except:
        return "You are Sannlas AI for Sannlas.com - Ugandan shopping + reels"

@ai_bp.route('/api/ai/chat', methods=['POST'])
def ai_chat():
    try:
        data = request.json
        user_msg = data.get('message','').strip()
        history = data.get('history',[])
        
        if not user_msg:
            return jsonify({'reply':'Hi Boss! 👋 I am Sannlas AI! Ask me anything - products, shops, or how to sell on Sannlas!','products':[]})
        
        groq_key = os.environ.get('GROQ_API_KEY')
        if not groq_key:
            return jsonify({'reply':'Sannlas AI is setting up Boss! Add GROQ_API_KEY in Render and I will be live! 🚀','products':[]})
        
        context = get_sannlas_context()
        messages = [{"role":"system","content":context}]
        for h in history[-6:]:
            if h.get('role') in ['user','assistant']:
                messages.append({"role":h['role'],"content":h['content'][:400]})
        messages.append({"role":"user","content":user_msg})
        
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization":f"Bearer {groq_key}","Content-Type":"application/json"},
            json={
                "model":"llama-3.3-70b-versatile",
                "messages":messages,
                "temperature":0.7,
                "max_tokens":350
            },
            timeout=15
        )
        
        if resp.status_code != 200:
            return jsonify({'reply':'Kale Boss, small network! Try again Boss? I am ready!','products':[]})
        
        ai_reply = resp.json()['choices'][0]['message']['content']
        
        products = load_db('products.json', [])
        relevant = []
        keywords = user_msg.lower().split()
        for p in products:
            name = str(p.get('name','')+p.get('title','')).lower()
            if any(k in name for k in keywords if len(k)>2):
                relevant.append(p)
            if len(relevant)>=3:
                break
        
        return jsonify({'reply':ai_reply,'products':relevant[:3]})
    except Exception as e:
        return jsonify({'reply':'Sorry Boss, try again? I am Sannlas AI ready to help! 🚀','products':[],'error':str(e)})
