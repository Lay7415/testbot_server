# app.py
import os
from flask import Flask, request, jsonify, g, send_from_directory
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy import or_, func
from flasgger import Swagger

from database import SessionLocal
from models import Chapter, Article, Tariff
from utils import admin_required, save_photo, delete_photo, UPLOAD_FOLDER

app = Flask(__name__)

# --- Конфигурация Swagger ---
swagger_config = {
    "headers": [],
    "specs": [
        {
            "endpoint": 'apispec_1',
            "route": '/apispec_1.json',
            "rule_filter": lambda rule: True,
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/",
    "securityDefinitions": {
        "APIKeyHeader": {
            "type": "apiKey",
            "name": "X-Telegram-ID",
            "in": "header",
            "description": "Telegram ID для аутентификации администратора"
        }
    }
}
swagger = Swagger(app, config=swagger_config)
# -----------------------------

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Создаем папку для загрузок, если её нет
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- Управление сессией БД ---
@app.before_request
def before_request():
    g.db = SessionLocal()

@app.teardown_appcontext
def teardown_appcontext(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# --- Роут для раздачи загруженных файлов ---
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# --- Эндпоинты для РАЗДЕЛОВ (Chapters) ---

@app.route('/chapters', methods=['POST'])
@admin_required
def create_chapter():
    """
    Создание нового раздела
    Поле 'order' присваивается автоматически.
    ---
    tags:
      - Chapters
    security:
      - APIKeyHeader: []
    consumes:
      - multipart/form-data
    parameters:
      - in: formData
        name: title
        type: string
        required: true
        description: Название раздела
      - in: formData
        name: photo
        type: file
        required: true
        description: Файл обложки (проверяется соотношение сторон)
    responses:
      201:
        description: Раздел успешно создан
      400:
        description: Ошибка в запросе
      403:
        description: Доступ запрещен
    """
    db = g.db
    title = request.form.get('title')
    file = request.files.get('photo')

    if not title:
        return jsonify({"error": "Title is required"}), 400
    
    photo_filename, error = save_photo(file)
    if error:
        return jsonify({"error": error}), 400

    max_order = db.query(func.max(Chapter.order)).scalar()
    new_order = (max_order or 0) + 1

    new_chapter = Chapter(title=title, order=new_order, photo_path=photo_filename)
    db.add(new_chapter)
    db.commit()
    db.refresh(new_chapter)
    return jsonify(new_chapter.to_dict()), 201

@app.route('/chapters/<int:chapter_id>', methods=['GET'])
def get_chapter(chapter_id):
    """
    Получение конкретного раздела по ID
    ---
    tags:
      - Chapters
    parameters:
      - in: path
        name: chapter_id
        type: integer
        required: true
    responses:
      200:
        description: Данные раздела
      404:
        description: Раздел не найден
    """
    chapter = g.db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        return jsonify({"error": "Chapter not found"}), 404
    return jsonify(chapter.to_dict())

@app.route('/chapters', methods=['GET'])
def get_all_chapters():
    """
    Получение списка всех разделов
    ---
    tags:
      - Chapters
    responses:
      200:
        description: Список всех разделов, отсортированных по полю order
    """
    chapters = g.db.query(Chapter).order_by(Chapter.order).all()
    return jsonify([c.to_dict() for c in chapters])

@app.route('/chapters/search', methods=['GET'])
def search_chapters():
    """
    Поиск разделов по названию
    ---
    tags:
      - Chapters
    parameters:
      - in: query
        name: title
        type: string
        required: true
    responses:
      200:
        description: Найденные разделы
      400:
        description: Параметр 'title' не указан
    """
    query = request.args.get('title', '')
    if not query:
        return jsonify({"error": "Search query 'title' is required"}), 400
    
    chapters = g.db.query(Chapter).filter(Chapter.title.ilike(f'%{query}%')).order_by(Chapter.order).all()
    return jsonify([c.to_dict() for c in chapters])
    
@app.route('/chapters', methods=['PUT'])
@admin_required
def update_chapter():
    """
    Обновление существующего раздела
    ---
    tags:
      - Chapters
    security:
      - APIKeyHeader: []
    consumes:
      - multipart/form-data
    parameters:
      - in: formData
        name: id
        type: integer
        required: true
      - in: formData
        name: title
        type: string
      - in: formData
        name: order
        type: integer
      - in: formData
        name: photo
        type: file
    responses:
      200:
        description: Раздел успешно обновлен
      404:
        description: Раздел не найден
    """
    db = g.db
    data = request.form
    file = request.files.get('photo')
    chapter_id = data.get('id')

    if not chapter_id:
        return jsonify({"error": "Chapter ID is required in body"}), 400

    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        return jsonify({"error": "Chapter not found"}), 404

    if 'title' in data:
        chapter.title = data['title']
    if 'order' in data:
        chapter.order = int(data['order'])
    
    if file:
        delete_photo(chapter.photo_path)
        photo_filename, error = save_photo(file)
        if error:
            return jsonify({"error": error}), 400
        chapter.photo_path = photo_filename

    db.commit()
    return jsonify(chapter.to_dict())

@app.route('/chapters/<int:chapter_id>', methods=['DELETE'])
@admin_required
def delete_chapter(chapter_id):
    """
    Удаление раздела по ID
    ---
    tags:
      - Chapters
    security:
      - APIKeyHeader: []
    parameters:
      - in: path
        name: chapter_id
        type: integer
        required: true
    responses:
      200:
        description: Раздел успешно удален
      404:
        description: Раздел не найден
    """
    db = g.db
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        return jsonify({"error": "Chapter not found"}), 404
    
    delete_photo(chapter.photo_path)
    db.delete(chapter)
    db.commit()
    return jsonify({"message": "Chapter deleted successfully"})

@app.route('/chapters/order', methods=['PATCH'])
@admin_required
def update_chapters_order():
    """
    Изменение порядка нескольких разделов
    ---
    tags:
      - Chapters
    security:
      - APIKeyHeader: []
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: array
          items:
            type: object
            properties:
              id:
                type: integer
              order:
                type: integer
    responses:
      200:
        description: Порядок успешно обновлен
    """
    db = g.db
    order_data = request.get_json()
    if not isinstance(order_data, list):
        return jsonify({"error": "Invalid data format. Expected a list of objects."}), 400
    
    try:
        chapter_map = {c.id: c for c in db.query(Chapter).filter(Chapter.id.in_([item['id'] for item in order_data])).all()}
        for item in order_data:
            if item['id'] in chapter_map:
                chapter_map[item['id']].order = item['order']
            else:
                raise NoResultFound
        db.commit()
    except NoResultFound:
        db.rollback()
        return jsonify({"error": f"Chapter with id {item.get('id')} not found"}), 404
    except Exception as e:
        db.rollback()
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500
        
    return jsonify({"message": "Chapters order updated successfully"})

# --- Эндпоинты для СТАТЕЙ (Articles) ---

@app.route('/articles', methods=['POST'])
@admin_required
def create_article():
    """
    Создание новой статьи
    Поле 'order' присваивается автоматически в рамках указанного chapter_id.
    ---
    tags:
      - Articles
    security:
      - APIKeyHeader: []
    consumes:
      - multipart/form-data
    parameters:
      - name: title
        in: formData
        type: string
        required: true
      - name: description
        in: formData
        type: string
        required: true
      - name: link
        in: formData
        type: string
        required: true
      - name: chapter_id
        in: formData
        type: integer
        required: true
      - name: photo
        in: formData
        type: file
    responses:
      201:
        description: Статья успешно создана
      404:
        description: Раздел для статьи не найден
    """
    db = g.db
    data = request.form
    file = request.files.get('photo')

    required_fields = ['title', 'description', 'link', 'chapter_id']
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    chapter_id = int(data['chapter_id'])
    if not db.query(Chapter).filter(Chapter.id == chapter_id).first():
        return jsonify({"error": f"Chapter with id {chapter_id} not found"}), 404

    photo_filename, error = save_photo(file)
    if error:
        return jsonify({"error": error}), 400

    max_order = db.query(func.max(Article.order)).filter(Article.chapter_id == chapter_id).scalar()
    new_order = (max_order or 0) + 1

    new_article = Article(
        title=data['title'], description=data['description'], link=data['link'],
        order=new_order, chapter_id=chapter_id, photo_path=photo_filename
    )
    db.add(new_article)
    db.commit()
    db.refresh(new_article)
    return jsonify(new_article.to_dict()), 201

@app.route('/articles/<int:article_id>', methods=['GET'])
def get_article(article_id):
    """
    Получение конкретной статьи по ID
    ---
    tags:
      - Articles
    parameters:
      - in: path
        name: article_id
        type: integer
        required: true
    responses:
      200:
        description: Данные статьи
      404:
        description: Статья не найдена
    """
    article = g.db.query(Article).filter(Article.id == article_id).first()
    if not article:
        return jsonify({"error": "Article not found"}), 404
    return jsonify(article.to_dict())

@app.route('/chapters/<int:chapter_id>/articles', methods=['GET'])
def get_articles_by_chapter(chapter_id):
    """
    Получение всех статей для конкретного раздела
    ---
    tags:
      - Articles
    parameters:
      - in: path
        name: chapter_id
        type: integer
        required: true
    responses:
      200:
        description: Список статей раздела
    """
    articles = g.db.query(Article).filter(Article.chapter_id == chapter_id).order_by(Article.order).all()
    return jsonify([a.to_dict() for a in articles])

@app.route('/articles/search', methods=['GET'])
def search_articles():
    """
    Поиск статей по названию и описанию
    ---
    tags:
      - Articles
    parameters:
      - in: query
        name: q
        type: string
        required: true
    responses:
      200:
        description: Список найденных статей
    """
    query = request.args.get('q', '')
    if not query:
        return jsonify({"error": "Search query 'q' is required"}), 400
    
    search_term = f'%{query}%'
    articles = g.db.query(Article).filter(
        or_(Article.title.ilike(search_term), Article.description.ilike(search_term))
    ).order_by(Article.order).all()
    return jsonify([a.to_dict() for a in articles])

@app.route('/articles', methods=['PUT'])
@admin_required
def update_article():
    """
    Обновление существующей статьи
    ---
    tags:
      - Articles
    security:
      - APIKeyHeader: []
    consumes:
      - multipart/form-data
    parameters:
      - in: formData
        name: id
        type: integer
        required: true
      - name: title
        in: formData
        type: string
      - name: description
        in: formData
        type: string
      - name: link
        in: formData
        type: string
      - name: order
        in: formData
        type: integer
      - name: chapter_id
        in: formData
        type: integer
      - name: photo
        in: formData
        type: file
    responses:
      200:
        description: Статья обновлена
      404:
        description: Статья не найдена
    """
    db = g.db
    data = request.form
    file = request.files.get('photo')
    article_id = data.get('id')

    if not article_id:
        return jsonify({"error": "Article ID is required in body"}), 400

    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        return jsonify({"error": "Article not found"}), 404

    for key in ['title', 'description', 'link', 'order', 'chapter_id']:
        if key in data:
            value = int(data[key]) if key in ['order', 'chapter_id'] else data[key]
            setattr(article, key, value)

    if file:
        delete_photo(article.photo_path)
        photo_filename, error = save_photo(file)
        if error:
            return jsonify({"error": error}), 400
        article.photo_path = photo_filename

    db.commit()
    return jsonify(article.to_dict())

@app.route('/articles/<int:article_id>', methods=['DELETE'])
@admin_required
def delete_article(article_id):
    """
    Удаление статьи по ID
    ---
    tags:
      - Articles
    security:
      - APIKeyHeader: []
    parameters:
      - in: path
        name: article_id
        type: integer
        required: true
    responses:
      200:
        description: Статья удалена
      404:
        description: Статья не найдена
    """
    db = g.db
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        return jsonify({"error": "Article not found"}), 404
    
    delete_photo(article.photo_path)
    db.delete(article)
    db.commit()
    return jsonify({"message": "Article deleted successfully"})

@app.route('/articles/order', methods=['PATCH'])
@admin_required
def update_articles_order():
    """
    Изменение порядка нескольких статей
    ---
    tags:
      - Articles
    security:
      - APIKeyHeader: []
    consumes:
      - application/json
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: array
          items:
            type: object
            properties:
              id:
                type: integer
              order:
                type: integer
    responses:
      200:
        description: Порядок обновлен
    """
    db = g.db
    order_data = request.get_json()
    if not isinstance(order_data, list):
        return jsonify({"error": "Invalid data format. Expected a list of objects."}), 400
    
    try:
        article_map = {a.id: a for a in db.query(Article).filter(Article.id.in_([item['id'] for item in order_data])).all()}
        for item in order_data:
            if item['id'] in article_map:
                article_map[item['id']].order = item['order']
            else:
                raise NoResultFound
        db.commit()
    except NoResultFound:
        db.rollback()
        return jsonify({"error": f"Article with id {item.get('id')} not found"}), 404
    except Exception as e:
        db.rollback()
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500
        
    return jsonify({"message": "Articles order updated successfully"})

# --- Эндпоинты для ТАРИФОВ (Tariffs) ---

@app.route('/tariffs/<int:tariff_id>', methods=['GET'])
def get_tariff(tariff_id):
    """
    Получение активного тарифа по ID
    ---
    tags:
      - Tariffs
    parameters:
      - in: path
        name: tariff_id
        type: integer
        required: true
    responses:
      200:
        description: Данные тарифа
      404:
        description: Активный тариф не найден
    """
    tariff = g.db.query(Tariff).filter(Tariff.id == tariff_id, Tariff.is_active == True).first()
    if not tariff:
        return jsonify({"error": "Active tariff not found"}), 404
    return jsonify(tariff.to_dict())

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)