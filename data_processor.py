import pandas as pd
import sqlite3
import os
from datetime import datetime
import json

class DataProcessor:
    def __init__(self, excel_file="data.xlsx", db_file="sales_data.db"):
        self.excel_file = excel_file
        self.db_file = db_file
        
    def load_excel_data(self):
        """Excel 파일에서 데이터를 로드합니다."""
        try:
            # Excel 파일 읽기 (헤더가 있는 경우)
            df = pd.read_excel(self.excel_file)
            
            # datetime 컬럼명을 문자열로 변환
            new_columns = []
            for col in df.columns:
                if isinstance(col, datetime):
                    # datetime을 YYYY-MM 형식의 문자열로 변환
                    new_columns.append(col.strftime('%Y-%m'))
                else:
                    new_columns.append(str(col))
            
            df.columns = new_columns
            print(f"Excel 파일 로드 완료: {df.shape[0]}행, {df.shape[1]}열")
            print(f"컬럼명: {list(df.columns)}")
            return df
        except Exception as e:
            print(f"Excel 파일 로드 오류: {e}")
            return None
    
    def analyze_data_structure(self, df):
        """데이터 구조를 분석합니다."""
        analysis = {
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "columns": list(df.columns),
            "data_types": df.dtypes.to_dict(),
            "null_counts": df.isnull().sum().to_dict(),
            "sample_data": df.head().to_dict()
        }
        
        # 분석 결과 저장
        with open("data_analysis.json", "w", encoding="utf-8") as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2, default=str)
        
        return analysis
    
    def create_sqlite_db(self, df):
        """SQLite 데이터베이스를 생성합니다."""
        try:
            # 기존 DB 파일이 있으면 삭제
            if os.path.exists(self.db_file):
                os.remove(self.db_file)
            
            # SQLite 연결
            conn = sqlite3.connect(self.db_file)
            
            # 데이터를 sales_data 테이블에 저장
            df.to_sql('sales_data', conn, index=False, if_exists='replace')
            
            # 메타데이터 테이블 생성
            metadata = {
                'created_at': datetime.now().isoformat(),
                'total_records': len(df),
                'columns': ', '.join(df.columns),
                'source_file': self.excel_file
            }
            
            metadata_df = pd.DataFrame([metadata])
            metadata_df.to_sql('metadata', conn, index=False, if_exists='replace')
            
            conn.close()
            print(f"SQLite 데이터베이스 생성 완료: {self.db_file}")
            
        except Exception as e:
            print(f"데이터베이스 생성 오류: {e}")
    
    def get_sample_queries(self):
        """샘플 SQL 쿼리들을 반환합니다."""
        queries = {
            "전체_데이터_조회": "SELECT * FROM sales_data LIMIT 10",
            "컬럼_정보": "PRAGMA table_info(sales_data)",
            "메타데이터": "SELECT * FROM metadata",
            "총_레코드_수": "SELECT COUNT(*) as total_count FROM sales_data"
        }
        return queries
    
    def test_database(self):
        """데이터베이스 연결 테스트를 수행합니다."""
        try:
            conn = sqlite3.connect(self.db_file)
            
            # 테이블 목록 확인
            tables = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table'", conn)
            print("데이터베이스 테이블:", tables['name'].tolist())
            
            # 샘플 데이터 확인
            sample_data = pd.read_sql("SELECT * FROM sales_data LIMIT 5", conn)
            print("\n샘플 데이터:")
            print(sample_data)
            
            conn.close()
            return True
            
        except Exception as e:
            print(f"데이터베이스 테스트 오류: {e}")
            return False

def main():
    """메인 실행 함수"""
    processor = DataProcessor()
    
    # Excel 데이터 로드
    df = processor.load_excel_data()
    if df is None:
        return
    
    # 데이터 구조 분석
    analysis = processor.analyze_data_structure(df)
    print("\n데이터 분석 완료:")
    print(f"- 총 {analysis['total_rows']}행, {analysis['total_columns']}열")
    print(f"- 컬럼: {analysis['columns']}")
    
    # SQLite 데이터베이스 생성
    processor.create_sqlite_db(df)
    
    # 데이터베이스 테스트
    processor.test_database()
    
    # 샘플 쿼리 출력
    print("\n사용 가능한 샘플 쿼리:")
    for name, query in processor.get_sample_queries().items():
        print(f"- {name}: {query}")

if __name__ == "__main__":
    main() 