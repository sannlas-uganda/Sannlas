# seo.py - SANNLAS SEO ENGINE - Single File for ALL Google Words
# If someone types ANY shopping word in Google, this file helps bring them to Sannlas!

SEO_KEYWORDS = "buy, sell, shop Kampala, online shopping Uganda, buy watch Kampala, buy shoes Kampala, buy phone Uganda, buy laptop Kampala, buy bag Kampala, buy TV Uganda, buy fridge Kampala, buy sofa Uganda, iPhone price Uganda, Samsung price Uganda, watch price Uganda, laptop price Uganda, shoes price Kampala, bag price Uganda, TV price Uganda, solar panel price Uganda, sneakers Uganda, fashion Kampala, reels shopping Uganda, TikTok shopping Uganda, video shopping Kampala, wants Uganda, request anything Kampala, find seller Kampala, where to buy anything Kampala, affiliate Uganda, earn money Uganda, promote and earn Uganda, sell online Uganda, make money WhatsApp Uganda, shops in Kampala, market Kampala, online shop Kampala, shopping in Kampala, buy anything Uganda, cheap prices Kampala, delivery Kampala, MTN MoMo shopping Uganda"

SEO_PAGES = {
    "/": {
        "title": "SANNLAS Uganda - #1 Reels Shopping App | Buy, Sell & Request Anything in Kampala",
        "desc": "Buy, sell and request anything in Kampala. Watch reels, buy watches, bags, shoes, phones, laptops, electronics instantly. Post Wants and get offers. Best prices in Uganda."
    },
    "/reels": {
        "title": "Reels Shopping - Watch & Buy in Kampala | Sannlas Uganda",
        "desc": "Watch short reels and buy instantly in Uganda. Watches, bags, shoes, electronics, fashion. TikTok-style shopping in Kampala. Best prices."
    },
    "/shop": {
        "title": "Shops in Kampala - Buy from Verified Sellers | Sannlas",
        "desc": "Browse verified shops in Kampala. Buy watches, phones, shoes, bags, electronics, furniture. Best shops in Uganda, delivery available."
    },
    "/shops": {
        "title": "Shops in Kampala - Buy from Verified Sellers | Sannlas",
        "desc": "Browse verified shops in Kampala. Buy watches, phones, shoes, bags, electronics, furniture. Best shops in Uganda."
    },
    "/wants": {
        "title": "Wants - Request Anything in Kampala | Sannlas Uganda",
        "desc": "Post a Want FREE in Kampala. Request watches, phones, shoes, furniture, anything. Sellers send offers instantly. Best price in Uganda."
    },
    "/sell": {
        "title": "Sell Online FREE in Uganda - Sell Anything | Sannlas",
        "desc": "Sell online FREE in Kampala. Upload product FREE, get buyers instantly. No fees. Best place to sell in Uganda. Earn money online."
    },
    "/upload": {
        "title": "Upload Reel - Sell on Sannlas | Sell in Kampala",
        "desc": "Upload a reel and sell instantly in Kampala. Free to upload, buyers watch and buy. Sell watches, shoes, phones, fashion in Uganda."
    },
    "/transport": {
        "title": "Transport - Bus, Taxi, Boda in Kampala | Sannlas",
        "desc": "Book Bus, Taxi, Boda Boda in Kampala, Uganda. Cheap transport, fast booking on Sannlas. Travel in Uganda."
    },
    "/manufacturers": {
        "title": "Manufacturers in Uganda - Find Factories | Sannlas",
        "desc": "Find manufacturers and factories in Uganda. Buy direct from factory in Kampala. Best wholesale prices."
    },
    "/live": {
        "title": "Live Shopping in Kampala | Sannlas Live",
        "desc": "Watch live shopping in Uganda. Buy live, chat with sellers, best deals in Kampala. Live reels shopping."
    },
    "/delivery": {
        "title": "Delivery Tracking in Kampala | Sannlas Delivery",
        "desc": "Track your delivery in Kampala, Uganda. Fast delivery from Sannlas shops. Order tracking."
    },
    "/invite": {
        "title": "Invite & Earn - Earn Coins in Uganda | Sannlas",
        "desc": "Invite friends and earn coins in Uganda. Earn 1 coin per friend. Invite & Earn on Sannlas. Make money online Uganda."
    },
    "/agency": {
        "title": "Agency - Earn 400 UGX Per Shop | Sannlas Uganda",
        "desc": "Become Sannlas Agency. Help shops join, earn 400 UGX per shop. Earn money in Kampala."
    },
    "/balance": {
        "title": "Balance & Coins - Withdraw Money | Sannlas",
        "desc": "Check balance, coins, withdraw money in Uganda. 1 coin = 599 UGX. Withdraw via MTN MoMo / Airtel Money."
    },
    "/terms": {
        "title": "Terms - Sannlas Uganda",
        "desc": "Terms of Service for Sannlas Uganda - Reels Shopping App in Kampala."
    },
    "/privacy": {
        "title": "Privacy Policy - Sannlas Uganda",
        "desc": "Privacy Policy for Sannlas Uganda - Reels Shopping App in Kampala."
    },
}

