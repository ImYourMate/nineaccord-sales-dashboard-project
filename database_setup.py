# database_setup.py
import sqlite3

DATABASE_NAME = 'sales.db'
# 브랜드별 테이블 이름 정의
BRANDS = ['nine', 'curu']

def create_table():
    with sqlite3.connect(DATABASE_NAME) as conn:
        for brand in BRANDS:
            table_name = f"sales_data_{brand}"
            conn.execute(
                f'''
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    warehouse TEXT NOT NULL,
                    category TEXT NOT NULL,
                    month_year TEXT NOT NULL,
                    item_name TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    series TEXT,
                    stock INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                '''
            )
            print(f"테이블 '{table_name}'이(가) 준비되었습니다.")

if __name__ == '__main__':
    create_table()