# sannlas_follow.py - ONE FILE = FOLLOW SYSTEM - FINAL FIXED
from flask import Blueprint, Response, request, jsonify
import os, json, time

sannlas_follow_bp = Blueprint('sannlas_follow_bp', __name__)

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

def get_users():
    return load_db('users.json', [])

def get_follows():
    return load_db('follows.json', [])

def save_follows(data):
    save_db('follows.json', data)

# EMBED HTML INSIDE PY - SAME AS WANTS/SELL PATTERN
COMBINED_FOLLOW_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>FOLLOW - SANNLAS</title>
<style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:Arial;background:#f1f5f9;padding-bottom:80px}.navbar{background:#000;color:#FFCC02;padding:12px;display:flex;justify-content:space-between;position:sticky;top:0;z-index:10}.tab-bar{background:#fff;display:flex;padding:0;border-bottom:2px solid #eee;position:sticky;top:50px;z-index:9}.tab-bar button{flex:1;padding:14px;border:none;background:#fff;font-weight:900;cursor:pointer;border-bottom:3px solid transparent}.tab-bar button.active{border-bottom-color:#FFCC02;background:#fffde7}.user-card{background:#fff;border-radius:14px;padding:12px;margin:8px 10px;display:flex;align-items:center;gap:10px;box-shadow:0 1px 5px rgba(0,0,0,.06)}.avatar{width:50px;height:50px;border-radius:50%;background:#000;color:#FFCC02;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:20px}.follow-btn{margin-left:auto;padding:8px 16px;border-radius:20px;border:2px solid #000;font-weight:900;cursor:pointer}.btn-follow{background:#FFCC02;color:#000}.btn-following{background:#000;color:#fff}.btn-self{background:#eee;color:#999;cursor:not-allowed}.stats{background:#000;color:#FFCC02;padding:12px;display:flex;justify-content:space-around;text-align:center}.stats b{display:block;font-size:20px}</style>
</head><body>
<div class="navbar"><a href="/" style="color:#FFCC02;text-decoration:none;font-weight:bold">← SANNLAS</a><b>👥 FOLLOW</b><span></span></div>
<div class="stats"><div><b id="followersCount">0</b><small>Followers</small></div><div><b id="followingCount">0</b><small>Following</small></div><div><b id="totalUsers">0</b><small>Users</small></div></div>
<div class="tab-bar"><button id="tab-followers" class="active" onclick="switchTab('followers')">Followers</button><button id="tab-following" onclick="switchTab('following')">Following</button><button id="tab-discover" onclick="switchTab('discover')">Discover</button></div>
<div style="padding:8px"><input id="searchUser" placeholder="Search users..." oninput="filterUsers()" style="width:100%;padding:12px;border-radius:20px;border:1px solid #ddd"></div>
<div id="usersList"><p style="text-align:center;padding:30px">Loading...</p></div>
<script>
let currentUser=JSON.parse(localStorage.getItem('sannlas_user')||'{}');
let currentTab='followers';
let allData={followers:[], following:[], discover:[]};
function switchTab(tab){currentTab=tab;document.querySelectorAll('.tab-bar button').forEach(b=>b.classList.remove('active'));document.getElementById('tab-'+tab).classList.add('active');renderList();}
async function loadFollowData(){let email=currentUser.email||''; let phone=currentUser.phone||'';try{let r=await fetch(`/api/follow/stats?email=${encodeURIComponent(email)}&phone=${encodeURIComponent(phone)}`);let d=await r.json();document.getElementById('followersCount').innerText=d.followers||0;document.getElementById('followingCount').innerText=d.following||0;allData.followers=d.followers_list||[];allData.following=d.following_list||[];allData.discover=d.discover||[];document.getElementById('totalUsers').innerText=(d.total_users||0);renderList();}catch(e){document.getElementById('usersList').innerHTML='<p style="color:red;text-align:center">Error: '+e.message+'</p>';}}
function renderList(){let list=allData[currentTab]||[];let q=document.getElementById('searchUser').value.toLowerCase();if(q)list=list.filter(u=>(u.business||'').toLowerCase().includes(q)||(u.email||'').toLowerCase().includes(q));if(list.length==0){document.getElementById('usersList').innerHTML=`<p style="text-align:center;padding:30px;color:#666">No ${currentTab} yet</p>`;return;}document.getElementById('usersList').innerHTML=list.map(u=>{let isSelf=(u.email||'').toLowerCase()===(currentUser.email||'').toLowerCase();let initial=(u.business||u.email||'U')[0].toUpperCase();let btn=isSelf?`<button class="follow-btn btn-self">You</button>`:(u.is_following?`<button class="follow-btn btn-following" onclick="unfollowUser('${u.email}')">Following ✓</button>`:`<button class="follow-btn btn-follow" onclick="followUser('${u.email}')">+ Follow</button>`);return `<div class="user-card"><div class="avatar">${initial}</div><div><b>${u.business||u.email.split('@')[0]}</b><br><small>${u.email} • ${u.followers||0} followers</small></div>${btn}</div>`;}).join('');}
function filterUsers(){renderList();}
async function followUser(targetEmail){if(!currentUser.email){alert('Login first!');return;}let r=await fetch('/api/follow',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:currentUser.email,phone:currentUser.phone,target_email:targetEmail})});let d=await r.json();alert(d.message);if(d.success)loadFollowData();}
async function unfollowUser(targetEmail){if(!currentUser.email){alert('Login first!');return;}if(!confirm('Unfollow?'))return;let r=await fetch('/api/unfollow',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:currentUser.email,phone:currentUser.phone,target_email:targetEmail})});let d=await r.json();alert(d.message);if(d.success)loadFollowData();}
loadFollowData();
</script>
</body></html>
"""

@sannlas_follow_bp.route('/follow')
def follow_page():
    return Response(COMBINED_FOLLOW_HTML, mimetype='text/html')

@sannlas_follow_bp.route('/api/follow/stats')
def follow_stats():
    email = request.args.get('email','').lower().strip()
    phone = request.args.get('phone','').strip()
    users = get_users()
    follows = get_follows()

    # Find me
    me = next((u for u in users if (email and str(u.get('email','')).lower()==email) or (phone and str(u.get('phone',''))==phone)), None)
    my_email = (me.get('email','').lower() if me else email)

    # My followers = who follows me
    my_followers_emails = [f['follower_email'].lower() for f in follows if f.get('following_email','').lower()==my_email]
    # My following = who I follow
    my_following_emails = [f['following_email'].lower() for f in follows if f.get('follower_email','').lower()==my_email]

    def enrich(email_list):
        result=[]
        for em in email_list:
            u = next((x for x in users if str(x.get('email','')).lower()==em), None)
            if u:
                # count followers of this user
                f_count = len([f for f in follows if f.get('following_email','').lower()==em])
                is_following = em in my_following_emails
                result.append({
                    'email': u.get('email'),
                    'business': u.get('business',''),
                    'phone': u.get('phone',''),
                    'followers': f_count,
                    'is_following': is_following
                })
        return result

    followers_list = enrich(my_followers_emails)
    following_list = enrich(my_following_emails)

    # Discover = all users except me and except already following
    discover=[]
    for u in users[:100]:
        em = str(u.get('email','')).lower()
        if em==my_email: continue
        if em in my_following_emails: continue
        f_count = len([f for f in follows if f.get('following_email','').lower()==em])
        discover.append({
            'email': u.get('email'),
            'business': u.get('business',''),
            'phone': u.get('phone',''),
            'followers': f_count,
            'is_following': False
        })
    discover = sorted(discover, key=lambda x: x['followers'], reverse=True)[:50]

    return jsonify({
        'followers': len(my_followers_emails),
        'following': len(my_following_emails),
        'followers_list': followers_list,
        'following_list': following_list,
        'discover': discover,
        'total_users': len(users)
    })

@sannlas_follow_bp.route('/api/follow', methods=['POST'])
def api_follow():
    data = request.json or {}
    email = data.get('email','').lower().strip()
    phone = data.get('phone','').strip()
    target = data.get('target_email','').lower().strip()

    if not target:
        return jsonify({'success':False,'message':'Target required'}),400
    if email==target:
        return jsonify({'success':False,'message':'Cannot follow yourself!'}),400

    users = get_users()
    follows = get_follows()

    target_user = next((u for u in users if str(u.get('email','')).lower()==target), None)
    if not target_user:
        return jsonify({'success':False,'message':'User not found!'}),404

    # Already following?
    exists = next((f for f in follows if f.get('follower_email','').lower()==email and f.get('following_email','').lower()==target), None)
    if exists:
        return jsonify({'success':False,'message':'Already following!'}),400

    follows.append({
        'follower_email': email,
        'follower_phone': phone,
        'following_email': target,
        'time': time.time()
    })
    save_follows(follows)

    # Update follower count in users.json
    for u in users:
        if str(u.get('email','')).lower()==target:
            u['followers'] = int(u.get('followers',0)) + 1
            break
    save_db('users.json', users)

    return jsonify({'success':True,'message':f'✅ Following {target_user.get("business") or target}! 🎉'})

@sannlas_follow_bp.route('/api/unfollow', methods=['POST'])
def api_unfollow():
    data = request.json or {}
    email = data.get('email','').lower().strip()
    target = data.get('target_email','').lower().strip()

    follows = get_follows()
    before = len(follows)
    follows = [f for f in follows if not (f.get('follower_email','').lower()==email and f.get('following_email','').lower()==target)]
    after = len(follows)

    if before==after:
        return jsonify({'success':False,'message':'Not following!'}),400

    save_follows(follows)

    # Decrement count
    users = get_users()
    for u in users:
        if str(u.get('email','')).lower()==target:
            u['followers'] = max(0, int(u.get('followers',0)) - 1)
            break
    save_db('users.json', users)

    return jsonify({'success':True,'message':'Unfollowed!'})

@sannlas_follow_bp.route('/api/follow/check')
def api_follow_check():
    email = request.args.get('email','').lower()
    target = request.args.get('target','').lower()
    follows = get_follows()
    is_following = any(f.get('follower_email','').lower()==email and f.get('following_email','').lower()==target for f in follows)
    return jsonify({'is_following': is_following})
