# test_interrupt_system.py - 전체 중단 시스템 테스트
import sys
import os
import time
import uuid
from collections import deque
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

class MockGeminiClient:
    def __init__(self):
        self.history = deque()
        
    def add_system_message(self, message):
        print(f"[MockGemini] System message: {message}")
        self.history.append({'role': 'system', 'parts': [message]})
        
    def add_to_history(self, role, text):
        self.history.append({'role': role, 'parts': [text]})
        
    def get_formatted_history(self):
        return "\n".join([f"{msg['role']}: {msg['parts'][0]}" for msg in self.history])
        
    def generate_response(self, context, task_prompt):
        print(f"[MockGemini] Generating response for: {task_prompt}")
        return f"AI 응답: {task_prompt}에 대한 답변입니다."
        
    def refine_stt_text(self, text):
        return text.strip()

def test_interrupt_system():
    print("=== 중단 시스템 테스트 ===")
    
    # Mock 객체들
    gemini_client = MockGeminiClient()
    interrupted_response = None
    current_response_id = None
    
    # 1. 정상 응답 시뮬레이션
    print("\n1. 정상 응답 시뮬레이션")
    response_id = str(uuid.uuid4())[:8]
    current_response_id = response_id
    print(f"응답 ID: {response_id}")
    
    # 2. 중단 시뮬레이션
    print("\n2. 중단 시뮬레이션")
    interrupt_text = "잠깐, 다른 질문이 있어요"
    
    # 중단 정보 저장
    if current_response_id:
        interrupted_response = {
            "response_id": current_response_id,
            "interrupted_by": {"nickname": "사용자", "text": interrupt_text},
            "timestamp": time.time()
        }
        print(f"중단된 응답: {interrupted_response}")
    
    # 3. 중단 컨텍스트 추가
    print("\n3. 중단 컨텍스트 추가")
    if interrupted_response:
        interruption_context = f"[시스템: 이전 응답이 '{interrupted_response['interrupted_by']['nickname']}'의 발언 '{interrupted_response['interrupted_by']['text']}'로 중단되었습니다.]"
        gemini_client.add_system_message(interruption_context)
    
    # 4. 새로운 응답 생성
    print("\n4. 새로운 응답 생성")
    new_response_id = str(uuid.uuid4())[:8]
    current_response_id = new_response_id
    
    new_item = {
        "source": "stt",
        "nickname": "사용자",
        "content": interrupt_text,
        "is_interruption": True,
        "timestamp": time.time()
    }
    
    response = gemini_client.generate_response("컨텍스트", interrupt_text)
    print(f"새로운 응답: {response}")
    
    print("\n5. 대화 히스토리 확인")
    print(gemini_client.get_formatted_history())
    
    print("\n테스트 완료!")

if __name__ == "__main__":
    test_interrupt_system()
