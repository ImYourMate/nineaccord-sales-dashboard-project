# app/routes.py (최종 수정)

import os
import sys  # sys 모듈 임포트
import subprocess  # subprocess 모듈 임포트
from flask import current_app, jsonify, request, render_template, session, redirect, url_for
from .services import process_data, get_filter_options, process_item_data
from . import cache

# 환경 변수에서 업데이트용 시크릿 키 불러오기 (cron job 등 다른 용도로는 사용 가능하지만,
# 이 엔드포인트에서는 직접적인 키 검증은 제거합니다.)
UPDATE_SECRET_KEY = os.environ.get('UPDATE_SECRET_KEY')

@current_app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form['username'] == 'nineaccord' and request.form['password'] == 'gmlwns0820':
            session['logged_in'] = True
            return redirect(url_for('dashboard_main_view'))
        else:
            error = '아이디 또는 비밀번호가 올바르지 않습니다.'
    return render_template('login.html', error=error)

@current_app.route('/dashboard_item')
def dashboard_item_view():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('dashboard_item.html')

@current_app.route('/dashboard_main')
def dashboard_main_view():
    if not session.get('logged_in'):
        return redirect(url_for('login'))
    return render_template('dashboard_main.html')

@current_app.route('/api/data')
def api_data():
    if not session.get('logged_in'):
        return jsonify({'error': 'Authentication required'}), 401
    filters = {
        'warehouses': request.args.getlist('warehouse'),
        'categories': request.args.getlist('category'),
        'main_year': request.args.get('main_year'),
        'comp_year': request.args.get('comp_year'),
        'start_month': request.args.get('start_month'),
        'end_month': request.args.get('end_month'),
    }
    frozen_filters = tuple(sorted(filters.items()))
    months, rows = process_data(frozen_filters)
    return jsonify({'months': months, 'rows': rows})

@current_app.route('/api/data/item')
def api_item_data():
    if not session.get('logged_in'):
        return jsonify({'error': 'Authentication required'}), 401
    filters = {
        'warehouses': request.args.getlist('warehouse'),
        'categories': request.args.getlist('category'),
        'main_year': request.args.get('main_year'),
        'start_month': request.args.get('start_month'),
        'end_month': request.args.get('end_month'),
    }
    frozen_filters = tuple(sorted(filters.items()))
    months, rows, top_series = process_item_data(frozen_filters)
    return jsonify({'months': months, 'rows': rows, 'top_series_data': top_series})

@current_app.route('/api/filters')
def api_filters():
    if not session.get('logged_in'):
        return jsonify({'error': 'Authentication required'}), 401
    warehouses, categories, years, months = get_filter_options()
    return jsonify({'warehouses': warehouses, 'categories': categories, 'years': years, 'months': months})

@current_app.route('/api/clear-cache')
def clear_all_cache():
    if not session.get('logged_in'):
        return jsonify({'error': 'Authentication required'}), 401
    cache.clear()
    return jsonify({'status': 'success', 'message': 'Cache cleared!'})

# --- ★★★ 수정된 업데이트 함수 ★★★ ---
@current_app.route('/api/update-data')
def trigger_update():
    """
    로그인된 사용자만 별도 프로세스로 migrate_data.py를 실행하고 캐시를 초기화합니다.
    URL 파라미터 'key'를 통한 외부 검증은 더 이상 필수적이지 않으며,
    로그인 세션만으로 권한을 확인합니다.
    """
    # 1. 로그인 여부 확인 (필수)
    if not session.get('logged_in'):
        return jsonify({'status': 'error', 'message': 'Authentication required. Please log in.'}), 401

    # 2. (선택 사항) 이전의 UPDATE_SECRET_KEY 검증 로직은 제거합니다.
    #    이제 이 엔드포인트는 로그인된 사용자만 호출할 수 있습니다.
    # secret_key = request.args.get('key')
    # if secret_key != UPDATE_SECRET_KEY:
    #    return jsonify({'status': 'error', 'message': 'Permission denied'}), 403

    try:
        # 현재 실행중인 파이썬 인터프리터(가상환경의 파이썬)를 사용해 스크립트를 실행
        # 프로젝트 루트에 있는 migrate_data.py를 지정
        migrate_script_path = os.path.join(current_app.root_path, '..', 'migrate_data.py')

        # subprocess의 encoding을 시스템 기본 인코딩으로 설정하여 한글 출력 문제 해결
        result = subprocess.run(
            [sys.executable, migrate_script_path],
            capture_output=True,
            text=True,
            check=True,  # 오류 발생 시 예외를 발생시킴
            encoding=sys.getdefaultencoding() # <- 이 부분이 수정되었습니다.
        )

        # 성공적으로 실행되면 캐시 클리어
        cache.clear()
        print("--- 서버 캐시가 성공적으로 초기화되었습니다. ---")

        # 스크립트의 표준 출력(print문)을 메시지로 사용
        output_message = result.stdout
        return jsonify({'status': 'success', 'message': output_message})

    except subprocess.CalledProcessError as e:
        # 스크립트 실행 중 오류가 발생한 경우
        error_output = e.stderr
        return jsonify({'status': 'error', 'message': '스크립트 실행 실패', 'details': error_output}), 500
    except Exception as e:
        # 기타 예외 처리
        return jsonify({'status': 'error', 'message': str(e)}), 500

@current_app.route('/')
def home():
    return redirect(url_for('login'))