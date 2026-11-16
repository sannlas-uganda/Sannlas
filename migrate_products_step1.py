# migrate_products_step1.py - Run ONCE!
import os, json, base64, io
import sannlas_db

# 1. Get from Neon - Use YOUR existing load_db
from sannlas_products import load_db

products = load_db('products.json', [])
print(f"Found {len(products)} products in Neon")

sannlas_db.init_sannlas_db()

moved = 0
skipped_base64 = 0
for p in products:
    # CLEAN IMAGE: If base64, throw away, use placeholder
    # Cloudinary images start with https:// - KEEP those!
    img = str(p.get('image',''))
    if img.startswith('data:image'):
        p['image'] = 'https://via.placeholder.com/300'
        p['images'] = ['https://via.placeholder.com/300']
        skipped_base64 += 1
    # Keep Cloudinary URLs as they are - No need to download yet!
    sannlas_db.add_product_db(p)
    moved += 1

print(f"✅ Moved {moved} products to sannlas.db")
print(f"🧹 Cleaned {skipped_base64} old base64 images")
print("Your Neon is now free - Sannlas DB has it all!")
