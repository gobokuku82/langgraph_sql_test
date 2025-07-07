import streamlit as st
import pandas as pd
import os
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
from data_processor import DataProcessor
from langgraph_system import PerformanceReportSystem
import sqlite3

# 페이지 설정
st.set_page_config(
    page_title="LangGraph 성과 보고서 시스템",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 스타일 설정
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        color: #1e3a8a;
        text-align: center;
        margin-bottom: 2rem;
    }
    .section-header {
        font-size: 1.5rem;
        font-weight: bold;
        color: #3b82f6;
        margin: 1rem 0;
    }
    .info-box {
        background-color: #f0f9ff;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #3b82f6;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

def initialize_session_state():
    """세션 상태를 초기화합니다."""
    if 'db_created' not in st.session_state:
        st.session_state.db_created = False
    if 'system_initialized' not in st.session_state:
        st.session_state.system_initialized = False
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    if 'auto_check_done' not in st.session_state:
        st.session_state.auto_check_done = False
    if 'system_error' not in st.session_state:
        st.session_state.system_error = None

def auto_check_systems():
    """시스템 상태를 자동으로 확인합니다."""
    if st.session_state.auto_check_done:
        return
    
    # 데이터베이스 자동 확인
    try:
        import os
        if os.path.exists("sales_data.db"):
            from data_processor import DataProcessor
            processor = DataProcessor()
            if processor.test_database():
                st.session_state.db_created = True
                if os.path.exists("data_analysis.json"):
                    import json
                    with open("data_analysis.json", "r", encoding="utf-8") as f:
                        st.session_state.data_analysis = json.load(f)
    except Exception as e:
        st.session_state.db_created = False
    
    # AI 시스템 자동 확인
    try:
        from dotenv import load_dotenv
        import os
        load_dotenv()
        if os.getenv('OPENAI_API_KEY'):
            from langgraph_system import PerformanceReportSystem
            system = PerformanceReportSystem()
            st.session_state.system = system
            st.session_state.system_initialized = True
    except Exception as e:
        st.session_state.system_initialized = False
        st.session_state.system_error = str(e)
    
    st.session_state.auto_check_done = True

def create_database():
    """데이터베이스를 생성합니다."""
    try:
        processor = DataProcessor()
        df = processor.load_excel_data()
        
        if df is not None:
            processor.create_sqlite_db(df)
            analysis = processor.analyze_data_structure(df)
            st.session_state.db_created = True
            st.session_state.data_analysis = analysis
            return True, analysis
        else:
            return False, None
    except Exception as e:
        st.error(f"데이터베이스 생성 오류: {e}")
        return False, None

def initialize_system():
    """LangGraph 시스템을 초기화합니다."""
    try:
        from dotenv import load_dotenv
        import os
        load_dotenv()
        
        # API 키 확인
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            st.error("OPENAI_API_KEY가 설정되지 않았습니다. .env 파일을 확인해주세요.")
            return False
        
        from langgraph_system import PerformanceReportSystem
        system = PerformanceReportSystem()
        st.session_state.system = system
        st.session_state.system_initialized = True
        st.success("AI 시스템이 성공적으로 초기화되었습니다!")
        return True
    except Exception as e:
        error_msg = f"시스템 초기화 오류: {e}"
        st.error(error_msg)
        st.session_state.system_initialized = False
        st.session_state.system_error = str(e)
        return False

def display_data_overview():
    """데이터 개요를 표시합니다."""
    if not st.session_state.db_created:
        return
    
    st.markdown('<div class="section-header">📊 데이터 개요</div>', unsafe_allow_html=True)
    
    analysis = st.session_state.data_analysis
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("총 레코드 수", f"{analysis['total_rows']:,}")
    with col2:
        st.metric("컬럼 수", analysis['total_columns'])
    with col3:
        st.metric("데이터 타입", len(set(str(t) for t in analysis['data_types'].values())))
    
    # 컬럼 정보 표시
    with st.expander("컬럼 정보 보기"):
        col_df = pd.DataFrame({
            '컬럼명': analysis['columns'],
            '데이터 타입': [str(analysis['data_types'][col]) for col in analysis['columns']],
            '결측값 수': [analysis['null_counts'][col] for col in analysis['columns']]
        })
        st.dataframe(col_df, use_container_width=True)

def display_sample_data():
    """샘플 데이터를 표시합니다."""
    if not st.session_state.db_created:
        return
    
    st.markdown('<div class="section-header">📋 샘플 데이터</div>', unsafe_allow_html=True)
    
    try:
        conn = sqlite3.connect("sales_data.db")
        sample_data = pd.read_sql("SELECT * FROM sales_data LIMIT 10", conn)
        conn.close()
        
        st.dataframe(sample_data, use_container_width=True)
        
    except Exception as e:
        st.error(f"샘플 데이터 로드 오류: {e}")

def chat_interface():
    """채팅 인터페이스를 표시합니다."""
    if not st.session_state.system_initialized:
        return
    
    st.markdown('<div class="section-header">💬 AI 성과 보고서 생성</div>', unsafe_allow_html=True)
    
    # 채팅 히스토리 표시
    for i, (user_msg, ai_response) in enumerate(st.session_state.chat_history):
        with st.chat_message("user"):
            st.write(user_msg)
        with st.chat_message("assistant"):
            st.write(ai_response)
    
    # 사용자 입력
    user_input = st.chat_input("성과 보고서 요청을 입력하세요... (예: '전체 매출 현황 보고서를 만들어주세요')")
    
    if user_input:
        # 사용자 메시지 표시
        with st.chat_message("user"):
            st.write(user_input)
        
        # AI 응답 생성
        with st.chat_message("assistant"):
            with st.spinner("보고서를 생성하고 있습니다..."):
                try:
                    response = st.session_state.system.run(user_input)
                    st.write(response)
                    
                    # 차트가 생성된 경우 표시
                    chart_files = [f for f in os.listdir('.') if f.startswith('chart_') and f.endswith('.png')]
                    if chart_files:
                        latest_chart = max(chart_files, key=os.path.getctime)
                        st.image(latest_chart, caption="생성된 차트", use_column_width=True)
                    
                    # 채팅 히스토리에 추가
                    st.session_state.chat_history.append((user_input, response))
                    
                except Exception as e:
                    error_msg = f"오류가 발생했습니다: {e}"
                    st.error(error_msg)
                    st.session_state.chat_history.append((user_input, error_msg))

def sidebar():
    """사이드바를 구성합니다."""
    st.sidebar.markdown("## 🔧 시스템 설정")
    
    # 시스템 상태 확인 버튼
    if st.sidebar.button("🔍 시스템 상태 재확인", use_container_width=True):
        st.session_state.auto_check_done = False
        auto_check_systems()
        st.rerun()
    
    # 데이터베이스 상태
    if st.session_state.db_created:
        st.sidebar.success("✅ 데이터베이스 준비됨")
        if hasattr(st.session_state, 'data_analysis'):
            st.sidebar.info(f"📊 {st.session_state.data_analysis.get('total_rows', 0)}행 데이터 로드됨")
    else:
        st.sidebar.warning("⚠️ 데이터베이스 미준비")
    
    # 시스템 상태
    if st.session_state.system_initialized:
        st.sidebar.success("✅ AI 시스템 준비됨")
        st.sidebar.info("🤖 GPT-4o 모델 연결됨")
    else:
        st.sidebar.warning("⚠️ AI 시스템 미준비")
        if hasattr(st.session_state, 'system_error'):
            st.sidebar.error(f"오류: {st.session_state.system_error}")
    
    st.sidebar.markdown("---")
    
    # 초기화 버튼들
    if st.sidebar.button("🔄 데이터베이스 초기화", use_container_width=True):
        with st.spinner("데이터베이스를 생성하고 있습니다..."):
            try:
                success, analysis = create_database()
                if success:
                    st.sidebar.success("데이터베이스가 성공적으로 생성되었습니다!")
                    st.rerun()
                else:
                    st.sidebar.error("데이터베이스 생성에 실패했습니다.")
            except Exception as e:
                st.sidebar.error(f"데이터베이스 초기화 오류: {e}")
    
    if st.sidebar.button("🚀 AI 시스템 초기화", use_container_width=True):
        with st.spinner("AI 시스템을 초기화하고 있습니다..."):
            try:
                success = initialize_system()
                if success:
                    st.sidebar.success("AI 시스템이 성공적으로 초기화되었습니다!")
                    st.rerun()
                else:
                    st.sidebar.error("AI 시스템 초기화에 실패했습니다.")
            except Exception as e:
                st.sidebar.error(f"AI 시스템 초기화 오류: {e}")
    
    # 채팅 히스토리 클리어
    if st.sidebar.button("🗑️ 채팅 히스토리 클리어", use_container_width=True):
        st.session_state.chat_history = []
        st.rerun()
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📖 사용법")
    st.sidebar.markdown("""
    1. **데이터베이스 초기화**: Excel 데이터를 SQLite DB로 변환
    2. **AI 시스템 초기화**: LangGraph 시스템 준비
    3. **보고서 요청**: 자연어로 성과 보고서 요청
    
    **예시 요청:**
    - "전체 매출 현황 보고서를 만들어주세요"
    - "특정 제품의 실적을 분석해주세요"
    - "월별 트렌드를 보여주세요"
    """)

def main():
    """메인 앱 함수"""
    initialize_session_state()
    auto_check_systems()
    
    # 헤더
    st.markdown('<div class="main-header">📊 LangGraph 성과 보고서 시스템</div>', unsafe_allow_html=True)
    
    # 사이드바
    sidebar()
    
    # 메인 콘텐츠
    tab1, tab2, tab3 = st.tabs(["🏠 홈", "📊 데이터 개요", "💬 AI 채팅"])
    
    with tab1:
        st.markdown("""
        <div class="info-box">
            <h3>🎯 시스템 소개</h3>
            <p>이 시스템은 <strong>LangGraph</strong>와 <strong>OpenAI GPT-4o</strong>를 활용하여 
            Excel 데이터를 분석하고 전문적인 성과 보고서를 자동 생성하는 AI 시스템입니다.</p>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("### 🔄 시스템 워크플로우")
        st.image("https://via.placeholder.com/800x400/3b82f6/ffffff?text=LangGraph+Workflow", 
                caption="LangGraph 기반 AI 워크플로우")
        
        st.markdown("### ✨ 주요 기능")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            **📊 데이터 처리**
            - Excel 파일 자동 분석
            - SQLite 데이터베이스 변환
            - 실시간 데이터 쿼리
            """)
            
        with col2:
            st.markdown("""
            **🤖 AI 분석**
            - 자연어 요청 처리
            - 자동 보고서 생성
            - 차트 및 시각화
            """)
    
    with tab2:
        display_data_overview()
        display_sample_data()
    
    with tab3:
        if not st.session_state.db_created or not st.session_state.system_initialized:
            st.warning("먼저 사이드바에서 데이터베이스와 AI 시스템을 초기화해주세요.")
        else:
            chat_interface()

if __name__ == "__main__":
    main() 