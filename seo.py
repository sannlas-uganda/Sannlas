# seo.py - SANNLAS SEO - MAJOR PAGES ONLY
from flask import Response

SEO_PAGES = {
    "/": {"title": "SANNLAS Uganda - #1 Reels Shopping App | Buy, Sell & Request Anything in Kampala", "desc": "Buy, sell and request anything in Kampala. Watch reels, buy watches, bags, shoes, phones, laptops. Post Wants and get offers."},
    "/reels": {"title": "Reels Shopping - Watch & Buy in Kampala | Sannlas Uganda", "desc": "Watch short reels and buy instantly in Uganda. Watches, bags, shoes, electronics, fashion."},
    "/shop": {"title": "Shops in Kampala - Buy from Verified Sellers | Sannlas", "desc": "Browse verified shops in Kampala. Buy watches, phones, shoes, bags, electronics."},
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
}

def get_seo_for_path(path):
    # PRODUCTS = DO NOT INDEX - We only want major pages!
    if path.startswith("/product/"):
        return {"title": "Sannlas - Buy in Kampala", "desc": "Buy in Kampala on Sannlas.", "robots": "noindex, follow"}
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
    # === SITEMAP - MAJOR PAGES ONLY - LIVES HERE, NOT IN app.py ===

@app.route('/sitemap.xml')
    def sitemap_xml():
        xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        for path, data in SEO_PAGES.items():
            loc = f"https://sannlas.store{path}" if path != "/" else "https://sannlas.store/"
            xml += f'  <url><loc>{loc}</loc><priority>0.9</priority><changefreq>daily</changefreq></url>\n'
        xml += '</urlset>'
        return Response(xml, mimetype='text/xml')
    return app
