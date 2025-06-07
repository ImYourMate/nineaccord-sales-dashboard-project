# app/routes.py (최종 수정 완료)

import os
import sys
import subprocess
import threading
from flask import current_app, jsonify, request, render_template, session, redirect, url_for
from .services import process_data, get_filter_options, process_item_data
from . import cache

UPDATE_SECRET_KEY = os.environ.get('UPDATE_SECRET_KEY')

def run_migration_in_background(app):
    """
    백그라운드에서 마이그레이션 스크립트를 실행하는 함수.
    Flask 앱 인스턴스를 인자로 받습니다.
    """
    # with app.app_context()를 사용하여 전달받은 앱의 컨텍스트를 생성합니다.
    with app.app_context():
        try:
            python_executable = sys.executable
            script_path = os.path.join(app.root_path, '..', 'migrate_data.py')
            
            print("--- 백그라운드 데이터 마이그레이션 시작 ---")
            result = subprocess.run(
                [python_executable, script_path],
                capture_output=True, text=True, check=True, encoding='utf-8'
            )
            cache.clear()
            print("--- 백그라운드 데이터 마이그레이션 완료. 캐시 초기화됨 ---")
            print("스크립트 실행 결과:")
            print(result.stdout)
        except subprocess.CalledProcessError as e:
            print(f"--- 백그라운드 마이그레이션 실패 ---\nError: {e.stderr}")
        except Exception as e:
            print(f"--- 백그라운드 실행 중 알 수 없는 오류: {str(e)} ---")


@current_app.route('/api/update-data')
def trigger_update():
    """
    보안 키가 맞을 경우, 데이터베이스 업데이트를 백그라운드에서 실행하고 즉시 응답합니다.
    """
    secret_key = request.args.get('key')
    if secret_key != UPDATE_SECRET_KEY:
        return jsonify({'status': 'error', 'message': 'Permission denied'}), 403

    # --- ★★★ 수정된 부분 ★★★ ---
    # current_app._get_current_object()를 통해 실제 앱 인스턴스를 가져옵니다.
    app_context = current_app._get_current_object()
    # 스레드를 생성할 때, 앱 인스턴스를 인자(args)로 전달합니다.
    thread = threading.Thread(target=run_migration_in_background, args=[app_context])
    thread.start()

    return jsonify({
        'status': 'success',
        'message': '데이터 업데이트 요청을 수락했습니다. 백그라운드에서 작업이 시작됩니다. 완료까지 몇 분 정도 소요될 수 있으며, 진행 상황은 Render 대시보드의 Logs 탭에서 확인할 수 있습니다.'
    })


@current_app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form['username'] == 'nineaccord' and request.form['password'] == 'gmlwns0820':
            session['logged_in'] = True
            session.permanent = True
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

@current_app.route('/')
def home():
    return redirect(url_for('login'))