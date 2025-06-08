# run.py
import sys
import os

# 이 파일(run.py)이 위치한 디렉토리의 절대 경로를 파이썬 경로에 추가합니다.
# 이렇게 하면 어떤 위치에서 실행하더라도 'app' 폴더를 항상 찾을 수 있습니다.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app

# 애플리케이션 팩토리로부터 앱 인스턴스 생성
app = create_app()

if __name__ == '__main__':
    # 디버그 모드로 앱 실행
    # 실제 운영 환경에서는 debug=False로 설정해야 합니다.
    app.run(debug=True)