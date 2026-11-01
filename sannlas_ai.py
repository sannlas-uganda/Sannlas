from flask import Blueprint, request, jsonify
import os, requests
ai_bp = Blueprint('sannlas_ai', __name__)

@ai_bp.route('/api/ai/chat', methods=['POST','OPTIONS','GET'])
def ai_chat():
    if request.method != 'POST':
        return jsonify({'ok': True, 'has_key': bool(os.environ.get('GROQ_API_KEY'))})
    try:
        data = request.get_json(silent=True) or {}
        msg = data.get('message','')
        key = os.environ.get('GROQ_API_KEY','').strip()
        
        if not key:
            return jsonify({'reply': 'No GROQ key in Render!', 'products': []})
        
        # Test Groq
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": "llama-3.1-8b-instant",
                "messages": [
                    {"role": "system", "content": "You are Sannlas AI, Ugandan shopping assistant. Reply short, call user Boss."},
                    {"role": "user", "content": msg}
                ],
                "max_tokens": 200
            },
            timeout=20
        )
        
        # DEBUG: If fails, show real Groq error
        if r.status_code != 200:
            print(f"GROQ FAILED {r.status_code}: {r.text}")
            return jsonify({
                'reply': f"Boss, Groq Error {r.status_code}: {r.text[:200]}. Check key! I will still help - you said '{msg}'?",
                'products': []
            })
        
        reply = r.json()['choices'][0]['message']['content']
        return jsonify({'reply': reply, 'products': []})
        
    except Exception as e:
        print(f"ERROR: {e}")
        return jsonify({'reply': f"Debug error: {str(e)}", 'products': []}), 200
