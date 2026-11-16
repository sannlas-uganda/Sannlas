import os, ftplib, time
from werkzeug.utils import secure_filename

FTP_HOST = os.environ.get('YOTTA_FTP_HOST', '152.89.253.10')
FTP_USER = os.environ.get('YOTTA_FTP_USER', 'sannlass')
FTP_PASS = os.environ.get('YOTTA_FTP_PASS', '')
FTP_REELS_DIR = '/public_html/reels'
SITE_URL = 'https://sannlas.store'

def save_reel_to_yottasrc(file_obj, prefix="reel"):
    """ONLY REELS go to YottaSrc. Nothing else."""
    if not FTP_PASS:
        raise Exception("YOTTA_FTP_PASS not set in Render Env!")
    filename = f"{prefix}_{int(time.time())}_{secure_filename(file_obj.filename)}"
    tmp_path = f"/tmp/{filename}"
    file_obj.save(tmp_path)
    ftp = ftplib.FTP(FTP_HOST, timeout=60)
    ftp.login(FTP_USER, FTP_PASS)
    try:
        ftp.cwd(FTP_REELS_DIR)
    except:
        ftp.mkd(FTP_REELS_DIR)
        ftp.cwd(FTP_REELS_DIR)
    with open(tmp_path, 'rb') as f:
        ftp.storbinary(f'STOR {filename}', f)
    ftp.quit()
    os.remove(tmp_path)
    return f"{SITE_URL}/reels/{filename}"
