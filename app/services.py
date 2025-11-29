# app/services.py

import sqlite3
import pandas as pd
from flask import current_app
from . import cache

DB_PATH = 'sales.db'

def _get_connection():
    """데이터베이스 연결을 반환합니다."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _safe_int(x):
    """안전하게 정수형으로 변환합니다."""
    try:
        return int(float(x))
    except (ValueError, TypeError):
        return 0

@cache.memoize()
def get_filter_options(brand):
    """
    브랜드별 테이블에서 필터 옵션을 가져옵니다.
    """
    table_name = f"sales_data_{brand}"
    conn = _get_connection()
    try:
        # 테이블 이름은 바인딩이 안 되므로 f-string 사용 (내부 변수라 안전)
        query = f"SELECT DISTINCT warehouse, category, month_year FROM {table_name}"
        df = pd.read_sql_query(query, conn)
    except Exception:
        # 테이블이 아직 생성되지 않았거나 오류 발생 시 빈 리스트 반환
        return [], [], [], []
    finally:
        conn.close()

    if df.empty:
        return [], [], [], []

    warehouses = sorted(df['warehouse'].dropna().unique())
    categories = sorted(df['category'].dropna().unique())

    df['month_dt'] = pd.to_datetime(df['month_year'], format='%y/%m', errors='coerce').dropna()
    
    if df.empty:
        return warehouses, categories, [], []
        
    years = sorted(df['month_dt'].dt.year.unique(), reverse=True)
    months = sorted(df['month_dt'].dt.month.unique())
    
    return warehouses, categories, [str(y) for y in years], [str(m).zfill(2) for m in months]

def _get_base_data(brand, filters, for_comp_year=False):
    """
    브랜드별 테이블에서 필터 조건에 따라 데이터를 조회합니다.
    """
    table_name = f"sales_data_{brand}"
    query_parts = [f"SELECT warehouse, category, series, item_name, month_year, quantity, stock FROM {table_name} WHERE 1=1"]
    params = []

    year_key = 'comp_year' if for_comp_year else 'main_year'
    
    if filters.get(year_key):
        year_str = str(int(filters[year_key]))[-2:]
        query_parts.append("AND substr(month_year, 1, 2) = ?")
        params.append(year_str)

    if filters.get('start_month') and filters.get('end_month'):
        query_parts.append("AND CAST(substr(month_year, 4, 2) AS INTEGER) BETWEEN ? AND ?")
        params.append(int(filters['start_month']))
        params.append(int(filters['end_month']))

    if filters.get('warehouses'):
        placeholders = ', '.join('?' for _ in filters['warehouses'])
        query_parts.append(f"AND warehouse IN ({placeholders})")
        params.extend(filters['warehouses'])
    
    if filters.get('categories'):
        placeholders = ', '.join('?' for _ in filters['categories'])
        query_parts.append(f"AND category IN ({placeholders})")
        params.extend(filters['categories'])

    conn = _get_connection()
    try:
        df = pd.read_sql_query(' '.join(query_parts), conn, params=params)
    except Exception:
        df = pd.DataFrame()
    conn.close()
    
    if not df.empty:
        df['quantity'] = df['quantity'].apply(_safe_int)
        df['stock'] = df['stock'].apply(_safe_int)
        df['month_str'] = df['month_year']
    
    return df

@cache.memoize()
def process_data(brand, filters_tuple):
    """
    메인 집계 데이터를 처리합니다. (브랜드 인자 추가됨)
    """
    filters = dict(filters_tuple)
    # brand 인자를 전달하여 데이터 조회
    df_main = _get_base_data(brand, filters)
    if df_main.empty: return [], []

    agg = df_main.groupby(['warehouse', 'category', 'month_str']).quantity.agg(net='sum', neg=lambda x: int(x[x<0].sum())).reset_index()
    months = sorted(df_main['month_str'].unique(), reverse=True)
    total_main = df_main.groupby(['warehouse', 'category']).quantity.agg(main_net='sum', main_neg=lambda x: int(x[x<0].sum())).reset_index()

    comp_data = None
    if filters.get('comp_year') and filters.get('comp_year') != filters.get('main_year'):
        # brand 인자 전달
        df_comp = _get_base_data(brand, filters, for_comp_year=True)
        if not df_comp.empty:
            comp_data = df_comp.groupby(['warehouse', 'category']).quantity.agg(comp_net='sum', comp_neg=lambda x: int(x[x<0].sum())).reset_index()

    warehouses_all = agg['warehouse'].unique().tolist()
    desired_order = ["안경원", "면세", "수출", "온라인주문", "클립", "모던"]
    others = sorted([w for w in warehouses_all if w not in desired_order])
    final_order = [w for w in desired_order if w in warehouses_all] + others

    subtotals = {m: {'net': 0, 'neg': 0} for m in months}
    total_sub = {'net': 0, 'neg': 0}
    if comp_data is not None:
        total_sub['compare'] = {'net': 0, 'neg': 0}
        
    subtotal_targets = ["안경원", "면세", "수출", "온라인주문", "클립"]
    rows = []

    for wh in final_order:
        tmp = agg[agg['warehouse'] == wh]
        if tmp.empty: continue

        wh_row = {'name': wh, 'is_header': True, 'data': {}, 'categories': []}
        for m in months:
            grp = tmp[tmp['month_str'] == m]
            net_val, neg_val = int(grp['net'].sum()), int(grp['neg'].sum())
            wh_row['data'][m] = {'net': net_val, 'neg': neg_val}
            if wh in subtotal_targets:
                subtotals[m]['net'] += net_val
                subtotals[m]['neg'] += neg_val

        main_row = total_main[total_main['warehouse'] == wh]
        net_tot, neg_tot = int(main_row['main_net'].sum()), int(main_row['main_neg'].sum())
        wh_row['total'] = {'net': net_tot, 'neg': neg_tot}
        if wh in subtotal_targets:
            total_sub['net'] += net_tot
            total_sub['neg'] += neg_tot

        if comp_data is not None:
            cwh = comp_data[comp_data['warehouse'] == wh]
            comp_net_sum, comp_neg_sum = int(cwh['comp_net'].sum()), int(cwh['comp_neg'].sum())
            wh_row['compare'] = {'net': comp_net_sum, 'neg': comp_neg_sum}
            wh_row['pct_change'] = round((net_tot - comp_net_sum) / abs(comp_net_sum) * 100, 1) if comp_net_sum != 0 else None
            if wh in subtotal_targets:
                total_sub['compare']['net'] += comp_net_sum
                total_sub['compare']['neg'] += comp_neg_sum

        all_categories_in_wh = tmp['category'].unique()
        cat_desired_order = ["안경테", "선글라스", "클립", "모던"]
        cat_ordered = [c for c in cat_desired_order if c in all_categories_in_wh]
        cat_ordered += sorted([c for c in all_categories_in_wh if c not in cat_desired_order])
        
        for cat in cat_ordered:
            group = tmp[tmp['category'] == cat]
            cat_row = {'name': cat, 'data': {}, 'total': {}, 'parentId': wh}
            for m in months:
                gr2 = group[group['month_str'] == m]
                cat_row['data'][m] = {'net': int(gr2['net'].sum()), 'neg': int(gr2['neg'].sum())}
            
            mc = total_main[(total_main['warehouse'] == wh) & (total_main['category'] == cat)]
            cat_row['total'] = {'net': int(mc['main_net'].sum()), 'neg': int(mc['main_neg'].sum())}

            if comp_data is not None:
                c2 = comp_data[(comp_data['warehouse'] == wh) & (comp_data['category'] == cat)]
                comp_c_net, comp_c_neg = int(c2['comp_net'].sum()), int(c2['comp_neg'].sum())
                cat_row['compare'] = {'net': comp_c_net, 'neg': comp_c_neg}
                cat_row['pct_change'] = round((cat_row['total']['net'] - comp_c_net) / abs(comp_c_net) * 100, 1) if comp_c_net != 0 else None
            
            wh_row['categories'].append(cat_row)
        
        rows.append(wh_row)

        if wh == '클립':
            row_sub = {'name': '합계', 'is_subtotal': True, 'data': subtotals, 'total': total_sub}
            if comp_data is not None and 'compare' in total_sub:
                row_sub['compare'] = total_sub['compare']
                if total_sub['compare']['net'] != 0:
                    row_sub['pct_change'] = round((total_sub['net'] - total_sub['compare']['net']) / abs(total_sub['compare']['net']) * 100, 1)
            rows.append(row_sub)
    
    return months, rows

@cache.memoize()
def process_item_data(brand, filters_tuple):
    """
    품목 집계 데이터를 처리합니다. (브랜드 인자 추가됨)
    """
    filters = dict(filters_tuple)
    # brand 인자 전달
    df_main = _get_base_data(brand, filters)
    if df_main.empty: return [], [], []

    df_for_chart = df_main[df_main['category'] != '케이스']
    series_sales = df_for_chart.groupby('series')['quantity'].sum().nlargest(10)
    top_series_data = [{'series': index, 'quantity': int(value)} for index, value in series_sales.items()]
    
    months = sorted(df_main['month_str'].unique(), reverse=True)
    
    agg = df_main.groupby(['category', 'series', 'item_name', 'month_str']).quantity.agg(net='sum', neg=lambda x: int(x[x<0].sum())).reset_index()
    
    total_agg = agg.groupby(['category', 'series', 'item_name']).agg(total_net=('net', 'sum'), total_neg=('neg', 'sum')).reset_index()
    stock_agg = df_main.groupby('item_name')['stock'].max().reset_index()
    total_agg = pd.merge(total_agg, stock_agg, on='item_name', how='left').fillna(0)
    total_agg['stock'] = total_agg['stock'].astype(int)

    rows = []
    all_categories = agg['category'].unique()
    desired_order = ["안경테", "선글라스", "클립", "모던"]
    ordered_categories = [cat for cat in desired_order if cat in all_categories]
    ordered_categories += sorted([cat for cat in all_categories if cat not in desired_order])
    
    subtotal_targets = ["안경테", "선글라스", "클립"]
    subtotals = {m: {'net': 0, 'neg': 0} for m in months}
    subtotals['total'] = {'net': 0, 'neg': 0}

    for cat_name in ordered_categories:
        cat_group = agg[agg['category'] == cat_name]
        cat_row = {'name': cat_name, 'id': f"cat_{cat_name}", 'level': 1, 'data': {}, 'children': []}
        
        for series_name in sorted(cat_group['series'].unique()):
            series_group = cat_group[cat_group['series'] == series_name]
            series_total_info = total_agg[(total_agg['category'] == cat_name) & (total_agg['series'] == series_name)]
            series_row = {'name': series_name, 'id': f"series_{cat_name}_{series_name}", 'parentId': cat_row['id'], 'level': 2, 'data': {}, 'children': []}
            
            for item_name in sorted(series_group['item_name'].unique()):
                item_group = series_group[series_group['item_name'] == item_name].set_index('month_str')
                item_total = series_total_info[series_total_info['item_name'] == item_name]
                
                item_row = {
                    'name': item_name,
                    'id': f"item_{cat_name}_{series_name}_{item_name}",
                    'parentId': series_row['id'], 'level': 3, 'data': {},
                    'total': {'net': int(item_total['total_net'].iloc[0]) if not item_total.empty else 0, 'neg': int(item_total['total_neg'].iloc[0]) if not item_total.empty else 0},
                    'stock': int(item_total['stock'].iloc[0]) if not item_total.empty else 0,
                }
                item_row['data'] = {m: {'net': int(item_group.at[m, 'net']) if m in item_group.index else 0, 'neg': int(item_group.at[m, 'neg']) if m in item_group.index else 0} for m in months}
                series_row['children'].append(item_row)

            series_row['data'] = {m: {'net': sum(i['data'][m]['net'] for i in series_row['children']), 'neg': sum(i['data'][m]['neg'] for i in series_row['children'])} for m in months}
            series_row['total'] = {'net': sum(i['total']['net'] for i in series_row['children']), 'neg': sum(i['total']['neg'] for i in series_row['children'])}
            cat_row['children'].append(series_row)

        cat_row['data'] = {m: {'net': sum(s['data'][m]['net'] for s in cat_row['children']), 'neg': sum(s['data'][m]['neg'] for s in cat_row['children'])} for m in months}
        cat_row['total'] = {'net': sum(s['total']['net'] for s in cat_row['children']), 'neg': sum(s['total']['neg'] for s in cat_row['children'])}

        if cat_name in subtotal_targets:
            for m in months:
                subtotals[m]['net'] += cat_row['data'][m]['net']
                subtotals[m]['neg'] += cat_row['data'][m]['neg']
            subtotals['total']['net'] += cat_row['total']['net']
            subtotals['total']['neg'] += cat_row['total']['neg']
        rows.append(cat_row)

        if cat_name == '클립':
            subtotal_row = {'name': '합계', 'id': 'subtotal_row', 'level': 0, 'data': subtotals, 'total': subtotals['total']}
            rows.append(subtotal_row)
            
    return months, rows, top_series_data