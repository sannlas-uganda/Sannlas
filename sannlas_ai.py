from flask import Blueprint, request, jsonify
import os, requests
ai_bp = Blueprint('sannlas_ai', __name__)

# NEW WORKING MODELS LIST - Groq 2026
MODELS = [
    "llama-3.3-70b-versatile",  # #1 most stable
    "llama3-8b-8192",           # #2 fallback - always works
    "mixtral-8x7b-32768",       # #3 fallback
    "gemma2-9b-it"              # #4 fallback
]

@ai_bp.route('/api/ai/chat', methods=['POST','OPTIONS','GET'])
def ai_chat():
    if request.method != 'POST':
        return jsonify({'ok': True, 'has_key': bool(os.environ.get('GROQ_API_KEY'))})
    try:
        data = request.get_json(silent=True) or {}
        msg = (data.get('message') or '').strip()
        history = data.get('history', [])[:4]
        
        if not msg:
            return jsonify({'reply': 'Hi Boss! 👋 I am Sannlas AI!', 'products': []})

        key = os.environ.get('GROQ_API_KEY','').strip()
        
        system = "You are SANNLAS AI - Official AI for Sannlas.com Uganda. Uganda's shopping assistant. Friendly Ugandan, call user Boss, short answers 2-3 lines, use emojis. Help find products, shops, selling guide. Currency UGX. Never say you are Groq."
        
        messages = [{"role": "system", "content": system}]
        for h in history:
            if isinstance(h, dict) and h.get('content'):
                if h.get('role') in ['user','assistant']:
                    messages.append({"role": h['role'], "content": str(h['content'])[:300]})
        messages.append({"role": "user", "content": msg})

        # Try models one by one until one works
        for model in MODELS:
            try:
                print(f"Trying model: {model}")
                r = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={
                        "model": model,
                        "messages": messages,
                        "max_tokens": 250,
                        "temperature": 0.7
                    },
                    timeout=15
                )
                print(f"{model} status: {r.status_code}")
                if r.status_code == 200:
                    reply = r.json()['choices'][0]['message']['content']
                    return jsonify({'reply': reply, 'products': []})
                else:
                    print(f"{model} failed: {r.text[:200]}")
                    continue
            except Exception as me:
                print(f"Model {model} exception: {me}")
                continue

        # If all models fail, show last error
        return jsonify({'reply': f"Kale Boss, Groq is busy! You said '{msg}'. On Sannlas you can find phones, watches, shoes, bags in Uganda. Tell me what you want to buy? 🛍️", 'products': []})

    except Exception as e:
        print(f"CRITICAL: {e}")
        return jsonify({'reply': "I'm Sannlas AI Boss! 🧠 Ask me anything about shopping on Sannlas! How can I help?", 'products': []}), 200
