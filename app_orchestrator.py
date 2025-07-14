# app_orchestrator.py
import time
import threading
import queue
import random
from collections import deque
import traceback # Import traceback for detailed error logging

# Local module imports
from STT.realtime_stt import RealTimeSTT
from TTS.gsv_api_client import GPTSoVITSClient
from gemini_api import GeminiAPI
from long_term_memory import LongTermMemory
from CHZZK.chzzk_chat_collector import ChzzkChatScraper
from context_manager import ContextManager
from audio_player import AudioPlayer

class AppOrchestrator:
    """
    Orchestrates all components of the AI Youtuber application.
    """
    def __init__(self, config: dict):
        print("[Orchestrator] Initializing AppOrchestrator...")
        self.config = config
        self.running = threading.Event()
        self.last_interaction_time = time.time()
        
        # Communication & Data Stores
        self.llm_input_queue = queue.Queue()
        self.tts_queue = queue.Queue()
        self.recent_chats = deque(maxlen=config.get("chat", {}).get("max_recent_chats", 20))
        self.barge_in_buffer = deque(maxlen=5) # Buffer for user speech during AI speech
        
        # State variables for GUI
        self.current_status = "Initializing..."
        self.last_full_prompt = ""

        # Core components
        self.audio_player = AudioPlayer()
        self.stt_client = self.tts_client = self.gemini_client = self.long_term_memory = self.chat_collector = self.context_manager = None
        
        # Worker threads
        self.tts_thread = self.idle_chatter_thread = self.chat_collector_thread = self.memory_thread = self.main_loop_thread = None
        print("[Orchestrator] AppOrchestrator initialized.")

    def _update_interaction_time(self):
        self.last_interaction_time = time.time()

    def _stt_callback(self, nickname: str, text: str):
        print(f"[STT Callback] Received text: '{text}'")
        # Barge-in logic: If AI is speaking, buffer the user's speech.
        if self.audio_player.is_playing.is_set():
            print(f"[Barge-in] User spoke while AI was talking. Buffering: '{text}'")
            self.barge_in_buffer.append({"source": "stt", "nickname": nickname, "content": text})
            self.current_status = f"Barge-in: {text[:30]}..."
            return

        self.current_status = f"User said: {text}"
        self.llm_input_queue.put({"source": "stt", "nickname": nickname, "content": text})
        self._update_interaction_time()
        print(f"[STT Callback] Input added to LLM queue: {text}")

    def _chat_callback(self, chat: dict):
        print(f"[Chat Callback] Received chat: [{chat['user']}] {chat['message']}")
        self.recent_chats.append(f"[{chat['user']}] {chat['message']}")
        if random.random() < self.config.get("chat", {}).get("response_chance", 0.1):
            if self.audio_player.is_playing.is_set():
                print("[Chat Callback] AI is speaking, ignoring chat for response.")
                return
            self.current_status = f"Responding to chat from {chat['user']}"
            self.llm_input_queue.put({"source": "chat", "nickname": chat['user'], "content": chat['message']})
            self._update_interaction_time()
            print(f"[Chat Callback] Chat added to LLM queue: {chat['message']}")

    def _initialize_components(self):
        print("[Orchestrator] Initializing components...")
        self.current_status = "Initializing components..."
        llm_cfg = self.config.get("llm", {})
        if llm_cfg.get("provider") == "gemini":
            print("[Orchestrator] Initializing GeminiAPI...")
            self.gemini_client = GeminiAPI(api_key=llm_cfg.get("api_key"), model_name=llm_cfg.get("model"), max_history_length=llm_cfg.get("max_history", 20))
        print("[Orchestrator] Initializing LongTermMemory...")
        self.long_term_memory = LongTermMemory(file_path=llm_cfg.get("memory_path", "long_term_memory.json"))
        print("[Orchestrator] Initializing ContextManager...")
        self.context_manager = ContextManager(self.config, self.long_term_memory, self.gemini_client)
        tts_cfg = self.config.get("tts", {})
        print("[Orchestrator] Initializing GPTSoVITSClient...")
        self.tts_client = GPTSoVITSClient(host=tts_cfg.get("host", "127.0.0.1"), port=tts_cfg.get("port", 9880))
        stt_cfg = self.config.get("stt", {})
        if stt_cfg.get("enabled", False):
            print("[Orchestrator] Initializing RealTimeSTT...")
            self.stt_client = RealTimeSTT(device_config=stt_cfg.get("devices", {}), on_text_transcribed=self._stt_callback, **stt_cfg.get("params", {}))
        chat_cfg = self.config.get("chat", {})
        if chat_cfg.get("enabled", False):
            print("[Orchestrator] Initializing ChzzkChatScraper...")
            self.chat_collector = ChzzkChatScraper(chat_cfg.get("widget_url"))
        self.current_status = "Initialization complete. Waiting for input."
        print("[Orchestrator] All components initialized.")

    def _tts_worker(self):
        print("[TTS Worker] Starting TTS worker thread.")
        while self.running.is_set() or not self.tts_queue.empty():
            try:
                task = self.tts_queue.get(timeout=1)
                self.current_status = f"Speaking: '{task['text'][:40]}...'"
                self._update_interaction_time()
                tts_cfg = self.config.get("tts", {})
                print(f"[TTS Worker] Requesting TTS for: {task['text'][:30]}...")
                audio_stream = self.tts_client.tts(text=task['text'], **tts_cfg.get("params", {}))
                if audio_stream:
                    print("[TTS Worker] Playing audio stream.")
                    self.audio_player.play_stream(audio_stream)
                self.tts_queue.task_done()
                self.current_status = "Finished speaking. Waiting for input."
                print("[TTS Worker] Audio playback finished.")
            except queue.Empty: 
                continue
            except Exception as e:
                print(f"[TTS Worker Error] An error occurred: {e}")
                traceback.print_exc() # Print full traceback

    def _idle_chatter_worker(self):
        print("[Idle Chatter Worker] Starting idle chatter thread.")
        idle_cfg = self.config.get("idle_chatter", {})
        if not idle_cfg.get("enabled", False): 
            print("[Idle Chatter Worker] Idle chatter is disabled.")
            return
        min_idle, max_idle = idle_cfg.get("min_interval_s", 30), idle_cfg.get("max_interval_s", 90)
        while self.running.is_set():
            current_idle_time = time.time() - self.last_interaction_time
            if current_idle_time > random.uniform(min_idle, max_idle):
                if not self.audio_player.is_playing.is_set() and self.llm_input_queue.empty():
                    self.current_status = "Idle. Thinking of something to say..."
                    self.llm_input_queue.put({"source": "idle"})
                    self._update_interaction_time()
                    print("[Idle Chatter Worker] Triggered idle talk.")
            time.sleep(5)
        print("[Idle Chatter Worker] Idle chatter thread stopped.")

    def _chat_collector_worker(self):
        print("[Chat Collector Worker] Starting chat collector thread.")
        if not self.chat_collector: 
            print("[Chat Collector Worker] Chat collector is not initialized.")
            return
        last_chats = []
        while self.running.is_set():
            try:
                current_chats = self.chat_collector.get_latest_chats(limit=20)
                new_chats = [chat for chat in current_chats if chat not in last_chats]
                if new_chats:
                    print(f"[Chat Collector Worker] Found {len(new_chats)} new chats.")
                for chat in reversed(new_chats): 
                    self._chat_callback(chat)
                last_chats = current_chats
                time.sleep(self.config.get("chat", {}).get("poll_interval_s", 2))
            except Exception as e:
                print(f"[Chat Collector Worker Error] An error occurred: {e}")
                traceback.print_exc() # Print full traceback
                time.sleep(10) # Wait longer on error to prevent rapid error looping
        print("[Chat Collector Worker] Chat collector thread stopped.")

    def _memory_worker(self):
        print("[Memory Worker] Starting memory worker thread.")
        llm_cfg = self.config.get("llm", {})
        if not llm_cfg.get("enable_memory_summarization", False): 
            print("[Memory Worker] Memory summarization is disabled.")
            return
        interval = llm_cfg.get("memory_summarize_interval_s", 300)
        while self.running.is_set():
            time.sleep(interval)
            if self.gemini_client and self.gemini_client.history:
                self.current_status = "Summarizing conversation for long-term memory..."
                print("[Memory Worker] Summarizing recent conversation for long-term memory...")
                history_text = self.gemini_client.get_formatted_history()
                summary = self.gemini_client.summarize_for_memory(history_text)
                if summary: 
                    self.long_term_memory.add_memory(summary)
                    print(f"[Memory Worker] Added summary to memory: {summary[:50]}...")
                self.current_status = "Waiting for input."
        print("[Memory Worker] Memory worker thread stopped.")

    def run_main_loop(self):
        print("[Main Loop] Starting main logic loop thread.")
        while self.running.is_set():
            try:
                # 1. Wait until AI is NOT speaking.
                # This loop ensures we only proceed when the audio player is idle.
                while self.audio_player.is_playing.is_set():
                    time.sleep(0.1) # Small delay to prevent busy-waiting
                    # Inputs will accumulate in queues/buffers while AI is speaking.

                # 2. AI is not speaking. Now, collect all pending inputs.
                item_to_process = None
                all_pending_items = []

                # Drain all items from the regular LLM input queue
                while not self.llm_input_queue.empty():
                    try:
                        item = self.llm_input_queue.get_nowait()
                        all_pending_items.append(item)
                        self.llm_input_queue.task_done() # Mark as done as we're consuming it
                    except queue.Empty:
                        break # Should not happen with empty() check, but good practice

                # Drain all items from the barge-in buffer
                while self.barge_in_buffer:
                    all_pending_items.append(self.barge_in_buffer.popleft()) # popleft() to maintain order if needed, but we only care about the last one

                if all_pending_items:
                    # 3. Take only the very last item (most recent) from all collected inputs.
                    item_to_process = all_pending_items[-1]
                    print(f"[Main Loop] Processed {len(all_pending_items)} pending inputs. Prioritizing latest: {item_to_process['content'][:30]}...")
                else:
                    # If no pending items, wait for a new one (blocking call).
                    # This is the normal state when AI is idle and waiting for new input.
                    item_to_process = self.llm_input_queue.get(timeout=1) 
                    content_preview = item_to_process.get('content', str(item_to_process))[:30]
                    print(f"[Main Loop] No pending inputs, waiting for new. Received: {content_preview}...")

                # 4. Now process the selected item_to_process
                source = item_to_process.get('source', 'unknown')
                content = item_to_process.get('content', str(item_to_process))
                self.current_status = f"Thinking about response for {source}... (Input: {content[:20]}...)"
                print(f"[Main Loop] Processing input from {source}.")
                if self.context_manager and self.gemini_client:
                    full_prompt, task_prompt = self.context_manager.build_prompt(item_to_process, list(self.recent_chats))
                    self.last_full_prompt = full_prompt
                    print(f"[Main Loop] Built prompt for LLM. Task: {task_prompt[:50]}...")
                    response_text = self.gemini_client.generate_response(full_prompt, task_prompt)
                    print(f"[Main Loop] Received response from LLM: {response_text[:50]}...")
                    if response_text: 
                        self.tts_queue.put({"text": response_text})
                        print(f"[Main Loop] Response added to TTS queue.")
                self.llm_input_queue.task_done()
                self.current_status = "Waiting for input."

            except queue.Empty: 
                # This is expected when no input is available after timeout, or if all_pending_items was empty
                continue
            except Exception as e:
                print(f"[Main Loop Error] An error occurred: {e}")
                traceback.print_exc() 
        print("[Main Loop] Main logic loop thread stopped.")

    def start(self):
        print("[Orchestrator] Starting all orchestrator threads...")
        if self.running.is_set(): 
            print("[Orchestrator] Orchestrator is already running.")
            return
        self.running.set()
        self._initialize_components()
        if self.stt_client: self.stt_client.start()
        
        self.main_loop_thread = threading.Thread(target=self.run_main_loop, daemon=True)
        self.tts_thread = threading.Thread(target=self._tts_worker, daemon=True)
        self.idle_chatter_thread = threading.Thread(target=self._idle_chatter_worker, daemon=True)
        self.chat_collector_thread = threading.Thread(target=self._chat_collector_worker, daemon=True)
        self.memory_thread = threading.Thread(target=self._memory_worker, daemon=True)
        
        self.main_loop_thread.start()
        self.tts_thread.start()
        self.idle_chatter_thread.start()
        self.chat_collector_thread.start()
        self.memory_thread.start()
        
        print("[Orchestrator] All orchestrator threads started.")
        print("AI Youtuber application orchestrated and started successfully.")

    def stop(self):
        print("[Orchestrator] Stopping AI Youtuber orchestrator...")
        if not self.running.is_set(): 
            print("[Orchestrator] Orchestrator is not running.")
            return
        self.running.clear()
        
        if self.stt_client: self.stt_client.stop()
        if self.chat_collector: self.chat_collector.close()
        
        threads = [self.main_loop_thread, self.tts_thread, self.idle_chatter_thread, self.chat_collector_thread, self.memory_thread]
        for t in threads:
            if t and t.is_alive(): # Check if thread exists and is alive before joining
                print(f"[Orchestrator] Joining thread: {t.name}")
                t.join(timeout=5) # Give threads a chance to finish
                if t.is_alive():
                    print(f"[Orchestrator] Warning: Thread {t.name} did not terminate gracefully.")
        
        self.audio_player.terminate()
        print("[Orchestrator] AI Youtuber orchestrator stopped.")
