# sannlas_ai_admin.py - ADMIN PANEL TO ADD Q&A - FINAL
from flask import Blueprint, request, jsonify, render_template_string
import os, json

admin_ai_bp = Blueprint('admin_ai', __name__)

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
        # Create table if not exists
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

# API - Get all Q&A
@admin_ai_bp.route('/api/admin/ai-knowledge', methods=['GET'])
def get_knowledge():
    knowledge = load_knowledge()
    return jsonify({'count': len(knowledge), 'data': knowledge})

# API - Add Q&A
@admin_ai_bp.route('/api/admin/ai-knowledge', methods=['POST'])
def add_knowledge():
    try:
        data = request.get_json()
        q = data.get('question','').strip()
        a = data.get('answer','').strip()
        category = data.get('category','general')
        if not q or not a:
            return jsonify({'error': 'Question and Answer required'}), 400
        
        knowledge = load_knowledge()
        knowledge.append({
            'id': len(knowledge) + 1,
            'question': q,
            'answer': a,
            'category': category,
            'keywords': q.lower().split()[:5]
        })
        save_knowledge(knowledge)
        return jsonify({'success': True, 'count': len(knowledge)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# API - Delete Q&A
@admin_ai_bp.route('/api/admin/ai-knowledge/<int:qid>', methods=['DELETE'])
def delete_knowledge(qid):
    knowledge = load_knowledge()
    knowledge = [k for k in knowledge if k.get('id') != qid]
    # Re-index
    for i, k in enumerate(knowledge):
        k['id'] = i+1
    save_knowledge(knowledge)
    return jsonify({'success': True, 'count': len(knowledge)})

# ADMIN PAGE - HTML INTERFACE
@admin_ai_bp.route('/admin/ai-knowledge')
def admin_page():
    html = """
<!DOCTYPE html>
<html>
<head>
    <title>Sannlas AI Knowledge Admin</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial; max-width: 900px; margin: 20px auto; padding: 15px; background: #f5f5f5; }
        .card { background: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        input, textarea, select { width: 100%; padding: 12px; margin: 8px 0; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; }
        button { background: #ff6b00; color: white; border: none; padding: 12px 20px; border-radius: 6px; cursor: pointer; font-weight: bold; }
        button:hover { background: #e55a00; }
        .qa-item { background: #f9f9f9; padding: 15px; border-radius: 8px; margin: 10px 0; border-left: 4px solid #ff6b00; }
        .delete { background: #ff4444; float: right; padding: 5px 10px; font-size: 12px; }
        h1 { color: #ff6b00; }
        .count { background: #ff6b00; color: white; padding: 5px 12px; border-radius: 20px; }
    </style>
</head>
<body>
    <h1>🤖 Sannlas AI Knowledge Admin <span class="count" id="count">0</span></h1>
    
    <div class="card">
        <h3>➕ Add New Q&A</h3>
        <select id="category">
            <option value="general">General</option>
            <option value="buying">Buying</option>
            <option value="selling">Selling</option>
            <option value="payment">Payment</option>
            <option value="delivery">Delivery</option>
            <option value="products">Products</option>
            <option value="coins">Coins</option>
            <option value="shops">Shops</option>
        </select>
        <input type="text" id="question" placeholder="Question - e.g. How to buy on Sannlas?">
        <textarea id="answer" rows="4" placeholder="Answer - e.g. Go to Sannlas.com, search product, add to cart..."></textarea>
        <button onclick="addQA()">💾 Save Q&A</button>
        <p id="status"></p>
    </div>

    <div class="card">
        <h3>📚 All Q&A (<span id="count2">0</span>)</h3>
        <input type="text" id="search" placeholder="🔍 Search Q&A..." onkeyup="filterQA()">
        <div id="list">Loading...</div>
    </div>

<script>
let allData = [];

async function loadQA() {
    const res = await fetch('/api/admin/ai-knowledge');
    const json = await res.json();
    allData = json.data || [];
    document.getElementById('count').innerText = allData.length;
    document.getElementById('count2').innerText = allData.length;
    renderQA(allData);
}

function renderQA(data) {
    const list = document.getElementById('list');
    if (data.length === 0) {
        list.innerHTML = '<p>No Q&A yet. Add first one above!</p>';
        return;
    }
    list.innerHTML = data.map(item => `
        <div class="qa-item">
            <button class="delete" onclick="deleteQA(${item.id})">Delete</button>
            <strong>Q${item.id} [${item.category}]:</strong> ${item.question}<br>
            <strong>A:</strong> ${item.answer}
        </div>
    `).join('');
}

async function addQA() {
    const q = document.getElementById('question').value.trim();
    const a = document.getElementById('answer').value.trim();
    const cat = document.getElementById('category').value;
    if (!q || !a) { alert('Enter question and answer!'); return; }
    
    document.getElementById('status').innerText = 'Saving...';
    const res = await fetch('/api/admin/ai-knowledge', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({question: q, answer: a, category: cat})
    });
    const json = await res.json();
    if (json.success) {
        document.getElementById('status').innerText = '✅ Saved! Total: ' + json.count;
        document.getElementById('question').value = '';
        document.getElementById('answer').value = '';
        loadQA();
    } else {
        document.getElementById('status').innerText = '❌ Error: ' + json.error;
    }
}

async function deleteQA(id) {
    if (!confirm('Delete Q'+id+'?')) return;
    await fetch('/api/admin/ai-knowledge/'+id, {method: 'DELETE'});
    loadQA();
}

function filterQA() {
    const term = document.getElementById('search').value.toLowerCase();
    const filtered = allData.filter(k => 
        k.question.toLowerCase().includes(term) || 
        k.answer.toLowerCase().includes(term)
    );
    renderQA(filtered);
}

loadQA();
</script>
</body>
</html>
    """
    return render_template_string(html)

# Auto-load default Q&A if empty
@admin_ai_bp.route('/api/admin/ai-knowledge/init', methods=['POST'])
def init_default():
    knowledge = load_knowledge()
    if len(knowledge) > 0:
        return jsonify({'message': 'Already has data', 'count': len(knowledge)})
    
    default_qa = [
        {"id": 1, "question": "What is Sannlas?", "answer": "Sannlas is Uganda's marketplace! Buy & sell anything in Kampala & Kawempe! 🛍️", "category": "general", "keywords": ["what", "sannlas"]},
        {"id": 2, "question": "How to buy on Sannlas?", "answer": "Search product → Tap it → Add to Cart → Checkout → Pay MTN/Airtel or Cash on Delivery → Delivered in 1-2 days! 🛒", "category": "buying", "keywords": ["buy"]},
        {"id": 3, "question": "How to sell on Sannlas?", "answer": "FREE 14 days! Tap SELL → Upload photo → Set price & location → Post! 🚀", "category": "selling", "keywords": ["sell"]},
        {"id": 4, "question": "What payment methods?", "answer": "MTN Mobile Money, Airtel Money, or Cash on Delivery! 💰 Safe & easy!", "category": "payment", "keywords": ["payment"]},
        {"id": 5, "question": "Delivery time?", "answer": "1-2 days in Kampala & Kawempe! Fee ~5k-10k UGX! 🚚", "category": "delivery", "keywords": ["delivery"]},
    ]
    save_knowledge(default_qa)
    return jsonify({'success': True, 'count': len(default_qa)})
