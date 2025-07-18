# test_core_memory.py
"""
Core Memory 시스템 테스트 스크립트
"""
import os
from dotenv import load_dotenv
from core_memory_processor import CoreMemoryProcessor

# Load environment variables
load_dotenv()

def test_core_memory():
    """Core Memory 시스템 테스트"""
    
    # Core Memory Processor 초기화
    core_memory = CoreMemoryProcessor(
        api_key=os.getenv("GEMINI_API_KEY"),
        model_name="gemini-2.5-flash",
        core_memory_file="test_core_memory.json"
    )
    
    # 테스트용 long-term memory 데이터
    test_memories = [
        "사용자가 좋아하는 음식은 피자이고, 특히 페퍼로니 피자를 선호한다.",
        "사용자는 오늘 날씨가 좋다고 말했다.",
        "사용자의 이름은 김철수이고, 대학생이다.",
        "사용자는 고양이를 키우고 있으며, 이름은 나비이다.",
        "사용자가 최근 영화 '인셉션'을 봤다고 했다.",
        "사용자는 주말에 등산을 자주 간다고 했다.",
        "사용자의 생일은 3월 15일이다.",
        "사용자는 프로그래밍을 공부하고 있으며, 파이썬을 좋아한다.",
        "사용자가 커피보다 차를 선호한다고 했다.",
        "사용자는 클래식 음악을 좋아한다고 했다."
    ]
    
    print("=== Core Memory 시스템 테스트 ===")
    print(f"테스트 메모리 개수: {len(test_memories)}")
    print("\n테스트 메모리:")
    for i, memory in enumerate(test_memories, 1):
        print(f"{i}. {memory}")
    
    print("\n=== Core Memory 처리 시작 ===")
    
    # Core Memory 처리
    success = core_memory.process_long_term_memories(test_memories)
    
    if success:
        print("\n✅ Core Memory 처리 완료!")
        
        # 결과 확인
        core_memories = core_memory.get_core_memories()
        print(f"\n생성된 Core Memory 개수: {len(core_memories)}")
        
        # Core Memory 요약 출력
        print("\n" + "="*50)
        print(core_memory.get_core_memories_summary())
        
        # 상세 정보 출력
        print("\n=== Core Memory 상세 정보 ===")
        for i, memory in enumerate(core_memories, 1):
            print(f"{i}. {memory['memory_text']}")
            print(f"   중요도: {memory['importance_level']}")
            print(f"   카테고리: {memory['category']}")
            print(f"   생성 시간: {memory['timestamp']}")
            print()
    else:
        print("❌ Core Memory 처리 실패")

if __name__ == "__main__":
    test_core_memory()
