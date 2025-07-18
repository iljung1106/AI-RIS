# AI-RIS / AI-RIS (한국어)

AI-RIS는 Live2D 모델 제어, 실시간 채팅 컨텍스트 관리, TTS/STT 통합, 그리고 지속적인 메모리 시스템을 갖춘 고급 AI 어시스턴트입니다. Google Gemini API를 활용하여 LLM 기반 채팅 및 메모리 요약을 수행하며, 함수 호출 기반의 코어 메모리 추출을 지원합니다.

# AI-RIS

AI-RIS is an advanced AI assistant system featuring Live2D model control, real-time chat context management, TTS/STT integration, and persistent memory systems. It leverages Google Gemini API for LLM-based chat and memory summarization, and supports function-calling for core memory extraction.

## 주요 기능 / Features
- **Live2D 모델 제어**: pyvts를 통해 VTube Studio와 연동하여 실시간 아바타 애니메이션을 지원합니다.
- **채팅 컨텍스트 관리**: AI가 본 채팅과 못 본 채팅을 구분하며, 현재 날짜/시간을 포함한 컨텍스트를 유지합니다.
- **TTS/STT 통합**: 실시간 음성 인식(STT) 및 음성 합성(TTS)을 지원하며, TTS 재생 중 인터럽트 처리가 가능합니다.
- **코어 메모리 시스템**: Gemini API 함수 호출을 통해 요약된 핵심 정보를 `core_memory.json`에 저장합니다.
- **장기 메모리**: 중요한 정보를 `long_term_memory.json`에 영구 저장합니다.
- **커스텀 GUI**: CustomTkinter 기반의 사용자 인터페이스 제공.

- **Live2D Model Control**: Integrates with VTube Studio via pyvts for real-time avatar animation.
- **Chat Context Management**: Distinguishes between seen and unseen chats, maintains context with current date/time.
- **TTS/STT Integration**: Supports real-time speech-to-text and text-to-speech, with interruption handling.
- **Core Memory System**: Persistent, function-calling-based memory summary using Gemini API, stored in `core_memory.json`.
- **Long-Term Memory**: Stores important information in `long_term_memory.json` for persistent recall.
- **Custom GUI**: Built with CustomTkinter for user interaction and control.

## 파일 구조 / File Structure
- `main.py`: 프로그램 실행 진입점 / Entry point for the application
- `app_orchestrator.py`: 스레드, 컨텍스트, 메모리 워커 관리 / Orchestrates threads, context, and memory workers
- `context_manager.py`: AI 컨텍스트 프롬프트 생성 (날짜/시간, 코어 메모리 포함) / Builds context prompts for AI
- `core_memory_processor.py`: Gemini API로 코어 메모리 추출 및 저장 / Extracts and stores core memories
- `long_term_memory.py`: 장기 메모리 저장 및 불러오기 / Handles long-term memory
- `live2d_controller.py`: pyvts로 Live2D 모델 제어 / Controls Live2D model
- `audio_player.py`: TTS 재생 및 인터럽트 관리 / Manages TTS playback
- `gui.py`: CustomTkinter 기반 GUI / CustomTkinter-based GUI
- `requirements.txt`: 파이썬 의존성 / Python dependencies
- `core_memory.json`, `long_term_memory.json`: 메모리 저장 파일 / Persistent memory storage
- `test_core_memory.py`: 코어 메모리 추출 테스트 / Test script for core memory

## 코어 메모리 형식 / Core Memory Format
각 코어 메모리 항목은 다음과 같은 JSON 객체입니다:
- `memory_text`: 중요한 정보의 요약 / Summary of important information
- `importance_level`: 중요도 (`critical`, `high`, `medium`) / Importance level
- `category`: 분류 (예: `user_preference`, `personal_info` 등) / Category
- `timestamp`: 날짜/시간 (`YYYY-MM-DD HH:MM:SS` 형식) / Date/time

예시 / Example:
```json
{
  "memory_text": "사용자가 TTS 음성 속도를 선호함.",
  "importance_level": "high",
  "category": "user_preference",
  "timestamp": "2025-07-18 14:23:01"
}
```

## 설치 및 실행 / Setup & Run
1. 의존성 설치 / Install dependencies:
   ```pwsh
   pip install -r requirements.txt
   ```
2. 프로그램 실행 / Run the application:
   ```pwsh
   python main.py
   ```

## 테스트 / Testing
코어 메모리 추출 테스트 실행 / Run core memory extraction test:
```pwsh
python test_core_memory.py
```

## 라이선스 / License
MIT License

## 저자 / Author
iljung1106

---

### 사용 예시 / Usage Example
- 프로그램을 실행하면 실시간 채팅, TTS/STT, Live2D 모델 제어가 통합되어 동작합니다.
- AI 컨텍스트에는 현재 날짜/시간, 코어 메모리 요약, 채팅 내역이 포함됩니다.
- 코어 메모리와 장기 메모리는 자동으로 저장/불러오기 됩니다.

### 문의 / Contact
- 개선 요청, 버그 신고 등은 GitHub 이슈 또는 이메일로 문의해 주세요.
