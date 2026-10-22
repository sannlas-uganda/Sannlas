# sannlas_likes.py - ONE FILE = LIKES & STARS SYSTEM - FINAL FIXED
from flask import Blueprint, Response, request, jsonify
import os, json, time

sannlas_likes_bp = Blueprint('sannlas_likes_bp', __name__)

def load_db(file, default):
    try:
        if os.path.exists(f'data/{file}'):
            return json.load(open(f'data/{file}'))
        if os.path.exists(file):
            return json.load(open(file))
        return default
    except:
        return default

def save_db(file, data):
    os.makedirs('data', exist_ok=True)
    json.dump(data, open(f'data/{file}','w'), indent=2)

def get_users(): return load_db('users.json', [])
def get_products(): return load_db('products.json', [])
def get_likes(): return load_db('likes.json', [])
def save_likes(d): save_db('likes.json', d)

COMBINED_LIKES_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>LIKES - SANNLAS</title>
<style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:Arial;background:#f1f5f9;padding-bottom:80px}.navbar{background:#000;color:#FFCC02;padding:12px;display:flex;justify-content:space-between;position:sticky;top:0;z-index:10}.tab-bar{background:#fff;display:flex;border-bottom:2px solid #eee;position:sticky;top:50px;z-index:9}.tab-bar button{flex:1;padding:14px;border:none;background:#fff;font-weight:900;cursor:pointer;border-bottom:3px solid transparent}.tab-bar button.active{border-bottom-color:#FF0000;background:#fff0f0}.product-card{background:#fff;border-radius:14px;overflow:hidden;margin:8px 10px;display:flex;gap:10px;padding:10px;box-shadow:0 1px 5px rgba(0,0,0,.06)}.product-card img{width:80px;height:80px;object-fit:cover;border-radius:10px}.like-btn{padding:6px 12px;border-radius:20px;border:none;font-weight:900;cursor:pointer;margin-top:6px}.btn-liked{background:#FF0000;color:#fff}.btn-like{background:#eee;color:#333}.stats{background:#000;color:#FFCC02;padding:12px;display:flex;justify-content:space-around;text-align:center}.stats b{display:block;font-size:20px}</style>
</head><body>
<div class="navbar"><a href="/" style="color:#FFCC02;text-decoration:none;font-weight:bold">← SANNLAS</a><b>❤️ LIKES</b><span></span></div>
<div class="stats"><div><b id="totalLikes">0</b><small>Total Likes Given</small></div><div><b id="totalLiked">0</b><small>Products Liked</small></div><div><b id="totalStars">0</b><small>Stars Received</small></div></div>
<div class="tab-bar"><button id="tab-liked" class="active" onclick="switchTab('liked')">Liked Products</button><button id="tab-received" onclick="switchTab('received')">Likes Received</button><button id="tab-discover" onclick="switchTab('discover')">Discover</button></div>
<div id="likesList"><p style="text-align:center;padding:30px">Loading...</p></div>
<script>
let currentUser=JSON.parse(localStorage.getItem('sannlas_user')||'{}');
let currentTab='liked';
let allData={liked:[], received:[], discover:[]};
function switchTab(tab){currentTab=tab;document.querySelectorAll('.tab-bar button').forEach(b=>b.classList.remove('active'));document.getElementById('tab-'+tab).classList.add('active');renderList();}
async function loadLikes(){let email=currentUser.email||''; let phone=currentUser.phone||'';try{let r=await fetch(`/api/likes/stats?email=${encodeURIComponent(email)}&phone=${encodeURIComponent(phone)}`);let d=await r.json();document.getElementById('totalLikes').innerText=d.total_given||0;document.getElementById('totalLiked').innerText=(d.liked_list||[]).length;document.getElementById('totalStars').innerText=d.total_received||0;allData.liked=d.liked_list||[];allData.received=d.received_list||[];allData.discover=d.discover||[];renderList();}catch(e){document.getElementById('likesList').innerHTML='<p style="color:red;text-align:center">Error: '+e.message+'</p>';}}
function renderList(){let list=allData[currentTab]||[];if(list.length==0){document.getElementById('likesList').innerHTML=`<p style="text-align:center;padding:30px;color:#666">No ${currentTab} yet</p>`;return;}document.getElementById('likesList').innerHTML=list.map(p=>{let btn=currentTab=='discover'?(p.is_liked?`<button class="like-btn btn-liked" onclick="unlikeProduct('${p.id}')">❤️ Liked</button>`:`<button class="like-btn btn-like" onclick="likeProduct('${p.id}')">🤍 Like</button>`):`<button class="like-btn btn-liked" onclick="unlikeProduct('${p.id}')">❤️ ${p.likes||0} Likes</button>`;return `<div class="product-card"><img src="${p.image||'https://via.placeholder.com/80'}" onclick="location.href='/sell/${p.id}'"><div><b>${(p.name||'').slice(0,30)}</b><br><small>${p.business||p.location||''} • UGX ${Number(p.price||0).toLocaleString()}</small><br>${btn}</div></div>`;}).join('');}
async function likeProduct(productId){if(!currentUser.email){alert('Login first!');return;}let r=await fetch('/api/like',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:currentUser.email,phone:currentUser.phone,product_id:productId})});let d=await r.json();if(d.success){loadLikes();}else alert(d.message);}
async function unlikeProduct(productId){if(!currentUser.email){alert('Login first!');return;}let r=await fetch('/api/unlike',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:currentUser.email,phone:currentUser.phone,product_id:productId})});let d=await r.json();if(d.success){loadLikes();}else alert(d.message);}
loadLikes();
</script>
</body></html>
"""

@sannlas_likes_bp.route('/likes')
def likes_page():
    return Response(COMBINED_LIKES_HTML, mimetype='text/html')

@sannlas_likes_bp.route('/api/likes/stats')
def likes_stats():
    email = request.args.get('email','').lower().strip()
    phone = request.args.get('phone','').strip()
    users = get_users()
    products = get_products()
    likes = get_likes()

    me = next((u for u in users if (email and str(u.get('email','')).lower()==email) or (phone and str(u.get('phone',''))==phone)), None)
    my_email = (me.get('email','').lower() if me else email)

    # Products I liked
    my_liked_ids = [l['product_id'] for l in likes if l.get('user_email','').lower()==my_email]
    liked_list=[]
    for pid in my_liked_ids:
        p = next((x for x in products if str(x.get('id'))==str(pid)), None)
        if p:
            # Count likes for this product
            p['likes'] = len([l for l in likes if str(l.get('product_id'))==str(pid)])
            p['is_liked'] = True
            liked_list.append(p)

    # Products where my products received likes
    my_product_ids = [str(p.get('id')) for p in products if (email and str(p.get('seller_email','')).lower()==my_email) or (phone and str(p.get('phone',''))==phone)]
    received_list=[]
    total_received=0
    for pid in my_product_ids:
        count = len([l for l in likes if str(l.get('product_id'))==str(pid)])
        if count>0:
            p = next((x for x in products if str(x.get('id'))==str(pid)), None)
            if p:
                p['likes']=count
                received_list.append(p)
                total_received+=count

    # Discover = most liked products not yet liked by me
    discover=[]
    for p in products[:100]:
        pid=str(p.get('id'))
        if pid in my_liked_ids: continue
        if pid in my_product_ids: continue
        likes_count = len([l for l in likes if str(l.get('product_id'))==pid])
        p_copy=dict(p)
        p_copy['likes']=likes_count
        p_copy['is_liked']=False
        discover.append(p_copy)
    discover = sorted(discover, key=lambda x: x.get('likes',0), reverse=True)[:50]

    return jsonify({
        'total_given': len(my_liked_ids),
        'total_received': total_received,
        'liked_list': liked_list[::-1],
        'received_list': sorted(received_list, key=lambda x: x.get('likes',0), reverse=True),
        'discover': discover
    })

@sannlas_likes_bp.route('/api/like', methods=['POST'])
def api_like():
    data = request.json or {}
    email = data.get('email','').lower().strip()
    phone = data.get('phone','').strip()
    product_id = str(data.get('product_id','')).strip()

    if not product_id:
        return jsonify({'success':False,'message':'Product ID required'}),400

    likes = get_likes()
    products = get_products()
    users = get_users()

    # Check product exists
    prod = next((p for p in products if str(p.get('id'))==product_id), None)
    if not prod:
        return jsonify({'success':False,'message':'Product not found!'}),404

    # Already liked?
    exists = next((l for l in likes if l.get('user_email','').lower()==email and str(l.get('product_id'))==product_id), None)
    if exists:
        return jsonify({'success':False,'message':'Already liked! ❤️'}),400

    # Cannot like own product? Allow but count differently
    if str(prod.get('seller_email','')).lower()==email:
        return jsonify({'success':False,'message':'Cannot like your own product Boss!'}),400

    likes.append({
        'user_email': email,
        'user_phone': phone,
        'product_id': product_id,
        'seller_email': prod.get('seller_email',''),
        'time': time.time()
    })
    save_likes(likes)

    # Update counts
    for u in users:
        if str(u.get('email','')).lower()==str(prod.get('seller_email','')).lower():
            u['total_likes'] = int(u.get('total_likes',0)) + 1
            u['total_stars'] = int(u.get('total_stars',0)) + 1
            break
    save_db('users.json', users)

    # Update product likes field
    for p in products:
        if str(p.get('id'))==product_id:
            p['total_likes'] = int(p.get('total_likes',0)) + 1
            p['likes'] = int(p.get('likes',0)) + 1
            break
    save_db('products.json', products)

    return jsonify({'success':True,'message':'❤️ Liked! Seller got +1 star!'})

@sannlas_likes_bp.route('/api/unlike', methods=['POST'])
def api_unlike():
    data = request.json or {}
    email = data.get('email','').lower().strip()
    product_id = str(data.get('product_id','')).strip()

    likes = get_likes()
    before = len(likes)
    likes = [l for l in likes if not (l.get('user_email','').lower()==email and str(l.get('product_id'))==product_id)]
    after = len(likes)

    if before==after:
        return jsonify({'success':False,'message':'Not liked yet!'}),400

    save_likes(likes)

    # Decrement counts
    products = get_products()
    users = get_users()
    prod = next((p for p in products if str(p.get('id'))==product_id), None)
    if prod:
        for p in products:
            if str(p.get('id'))==product_id:
                p['total_likes'] = max(0, int(p.get('total_likes',0)) - 1)
                p['likes'] = max(0, int(p.get('likes',0)) - 1)
                break
        save_db('products.json', products)

        for u in users:
            if str(u.get('email','')).lower()==str(prod.get('seller_email','')).lower():
                u['total_likes'] = max(0, int(u.get('total_likes',0)) - 1)
                u['total_stars'] = max(0, int(u.get('total_stars',0)) - 1)
                break
        save_db('users.json', users)

    return jsonify({'success':True,'message':'Unliked!'})

@sannlas_likes_bp.route('/api/likes/check')
def api_like_check():
    email = request.args.get('email','').lower()
    product_id = request.args.get('product_id','')
    likes = get_likes()
    is_liked = any(l.get('user_email','').lower()==email and str(l.get('product_id'))==str(product_id) for l in likes)
    count = len([l for l in likes if str(l.get('product_id'))==str(product_id)])
    return jsonify({'is_liked': is_liked, 'count': count})

@sannlas_likes_bp.route('/api/likes/product/<pid>')
def api_likes_product(pid):
    likes = get_likes()
    filtered = [l for l in likes if str(l.get('product_id'))==str(pid)]
    return jsonify({'count': len(filtered), 'likes': filtered})
