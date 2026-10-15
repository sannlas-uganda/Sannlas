try:
    from app import app
except Exception as e:
    import traceback, flask
    app = flask.Flask(__name__)
    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def show_error(path):
        return f"<h1>REAL ERROR FOUND BOSS!</h1><pre>{traceback.format_exc()}</pre>", 500
