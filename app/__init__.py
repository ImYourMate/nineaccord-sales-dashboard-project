# app/__init__.py
import os
from dotenv import load_dotenv
from flask import Flask
from flask_caching import Cache
from datetime import timedelta

# .env 파일 로드
load_dotenv()

cache = Cache(config={
    'CACHE_TYPE': 'simple',
    'CACHE_DEFAULT_TIMEOUT': 3600
})

def create_app():
    app = Flask(__name__)

    # 환경 변수에서 시크릿 키 불러오기
    app.secret_key = os.environ.get('FLASK_SECRET_KEY')

    app.permanent_session = True
    app.permanent_session_lifetime = timedelta(minutes=30)

    cache.init_app(app)

    with app.app_context():
        from . import routes # 라우트 모듈을 임포트합니다.

    return app