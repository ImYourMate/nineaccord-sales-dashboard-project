# migrate_data.py (수정)

import sqlite3
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# --- 상수 정의 ---
DATABASE_NAME = 'sales.db'
# 구글 시트 관련 설정
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
GOOGLE_CREDENTIALS_FILE = 'google_credentials.json' # 구글 서비스 계정 키 파일
GOOGLE_SHEET_NAME = 'NINE ACCORD 판매현황' # 액세스할 구글 시트 이름
GOOGLE_WORKSHEET_NAME = '사이트DB' # <- 이 줄을 추가합니다. 불러올 특정 탭 이름

def clean_data(df):
    """
    Pandas DataFrame을 데이터베이스에 저장하기 전에 정제합니다.
    - NOT NULL 제약 조건이 있는 컬럼의 빈 값을 처리합니다.
    """
    # '수량' 컬럼의 빈 값(NaN)을 0으로 채우고 정수형으로 변환
    df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0).astype(int)
    
    # '재고' 컬럼도 동일하게 처리 (NULL을 허용하지만 계산 편의를 위해 0으로 채움)
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

def migrate_google_sheet_to_db():
    """
    구글 시트의 데이터를 읽어 SQLite 데이터베이스로 이전합니다.
    - 구글 시트 데이터를 정제한 후, 데이터베이스의 모든 기존 데이터를 삭제하고 새로 채웁니다.
    """
    conn = None
    try:
        # 1. 구글 시트 데이터 읽기
        print("구글 시트 인증 및 데이터 로딩을 시작합니다...")
        creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=SCOPES)
        client = gspread.authorize(creds)
        
        spreadsheet = client.open(GOOGLE_SHEET_NAME)
        # worksheet = spreadsheet.get_worksheet(0)  # <- 이 줄을 주석 처리합니다.
        worksheet = spreadsheet.worksheet(GOOGLE_WORKSHEET_NAME) # <- 이 줄로 변경합니다.
        
        # 시트 데이터를 Pandas DataFrame으로 변환
        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        print(f"'{GOOGLE_SHEET_NAME}' 시트의 '{GOOGLE_WORKSHEET_NAME}' 탭에서 {len(df)}개 행을 성공적으로 읽었습니다.")

        # 엑셀 컬럼명 -> DB 컬럼명으로 변경
        expected_columns = ['창고별', '구분', '월별', '품목별', '수량', '시리즈', '재고']
        # 시트의 컬럼 순서나 이름이 다를 수 있으므로, 존재하는 컬럼만 선택하여 이름 변경
        df = df[expected_columns] # 정확한 컬럼 순서와 이름으로 DataFrame 재구성
        df.columns = ['warehouse', 'category', 'month_year', 'item_name', 'quantity', 'series', 'stock']

        # 2. 데이터 정제
        df_cleaned = clean_data(df)
        print("데이터 정제를 완료했습니다.")

        # 3. 데이터베이스에 연결
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()

        # 4. 기존 테이블의 모든 데이터를 삭제 (초기화)
        cursor.execute("DELETE FROM sales_data")
        print(f"'sales_data' 테이블의 기존 데이터 {cursor.rowcount}개를 삭제했습니다.")

        # 5. 정제된 데이터를 테이블에 삽입
        df_cleaned.to_sql('sales_data', conn, if_exists='append', index=False)
        conn.commit()

        print(f"성공: 총 {len(df_cleaned)}개의 정제된 행이 'sales_data' 테이블로 새로 이전되었습니다.")

    except gspread.exceptions.SpreadsheetNotFound:
        print(f"오류: 구글 시트 '{GOOGLE_SHEET_NAME}'를 찾을 수 없습니다.")
        print("서비스 계정에 시트가 공유되었는지, 이름이 정확한지 확인하세요.")
    except gspread.exceptions.WorksheetNotFound: # <- 이 부분 추가
        print(f"오류: 구글 시트 '{GOOGLE_SHEET_NAME}'에서 탭 '{GOOGLE_WORKSHEET_NAME}'을(를) 찾을 수 없습니다.")
        print("탭 이름이 정확한지 확인하세요.")
    except Exception as e:
        print(f"마이그레이션 중 알 수 없는 오류 발생: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    from database_setup import create_table
    
    # 테이블이 없는 경우를 대비해 생성 로직 실행
    print("테이블 구조를 확인 및 생성합니다...")
    create_table()
    
    # 데이터 마이그레이션 실행
    print("\n데이터 마이그레이션을 시작합니다...")
    migrate_google_sheet_to_db()