# CATEGORY KEYWORDS - So Google shows Sannlas for every product type!
CATEGORY_KEYWORDS = {
    "watches": "buy watch Kampala, watch price Uganda, Rolex Uganda, smartwatch Kampala",
    "shoes": "buy shoes Kampala, sneakers Uganda, Nike Uganda, shoes price Kampala",
    "phones": "buy phone Kampala, iPhone price Uganda, Samsung Uganda, Tecno Kampala",
    "bags": "buy bag Kampala, handbag Uganda, backpack Kampala, bag price Uganda",
    "laptops": "buy laptop Kampala, laptop price Uganda, HP Uganda, Macbook Kampala",
    "electronics": "buy TV Uganda, buy fridge Kampala, electronics Kampala, TV price Uganda",
    "fashion": "fashion Kampala, buy dress Uganda, clothes Kampala, gomesi Uganda",
    "furniture": "buy sofa Kampala, furniture Uganda, bed price Uganda, chair Kampala",
    "solar": "solar panel price Uganda, solar Kampala, inverter Uganda, battery Uganda",
    "vehicles": "buy boda Kampala, e-bike Uganda, motorcycle Kampala, car Uganda",
}

def get_seo_for_path(path):
    """Returns title, desc, keywords for any path"""
    # Product page - dynamic
    if path.startswith("/product/"):
        return {
            "title": "Buy Product in Kampala - Best Price in Uganda | Sannlas",
            "desc": "Buy this product in Kampala at best price. Delivery in Uganda via MTN MoMo / Airtel Money. Buy now on Sannlas - Reels Shopping App.",
            "keywords": SEO_KEYWORDS
        }
    # Shop page - dynamic
    if path.startswith("/shop/"):
        return {
            "title": "Shop in Kampala - Buy from This Seller | Sannlas",
            "desc": "Buy from this verified shop in Kampala. Watches, shoes, phones, bags, electronics. Best prices in Uganda on Sannlas.",
            "keywords": SEO_KEYWORDS
        }
    # Want page - dynamic
    if path.startswith("/wants/"):
        return {
            "title": "Want in Kampala - See Offers | Sannlas Wants",
            "desc": "See offers for this Want in Kampala. Sellers send best prices. Request anything in Uganda on Sannlas.",
            "keywords": SEO_KEYWORDS
        }
    # Static pages
    seo = SEO_PAGES.get(path, SEO_PAGES["/"])
    return {
        "title": seo["title"],
        "desc": seo["desc"],
        "keywords": SEO_KEYWORDS
    }

def register_seo(app):
    """Call this from app.py - 1 line!"""
    @app.context_processor
    def inject_seo():
        from flask import request
        seo = get_seo_for_path(request.path)
        return {
            "seo_title": seo["title"],
            "seo_desc": seo["desc"],
            "seo_keywords": seo["keywords"]
        }
    return app
