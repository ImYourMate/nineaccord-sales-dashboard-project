# migrate_data.py
import sqlite3
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import sys

DATABASE_NAME = 'sales.db'
SCOPES = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
GOOGLE_CREDENTIALS_FILE = 'google_credentials.json'
GOOGLE_SHEET_NAME = 'NINE ACCORD 판매현황'

# 브랜드별 탭 매핑 설정
BRAND_CONFIG = {
    'nine': {'sheet_tab': '사이트DB', 'table': 'sales_data_nine'},
    'curu': {'sheet_tab': '쿠루누루DB', 'table': 'sales_data_curu'}
}

def clean_data(df):
    # (기존 clean_data 함수 내용 동일)
    df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0).astype(int)
    df['stock'] = pd.to_numeric(df['stock'], errors='coerce').fillna(0).astype(int)
    not_null_text_cols = ['warehouse', 'category', 'month_year', 'item_name']
    for col in not_null_text_cols:
        if col in df.columns:
            df[col] = df[col].fillna('').astype(str)
    if 'series' in df.columns:
        df['series'] = df['series'].fillna('').astype(str)
    return df

def migrate_google_sheet_to_db(target_brand):
    if target_brand not in BRAND_CONFIG:
        print(f"오류: 알 수 없는 브랜드 '{target_brand}'")
        return

    config = BRAND_CONFIG[target_brand]
    tab_name = config['sheet_tab']
    table_name = config['table']

    conn = None
    try:
        print(f"[{target_brand.upper()}] 데이터 마이그레이션 시작...")
        creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=SCOPES)
        client = gspread.authorize(creds)
        
        spreadsheet = client.open(GOOGLE_SHEET_NAME)
        worksheet = spreadsheet.worksheet(tab_name)
        
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        expected_columns = ['창고별', '구분', '월별', '품목별', '수량', '시리즈', '재고']
        df = df[expected_columns]
        df.columns = ['warehouse', 'category', 'month_year', 'item_name', 'quantity', 'series', 'stock']

        df_cleaned = clean_data(df)

        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        cursor.execute(f"DELETE FROM {table_name}")
        df_cleaned.to_sql(table_name, conn, if_exists='append', index=False)
        conn.commit()

        print(f"성공: {len(df_cleaned)}행이 '{table_name}'에 저장되었습니다.")

    except Exception as e:
        print(f"오류 발생: {e}")
        # subprocess 호출 시 에러를 감지할 수 있도록 예외를 다시 던짐
        raise e 
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    # 명령줄 인자로 브랜드 코드 받기 (예: python migrate_data.py nine)
    if len(sys.argv) > 1:
        brand_arg = sys.argv[1]
        migrate_google_sheet_to_db(brand_arg)
    else:
        print("사용법: python migrate_data.py [nine|curu]")