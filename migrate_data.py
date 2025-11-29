# migrate_data.py

import sqlite3
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import sys

# --- 상수 정의 ---
DATABASE_NAME = 'sales.db'
# 구글 시트 관련 설정
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
GOOGLE_CREDENTIALS_FILE = 'google_credentials.json' # 구글 서비스 계정 키 파일
GOOGLE_SHEET_NAME = 'NINE ACCORD 판매현황' # 액세스할 구글 시트 이름

# 브랜드별 탭 매핑 설정
BRAND_CONFIG = {
    'nine': {'sheet_tab': '사이트DB', 'table': 'sales_data_nine'},
    'curu': {'sheet_tab': '쿠루누루DB', 'table': 'sales_data_curu'}
}

def clean_data(df):
    """
    Pandas DataFrame을 데이터베이스에 저장하기 전에 정제합니다.
    """
    # '수량' 컬럼의 빈 값(NaN)을 0으로 채우고 정수형으로 변환
    df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0).astype(int)
    
    # '재고' 컬럼도 동일하게 처리
    df['stock'] = pd.to_numeric(df['stock'], errors='coerce').fillna(0).astype(int)

    # 다른 NOT NULL 텍스트 컬럼들의 빈 값(NaN)을 빈 문자열('')로 채움
    not_null_text_cols = ['warehouse', 'category', 'month_year', 'item_name']
    for col in not_null_text_cols:
        if col in df.columns:
            df[col] = df[col].fillna('').astype(str)
            
    # '시리즈' 컬럼은 NULL을 허용하므로 비워둬도 되지만, 일관성을 위해 처리
    if 'series' in df.columns:
        df['series'] = df['series'].fillna('').astype(str)

    return df

def migrate_google_sheet_to_db(target_brand):
    """
    구글 시트의 데이터를 읽어 SQLite 데이터베이스로 이전합니다.
    """
    if target_brand not in BRAND_CONFIG:
        print(f"오류: 알 수 없는 브랜드 '{target_brand}'")
        return

    config = BRAND_CONFIG[target_brand]
    tab_name = config['sheet_tab']
    table_name = config['table']

    conn = None
    try:
        # 1. 구글 시트 데이터 읽기
        print(f"[{target_brand.upper()}] 데이터 마이그레이션 시작...")
        creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=SCOPES)
        client = gspread.authorize(creds)
        
        spreadsheet = client.open(GOOGLE_SHEET_NAME)
        worksheet = spreadsheet.worksheet(tab_name)
        
        # 시트 데이터를 Pandas DataFrame으로 변환
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        # 엑셀 컬럼명 -> DB 컬럼명으로 변경
        expected_columns = ['창고별', '구분', '월별', '품목별', '수량', '시리즈', '재고']
        df = df[expected_columns]
        df.columns = ['warehouse', 'category', 'month_year', 'item_name', 'quantity', 'series', 'stock']

        # 2. 데이터 정제
        df_cleaned = clean_data(df)

        # 3. 데이터베이스에 연결
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        # 4. 기존 테이블의 모든 데이터를 삭제 (초기화)
        cursor.execute(f"DELETE FROM {table_name}")
        
        # 5. 정제된 데이터를 테이블에 삽입
        df_cleaned.to_sql(table_name, conn, if_exists='append', index=False)
        conn.commit()

        print(f"성공: {len(df_cleaned)}행이 '{table_name}'에 저장되었습니다.")

    except Exception as e:
        # 상위 호출자에게 에러를 전달하기 위해 예외를 다시 발생시킴
        raise e
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    from database_setup import create_table, BRANDS
    
    # 1. 테이블 구조 확인 (없으면 생성)
    create_table()
    
    # 2. 인자 확인 및 실행
    if len(sys.argv) > 1:
        brand_arg = sys.argv[1]
        
        # 'all' 명령어가 들어오면 등록된 모든 브랜드 순차 실행
        if brand_arg == 'all':
            print("\n" + "="*50)
            print(f"   [전체 브랜드] 데이터 통합 업데이트 시작 (대상: {', '.join(BRANDS)})")
            print("="*50 + "\n")
            
            success_count = 0
            fail_count = 0
            
            for brand in BRANDS:
                try:
                    migrate_google_sheet_to_db(brand)
                    print("") # 줄바꿈
                    success_count += 1
                except Exception as e:
                    print(f"!!! [{brand.upper()}] 실패: {e}\n")
                    fail_count += 1
            
            print("="*50)
            print(f"   전체 업데이트 종료 (성공: {success_count}, 실패: {fail_count})")
            print("="*50)
            
            # 하나라도 실패하면 에러 코드 반환 (웹 서버가 알 수 있게)
            if fail_count > 0:
                sys.exit(1)
        else:
            # 기존처럼 단일 브랜드 실행
            try:
                migrate_google_sheet_to_db(brand_arg)
            except Exception as e:
                print(f"오류 발생: {e}")
                sys.exit(1)
    else:
        print("사용법: python migrate_data.py [nine|curu|all]")