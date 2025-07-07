import os
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from typing import Dict, Any, List, Optional
import json

from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict, Annotated
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

class GraphState(TypedDict):
    """LangGraph 상태 정의"""
    messages: Annotated[list, add_messages]
    task_type: str
    client_or_region: str
    sql_query: str
    query_result: pd.DataFrame
    analysis_result: Dict[str, Any]
    chart_path: Optional[str]
    report: str
    needs_human_review: bool
    final_answer: str

class PerformanceReportSystem:
    def __init__(self, db_file="sales_data.db"):
        self.db_file = db_file
        self.llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.1
        )
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """LangGraph 워크플로우를 구성합니다."""
        workflow = StateGraph(GraphState)
        
        # 노드 추가
        workflow.add_node("classify_task", self.classify_task_type)
        workflow.add_node("parse_client_region", self.parse_client_or_region)
        workflow.add_node("build_sql_query", self.build_sql_query)
        workflow.add_node("query_database", self.query_database)
        workflow.add_node("analyze_data", self.analyze_with_pandas)
        workflow.add_node("generate_charts", self.generate_charts)
        workflow.add_node("generate_report", self.generate_report)
        workflow.add_node("h2h_decision", self.h2h_decision)
        workflow.add_node("final_answer", self.generate_final_answer)
        
        # 진입점 설정
        workflow.set_entry_point("classify_task")
        
        # 엣지 추가
        workflow.add_conditional_edges(
            "classify_task",
            self.route_by_task_type,
            {
                "performance_report": "parse_client_region",
                "other": "final_answer"
            }
        )
        
        workflow.add_edge("parse_client_region", "build_sql_query")
        workflow.add_edge("build_sql_query", "query_database")
        workflow.add_edge("query_database", "analyze_data")
        workflow.add_edge("analyze_data", "generate_charts")
        workflow.add_edge("generate_charts", "generate_report")
        workflow.add_edge("generate_report", "h2h_decision")
        
        workflow.add_conditional_edges(
            "h2h_decision",
            self.route_h2h_decision,
            {
                "needs_review": "final_answer",  # 실제로는 human reviewer로 가야 함
                "auto": "final_answer"
            }
        )
        
        workflow.add_edge("final_answer", END)
        
        return workflow.compile()
    
    def classify_task_type(self, state: GraphState) -> GraphState:
        """사용자 입력을 분석하여 작업 타입을 분류합니다."""
        user_message = state["messages"][-1].content
        
        system_prompt = """
        사용자의 입력을 분석하여 작업 타입을 분류하세요.
        
        가능한 작업 타입:
        - PerformanceReport: 성과 보고서, 매출 분석, 실적 리포트 관련
        - Other: 기타
        
        응답은 반드시 다음 중 하나여야 합니다: "PerformanceReport" 또는 "Other"
        """
        
        response = self.llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ])
        
        task_type = "PerformanceReport" if "PerformanceReport" in response.content else "Other"
        state["task_type"] = task_type
        
        return state
    
    def parse_client_or_region(self, state: GraphState) -> GraphState:
        """클라이언트나 지역 정보를 파싱합니다."""
        user_message = state["messages"][-1].content
        
        system_prompt = """
        사용자의 요청에서 특정 클라이언트, 제품, 또는 지역 정보를 추출하세요.
        만약 명시적으로 언급되지 않았다면 "전체"로 응답하세요.
        
        예시:
        - "ABC 제품의 매출 현황" -> "ABC"
        - "서울 지역 실적" -> "서울"
        - "전체 매출 보고서" -> "전체"
        """
        
        response = self.llm.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message)
        ])
        
        state["client_or_region"] = response.content.strip()
        return state
    
    def build_sql_query(self, state: GraphState) -> GraphState:
        """SQL 쿼리를 생성합니다."""
        client_or_region = state["client_or_region"]
        
        # 기본 쿼리
        if client_or_region == "전체":
            sql_query = "SELECT * FROM sales_data"
        else:
            # 실제 컬럼명 사용: ID, 품목, 함량
            sql_query = f"SELECT * FROM sales_data WHERE (ID LIKE '%{client_or_region}%' OR 품목 LIKE '%{client_or_region}%' OR 함량 LIKE '%{client_or_region}%')"
        
        state["sql_query"] = sql_query
        return state
    
    def query_database(self, state: GraphState) -> GraphState:
        """데이터베이스에서 데이터를 조회합니다."""
        try:
            conn = sqlite3.connect(self.db_file)
            df = pd.read_sql(state["sql_query"], conn)
            conn.close()
            

            
            state["query_result"] = df
        except Exception as e:
            # 오류 발생 시 빈 DataFrame 반환
            state["query_result"] = pd.DataFrame()
            print(f"데이터베이스 쿼리 오류: {e}")
        
        return state
    
    def analyze_with_pandas(self, state: GraphState) -> GraphState:
        """Pandas를 사용하여 데이터를 분석합니다."""
        df = state["query_result"]
        
        if df.empty:
            state["analysis_result"] = {"error": "데이터가 없습니다."}
            return state
        
        analysis = {
            "총_레코드_수": len(df),
            "컬럼_수": len(df.columns),
            "컬럼명": list(df.columns),
            "기본_통계": {},
            "월별_분석": {}
        }
        
        # 숫자형 컬럼들에 대한 기본 통계
        numeric_columns = df.select_dtypes(include=['number']).columns
        if len(numeric_columns) > 0:
            analysis["기본_통계"] = df[numeric_columns].describe().to_dict()
        
        # 월별 데이터가 있는 경우 분석 (YYYY-MM 형태)
        date_columns = [col for col in df.columns if str(col).startswith(('2019', '2020', '2021', '2022', '2023', '2024')) and '-' in str(col)]
        if date_columns:
            monthly_data = df[date_columns].sum() if len(date_columns) > 0 else {}
            analysis["월별_분석"] = monthly_data.to_dict() if hasattr(monthly_data, 'to_dict') else {}
        
        state["analysis_result"] = analysis
        return state
    
    def generate_charts(self, state: GraphState) -> GraphState:
        """선택적으로 차트를 생성합니다."""
        df = state["query_result"]
        analysis = state["analysis_result"]
        
        if df.empty or "월별_분석" not in analysis or not analysis["월별_분석"]:
            state["chart_path"] = None
            return state
        
        try:
            # 월별 데이터 차트 생성
            monthly_data = analysis["월별_분석"]
            months = list(monthly_data.keys())
            values = list(monthly_data.values())
            
            plt.figure(figsize=(12, 6))
            plt.plot(months, values, marker='o', linewidth=2, markersize=6)
            plt.title('월별 매출 추이', fontsize=16, fontweight='bold')
            plt.xlabel('월', fontsize=12)
            plt.ylabel('매출액', fontsize=12)
            plt.xticks(rotation=45)
            plt.grid(True, alpha=0.3)
            plt.tight_layout()
            
            chart_path = f"chart_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            plt.savefig(chart_path, dpi=300, bbox_inches='tight')
            plt.close()
            
            state["chart_path"] = chart_path
        except Exception as e:
            print(f"차트 생성 오류: {e}")
            state["chart_path"] = None
        
        return state
    
    def generate_report(self, state: GraphState) -> GraphState:
        """LLM을 사용하여 성과 보고서를 생성합니다."""
        analysis = state["analysis_result"]
        client_or_region = state["client_or_region"]
        
        system_prompt = f"""
        다음 분석 결과를 바탕으로 전문적인 성과 보고서를 한국어로 작성하세요.
        
        분석 대상: {client_or_region}
        분석 결과: {json.dumps(analysis, ensure_ascii=False, indent=2)}
        
        보고서는 다음 구조로 작성하세요:
        1. 요약 (Executive Summary)
        2. 주요 지표 분석
        3. 트렌드 분석
        4. 인사이트 및 권장사항
        
        전문적이고 읽기 쉬운 형태로 작성하세요.
        """
        
        response = self.llm.invoke([
            SystemMessage(content=system_prompt)
        ])
        
        state["report"] = response.content
        return state
    
    def h2h_decision(self, state: GraphState) -> GraphState:
        """사람의 검토가 필요한지 결정합니다."""
        analysis = state["analysis_result"]
        
        # 간단한 규칙 기반 결정 (실제로는 더 복잡한 로직 필요)
        needs_review = False
        
        if "error" in analysis:
            needs_review = True
        elif analysis.get("총_레코드_수", 0) == 0:
            needs_review = True
        elif len(analysis.get("월별_분석", {})) == 0:
            needs_review = True
        else:
            needs_review = False
        
        state["needs_human_review"] = needs_review
        return state
    
    def generate_final_answer(self, state: GraphState) -> GraphState:
        """최종 답변을 생성합니다."""
        if state["task_type"] == "PerformanceReport":
            if state.get("needs_human_review", False):
                final_answer = f"성과 보고서가 생성되었지만 사람의 검토가 필요합니다.\n\n{state.get('report', '보고서 생성 중 오류가 발생했습니다.')}"
            else:
                final_answer = state.get("report", "보고서 생성 중 오류가 발생했습니다.")
            
            # 차트가 생성된 경우 경로 포함
            if state.get("chart_path"):
                final_answer += f"\n\n📊 차트가 생성되었습니다: {state['chart_path']}"
        else:
            final_answer = "죄송합니다. 현재는 성과 보고서 생성만 지원합니다."
        
        state["final_answer"] = final_answer
        return state
    
    def route_by_task_type(self, state: GraphState) -> str:
        """작업 타입에 따라 라우팅합니다."""
        return "performance_report" if state["task_type"] == "PerformanceReport" else "other"
    
    def route_h2h_decision(self, state: GraphState) -> str:
        """H2H 결정에 따라 라우팅합니다."""
        return "needs_review" if state["needs_human_review"] else "auto"
    
    def run(self, user_input: str) -> str:
        """시스템을 실행합니다."""
        initial_state = {
            "messages": [HumanMessage(content=user_input)],
            "task_type": "",
            "client_or_region": "",
            "sql_query": "",
            "query_result": pd.DataFrame(),
            "analysis_result": {},
            "chart_path": None,
            "report": "",
            "needs_human_review": False,
            "final_answer": ""
        }
        
        result = self.graph.invoke(initial_state)
        return result["final_answer"]

def main():
    """메인 실행 함수"""
    system = PerformanceReportSystem()
    
    print("🚀 LangGraph 기반 성과 보고서 시스템이 시작되었습니다!")
    print("예시: '전체 매출 현황을 보고서로 만들어주세요'")
    print("종료하려면 'quit' 또는 'exit'를 입력하세요.\n")
    
    while True:
        user_input = input("사용자: ").strip()
        
        if user_input.lower() in ['quit', 'exit', '종료']:
            print("시스템을 종료합니다.")
            break
        
        if not user_input:
            continue
        
        try:
            response = system.run(user_input)
            print(f"\n🤖 AI: {response}\n")
        except Exception as e:
            print(f"❌ 오류가 발생했습니다: {e}\n")

if __name__ == "__main__":
    main() 