# models.py
import os
from sqlalchemy import Column, Integer, String, Text, BigInteger, ForeignKey, NUMERIC, Boolean
from sqlalchemy.orm import relationship
from database import Base
from dotenv import load_dotenv

load_dotenv()
BASE_IMAGE_URL = os.getenv("BASE_IMAGE_URL", "http://127.0.0.1:5000/uploads/")

class Chapter(Base):
    __tablename__ = 'chapters'
    id = Column(Integer, primary_key=True, autoincrement=True)
    photo_path = Column(String(500))
    title = Column(String(250))
    order = Column(Integer)
    
    articles = relationship("Article", back_populates="chapter", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'photo_url': f"{BASE_IMAGE_URL}{self.photo_path}" if self.photo_path else None,
            'order': self.order
        }

class Article(Base):
    __tablename__ = 'articles'
    id = Column(Integer, primary_key=True, autoincrement=True)
    photo_path = Column(String(500))
    title = Column(String(250))
    description = Column(Text)
    link = Column(String(500))
    order = Column(Integer)
    chapter_id = Column(BigInteger, ForeignKey('chapters.id', ondelete='CASCADE'))

    chapter = relationship("Chapter", back_populates="articles")

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'link': self.link,
            'photo_url': f"{BASE_IMAGE_URL}{self.photo_path}" if self.photo_path else None,
            'order': self.order,
            'chapter_id': self.chapter_id
        }

class Tariff(Base):
    __tablename__ = 'tariffs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    duration_days = Column(Integer, nullable=False)
    price = Column(NUMERIC(10, 2), nullable=False)
    currency = Column(String(10), nullable=False)
    is_active = Column(Boolean, default=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'duration_days': self.duration_days,
            'price': float(self.price),
            'currency': self.currency,
            'is_active': self.is_active
        }