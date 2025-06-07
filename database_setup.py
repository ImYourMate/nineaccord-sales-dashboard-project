import sqlite3

DATABASE_NAME = 'sales.db'


def create_table():
    """
    SQLite 데이터베이스에 sales_data 테이블을 생성합니다.
    """
    with sqlite3.connect(DATABASE_NAME) as conn:
        conn.execute(
            '''
            CREATE TABLE IF NOT EXISTS sales_data (
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
    print(f"'{DATABASE_NAME}'의 'sales_data' 테이블이 생성되었거나 이미 존재합니다.")


if __name__ == '__main__':
    create_table()