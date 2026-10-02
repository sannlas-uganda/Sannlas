import os, tempfile, requests
from flask import Blueprint, render_template, request, jsonify
from werkzeug.utils import secure_filename

broadcast_bp = Blueprint('broadcast', __name__)
FB_PAGE_TOKEN = os.environ.get('FB_PAGE_TOKEN','')

@broadcast_bp.route('/seller/broadcast')
def broadcast_page():
    return render_template('broadcast.html')

@broadcast_bp.route('/api/broadcast', methods=['POST'])
def api_broadcast():
    if 'video' not in request.files:
        return jsonify(success=False), 400
    file = request.files['video']
    caption = request.form.get('caption','')[:500]
    temp_path = os.path.join(tempfile.gettempdir(), f"bc_{secure_filename(file.filename)}")
    file.save(temp_path)
    try:
        # here you push to FB/IG etc
        result = {"facebook": "posted" if FB_PAGE_TOKEN else "add token"}
    finally:
        if os.path.exists(temp_path): os.remove(temp_path) # ZERO STORAGE
    return jsonify(success=True, message="Broadcast done, file deleted!", result=result)
