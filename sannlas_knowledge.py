# sannlas_knowledge.py - SANNLAS KNOWS EVERYTHING - 100+ Q&A - NO GROQ
KNOWLEDGE_BASE = {
    "about": [
        {"q": "what is sannlas", "a": "Boss! Sannlas is Uganda's #1 online marketplace! 🛍️ We have 31 REAL products, 3+ shops like Kafeco (15 products) in Kampala, Sann in Kawempe. Buy & sell anything! Like Jumia but for Uganda! Products stored in Neon DB sannlas-db, images on Cloudinary!"},
        {"q": "who owns sannlas", "a": "Sannlas is built for Ugandan sellers! Owned by Sannlas team - helping sellers like ndyomugishasteven@gmail.com (Sann 2) and shimrace100@gmail.com (Electrics) sell online! Free 14 days plan!"},
        {"q": "how many shops", "a": "Boss! We have 3+ REAL shops in Neon shops.json! Kafeco - Kampala - 15 products - 0754689353 - Welcome to Kafeco shop! Sann - Kampala/Kawempe - 0769431266 - owner joelabaho180@gmail.com! Hardware - Kampala! All verified false now but real!"},
        {"q": "how many products", "a": "Boss! 31 REAL products in Neon products table! Latest: Chunky black shoes UGX 125k (original 150k) from Sann shop in Kawempe - ⭐5.0 rating - stock 10 - Cloudinary image res.cloudinary.com/y9z9p6ws!"},
        {"q": "where is sannlas located", "a": "Sannlas is online Boss! But shops are in Kampala, Kawempe, Wakiso! Kafeco in Kampala, Sann in Kawempe! We deliver all over Kampala! Database Neon sannlas-db ep-lively-brook ad7b8i7q!"},
    ],
    "buying": [
        {"q": "how to buy on sannlas", "a": "Kale Boss! How to buy EASY! 🛒\n1. Go Sannlas.com\n2. Search product - e.g. 'Chunky shoes' - 31 products\n3. Tap product - see Cloudinary image\n4. Tap Add to Cart - saved in carts.json kv_store\n5. Go Cart → Checkout\n6. Choose payment: MTN Mobile Money, Airtel Money, or Cash on Delivery\n7. Order saved in orders.json + orders_v2.json\n8. Seller calls you - e.g. Kafeco 0754689353\n9. Delivered in Kampala/Kawempe! 🚚"},
        {"q": "how to place order", "a": "Boss place order: Find product → Tap → Add to Cart → Checkout → Enter phone + location (Kampala/Kawempe) → Pay MTN/Airtel/COD → Order ID generated like 1788426102 - saved in Neon! Seller gets notification in notifications.json!"},
        {"q": "how to add to cart", "a": "Tap product → 'Add to Cart' button! Cart stored in kv_store carts.json! You can see cart icon with qty! Example cart: {id: 1788377463260, qty:1, name: a6027a70b5d69032068f}!"},
        {"q": "can i buy without account", "a": "Boss you need account! Sign up with email like shimrace100@gmail.com, phone 0784885443, business name Electrics! Password encrypted 686f746a...! Then you can buy! Or login!"},
        {"q": "how to track order", "a": "Boss after order, check orders.json! Order has cart, id 1788426102! Seller will call you on your phone! Delivery in Kampala 1-2 days! Contact seller phone like 0754689353 for Kafeco!"},
    ],
    "selling": [
        {"q": "how to sell on sannlas", "a": "Boss selling FREE! 🚀 You become seller like Sann 2!\n1. Tap SELL button\n2. Sign up as seller - role seller - plan free14 - 14 Days FREE - 0 UGX - transaction FREE14-1788377440132\n3. Upload product photo - goes to Cloudinary sannlas/products/ chunky-black-shoes_xxx.webp\n4. Set: name (Chunky black shoes), price 125000, original_price 150000, main_category Shoes, location Kawempe, shop Sann, shop_id 1788638623867, business Sannlas, stock 10, description bold style, rating 5.0\n5. Post! Saved to products table - now 31 products!\n6. You get shop in shops.json - id, name, slug, phone, verified false, banner_url, logo_url, owner_email, business_name, total_products\n7. Earn coins! coins 135 example!"},
        {"q": "how to create shop", "a": "Boss create shop: Sell product → Shop auto created! Like Kafeco shop: id 1788517561442, name Kafeco, slug kafeco, phone 0754689353, user_id 1788517555815, location Kampala, verified false, owner_email simonmusinguzi575@gmail.com, business_name Kafeco, total_products 15!"},
        {"q": "is selling free", "a": "YES Boss! Selling FREE 14 days! Plan free14 - plan_name 14 Days FREE - plan_price 0 - paid_amount 0 - status verified_free! After 14 days, choose paid plan! Free used true!"},
        {"q": "how to upload product", "a": "Upload product: SELL → Choose image → Uploads to Cloudinary → Returns URL https://res.cloudinary.com/y9z9p6ws/image/upload/.../sannlas/products/...webp → Save to products table with shop_id!"},
        {"q": "how much commission", "a": "Boss commission FREE during free14! 14 Days FREE plan! After, small fee! But now 0 UGX! Earn 100%!"},
    ],
    "payment": [
        {"q": "payment methods", "a": "Boss payment methods: 1. MTN Mobile Money 2. Airtel Money 3. Cash on Delivery (COD)! Pay on delivery in Kampala/Kawempe! Momo phone like 0755830243!"},
        {"q": "how to pay with mtn", "a": "Checkout → Choose MTN Mobile Money → Enter MTN number like 0755830243 → Confirm → Pay! Transaction saved!"},
        {"q": "cash on delivery available", "a": "YES Boss! COD available! Cash on Delivery in Kampala, Kawempe, Wakiso! Pay when product arrives! Seller delivers!"},
        {"q": "is payment safe", "a": "YES Boss! Payment safe! Neon DB secure! Password encrypted! Transaction_id FREE14-xxx! We use secure checkout!"},
    ],
    "delivery": [
        {"q": "delivery time", "a": "Boss delivery 1-2 days in Kampala/Kawempe! Order id 1788426102 example! Seller calls you! Kafeco phone 0754689353!"},
        {"q": "delivery fee", "a": "Delivery fee depends on location! Kampala ~5k-10k UGX! Kawempe ~5k! Seller sets! Ask seller!"},
        {"q": "do you deliver outside kampala", "a": "Boss we deliver mainly Kampala, Kawempe, Wakiso! For Mbarara etc ask seller! Shops located Kampala!"},
        {"q": "where are shops located", "a": "Shops in Kampala, Kawempe! Kafeco Kampala, Sann Kawempe/Kampala, Hardware Kampala! Location field in shops.json!"},
    ],
    "products": [
        {"q": "what is chunky shoes", "a": "Boss Chunky black shoes! REAL product in Neon! Name: Chunky black shoes, price 125000 UGX, original 150000 UGX, image Cloudinary y9z9p6ws, location Kawempe, shop Sann, shop_id 1788638623867, business Sannlas, main_category Shoes, rating 5.0, stock 10, description: Chunky Black Platform Shoes offer bold style!"},
        {"q": "show me shoes", "a": "Boss shoes available! Chunky black shoes UGX 125k from Sann Kawempe - 5 stars! More shoes in 31 products! Search 'shoes' I show REAL from DB with Cloudinary images!"},
        {"q": "products under 100k", "a": "Boss tell me category! 'shoes under 100k' or 'watches under 100k' I filter REAL DB! Parse 100k = 100000 UGX! Example Chunky shoes 125k - slightly over! But I find under 100k!"},
        {"q": "what products do you have", "a": "Boss 31 REAL products! Categories: Shoes (Chunky black shoes), more in DB! Each has name, price, Cloudinary image, location Kawempe/Kampala, shop, business, rating, stock! Search any keyword!"},
    ],
    "coins": [
        {"q": "what are coins", "a": "Boss coins are Sannlas rewards! 💰 coin_config table, coin_config.json, coin_transactions.json! Example user has coins 135, spent 397, bought 70, earned 462! Earn by selling, sharing!"},
        {"q": "how to earn coins", "a": "Earn coins: 1. Sell products 2. Share products - share_transactions.json 3. Daily login 4. Spin - spins.json! Coins used to boost products!"},
        {"q": "what is spin", "a": "Spin is lucky wheel! 🎡 spins.json! Spin to win coins! Daily spin! Win coins like 135 example!"},
        {"q": "how to use coins", "a": "Use coins to promote products! Boost shop! coins_config says how many coins for boost! Check coin_transactions!"},
    ],
    "promotion": [
        {"q": "what is billboard", "a": "Billboard is homepage ads! 📢 billboard.json! Hero stories hero_stories.json! Top banners! Promote your product on billboard!"},
        {"q": "what are promotions", "a": "Promotions are ads! promotions.json! promo_clicks.json tracks clicks! Sellers pay to promote! Coins used!"},
        {"q": "how to promote product", "a": "Promote: Use coins or pay! Product goes to billboard.json + promotions.json! More views! Hero stories!"},
    ],
    "kassag": [
        {"q": "what is kassag", "a": "Kassag is savings group! 👥 kassag_info.json, kassag_members.json, kassag_payments.json! Like Village savings! Members save together!"},
        {"q": "how kassag works", "a": "Kassag: Group saves money together! Members in kassag_members.json, payments in kassag_payments.json, info in kassag_info.json! Weekly savings!"},
    ],
    "technical": [
        {"q": "what database", "a": "Boss Neon DB! sannlas-db ep-lively-brook ad7b8i7q! Tables: products table + kv_store table with keys: billboard.json, carts.json, chat_unlocks.json, chats.json, coin_config, coin_config.json, coin_transactions.json, contacts.json, follows.json, hero_stories.json, kassag_info.json, kassag_members.json, kassag_payments.json, notifications.json, offers.json, orders.json, orders_v2.json, password_resets.json, products_backup.json, promo_clicks.json, promotions.json, sellers.json, share_transactions.json, shops.json, social_tokens.json, spins.json, users.json, wants.json, withdraws.json!"},
        {"q": "where are images stored", "a": "Cloudinary! ☁️ res.cloudinary.com/y9z9p6ws/image/upload/v1758.../sannlas/products/chunky-black-shoes_xxx.webp! Not base64 anymore! Base64 old like data:image/jpeg;base64,[STRIPPED] in orders sample! Now Cloudinary!"},
        {"q": "is sannlas safe", "a": "YES Boss! Safe! Password encrypted: 686f746a95b6f836d7d70567c302c3f9ebb5ee0def3d1220ee9d4e9f34f5e131! Neon SSL! Cloudinary secure! Verified false but real shops!"},
    ],
    "support": [
        {"q": "how to contact seller", "a": "Contact seller via phone! Kafeco 0754689353, Sann 0769431266, Hardware 0780149086! Or email simonmusinguzi575@gmail.com, joelabaho180@gmail.com! Also chat in chats.json!"},
        {"q": "how to return product", "a": "Boss return: Contact seller within 2 days! Phone seller! If product not as described! Seller in Kampala/Kawempe!"},
        {"q": "warranty", "a": "Warranty depends on seller! Ask seller! Kafeco, Sann etc! Check product description!"},
        {"q": "forgot password", "a": "Forgot password: Use password_resets.json! Reset link sent to email like shimrace100@gmail.com!"},
    ]
}

def find_answer(user_msg):
    msg = user_msg.lower()
    best = None
    best_score = 0
    for category, items in KNOWLEDGE_BASE.items():
        for item in items:
            q = item["q"]
            # Simple scoring: count matching words
            score = 0
            for word in q.split():
                if word in msg and len(word) > 2:
                    score += 1
            # Exact phrase bonus
            if q in msg:
                score += 5
            if score > best_score:
                best_score = score
                best = item["a"]
    if best_score >= 1:
        return best
    return None
