# app/routes.py (최종 간소화 버전)

import os
from flask import current_app, jsonify, request, render_template, session, redirect, url_for
from .services import process_data, get_filter_options, process_item_data
from . import cache

# UPDATE_SECRET_KEY 및 관련 임포트들 삭제

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

# /api/update-data 경로 및 관련 함수 모두 삭제

@current_app.route('/')
def home():
    return redirect(url_for('login'))