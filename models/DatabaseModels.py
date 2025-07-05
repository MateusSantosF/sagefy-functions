from tkinter import Text
from sqlalchemy.ext.declarative import declarative_base
from utils.db_session import db_engine
from datetime import datetime
from sqlalchemy.orm import relationship
import uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy import (
  Column, String, Integer, JSON, ForeignKey,DateTime,Date, Boolean
)

Base = declarative_base()

class UserModel(Base):
    __tablename__ = 'users'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    role = Column(String, nullable=False)  # 'ADMIN' or 'TEACHER'
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=True)
    is_active = Column(Boolean, default=True) 
    classes = relationship('ClassModel', back_populates='teacher')

class ClassModel(Base):
    __tablename__ = 'classes'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    class_name = Column(String, nullable=False)
    class_code = Column(String, unique=True, index=True, nullable=False)
    access_code = Column(String, index=True, nullable=False)
    teacher_id = Column(String, ForeignKey('users.id'), nullable=False)
    teacher = relationship('UserModel', back_populates='classes')
    students = Column(JSONB, default=list)  # list of student emails
    student_count = Column(Integer, default=0)

class FileMeta(Base):
    __tablename__ = 'file_meta'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    file_id = Column(String, unique=True, index=True, nullable=False)
    class_code= Column(String, index=True, nullable=False)
    blob_name = Column(String, nullable=False)
    blob_metadata = Column(JSON, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class MetricsModel(Base):
    __tablename__ = 'metrics'
    id = Column(String, primary_key=True)  # row_key
    request_id = Column(String, unique=True, nullable=False)
    user_email = Column(String, nullable=False)
    user_role = Column(String, nullable=False)
    class_code = Column(String, nullable=True)
    categories = Column(String, nullable=True)
    subcategories = Column(String, nullable=True)
    prompt = Column(String, nullable=False)
    response = Column(String, nullable=False)
    prompt_tokens = Column(Integer, nullable=False)
    completion_tokens = Column(Integer, nullable=False)
    total_tokens = Column(Integer, nullable=False)
    timestamp = Column(DateTime, nullable=False)

class DailyDashboardModel(Base):
    __tablename__ = 'daily_dashboard'
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    class_code = Column(String, index=True, nullable=False)
    date = Column(Date, nullable=False, index=True)
    total_conversations = Column(Integer, nullable=False)
    total_prompt_tokens = Column(Integer, nullable=False)
    total_completion_tokens = Column(Integer, nullable=False)
    total_tokens = Column(Integer, nullable=False)
    top_categories = Column(JSON, nullable=False)
    top_subcategories = Column(JSON, nullable=False)
    top_students = Column(JSON, nullable=False)
    daily_summary = Column(String, nullable=True) 
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)

# Create tables
Base.metadata.create_all(bind=db_engine)

