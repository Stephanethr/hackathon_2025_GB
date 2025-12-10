import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-prod'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///workspace_smart.db'
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
    
    # Business Rules Defaults
    SINGLE_USER_CAPACITY_THRESHOLD = 6
    WORKING_HOURS_START = 8  # 8 AM
    WORKING_HOURS_END = 19   # 7 PM

class DevelopmentConfig(Config):
    DEBUG = True

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'

class ProductionConfig(Config):
    DEBUG = False
    # In prod, rely on env vars strictly
