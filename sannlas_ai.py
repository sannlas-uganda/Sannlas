# sannlas_ai.py - SANNLAS AI - FIXED BY BOSS
from flask import Blueprint, request, jsonify
import os
import requests

ai_bp = Blueprint('sannlas_ai', __name__)

@ai_bp.route('/api/ai/chat', methods=['POST', 'OPTIONS', 'GET'])
def ai_chat():
    if request.method == 'OPTIONS':
        return jsonify({'ok': True}), 200
    if request.method == 'GET':
        has_key = bool(os.environ.get('GROQ_API_KEY'))
        return jsonify({'status': 'Sannlas AI Live!', 'has_key': has_key})

    try:
        data = request.get_json(silent=True) or {}
        user_msg = (data.get('message') or '').strip()
        history = data.get('history', []) or []

        if not user_msg:
            return jsonify({'reply': 'Hi Boss! 👋 I am Sannlas AI! Ask me anything about Sannlas!', 'products': []})

        groq_key = os.environ.get('GROQ_API_KEY', '').strip()
        if not groq_key:
            return jsonify({'reply': 'Boss, add GROQ_API_KEY in Render → Environment → Save → I will be live! 🚀', 'products': []})

        # Simple context - NO DB CALL (fast!)
        system_prompt = """You are SANNLAS AI - Official AI for Sannlas.com, Uganda's #1 shopping + reels app (like TikTok + Jumia).
Products: phones, watches, shoes, bags, electronics in Kampala, Uganda.
Currency UGX. Style: Friendly Ugandan, call user Boss, short 2-3 lines, mobile friendly.
If user asks to buy, say you can find it on Sannlas.
If user asks how to sell: Click SELL button, upload photo, set price, FREE shop!
Never say you are Groq/ChatGPT, you are Sannlas AI built by Sannlas team.
"""

        messages = [{"role": "system", "content": system_prompt}]
        for h in history[-4:]:
            if isinstance(h, dict) and h.get('role') in ['user', 'assistant'] and h.get('content'):
                messages.append({"role": h['role'], "content": str(h['content'])[:300]})
        messages.append({"role": "user", "content": user_msg})

        # Use WORKING MODEL - 8b is FREE and FAST, 70b is deprecated!
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.1-8b-instant",  # FIXED MODEL - 70b deprecated!
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 250
            },
            timeout=20
        )

        print(f"Groq Status: {resp.status_code}")
        
        if resp.status_code != 200:
            print(f"Groq Error: {resp.text}")
            # Try fallback model
            resp2 = requests.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={"Authorization": f"Bearer {groq_key}", "Content-Type": "application/json"},
                json={
                    "model": "llama-3.2-3b-preview",
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 200
                },
                timeout=20
            )
            if resp2.status_code == 200:
                ai_reply = resp2.json()['choices'][0]['message']['content']
                return jsonify({'reply': ai_reply, 'products': []})
            
            # If both fail, show real error in logs, but friendly reply to user
            return jsonify({'reply': f"Hey Boss! 👋 I'm Sannlas AI, ready! You said '{user_msg}'. On Sannlas you can find everything in Uganda! What do you want to buy today? 🛍️", 'products': []})

        ai_reply = resp.json()['choices'][0]['message']['content']
        
        # Products - try but never crash
        products = []
        try:
            # Optional: fetch products without DB heavy call
            pr = requests.get('https://sannlas.onrender.com/api/products', timeout=4)
            if pr.status_code == 200:
                data_p = pr.json()
                all_p = data_p if isinstance(data_p, list) else data_p.get('products', [])[:5]
                # Simple keyword match
                kws = [k for k in user_msg.lower().split() if len(k) > 2]
                for p in all_p:
                    name = str(p.get('name','') + p.get('title','')).lower()
                    if any(k in name for k in kws):
                        products.append(p)
                if not products:
                    products = all_p[:3]
        except:
            pass

        return jsonify({'reply': ai_reply, 'products': products[:3]})

    except Exception as e:
        print(f"AI ERROR: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'reply': 'Kale Boss, I am here! 🧠 Ask me: Find watches under 100k, Shops in Kampala, or How to sell on Sannlas? 🚀', 'products': []}), 200
