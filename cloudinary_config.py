import cloudinary
import os

cloudinary.config( 
  cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME', 'y9z9p6ws'),
  api_key = os.environ.get('CLOUDINARY_API_KEY', '486335228977968'), 
  api_secret = os.environ.get('CLOUDINARY_API_SECRET', 'a5k4QK85iL9h_rGFLK6QwybVLC4'),
  secure = True
)
