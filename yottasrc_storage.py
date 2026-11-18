import os, ftplib, time, subprocess, shutil
from werkzeug.utils import secure_filename

FTP_HOST = os.environ.get('YOTTA_FTP_HOST', '152.89.253.10')
FTP_USER = os.environ.get('YOTTA_FTP_USER', 'sannlass')
FTP_PASS = os.environ.get('YOTTA_FTP_PASS', '')
FTP_REELS_DIR = '/public_html/reels'
SITE_URL = 'https://media.sannlas.store'

def get_ffmpeg():
    # Try system ffmpeg first, then python ffmpeg
    if shutil.which('ffmpeg'):
        return 'ffmpeg'
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except:
        return None

def compress_video(input_path):
    """Compress to 720p + faststart - THIS FIXES PAUSING"""
    ffmpeg = get_ffmpeg()
    if not ffmpeg:
        print("⚠️ No ffmpeg found, uploading original - ADD imageio-ffmpeg to requirements.txt!")
        return input_path
    
    output_path = input_path.rsplit('.', 1)[0] + '_compressed.mp4'
    try:
        # -movflags +faststart = browser can play instantly without downloading all
        # scale=720:-2 = 720p, enough for phone
        # crf 28 = small file, still clear
        # maxrate 1500k = caps bitrate so it never buffers on slow network
        cmd = [
            ffmpeg, '-y', '-i', input_path,
            '-vf', 'scale=720:-2',
            '-c:v', 'libx264', '-crf', '28', '-preset', 'veryfast',
            '-maxrate', '1500k', '-bufsize', '3000k',
            '-movflags', '+faststart',
            '-c:a', 'aac', '-b:a', '128k',
            '-t', '60',  # Max 60 sec reel - prevents huge files
            output_path
        ]
        subprocess.run(cmd, check=True, timeout=180, capture_output=True)
        
        # Only use compressed if it's actually smaller
        if os.path.exists(output_path) and os.path.getsize(output_path) < os.path.getsize(input_path):
            orig_mb = os.path.getsize(input_path)//1024//1024
            new_mb = os.path.getsize(output_path)//1024//1024
            print(f"✅ Compressed: {orig_mb}MB -> {new_mb}MB")
            os.remove(input_path)
            return output_path
        else:
            if os.path.exists(output_path):
                os.remove(output_path)
            return input_path
    except Exception as e:
        print(f"Compress failed, using original: {e}")
        if os.path.exists(output_path):
            try: os.remove(output_path)
            except: pass
        return input_path

def save_reel_to_yottasrc(file_obj, prefix="reel"):
    """ONLY REELS go to YottaSrc. Now COMPRESSED first!"""
    if not FTP_PASS:
        raise Exception("YOTTA_FTP_PASS not set in Render Env!")
    
    original_name = secure_filename(file_obj.filename)
    # Force .mp4
    base = original_name.rsplit('.', 1)[0]
    filename = f"{prefix}_{int(time.time())}_{base}.mp4"
    tmp_path = f"/tmp/{filename}"
    file_obj.save(tmp_path)
    
    # ✅ COMPRESS HERE - Before FTP!
    final_path = compress_video(tmp_path)
    final_filename = os.path.basename(final_path)
    
    ftp = None
    try:
        ftp = ftplib.FTP(FTP_HOST, timeout=180)
        ftp.login(FTP_USER, FTP_PASS)
        try:
            ftp.cwd(FTP_REELS_DIR)
        except:
            try: ftp.mkd(FTP_REELS_DIR)
            except: pass
            ftp.cwd(FTP_REELS_DIR)
        with open(final_path, 'rb') as f:
            ftp.storbinary(f'STOR {final_filename}', f)
    finally:
        if ftp:
            try: ftp.quit()
            except: pass
        # Cleanup - always, even if FTP fails
        try: os.remove(final_path)
        except: pass
        if final_path != tmp_path:
            try: os.remove(tmp_path)
            except: pass
    
    return f"{SITE_URL}/reels/{final_filename}"
