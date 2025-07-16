# main.py
import customtkinter as ctk # Changed from tkinter as tk
import threading
from app_orchestrator import AppOrchestrator
from gui import AIYoutuberGUI

# --- Configuration ---
APP_CONFIG = {
    "stt": {
        "enabled": True,
        "devices": {0: {"nickname": "한가운데(voice conversation)", "amplification": 1.0}},
        "params": {
            "model_size": "iic/SenseVoiceSmall", "language": "auto",
            "silence_duration_s": 0.5, "vad_threshold": 0.01
        }
    },
    "tts": {
        "enabled": True, "host": "127.0.0.1", "port": 9880,
        "params": {
            "ref_audio_path": "C:\Works\projects\AIRIS\SampleVoices\yangaji.mp3",
            "prompt_text": "첫번째 사진입니다. 여러분은 어떤 것을 보고 웅장하다 생각했는지 한 가지만 써 보세요.",
            "prompt_lang": "ko", "text_lang": "ko", "streaming_mode": True
        }
    },
    "chat": {
        "enabled": True,
        "widget_url": "https://chzzk.naver.com/chat/aa954e33851f4ecda45ff964305ed59d",
        "poll_interval_s": 2, "max_recent_chats": 20, "response_chance": 0.3
    },
    "llm": {
        "provider": "gemini",
        "api_key": "AIzaSyAGjuJurM_H95siusSx5xcERAvDefCFaKk",
        "model": "gemini-2.5-flash",
        "max_history": 50, "memory_path": "long_term_memory.json",
        "enable_memory_summarization": True, "memory_summarize_interval_s": 300,
        "persona_prompt": "Your name is 아이리스, a witty and friendly AI virtual YouTuber. You are live-streaming. Keep your responses in Korean, conversational, and concise (usually 1-2 sentences). 반말을 사용하세요. 방송중이란 걸 잊지 마세요. 한국 15살 여자애처럼 말하세요. 새로운 채팅이나 이야기를 진행하는 사람이 없으면 혼자서 이런저런 이야기나 썰을 풀고 정보를 전달하며 흥미를 돋구세요. 채팅에 대해 가끔은 응답하세요.",
        "user_prompt_template": "A viewer named '{nickname}' chatted: '{user_input}'",
        "idle_prompt": "The stream has been quiet. Say something to re-engage the audience."
    },
    "idle_chatter": {
        "enabled": True, "min_interval_s": 30, "max_interval_s": 60
    }
}

def main():
    """
    Main function to launch the AI Youtuber application.
    It starts the backend orchestrator in a separate thread and then launches the GUI.
    """
    print("==================================================")
    print("      AI Virtual Youtuber Prototype")
    print("==================================================")
    print("⚠️ Make sure the GPT-SoVITS API server is running.")
    print("⚠️ Make sure you have set your Gemini API key and Chzzk URL.")
    print("--------------------------------------------------")

    # 1. Initialize the orchestrator
    orchestrator = AppOrchestrator(APP_CONFIG)

    # 2. Start the orchestrator's components in a background thread
    orchestrator_thread = threading.Thread(target=orchestrator.start, daemon=True)
    orchestrator_thread.start()

    # 3. Set up and run the GUI in the main thread
    # AIYoutuberGUI is now the main window itself, inheriting from ctk.CTk
    app = AIYoutuberGUI(orchestrator) # Pass only orchestrator

    def on_closing():
        print("\n[Main] GUI closed. Shutting down...")
        orchestrator.stop()
        app.destroy() # Destroy the app instance

    app.protocol("WM_DELETE_WINDOW", on_closing)
    
    try:
        app.mainloop()
    except KeyboardInterrupt:
        print("\n[Main] Keyboard interrupt received. Shutting down...")
        on_closing()

if __name__ == "__main__":
    main()
