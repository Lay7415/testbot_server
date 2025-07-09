# database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Функция для создания таблиц в БД
def init_db():
    # Импортируем модели здесь, чтобы избежать циклических импортов
    import models
    Base.metadata.create_all(bind=engine)
    print("Database tables created successfully.")

# Этот блок позволяет запустить скрипт для инициализации БД
if __name__ == "__main__":
    init_db()