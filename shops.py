# shop.py - UPDATED WITH TAP PROFILE TO SEE STATS

@shops_bp.route('/shop/<path:slug>')
def shop_page_slug(slug):
    return """
<!DOCTYPE html>
<html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Shop</title><style>
body{font-family:system-ui;background:#f8fafc;margin:0}
.topnav{background:#000;color:#fff;padding:10px 14px;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:9999}
.topnav a{color:#FFCC02;text-decoration:none;font-weight:900}
.shop-profile-header{background:#fff;padding:16px;border-bottom:1px solid #eee}
.profile-top{display:flex;gap:14px;align-items:center}
.avatar-box{width:86px;height:86px;border-radius:50%;border:3px solid #FFCC02;background:#fff;overflow:hidden;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:34px;font-weight:900;cursor:pointer;position:relative}
.avatar-box:active{transform:scale(0.95)}
.avatar-box img{width:100%;height:100%;object-fit:cover}
.stats-row{flex:1;display:flex;justify-content:space-around;text-align:center}
.stat{cursor:pointer}
.stat b{display:block;font-size:17px;color:#111;line-height:1}
.stat span{font-size:10px;color:#666;font-weight:700;letter-spacing:0.5px;margin-top:3px;display:block}
.shop-name{font-weight:900;font-size:18px;margin-top:12px}
.shop-bio{font-size:12px;color:#666;margin:4px 0;line-height:1.4}
.action-row{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap}
.grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;padding:14px;max-width:1000px;margin:auto}
@media(min-width:700px){.grid{grid-template-columns:repeat(4,1fr)}}
.card{background:white;border-radius:16px;overflow:hidden;box-shadow:0 2px 10px rgba(0,0,0,.06);border:1px solid #eee}
.card img{width:100%;height:160px;object-fit:cover}
.card-body{padding:10px 12px}
.card h4{margin:0 0 6px;font-size:14px;line-height:1.2;height:34px;overflow:hidden}
.price{font-weight:900;color:#000}
.btn{display:block;text-align:center;background:#000;color:#FFCC02;padding:8px;border-radius:10px;text-decoration:none;margin-top:8px;font-weight:800;font-size:13px}
#loading{text-align:center;padding:60px 20px;font-size:18px}

/* === NEW MODAL === */
#profileStatsModal{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.85);z-index:10000;align-items:center;justify-content:center;padding:20px}
.modal-box{background:#fff;border-radius:24px;padding:20px;width:100%;max-width:380px;animation:pop .2s}
@keyframes pop{from{transform:scale(.9)}to{transform:scale(1)}}
.modal-top{display:flex;align-items:center;gap:14px;margin-bottom:16px}
.modal-avatar{width:64px;height:64px;border-radius:50%;border:3px solid #FFCC02;display:flex;align-items:center;justify-content:center;font-size:28px;font-weight:900;background:#000;color:#FFCC02;overflow:hidden}
.modal-avatar img{width:100%;height:100%;object-fit:cover}
.modal-stats{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:10px}
.modal-stat{background:#f8fafc;border-radius:14px;padding:14px;text-align:center;border:1px solid #eee}
.modal-stat b{font-size:20px;display:block}
.modal-stat span{font-size:11px;color:#666;font-weight:700}
</style></head>
<body>
<div class="topnav"><a href="javascript:history.back()" onclick="if(!document.referrer.includes('/shop')){location.href='/all-shops'}else{history.back()} return false">← Back to Shops</a><a href="/">SANNLAS</a></div>

<div class="shop-profile-header" id="shop-header" style="display:none">
  <div class="profile-top">
    <div class="avatar-box" id="shopAvatarBox" onclick="openStatsModal()">S</div>
    <div class="stats-row">
      <div class="stat" onclick="openStatsModal()"><b id="statFollowing">0</b><span>Following</span></div>
      <div class="stat" onclick="openStatsModal()"><b id="statFollowers">0</b><span>Followers</span></div>
      <div class="stat" onclick="openStatsModal()"><b id="statLikes">0</b><span>Likes</span></div>
      <div class="stat" onclick="openStatsModal()"><b id="statViews">0</b><span>Views</span></div>
    </div>
  </div>
  <div id="headerText">
    <div class="shop-name" id="shopNameBig">Loading...</div>
    <div class="shop-bio" id="shopBioText"></div>
    <div class="action-row" id="shopActions"></div>
  </div>
</div>

<div id="loading">⏳ Loading shop...</div>
<div id="products" class="grid"></div>

<!-- PROFILE STATS MODAL - WHEN TAP S -->
<div id="profileStatsModal" onclick="if(event.target==this)closeStatsModal()">
  <div class="modal-box">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
      <b style="font-size:16px">Shop Profile</b>
      <button onclick="closeStatsModal()" style="width:32px;height:32px;border-radius:50%;border:none;background:#000;color:#fff;font-weight:900">✕</button>
    </div>
    <div class="modal-top">
      <div class="modal-avatar" id="modalAvatar">S</div>
      <div>
        <div id="modalShopName" style="font-weight:900;font-size:16px">Shop</div>
        <div id="modalShopLocation" style="font-size:12px;color:#666">Kampala • Active now</div>
      </div>
    </div>
    <div class="modal-stats">
      <div class="modal-stat"><b id="mFollowing">0</b><span>Following</span></div>
      <div class="modal-stat"><b id="mFollowers">0</b><span>Followers</span></div>
      <div class="modal-stat"><b id="mLikes">0</b><span>❤️ Likes</span></div>
      <div class="modal-stat"><b id="mViews">0</b><span>👁️ Views</span></div>
      <div class="modal-stat" style="grid-column:span 2;background:#000;color:#FFCC02;border-color:#000"><b id="mProducts">0</b><span style="color:#FFCC02">Products</span></div>
    </div>
    <button onclick="closeStatsModal()" style="width:100%;margin-top:14px;background:#FFCC02;color:#000;border:none;padding:12px;border-radius:20px;font-weight:900">Close</button>
  </div>
</div>

<script>
let CURRENT_STATS = null;
let CURRENT_SHOP = null;

function cleanSlug(s){return (s||'shop').toString().toLowerCase().replace(/%20|%2520/gi,'-').replace(/\\s+/g,'-').replace(/[^a-z0-9-]+/g,'-').replace(/-+/g,'-').replace(/^-|-$/g,'')||'shop';}

function openStatsModal(){
  if(!CURRENT_STATS && !CURRENT_SHOP) return;
  document.getElementById('profileStatsModal').style.display='flex';
  if(CURRENT_SHOP){
    document.getElementById('modalShopName').innerText = CURRENT_SHOP.business_name||CURRENT_SHOP.name||'Shop';
    document.getElementById('modalShopLocation').innerText = (CURRENT_SHOP.location||'Kampala') + ' • Active now';
    let av = document.getElementById('modalAvatar');
    if(CURRENT_SHOP.logo) av.innerHTML = `<img src="${CURRENT_SHOP.logo}">`;
    else av.innerText = (CURRENT_SHOP.business_name||'S')[0].toUpperCase();
  }
  if(CURRENT_STATS){
    document.getElementById('mFollowing').innerText = (CURRENT_STATS.following||0).toLocaleString();
    document.getElementById('mFollowers').innerText = (CURRENT_STATS.followers||0).toLocaleString();
    document.getElementById('mLikes').innerText = (CURRENT_STATS.total_likes||0).toLocaleString();
    document.getElementById('mViews').innerText = (CURRENT_STATS.total_views||0).toLocaleString();
    document.getElementById('mProducts').innerText = (CURRENT_STATS.total_products||0).toLocaleString();
  }
}
function closeStatsModal(){document.getElementById('profileStatsModal').style.display='none';}

async function loadShop(){
 let raw=decodeURIComponent(location.pathname.split('/shop/')[1].split('?')[0].split('/')[0]);
 let slug=cleanSlug(raw);
 try{
  const r=await fetch('/api/shop/'+encodeURIComponent(slug));
  const d=await r.json();
  if(!d.shop){ document.getElementById('loading').innerHTML='❌ Shop not found: '+raw; return;}
  const shop=d.shop, prods=d.products||[];
  CURRENT_SHOP = shop;
  document.getElementById('loading').style.display='none';
  document.getElementById('shop-header').style.display='block';
  
  let avatarBox=document.getElementById('shopAvatarBox');
  if(shop.logo){avatarBox.innerHTML=`<img src="${shop.logo}">`;}else{avatarBox.innerText=(shop.business_name||'S')[0].toUpperCase();}
  
  document.getElementById('shopNameBig').innerText='🏪 '+(shop.business_name||shop.name||slug);
  document.getElementById('shopBioText').innerHTML=`📍 ${shop.location||'Uganda'} | 📞 ${shop.phone||''}<br>${shop.description||'Quality products!'}<br><span style="color:#FF6A00;font-weight:800">${prods.length} Products • Kampala</span>`;
  
  try{
    let rs=await fetch('/api/shop/'+encodeURIComponent(slug)+'/stats');
    let stats=await rs.json();
    CURRENT_STATS = stats;
    document.getElementById('statFollowers').innerText=(stats.followers||0).toLocaleString();
    document.getElementById('statFollowing').innerText=(stats.following||0).toLocaleString();
    document.getElementById('statLikes').innerText=(stats.total_likes||0).toLocaleString();
    document.getElementById('statViews').innerText=(stats.total_views||0).toLocaleString();
  }catch(e){}

  document.getElementById('shopActions').innerHTML=`
    <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:10px">
      <button style="background:#25D366;color:#fff;padding:10px 14px;border-radius:20px;border:none;font-weight:800" onclick="location.href='https://wa.me/${(shop.phone||'').toString().replace(/[^0-9]/g,'')}'">💬 WhatsApp</button>
      <button style="background:#000;color:#FFCC02;border:2px solid #FFCC02;padding:10px 14px;border-radius:20px;font-weight:800">💬 Chat</button>
      <button style="background:#FFCC02;color:#000;padding:10px 14px;border-radius:20px;border:none;font-weight:800">📞 Call</button>
      <button style="background:#fff;color:#000;border:2px solid #000;padding:10px 14px;border-radius:20px" onclick="navigator.share?navigator.share({title:shop.business_name,url:location.href}):alert('Link copied: '+location.href)">🔗 Share</button>
    </div>
    <div style="margin-top:14px;display:flex;gap:10px;justify-content:center;flex-wrap:wrap;align-items:center">
      <a href="/@/${cleanSlug(shop.shop_slug||shop.business_name)}" style="color:#000;background:#FFCC02;text-decoration:none;font-weight:900;padding:12px 20px;border-radius:25px;font-size:14px">🎬 View Reels Profile</a>
      <a href="/my-shop" style="color:#FFCC02;background:#1a1a1a;text-decoration:none;font-weight:900;padding:12px 20px;border-radius:25px;font-size:14px;border:2px solid #FFCC02">🏪 My Shop</a>
    </div>
  `;
  
  let h='';
  prods.forEach(p=>{h+=`<div class="card"><img src="${p.image||'https://via.placeholder.com/300'}"><div class="card-body"><h4>${(p.name||p.title||'').replace(/</g,'&lt;')}</h4><div class="price">UGX ${(p.price||0).toLocaleString()}</div><a class="btn" href="/product/${p.id||p._id}">View Product</a></div></div>`;});
  if(!prods.length) h='<p style="padding:20px">No products yet</p>';
  document.getElementById('products').innerHTML=h;
 }catch(e){ document.getElementById('loading').innerHTML='Error: '+e.message; }
}
loadShop();
</script></body></html>
"""
