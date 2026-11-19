# seo.py - SANNLAS SEO - MAJOR PAGES + ONE BRAIN AUTO
from flask import Response

SEO_PAGES = {
    "/": {"title": "SANNLAS Uganda - #1 Reels Shopping App | Buy, Sell & Request Anything in Kampala", "desc": "Buy, sell and request anything in Kampala. Watch reels, buy watches, bags, shoes, phones, laptops. Post Wants and get offers."},
    "/reels": {"title": "Reels Shopping - Watch & Buy in Kampala | Sannlas Uganda", "desc": "Watch short reels and buy instantly in Uganda. Watches, bags, shoes, electronics, fashion."},
    "/shops": {"title": "Shops in Kampala - Buy from Verified Sellers | Sannlas", "desc": "Browse verified shops in Kampala. Buy watches, phones, shoes, bags, electronics."},
    "/wants": {"title": "Wants - Request Anything in Kampala | Sannlas Uganda", "desc": "Post a Want FREE in Kampala. Request watches, phones, shoes, furniture, anything."},
    "/sell": {"title": "Sell Online FREE in Uganda - Sell Anything | Sannlas", "desc": "Sell online FREE in Kampala. Upload product FREE, get buyers instantly."},
    "/upload": {"title": "Upload Reel - Sell on Sannlas | Sell in Kampala", "desc": "Upload a reel and sell instantly in Kampala. Free to upload."},
    "/transport": {"title": "Transport - Bus, Taxi, Boda in Kampala | Sannlas", "desc": "Book Bus, Taxi, Boda Boda in Kampala, Uganda. Cheap transport."},
    "/manufacturers": {"title": "Manufacturers in Uganda - Find Factories | Sannlas", "desc": "Find manufacturers and factories in Uganda. Buy direct from factory."},
    "/live": {"title": "Live Shopping in Kampala | Sannlas Live", "desc": "Watch live shopping in Uganda. Buy live, chat with sellers."},
    "/delivery": {"title": "Delivery Tracking in Kampala | Sannlas Delivery", "desc": "Track your delivery in Kampala, Uganda."},
    "/invite": {"title": "Invite & Earn - Earn Coins in Uganda | Sannlas", "desc": "Invite friends and earn coins in Uganda. Earn 1 coin per friend."},
    "/agency": {"title": "Agency - Earn 400 UGX Per Shop | Sannlas Uganda", "desc": "Become Sannlas Agency. Help shops join, earn 400 UGX per shop."},
    "/terms": {"title": "Terms - Sannlas Uganda", "desc": "Terms of Service for Sannlas Uganda."},
    "/privacy": {"title": "Privacy Policy - Sannlas Uganda", "desc": "Privacy Policy for Sannlas Uganda."},
    "/about": {"title": "What is SANNLAS? Uganda's #1 Reels Shopping App | Sannlas Uganda", "desc": "SANNLAS is Uganda's #1 Reels Shopping App in Kampala. Buy, sell, request anything, book transport, find manufacturers, go live, earn coins."},
    "/faq": {"title": "Sannlas FAQ - How to Buy, Sell & Request in Uganda | Sannlas", "desc": "How to buy, sell FREE, post Wants, book transport, earn coins on Sannlas Uganda. Frequently asked questions."},
}

def get_seo_for_path(path):
    if path.startswith("/product/"):
        # TRY BRAIN - Get real product name for Google title!
        try:
            from sannlas_brain import get_live_products
            pid = path.replace("/product/", "").strip()
            for p in get_live_products(limit=1000):
                if str(p.get("id")) == str(pid) or str(p.get("product_id")) == str(pid):
                    name = p.get("name", "Product")
                    price = p.get("price", "")
                    loc = p.get("location", "Kampala")
                    return {"title": f"Buy {name} in {loc} - {price} UGX | SANNLAS Uganda", "desc": f"Buy {name} in {loc} at best price {price} UGX on SANNLAS Uganda. Fast delivery in Kampala.", "robots": "index, follow"}
        except:
            pass
        return {"title": "Sannlas - Buy in Kampala", "desc": "Buy in Kampala on Sannlas.", "robots": "index, follow"}
    if path.startswith("/shop/"):
        return {"title": "Shop in Kampala - Buy from This Seller | Sannlas", "desc": "Buy from this verified shop in Kampala.", "robots": "index, follow"}
    seo = SEO_PAGES.get(path, SEO_PAGES["/"])
    return {"title": seo["title"], "desc": seo["desc"], "robots": "index, follow"}

def register_seo(app):
    @app.context_processor
    def inject_seo():
        from flask import request
        seo = get_seo_for_path(request.path)
        return {"seo_title": seo["title"], "seo_desc": seo["desc"], "seo_robots": seo["robots"], "seo_keywords": ""}

    @app.route('/sitemap.xml')
    def sitemap_xml():
        # ===== ONE BRAIN SITEMAP - STATIC + PRODUCTS + SHOPS AUTO =====
        xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        # 1. Your static pages - KEPT!
        for path, data in SEO_PAGES.items():
            loc = f"https://sannlas.store{path}" if path != "/" else "https://sannlas.store/"
            xml += f'  <url><loc>{loc}</loc><priority>0.9</priority><changefreq>daily</changefreq></url>\n'
        # 2. BRAIN - Auto products!
        try:
            from sannlas_brain import get_live_products, get_live_shops
            products = get_live_products(limit=1000)
            for p in products:
                pid = p.get("id") or p.get("product_id") or ""
                if pid:
                    xml += f'  <url><loc>https://sannlas.store/product/{pid}</loc><priority>0.8</priority><changefreq>daily</changefreq></url>\n'
            # 3. BRAIN - Auto shops!
            shops = get_live_shops(limit=500)
            for s in shops:
                sid = s.get("id") or s.get("shop_id") or ""
                if sid:
                    xml += f'  <url><loc>https://sannlas.store/shop/{sid}</loc><priority>0.7</priority><changefreq>daily</changefreq></url>\n'
            # 4. BRAIN - Auto categories!
            for cat in ["phones", "shoes", "watches", "bags", "laptops", "furniture", "hair", "groceries", "clothes"]:
                xml += f'  <url><loc>https://sannlas.store/buy-{cat}-in-kampala</loc><priority>0.8</priority><changefreq>daily</changefreq></url>\n'
        except Exception as e:
            print(f"Sitemap brain error: {e}")
        xml += '</urlset>'
        return Response(xml, mimetype='text/xml')

    @app.route('/about')
    def about_page():
        from flask import render_template
        return render_template('about.html')

    @app.route('/faq')
    def faq_page():
        from flask import render_template
        return render_template('faq.html')
    return app
