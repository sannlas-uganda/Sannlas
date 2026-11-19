# seo_auto.py - GOOGLE MOUTH - Uses ONE BRAIN!
# Google reads brain automatically. No manual writing!
from flask import Blueprint, Response
import json
from sannlas_brain import get_live_products, get_live_shops, BRAIN_KNOWLEDGE, get_live_admin_knowledge

seo_auto_bp = Blueprint('seo_auto', __name__)

# ===== 1. AUTO SITEMAP - Google checks this every day =====
@seo_auto_bp.route('/sitemap.xml')
def auto_sitemap():
    products = get_live_products(limit=1000)
    shops = get_live_shops(limit=500)
    xml = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    # Static pages
    for url in ["", "/about", "/faq"]:
        xml.append(f"<url><loc>https://sannlas.store{url}</loc><changefreq>daily</changefreq><priority>0.9</priority></url>")
    # AUTO: Every product = 1 Google page!
    for p in products:
        pid = p.get("id") or p.get("product_id") or ""
        if pid:
            xml.append(f"<url><loc>https://sannlas.store/product/{pid}</loc><changefreq>daily</changefreq><priority>0.8</priority></url>")
    # AUTO: Every shop = 1 Google page!
    for s in shops:
        sid = s.get("id") or s.get("shop_id") or ""
        if sid:
            xml.append(f"<url><loc>https://sannlas.store/shop/{sid}</loc><changefreq>daily</changefreq><priority>0.7</priority></url>")
    xml.append('</urlset>')
    return Response("\n".join(xml), mimetype='application/xml')

# ===== 2. AUTO PRODUCT PAGE - Google reads price, image, location =====
@seo_auto_bp.route('/product/<pid>')
def auto_product_page(pid):
    products = get_live_products(limit=1000)
    prod = None
    for p in products:
        if str(p.get("id")) == str(pid) or str(p.get("product_id")) == str(pid):
            prod = p
            break
    if not prod:
        return "Product not found on SANNLAS", 404
    name = prod.get("name", "Product")
    price = prod.get("price", "0")
    location = prod.get("location", "Kampala")
    image = prod.get("image", "")
    desc = prod.get("description", f"Buy {name} in {location} on SANNLAS Uganda. Best price {price} UGX.")
    schema = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": name,
        "description": desc,
        "image": image,
        "offers": {
            "@type": "Offer",
            "price": str(price).replace(",", "").replace("UGX", ""),
            "priceCurrency": "UGX",
            "availability": "https://schema.org/InStock",
            "seller": {"@type": "Organization", "name": "SANNLAS Uganda"}
        }
    }
    html = f"""
    <!DOCTYPE html><html><head>
    <title>Buy {name} in {location} - {price} UGX | SANNLAS Uganda</title>
    <meta name="description" content="{desc}">
    <script type="application/ld+json">{json.dumps(schema)}</script>
    </head><body>
    <h1>Buy {name} in {location}</h1>
    <p>Price: {price} UGX</p>
    <p>{desc}</p>
    <img src="{image}" alt="{name}" style="max-width:400px">
    <br><a href="https://sannlas.store">Buy Now on SANNLAS</a>
    <p>SANNLAS - Uganda's #1 Reels Shopping App in Kampala.</p>
    </body></html>
    """
    return html

# ===== 3. AUTO CATEGORY PAGE - Example: /buy-phones-in-kampala =====
@seo_auto_bp.route('/buy-<category>-in-kampala')
def auto_category(category):
    products = get_live_products(limit=1000)
    matched = [p for p in products if category.lower() in str(p.get("name", "")).lower() or category.lower() in str(p.get("category", "")).lower()]
    title = f"Buy {category.capitalize()} in Kampala - Best Prices | SANNLAS Uganda"
    items = ""
    for p in matched[:20]:
        items += f"<div><h3>{p.get('name')}</h3><p>{p.get('price')} UGX - {p.get('location', 'Kampala')}</p></div>"
    if not items:
        items = f"<p>No {category} yet in Kampala? Be first! Post a WANT FREE on SANNLAS and sellers will send you offers!</p>"
    html = f"""
    <!DOCTYPE html><html><head>
    <title>{title}</title>
    <meta name="description" content="Buy {category} in Kampala at best price. {len(matched)} {category} available on SANNLAS.">
    </head><body>
    <h1>Buy {category.capitalize()} in Kampala</h1>
    <p>{len(matched)} {category} found on SANNLAS Uganda!</p>
    {items}
    <br><a href="https://sannlas.store">Shop Now on SANNLAS</a>
    </body></html>
    """
    return html

# ===== 4. AUTO FAQ PAGE - Google reads your Admin Q&A too! =====
@seo_auto_bp.route('/auto-faq')
def auto_faq():
    admin = get_live_admin_knowledge()
    items = ""
    for q in admin:
        items += f"<div><h3>{q.get('question', '')}</h3><p>{q.get('answer', '')}</p></div>"
    for b in BRAIN_KNOWLEDGE:
        items += f"<div><h3>{b['keywords'][0]}</h3><p>{b['answer']}</p></div>"
    html = f"""
    <!DOCTYPE html><html><head>
    <title>SANNLAS FAQ - Auto Updated | SANNLAS Uganda</title>
    </head><body>
    <h1>SANNLAS FAQ - Auto Updated</h1>
    {items}
    </body></html>
    """
    return html
  
