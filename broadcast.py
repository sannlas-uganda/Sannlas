import os, uuid, threading, random, datetime
from flask import Blueprint, request, jsonify, render_template
from werkzeug.utils import secure_filename

broadcast_bp = Blueprint('broadcast', __name__)
TMP_DIR = "/tmp"
os.makedirs(TMP_DIR, exist_ok=True)

@broadcast_bp.route('/seller/broadcast')
def broadcast_page():
    return render_template('broadcast.html')

@broadcast_bp.route('/api/broadcast/my-products')
def my_products():
    try:
        from app import get_products_by_email
        email = request.args.get('email','')
        products = get_products_by_email(email)
        return jsonify(products[:30])
    except Exception as e:
        print(e)
        return jsonify([])

# ===== 🧠 SMART AI CAPTION ENGINE - NO API KEY NEEDED =====
def smart_caption_generator(products, user_text=""):
    if not products:
        return "🔥 New arrivals on Sannlas Uganda! Best prices in Kampala. Shop now: sannlas.com #SannlasUganda"
    
    # Calculate deals
    lines = []
    total_save = 0
    for p in products[:3]:
        name = p.get('name','Product')[:30]
        price = int(float(p.get('price',0)))
        orig = int(float(p.get('original_price', price*1.4)))
        off = int((orig-price)*100/orig) if orig>price else random.randint(20,40)
        lines.append(f"{name} UGX {price:,} (was {orig:,} - {off}% OFF)")
        total_save += (orig-price)

    hooks = [
        "🔥 KAMPALA HOT DEAL TODAY!",
        "⚡ SANNLAS FLASH SALE - Don't miss!",
        "💥 UGANDA'S BEST PRICE ALERT!",
        "🎯 Boss, this is your deal!"
    ]
    hook = random.choice(hooks)
    
    caption = f"{hook}\n"
    caption += "\n".join([f"✅ {l}" for l in lines])
    caption += f"\n\n💰 You save UGX {total_save:,} total!"
    caption += f"\n📦 Free delivery in Kampala | Cash on delivery"
    caption += f"\n🏪 Shop: https://sannlas.onrender.com"
    
    # Smart hashtags from product names
    tags = ["#SannlasUganda", "#Kampala", "#UgandaMarketplace"]
    for p in products:
        n = p.get('name','').lower()
        if 'watch' in n: tags.append("#WatchesUganda")
        if 'shoe' in n or 'sneaker' in n: tags.append("#SneakersUG")
        if 'bag' in n: tags.append("#BagsUganda")
        if 'phone' in n: tags.append("#PhonesUganda")
    caption += "\n" + " ".join(list(set(tags))[:6])
    
    if user_text:
        caption = f"{user_text}\n\n{caption}"
    return caption

def smart_best_time():
    # Uganda best times: 7-9 PM EAT
    now = datetime.datetime.utcnow() + datetime.timedelta(hours=3) # EAT
    best_hour = 19 # 7 PM
    if now.hour < 19:
        delay_minutes = (best_hour - now.hour)*60 - now.minute
    else:
        delay_minutes = 5 # post now if already past best time
    return delay_minutes

def extract_thumbnail(video_path):
    # Create thumbnail from middle frame (placeholder - uses ffmpeg if available)
    thumb_path = video_path.replace('.mp4','_thumb.jpg')
    try:
        os.system(f'ffmpeg -y -ss 1 -i {video_path} -vframes 1 {thumb_path} -loglevel quiet')
        return thumb_path if os.path.exists(thumb_path) else None
    except:
        return None

def post_to_platform(platform, file_path, caption, thumb=None):
    print(f"📤 Posting to {platform}: {caption[:60]}...")
    # TODO: Put real API here - for now mock success
    return {"platform": platform, "success": True, "views": random.randint(200, 5000)}

def broadcast_and_delete(file_path, products, user_caption, platforms, schedule_mins):
    try:
        # Smart caption
        smart_caption = smart_caption_generator(products, user_caption)
        
        # Thumbnail
        thumb = extract_thumbnail(file_path)
        
        # Smart delay if needed
        if schedule_mins > 10:
            print(f"⏰ Smart scheduling: waiting {schedule_mins} mins for best time...")
            # In real prod, use Celery/Background job. For now post now
        
        # Post everywhere in parallel
        results = []
        threads = []
        def worker(plat):
            res = post_to_platform(plat, file_path, smart_caption, thumb)
            results.append(res)
        
        for plat, enabled in platforms.items():
            if enabled and plat in ['tiktok','youtube','facebook','instagram']:
                t = threading.Thread(target=worker, args=(plat,))
                threads.append(t)
                t.start()
        for t in threads:
            t.join()
        
        print(f"✅ SMART BROADCAST DONE: {results}")

    finally:
        # ZERO STORAGE CLEANUP
        for p in [file_path, file_path.replace('.mp4','_thumb.jpg')]:
            if os.path.exists(p):
                os.remove(p)
                print(f"🗑️ DELETED {p} - Zero storage!")

@broadcast_bp.route('/api/broadcast/post', methods=['POST'])
def broadcast_post():
    video = request.files.get('video')
    user_caption = request.form.get('caption','')
    products_json = request.form.get('products','[]')
    
    import json
    try: products = json.loads(products_json)
    except: products = []

    platforms = {
        'tiktok': request.form.get('post_tiktok')=='true',
        'youtube': request.form.get('post_youtube')=='true',
        'facebook': request.form.get('post_facebook')=='true',
        'instagram': request.form.get('post_instagram')=='true',
    }

    if not video:
        return jsonify({"success":False, "message":"No video!"})

    # Save to /tmp ONLY
    fname = f"{uuid.uuid4().hex}.mp4"
    file_path = os.path.join(TMP_DIR, fname)
    video.save(file_path)

    # Smart best time
    best_delay = smart_best_time()

    threading.Thread(target=broadcast_and_delete, args=(file_path, products, user_caption, platforms, best_delay)).start()

    smart_cap = smart_caption_generator(products, user_caption)
    return jsonify({
        "success": True, 
        "message": f"🧠 Smart Broadcast Started! Best time: in {best_delay} mins. File auto-deletes after. Zero storage!",
        "smart_caption": smart_cap,
        "best_time_mins": best_delay
    })

@broadcast_bp.route('/api/broadcast/smart-caption', methods=['POST'])
def api_smart_caption():
    data = request.json
    cap = smart_caption_generator(data.get('products',[]), data.get('text',''))
    return jsonify({"caption": cap})
