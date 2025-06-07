# app/routes.py (수정)

import os
import sys
import subprocess
from flask import current_app, jsonify, request, render_template, session, redirect, url_for
from .services import process_data, get_filter_options, process_item_data
from . import cache

# UPDATE_SECRET_KEY는 이제 외부 자동 업데이트(cron)용으로만 사용되거나,
# 이 엔드포인트에서는 사용되지 않으므로, 이 줄은 그대로 둡니다.
# UPDATE_SECRET_KEY = os.environ.get('UPDATE_SECRET_KEY')

@current_app.route('/api/update-data')
def trigger_update():
    """
    로그인된 관리자만 별도 프로세스로 migrate_data.py를 실행하고 캐시를 초기화합니다.
    더 이상 URL 파라미터로 시크릿 키를 받지 않습니다.
    """
    # 로그인 여부만으로 권한 확인
    if not session.get('logged_in'):
        return jsonify({'status': 'error', 'message': 'Authentication required. Please log in.'}), 401

    # 이전의 secret_key 검증 로직은 이제 필요 없으므로 제거합니다.
    # secret_key = request.args.get('key')
    # if secret_key != UPDATE_SECRET_KEY:
    #     return jsonify({'status': 'error', 'message': 'Permission denied'}), 403

    try:
        migrate_script_path = os.path.join(current_app.root_path, '..', 'migrate_data.py')

        result = subprocess.run(
            [sys.executable, migrate_script_path],
            capture_output=True,
            text=True,
            check=True,
            encoding='utf-8'
        )

        cache.clear()
        print("--- 서버 캐시가 성공적으로 초기화되었습니다. ---")

        output_message = result.stdout
        return jsonify({'status': 'success', 'message': output_message})

    except subprocess.CalledProcessError as e:
        error_output = e.stderr
        return jsonify({'status': 'error', 'message': '스크립트 실행 실패', 'details': error_output}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500