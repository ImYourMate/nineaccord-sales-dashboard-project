import sqlite3
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import sys

# --- 상수 정의 ---
DATABASE_NAME = 'sales.db'
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
GOOGLE_CREDENTIALS_FILE = 'google_credentials.json'

# 1. 판매 데이터가 있는 시트 이름
GOOGLE_SHEET_NAME = 'NINE ACCORD 판매현황' 

# 2. [수정] 미입고 정보가 있는 외부 시트 ID (URL의 d/ 뒷부분)
# URL: https://docs.google.com/spreadsheets/d/1N2AH6tKe-uydqs5t5JdNNf_qRGvX_Wv3Jo4dZGnKws8/...
BACKORDER_SHEET_KEY = '1N2AH6tKe-uydqs5t5JdNNf_qRGvX_Wv3Jo4dZGnKws8'
BACKORDER_TAB_NAME = '발주표'

BRAND_CONFIG = {
    'nine': {'sheet_tab': 'DB_나인', 'table': 'sales_data_nine'},
    'curu': {'sheet_tab': 'DB_쿠루', 'table': 'sales_data_curu'}
}

def clean_number(value):
    """숫자 변환 (콤마 제거)"""
    try:
        return int(str(value).replace(',', '').strip())
    except:
        return 0

def clean_data(df):
    """기본 데이터 정제"""
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
        print(f"[{target_brand.upper()}] 데이터 마이그레이션 시작 (탭: {tab_name})...")
        creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=SCOPES)
        client = gspread.authorize(creds)
        
        # ---------------------------------------------------------
        # 1. 판매 데이터 읽기 (기존 시트)
        # ---------------------------------------------------------
        spreadsheet = client.open(GOOGLE_SHEET_NAME)
        
        try:
            worksheet = spreadsheet.worksheet(tab_name)
        except gspread.exceptions.WorksheetNotFound:
            raise Exception(f"구글 시트에서 '{tab_name}' 탭을 찾을 수 없습니다.")

        data = worksheet.get_all_records()
        df = pd.DataFrame(data)
        
        expected_columns = ['창고별', '구분', '월별', '품목별', '수량', '시리즈', '재고']
        if not all(col in df.columns for col in expected_columns):
             if len(df.columns) >= 7:
                 df = df.iloc[:, :7]
                 df.columns = expected_columns
             else:
                 raise Exception(f"'{tab_name}' 탭의 컬럼 형식이 맞지 않습니다.")
        else:
             df = df[expected_columns]

        df.columns = ['warehouse', 'category', 'month_year', 'item_name', 'quantity', 'series', 'stock']

        # ---------------------------------------------------------
        # 2. [수정] 발주표(미입고잔량) 데이터 읽기 (외부 시트 접근)
        # ---------------------------------------------------------
        try:
            # open_by_key를 사용하여 외부 시트 열기
            bo_spreadsheet = client.open_by_key(BACKORDER_SHEET_KEY)
            bo_sheet = bo_spreadsheet.worksheet(BACKORDER_TAB_NAME)
            bo_data = bo_sheet.get_all_values() 
            
            bo_map = {}
            # L열(인덱스 11) 품목명, M열(인덱스 12) 수량 매핑
            for row in bo_data[1:]:
                if len(row) > 12:
                    p_name = str(row[11]).strip() # L열
                    qty = clean_number(row[12])   # M열
                    if p_name:
                        bo_map[p_name] = qty
            
            df['backorder'] = df['item_name'].map(bo_map).fillna(0).astype(int)
            print(f"   - 미입고 정보 매핑 완료 (외부 시트 참조, {len(bo_map)}건)")
            
        except gspread.exceptions.SpreadsheetNotFound:
            print(f"   ⚠️ 경고: 발주표 시트 ID({BACKORDER_SHEET_KEY})를 찾을 수 없습니다. (공유 권한 확인 필요)")
            df['backorder'] = 0
        except gspread.exceptions.WorksheetNotFound:
            print(f"   ⚠️ 경고: 외부 시트에서 '{BACKORDER_TAB_NAME}' 탭을 찾을 수 없습니다.")
            df['backorder'] = 0
        except Exception as e:
            print(f"   ⚠️ 발주표 로드 중 알 수 없는 오류: {e}")
            df['backorder'] = 0

        # ---------------------------------------------------------
        # 3. 데이터 정제 및 저장
        # ---------------------------------------------------------
        df_cleaned = clean_data(df)

        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM {table_name}")
        df_cleaned.to_sql(table_name, conn, if_exists='append', index=False)
        conn.commit()

        print(f"성공: {len(df_cleaned)}행 저장 완료.")

    except Exception as e:
        raise e
    finally:
        if conn: conn.close()

if __name__ == '__main__':
    from database_setup import create_table, BRANDS
    
    # 테이블 구조 확인 (DB가 없으면 생성)
    create_table()
    
    if len(sys.argv) > 1:
        brand_arg = sys.argv[1]
        
        if brand_arg == 'all':
            print("\n" + "="*50)
            print(f"   [전체 브랜드] 데이터 통합 업데이트 시작 (대상: {', '.join(BRANDS)})")
            print("="*50 + "\n")
            
            success_count = 0
            fail_count = 0
            
            for brand in BRANDS:
                try:
                    migrate_google_sheet_to_db(brand)
                    print("")
                    success_count += 1
                except Exception as e:
                    print(f"!!! [{brand.upper()}] 실패: {e}\n")
                    fail_count += 1
            
            print("="*50)
            print(f"   전체 업데이트 종료 (성공: {success_count}, 실패: {fail_count})")
            print("="*50)
            
            if fail_count > 0: sys.exit(1)
        else:
            try:
                migrate_google_sheet_to_db(brand_arg)
            except Exception as e:
                print(f"오류: {e}")
                sys.exit(1)
    else:
        print("사용법: python migrate_data.py [nine|curu|all]")