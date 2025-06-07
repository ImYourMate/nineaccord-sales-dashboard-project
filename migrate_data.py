# migrate_data.py (구글 시트 연동 버전)

import pandas as pd
import gspread
from gspread_dataframe import get_as_dataframe
import sqlite3
import os

# 파일 경로 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_NAME = os.path.join(BASE_DIR, 'sales.db')
CREDENTIALS_PATH = os.path.join(BASE_DIR, 'google_credentials.json') # 인증키 경로
# --- 수정: 구글 시트 이름 입력 ---
GOOGLE_SHEET_NAME = "NINE ACCORD 판매현황" 

def clean_data(df):
    # (clean_data 함수 내용은 변경 없음)
    # ...
    return df

def get_data_from_google_sheet():
    """
    gspread를 사용하여 구글 시트에서 데이터를 읽어 DataFrame으로 반환합니다.
    """
    gc = gspread.service_account(filename=CREDENTIALS_PATH)
    spreadsheet = gc.open(GOOGLE_SHEET_NAME)
    worksheet = spreadsheet.sheet1 # 첫 번째 시트를 가져옴
    
    # 헤더를 포함한 모든 데이터를 가져와서 DataFrame으로 변환
    df = get_as_dataframe(worksheet, evaluate_formulas=True)
    return df

def update_database_from_sheet():
    """
    구글 시트 데이터를 읽어 DB를 업데이트하는 메인 함수.
    """
    conn = None
    try:
        print("구글 시트에서 데이터 로드를 시작합니다...")
        df = get_data_from_google_sheet()
        
        # 원본 데이터와 동일한 컬럼명이 되도록 수정
        df.rename(columns={
            '창고별': 'warehouse', '구분': 'category', '월별': 'month_year', 
            '품목별': 'item_name', '수량': 'quantity', '시리즈': 'series', '재고': 'stock'
        }, inplace=True)

        df_cleaned = clean_data(df)
        print(f"구글 시트에서 {len(df)}개 행을 읽어 데이터 정제를 완료했습니다.")

        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM sales_data")
        print(f"'sales_data' 테이블의 기존 데이터 {cursor.rowcount}개를 삭제했습니다.")

        df_cleaned.to_sql('sales_data', conn, if_exists='append', index=False, chunksize=10000)
        
        conn.commit()
        success_message = f"성공: 총 {len(df_cleaned)}개의 행이 'sales_data' 테이블로 새로 이전되었습니다."
        print(success_message)
        return True, success_message

    except Exception as e:
        error_message = f"마이그레이션 중 알 수 없는 오류 발생: {e}"
        print(error_message)
        return False, error_message
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    from database_setup import create_table
    print("테이블 구조를 확인 및 생성합니다...")
    create_table()
    
    print("\n데이터 마이그레이션을 시작합니다...")
    update_database_from_sheet()