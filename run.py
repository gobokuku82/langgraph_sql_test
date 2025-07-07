#!/usr/bin/env python3
"""
LangGraph 기반 성과 보고서 시스템 실행 스크립트
"""

import os
import sys
import argparse
from data_processor import DataProcessor
from langgraph_system import PerformanceReportSystem

def setup_data():
    """데이터 설정 및 데이터베이스 생성"""
    print("📊 데이터 처리를 시작합니다...")
    
    processor = DataProcessor()
    
    # Excel 데이터 로드
    df = processor.load_excel_data()
    if df is None:
        print("❌ Excel 파일 로드에 실패했습니다.")
        return False
    
    # 데이터 분석
    analysis = processor.analyze_data_structure(df)
    print(f"✅ 데이터 분석 완료: {analysis['total_rows']}행, {analysis['total_columns']}열")
    
    # SQLite 데이터베이스 생성
    processor.create_sqlite_db(df)
    print("✅ SQLite 데이터베이스 생성 완료")
    
    # 데이터베이스 테스트
    if processor.test_database():
        print("✅ 데이터베이스 테스트 통과")
        return True
    else:
        print("❌ 데이터베이스 테스트 실패")
        return False

def run_console():
    """콘솔 모드로 실행"""
    print("🚀 LangGraph 성과 보고서 시스템 - 콘솔 모드")
    
    # 시스템 초기화
    system = PerformanceReportSystem()
    print("✅ AI 시스템 초기화 완료")
    
    print("\n💬 채팅을 시작합니다. '종료' 또는 'quit'를 입력하면 종료됩니다.")
    print("예시: '전체 매출 현황 보고서를 만들어주세요'\n")
    
    while True:
        try:
            user_input = input("사용자: ").strip()
            
            if user_input.lower() in ['종료', 'quit', 'exit']:
                print("시스템을 종료합니다.")
                break
            
            if not user_input:
                continue
            
            print("🤖 AI가 응답을 생성하고 있습니다...")
            response = system.run(user_input)
            print(f"\n🤖 AI: {response}\n")
            
        except KeyboardInterrupt:
            print("\n\n시스템을 종료합니다.")
            break
        except Exception as e:
            print(f"❌ 오류가 발생했습니다: {e}")

def run_streamlit():
    """Streamlit 웹 앱으로 실행"""
    print("🌐 Streamlit 웹 앱을 시작합니다...")
    os.system("streamlit run app.py")

def check_environment():
    """환경 설정을 확인합니다."""
    print("🔍 환경 설정을 확인합니다...")
    
    # .env 파일 확인
    if not os.path.exists('.env'):
        print("⚠️  .env 파일이 없습니다. .env.example을 참고하여 생성해주세요.")
        return False
    
    # OpenAI API 키 확인
    from dotenv import load_dotenv
    load_dotenv()
    
    if not os.getenv('OPENAI_API_KEY'):
        print("❌ OPENAI_API_KEY가 설정되지 않았습니다.")
        return False
    
    # 필수 파일 확인
    if not os.path.exists('data.xlsx'):
        print("❌ data.xlsx 파일이 없습니다.")
        return False
    
    print("✅ 환경 설정이 올바릅니다.")
    return True

def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='LangGraph 성과 보고서 시스템')
    parser.add_argument('--mode', choices=['setup', 'console', 'web'], default='web',
                       help='실행 모드 선택 (default: web)')
    parser.add_argument('--force-setup', action='store_true',
                       help='강제로 데이터 설정 다시 실행')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🚀 LangGraph 기반 성과 보고서 시스템")
    print("=" * 60)
    
    # 환경 확인
    if not check_environment():
        print("\n환경 설정을 완료한 후 다시 실행해주세요.")
        return
    
    # 데이터 설정
    if args.mode == 'setup' or args.force_setup or not os.path.exists('sales_data.db'):
        if not setup_data():
            print("데이터 설정에 실패했습니다.")
            return
    
    # 모드별 실행
    if args.mode == 'setup':
        print("✅ 데이터 설정이 완료되었습니다.")
    elif args.mode == 'console':
        run_console()
    elif args.mode == 'web':
        run_streamlit()

if __name__ == "__main__":
    main() 