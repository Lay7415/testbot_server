# utils.py
import os
import uuid
from functools import wraps
from flask import request, jsonify
from PIL import Image
from werkzeug.utils import secure_filename

# --- Конфигурация ---
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
# Требуемое соотношение сторон (16:9) с погрешностью 5%
ASPECT_RATIO = 16 / 9
ASPECT_RATIO_TOLERANCE = 0.05

# Загружаем ID админов из .env
ADMIN_TELEGRAM_IDS = os.getenv('ADMIN_TELEGRAM_IDS', '').split(',')

def allowed_file(filename):
    """Проверяет, разрешено ли расширение файла."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# --- Декоратор для проверки прав администратора ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        telegram_id = request.headers.get('X-Telegram-ID')
        if not telegram_id or telegram_id not in ADMIN_TELEGRAM_IDS:
            return jsonify({"error": "Forbidden: Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated_function

# --- Функции для работы с изображениями ---
def save_photo(file):
    """Сохраняет фото, проверяет расширение и соотношение сторон."""
    if not file or file.filename == '':
        return None, None # Файл не был предоставлен, это не ошибка
    
    if not allowed_file(file.filename):
        return None, "Invalid file type. Allowed types: png, jpg, jpeg, gif"

    filename = secure_filename(f"{uuid.uuid4()}.{file.filename.rsplit('.', 1)[1].lower()}")
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    
    try:
        # Сначала сохраняем, потом проверяем
        file.save(filepath)

        with Image.open(filepath) as img:
            width, height = img.size
            if height == 0:
                raise ValueError("Image height cannot be zero.")
            
            actual_ratio = width / height
            lower_bound = ASPECT_RATIO * (1 - ASPECT_RATIO_TOLERANCE)
            upper_bound = ASPECT_RATIO * (1 + ASPECT_RATIO_TOLERANCE)

            if not (lower_bound <= actual_ratio <= upper_bound):
                os.remove(filepath) # Удаляем некорректный файл
                error_msg = f"Invalid aspect ratio. Required: ~{ASPECT_RATIO:.2f}, found: {actual_ratio:.2f}"
                return None, error_msg
    except Exception as e:
        if os.path.exists(filepath):
            os.remove(filepath)
        return None, f"Error processing image: {str(e)}"

    return filename, None # Возвращаем имя файла для сохранения в БД

def delete_photo(photo_filename):
    """Удаляет файл фото с диска."""
    if not photo_filename:
        return
    try:
        filepath = os.path.join(UPLOAD_FOLDER, photo_filename)
        if os.path.exists(filepath):
            os.remove(filepath)
    except Exception as e:
        # Логируем ошибку, но не останавливаем процесс
        print(f"Error deleting file {photo_filename}: {e}")