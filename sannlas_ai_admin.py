# sannlas_ai_admin.py - WITH CRAWL BUTTONS + AUTO PRODUCTS - FINAL
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

# HTML TEMPLATE WITH CRAWL BUTTONS
ADMIN_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>Sannlas AI Admin - {{count}} Q&A</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body{font-family:Arial;background:#FFF8F0;padding:10px;margin:0}
.container{max-width:900px;margin:0 auto}
.header{background:linear-gradient(135deg,#FF6B00,#FF8C00);color:white;padding:20px;border-radius:15px;margin-bottom:15px}
.btn{padding:12px 20px;border:none;border-radius:10px;font-weight:bold;cursor:pointer;margin:5px;display:inline-block;text-decoration:none;color:white}
.btn-orange{background:#FF6B00}
.btn-blue{background:#2563EB}
.btn-green{background:#059669}
.btn-red{background:#DC2626}
.btn-black{background:#111}
.card{background:white;padding:15px;border-radius:12px;margin:10px 0;box-shadow:0 2px 10px rgba(0,0,0,0.1);border-left:4px solid #FF6B00}
input,textarea,select{width:100%;padding:12px;margin:8px 0;border:2px solid #FFD4A8;border-radius:10px;font-size:16px;box-sizing:border-box}
.search{border-color:#2563EB}
.stats{display:flex;gap:10px;flex-wrap:wrap;margin:15px 0}
.stat{background:white;padding:15px;border-radius:12px;flex:1;min-width:120px;text-align:center;box-shadow:0 2px 5px rgba(0,0,0,0.1)}
</style>
</head>
<body>
<div class="container">
<div class="header">
<h1>🤖 Sannlas AI Knowledge Admin</h1>
<p>Total: <b>{{count}} Q&A</b> | Products: Auto-synced | Safe: No leaks ✅</p>
</div>

<div class="stats">
<div class="stat"><h2>{{count}}</h2><p>Total Q&A</p></div>
<div class="stat"><h2>{{general}}</h2><p>General</p></div>
<div class="stat"><h2>{{products}}</h2><p>Products</p></div>
<div class="stat"><h2>{{shops}}</h2><p>Shops</p></div>
</div>

<!-- CRAWL BUTTONS - NEW! -->
<div class="card" style="border-left-color:#2563EB;background:#EFF6FF">
<h3>🚀 Auto Tools (A + B)</h3>
<button class="btn btn-blue" onclick="autoCrawl()">🔍 A) Auto Crawl Website (25 Q&A)</button>
<button class="btn btn-green" onclick="autoProducts()">📦 B) Auto-Add Products Q&A (30 Products)</button>
<button class="btn btn-black" onclick="autoShops()">🏪 Auto-Add Shops Q&A</button>
<button class="btn btn-orange" onclick="location.reload()">🔄 Refresh</button>
<p id="crawlStatus" style="margin-top:10px;font-weight:bold"></p>
</div>

<div class="card">
<h3>➕ Add New Q&A</h3>
<select id="category">
<option value="general">General</option>
<option value="buying">Buying</option>
<option value="selling">Selling</option>
<option value="payment">Payment</option>
<option value="delivery">Delivery</option>
<option value="products">Products</option>
<option value="shops">Shops</option>
<option value="coins">Coins</option>
<option value="auto">Auto</option>
</select>
<input id="question" placeholder="Question - e.g. What is Sannlas?">
<textarea id="answer" rows="3" placeholder="Answer - e.g. Sannlas is Uganda's marketplace..."></textarea>
<input id="keywords" placeholder="Keywords (comma separated) - e.g. sannlas, what">
<button class="btn btn-orange" onclick="addQA()">💾 Save Q&A</button>
<p id="saveStatus"></p>
</div>

<div class="card">
<input id="searchBox" class="search" placeholder="🔍 Search Q&A..." onkeyup="filterQA()">
<p>Showing <span id="showCount">{{count}}</span> Q&A</p>
</div>

<div id="qaList">
{% for item in knowledge %}
<div class="card qa-item" data-q="{{item.question.lower()}} {{item.answer.lower()}}">
<div style="display:flex;justify-content:space-between;align-items:start">
<div style="flex:1">
<span style="background:#FF6B00;color:white;padding:3px 8px;border-radius:15px;font-size:12px">{{item.category}}</span>
<span style="background:#EEE;padding:3px 8px;border-radius:15px;font-size:12px;margin-left:5px">#{{item.id}}</span>
<h4 style="margin:8px 0">Q: {{item.question}}</h4>
<p style="background:#FFF8F0;padding:10px;border-radius:8px">A: {{item.answer}}</p>
<small style="color:#888">Keywords: {{item.keywords}} | Source: {{item.source if item.source else 'manual'}}</small>
</div>
<button class="btn btn-red" style="margin-left:10px" onclick="deleteQA({{item.id}})">🗑️ Delete</button>
</div>
</div>
{% endfor %}
</div>

</div>

<script>
function autoCrawl(){
  document.getElementById('crawlStatus').innerHTML = '⏳ Crawling sannlas.onrender.com... 15 secs...';
  fetch('/api/admin/crawl/auto')
    .then(r=>r.json())
    .then(d=>{
      document.getElementById('crawlStatus').innerHTML = '✅ ' + d.message + ' Total: ' + d.total_qa;
      setTimeout(()=>location.reload(), 2000);
    })
    .catch(e=>{document.getElementById('crawlStatus').innerHTML = '❌ Error: ' + e;});
}

function autoProducts(){
  document.getElementById('crawlStatus').innerHTML = '⏳ Adding products Q&A from Neon DB...';
  fetch('/api/admin/crawl/products', {method:'POST'})
    .then(r=>r.json())
    .then(d=>{
      document.getElementById('crawlStatus').innerHTML = '✅ Added ' + d.new_added + ' products! Total: ' + d.total_qa;
      setTimeout(()=>location.reload(), 2000);
    })
    .catch(e=>{document.getElementById('crawlStatus').innerHTML = '❌ Error: ' + e;});
}

function autoShops(){
  document.getElementById('crawlStatus').innerHTML = '⏳ Adding shops Q&A...';
  fetch('/api/admin/crawl/shops', {method:'POST'})
    .then(r=>r.json())
    .then(d=>{
      document.getElementById('crawlStatus').innerHTML = '✅ Added ' + d.new_added + ' shops! Total: ' + d.total_qa;
      setTimeout(()=>location.reload(), 2000);
    })
    .catch(e=>{document.getElementById('crawlStatus').innerHTML = '❌ Error: ' + e;});
}

function addQA(){
  const q = document.getElementById('question').value;
  const a = document.getElementById('answer').value;
  const cat = document.getElementById('category').value;
  const kw = document.getElementById('keywords').value;
  if(!q || !a){ alert('Question and Answer required!'); return; }
  fetch('/api/admin/ai-knowledge', {
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body: JSON.stringify({question:q, answer:a, category:cat, keywords:kw})
  }).then(r=>r.json()).then(d=>{
    document.getElementById('saveStatus').innerHTML = '✅ Saved! Total: ' + d.total;
    document.getElementById('question').value='';
    document.getElementById('answer').value='';
    setTimeout(()=>location.reload(), 1000);
  });
}

function deleteQA(id){
  if(!confirm('Delete Q&A #' + id + '?')) return;
  fetch('/api/admin/ai-knowledge/' + id, {method:'DELETE'})
    .then(r=>r.json()).then(d=>{
      alert('Deleted! Total: ' + d.total);
      location.reload();
    });
}

function filterQA(){
  const s = document.getElementById('searchBox').value.toLowerCase();
  let count=0;
  document.querySelectorAll('.qa-item').forEach(el=>{
    const q = el.getAttribute('data-q');
    if(q.includes(s)){ el.style.display='block'; count++; } else { el.style.display='none'; }
  });
  document.getElementById('showCount').innerText = count;
}
</script>
</body>
</html>
"""

@admin_ai_bp.route('/admin/ai-knowledge')
def admin_page():
    knowledge = load_knowledge()
    # Stats
    cats = {}
    for k in knowledge:
        c = k.get('category','general')
        cats[c] = cats.get(c,0)+1
    return render_template_string(ADMIN_HTML, 
                                  knowledge=list(reversed(knowledge)), 
                                  count=len(knowledge),
                                  general=cats.get('general',0),
                                  products=cats.get('products',0),
                                  shops=cats.get('shops',0))

@admin_ai_bp.route('/api/admin/ai-knowledge', methods=['GET','POST'])
def api_knowledge():
    if request.method == 'GET':
        return jsonify(load_knowledge())
    
    data = request.get_json()
    knowledge = load_knowledge()
    new_id = len(knowledge) + 1
    if knowledge:
        new_id = max([k.get('id',0) for k in knowledge]) + 1
    
    kw = data.get('keywords','')
    if isinstance(kw, str):
        kw = [k.strip() for k in kw.split(',') if k.strip()]
    
    new_item = {
        'id': new_id,
        'question': data.get('question','').strip(),
        'answer': data.get('answer','').strip(),
        'category': data.get('category','general'),
        'keywords': kw if kw else data.get('question','').lower().split()[:5],
        'source': 'manual'
    }
    knowledge.append(new_item)
    save_knowledge(knowledge)
    return jsonify({'success': True, 'total': len(knowledge), 'item': new_item})

@admin_ai_bp.route('/api/admin/ai-knowledge/<int:qid>', methods=['DELETE'])
def delete_knowledge(qid):
    knowledge = load_knowledge()
    knowledge = [k for k in knowledge if k.get('id') != qid]
    save_knowledge(knowledge)
    return jsonify({'success': True, 'total': len(knowledge)})

@admin_ai_bp.route('/api/admin/ai-knowledge/init', methods=['POST','GET'])
def init_knowledge():
    # Keep empty - use crawler auto
    return jsonify({'message': 'Use /api/admin/crawl/auto to load Q&A'})
