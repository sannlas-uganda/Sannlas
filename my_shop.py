<!DOCTYPE html>
<html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<title>My Shop - SANNLAS</title>
<style>
body{font-family:Arial;background:#f5f5f5;margin:0;padding-bottom:80px;color:#000}
.header{background:#000;color:#fff;padding:20px;text-align:center;position:relative;min-height:160px}
.header h1{color:#FFCC02;margin:8px 0;font-size:20px}
.shop-logo{width:90px;height:90px;border-radius:50%;border:3px solid #FFCC02;object-fit:cover;background:#fff;cursor:pointer;margin-top:10px}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;padding:10px}
.stat-card{background:#fff!important;border-radius:12px;padding:10px;text-align:center;box-shadow:0 2px 6px rgba(0,0,0,.1);color:#000!important}
.stat-card b{font-size:18px;display:block;color:#000!important}
.stat-card small{color:#666}
.card{background:#fff;border-radius:12px;margin:10px;padding:12px;box-shadow:0 2px 10px rgba(0,0,0,.08);color:#000}
.products{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:10px;padding:10px}
.pcard{background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,.1);position:relative;color:#000}
.pcard img{width:100%;height:150px;object-fit:cover}
.pcard video{width:100%;height:150px;object-fit:cover}
.btn{padding:8px 12px;border:none;border-radius:10px;font-weight:bold;cursor:pointer;margin:3px;font-size:12px}
.badge{position:absolute;top:8px;right:8px;padding:4px 8px;border-radius:20px;font-size:11px;font-weight:bold}
.quick{display:grid;grid-template-columns:1fr 1fr;gap:10px;padding:10px}
.quick button{padding:14px;border-radius:12px;font-size:14px;border:none;font-weight:800}
.modal{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,.7);z-index:9999;align-items:center;justify-content:center;padding:15px}
.modal-box{background:#fff;border-radius:15px;padding:15px;max-width:400px;width:100%;color:#000}
input,textarea,select{width:100%;padding:10px;margin:6px 0;border:1px solid #ddd;border-radius:10px}
.bell-btn{position:absolute;top:12px;right:12px;background:#FFCC02;color:#000;border:none;padding:10px 12px;border-radius:50%;font-size:18px;cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,0.3)}
.bell-count{position:absolute;top:-5px;right:-5px;background:red;color:white;font-size:11px;font-weight:900;padding:3px 7px;border-radius:20px;min-width:10px;display:none;text-align:center;border:2px solid #000}
.order-card{background:#fff;border:2px solid #FFCC02;border-radius:14px;padding:12px;margin-bottom:10px}
.order-badge{padding:4px 10px;border-radius:20px;font-size:11px;font-weight:800}
.PENDING{background:#FEF3C7;color:#92400E} .CONFIRMED{background:#DBEAFE;color:#1E40AF} .PACKED{background:#E0E7FF;color:#3730A3} .SHIPPED{background:#FEF08A;color:#713F12} .DELIVERED{background:#D1FAE5;color:#065F46}
</style></head><body>

<div class="header" id="shopHeader">
 <button onclick="location.href='/'" style="position:absolute;top:12px;left:12px;background:#FFCC02;color:#000;border:none;padding:8px 16px;border-radius:20px;font-weight:900">🏠 Home</button>
 <button class="bell-btn" onclick="document.getElementById('ordersSection').scrollIntoView({behavior:'smooth'}); loadSellerOrders();">🔔<span id="orderCount" class="bell-count">0</span></button>
 <img id="sLogo" class="shop-logo" src="https://via.placeholder.com/150" onclick="document.getElementById('logoInput').click()">
 <input type="file" id="logoInput" accept="image/*" hidden onchange="uploadLogo()">
 <div id="sName" style="color:#fff;margin-top:8px">Loading...</div>
 <div id="sInfo" style="font-size:13px;color:#aaa"></div>
 <div style="margin-top:8px"><span style="background:#FFCC02;color:#000;padding:3px 10px;border-radius:20px;font-size:11px" id="sVerified">⏳ Checking</span></div>
</div>

<!-- 🔔 PENDING AGENCY REQUESTS - OWNER APPROVAL BOX - NEW INSERTED -->
<div id="pendingRequestsBox" style="display:none;background:#fff;border:3px solid #FF6A00;border-radius:16px;padding:16px;margin:10px;box-shadow:0 4px 12px rgba(0,0,0,0.1)">
  <h3 style="margin:0 0 8px 0;color:#000">🔔 New Helper Requests (<span id="pendingCount">0</span>) - Approve!</h3>
  <p style="font-size:11px;color:#666;margin:0 0 12px 0">Agents want to upload products FOR YOU and earn 400 UGX. You keep shop ownership!</p>
  <div id="pendingList">Loading...</div>
</div>

<div style="padding:10px 15px 0 15px;display:flex;justify-content:space-between;align-items:center;background:#f5f5f5"><h3 style="margin:0;color:#000">📊 Today's Business</h3><small id="todayDate" style="color:#666"></small></div>
<div class="stats">
 <div class="stat-card">👁️<b id="stViews">0</b><small>Views</small></div>
 <div class="stat-card">📦<b id="stProducts">0</b><small>Products</small></div>
 <div class="stat-card">💬<b id="stWhats">0</b><small>WhatsApp</small></div>
 <div class="stat-card" style="border:2px solid #FFCC02">🪙<b id="stCoins">0</b><small>Coins</small></div>
</div>

<div class="card">
 <div style="display:flex;justify-content:space-between;align-items:center">
  <h3 style="margin:0">🛍️ My Products</h3>
  <button onclick="location.href='/?open=sell'" style="background:#FF6A00;color:#fff;padding:8px 14px;border-radius:10px;font-weight:900;border:none">➕ Add FREE</button>
 </div>
 <div class="products" id="myProducts" style="margin-top:10px"></div>
 <button id="loadMoreBtn" onclick="loadMoreProducts()" style="display:none;background:#fff;border:2px solid #FF6A00;color:#FF6A00;width:100%;padding:14px;border-radius:12px;font-weight:900;margin-top:12px">⬇️ Load More</button>
</div>

<div class="card" id="ordersSection">
 <h3 style="margin:0 0 12px 0">📦 My Shop Orders</h3>
 <button onclick="toggleOrders()" id="singleOrdersBtn" style="width:100%;padding:16px;background:#000;color:#FFCC02;border:3px solid #FFCC02;border-radius:14px;font-weight:900;font-size:16px;display:flex;justify-content:center;align-items:center;gap:10px">
   📦 Orders <span id="myOrdersBadge" style="background:red;color:#fff;padding:4px 10px;border-radius:20px;font-size:13px;display:none">0</span>
 </button>
 <div id="ordersBox" style="margin-top:12px">Loading orders...</div>
</div>

<div class="card">
 <h3>⚙️ Shop Settings</h3>
 <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
  <button class="btn" style="background:#000;color:#fff;width:100%" onclick="openSettings()">✏️ Edit Shop Info</button>
  <button class="btn" style="background:#fff;border:1px solid #ccc;width:100%" onclick="toggleHours()">🕒 Hours</button>
 </div>
 <div id="settingsPreview" style="font-size:13px;color:#555;margin-top:10px"></div>
</div>

<div class="card">
 <h3>⚡ Quick Actions</h3>
 <div class="quick">
  <button onclick="location.href='/?open=sell'" style="background:#FF6A00;color:#fff;width:100%">➕ Add Product FREE</button>
  <button onclick="shareShop()" style="background:#00AA00;color:#fff;width:100%">🔗 Share Shop</button>
  <button onclick="viewAsBuyer()" style="background:#fff;border:2px solid #00AA00;color:#00AA00;width:100%">👁️ View as Buyer</button>
  <button onclick="location.href='/@'+myShopSlug" style="background:#fff;border:2px solid #FFCC02;color:#000;width:100%">🎬 My Reels Profile</button>
 </div>
</div>
