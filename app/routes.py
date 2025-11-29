# app/routes.py
import os
import sys
import subprocess
from flask import current_app, jsonify, request, render_template, session, redirect, url_for
from .services import process_data, get_filter_options, process_item_data
from . import cache

# 브랜드별 표시 이름 매핑
BRAND_NAMES = {
    'nine': 'NINE ACCORD',
    'curu': 'CURUNURU'
}

@current_app.route('/')
def home():
    # 기본 루트 접속 시 로그인 페이지로
    return redirect(url_for('login'))

@current_app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        # 간단하게 동일 계정 사용 (필요시 분기 가능)
        if request.form['username'] == 'nineaccord' and request.form['password'] == 'gmlwns0820':
            session['logged_in'] = True
            # 로그인 성공 시 기본 브랜드(nine)로 이동
            return redirect(url_for('dashboard_main_view', brand='nine'))
        else:
            error = '아이디 또는 비밀번호가 올바르지 않습니다.'
    return render_template('login.html', error=error)

# URL에 <brand> 파라미터 추가
@current_app.route('/<brand>/dashboard_main')
def dashboard_main_view(brand):
    if not session.get('logged_in'): return redirect(url_for('login'))
    if brand not in BRAND_NAMES: return "Invalid Brand", 404
    
    return render_template('dashboard_main.html', 
                           brand_code=brand, 
                           brand_name=BRAND_NAMES[brand])

@current_app.route('/<brand>/dashboard_item')
def dashboard_item_view(brand):
    if not session.get('logged_in'): return redirect(url_for('login'))
    if brand not in BRAND_NAMES: return "Invalid Brand", 404

    return render_template('dashboard_item.html', 
                           brand_code=brand, 
                           brand_name=BRAND_NAMES[brand])

# API도 브랜드별로 구분
@current_app.route('/api/<brand>/data')
def api_data(brand):
    if not session.get('logged_in'): return jsonify({'error': 'Auth required'}), 401
    filters = {
        'warehouses': request.args.getlist('warehouse'),
        'categories': request.args.getlist('category'),
        'main_year': request.args.get('main_year'),
        'comp_year': request.args.get('comp_year'),
        'start_month': request.args.get('start_month'),
        'end_month': request.args.get('end_month'),
    }
    # brand를 process_data에 전달
    months, rows = process_data(brand, tuple(sorted(filters.items())))
    return jsonify({'months': months, 'rows': rows})

@current_app.route('/api/<brand>/data/item')
def api_item_data(brand):
    if not session.get('logged_in'): return jsonify({'error': 'Auth required'}), 401
    filters = {
        'warehouses': request.args.getlist('warehouse'),
        'categories': request.args.getlist('category'),
        'main_year': request.args.get('main_year'),
        'start_month': request.args.get('start_month'),
        'end_month': request.args.get('end_month'),
    }
    months, rows, top_series = process_item_data(brand, tuple(sorted(filters.items())))
    return jsonify({'months': months, 'rows': rows, 'top_series_data': top_series})

@current_app.route('/api/<brand>/filters')
def api_filters(brand):
    if not session.get('logged_in'): return jsonify({'error': 'Auth required'}), 401
    warehouses, categories, years, months = get_filter_options(brand)
    return jsonify({'warehouses': warehouses, 'categories': categories, 'years': years, 'months': months})

# app/routes.py 의 trigger_update 함수 부분 수정

@current_app.route('/api/<brand>/update-data')
def trigger_update(brand):
    if not session.get('logged_in'):
        return jsonify({'status': 'error', 'message': '로그인이 필요합니다.'}), 401

    try:
        # 1. 스크립트 경로 확인
        migrate_script_path = os.path.join(current_app.root_path, '..', 'migrate_data.py')
        
        # 2. 윈도우 환경 변수 설정 (한글 깨짐 방지)
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"

        # 3. 프로세스 실행 (check=False로 설정하여 에러가 나도 파이썬이 멈추지 않게 함)
        result = subprocess.run(
            [sys.executable, migrate_script_path, brand],
            capture_output=True,
            text=True,
            check=False,  # <-- 수정: 에러 발생 시에도 멈추지 않고 stderr를 캡처함
            env=env,
            encoding='utf-8' # <-- 수정: UTF-8 강제
        )

        # 4. 실행 결과 판단
        if result.returncode != 0:
            # 스크립트 실행 중 에러가 발생한 경우
            print(f"Update Error STDERR: {result.stderr}") # 서버 터미널에 로그 출력
            return jsonify({
                'status': 'error', 
                'message': '데이터 업데이트 스크립트 오류',
                'details': result.stderr  # 웹 화면에 에러 내용을 그대로 보여줌
            }), 500

        # 성공 시 캐시 비우기
        cache.clear()
        print(f"--- [{brand}] 업데이트 성공 ---")
        return jsonify({'status': 'success', 'message': result.stdout})

    except Exception as e:
        # 시스템 레벨의 에러 (파일을 못찾거나 권한 문제 등)
        print(f"System Error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500