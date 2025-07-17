# app_orchestrator.py
import time
import threading
import queue
import random
from collections import deque
import traceback # Import traceback for detailed error logging
import asyncio # Import asyncio for running coroutines in threads

# Local module imports
from STT.realtime_stt import RealTimeSTT
from TTS.gsv_api_client import GPTSoVITSClient
from gemini_api import GeminiAPI
from long_term_memory import LongTermMemory
from core_memory_processor import CoreMemoryProcessor
from CHZZK.chzzk_chat_collector import ChzzkChatScraper
from context_manager import ContextManager
from audio_player import AudioPlayer
from live2d_controller import Live2DController # Live2D 컨트롤러 임포트

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
        self.interrupted_response = None  # Store interrupted response info
        self.current_response_id = None  # Track current response for interruption
        
        # State variables for GUI
        self.current_status = "Initializing..."
        self.last_full_prompt = ""

        # Core components
        self.live2d_controller = None
        if self.config.get("live2d", {}).get("enabled", False):
            self.live2d_controller = Live2DController()

        self.audio_player = AudioPlayer(on_volume_update=self.on_audio_volume_update)
        # Set default output device if available
        try:
            output_devices = AudioPlayer.get_available_devices()
            if output_devices:
                self.audio_player.set_output_device(output_devices[0]['id'])
                print(f"[Orchestrator] Set default output device: {output_devices[0]['name']}")
        except Exception as e:
            print(f"[Orchestrator] Warning: Could not set default output device: {e}")
            
        self.stt_client = self.tts_client = self.gemini_client = self.long_term_memory = self.core_memory_processor = self.chat_collector = self.context_manager = None
        
        # Worker threads
        self.tts_thread = self.idle_chatter_thread = self.chat_collector_thread = self.memory_thread = self.main_loop_thread = None
        print("[Orchestrator] AppOrchestrator initialized.")

    def on_audio_volume_update(self, volume: float):
        """오디오 플레이어로부터 볼륨 값을 받아 Live2D 컨트롤러에 전달합니다."""
        if self.live2d_controller and self.live2d_controller.is_connected:
            # 비동기 함수를 스레드 안전하게 호출
            asyncio.run_coroutine_threadsafe(
                self.live2d_controller.set_mouth_open(volume),
                self.live2d_controller.loop
            )

    def _update_interaction_time(self):
        self.last_interaction_time = time.time()

    def _stt_callback(self, nickname: str, text: str):
        """Handle STT callback with robust error handling."""
        try:
            print(f"[STT Callback] Received raw text: '{text}'")
            
            # Check if we're in a valid state
            if not self.running.is_set():
                print("[STT Callback] Orchestrator is not running, ignoring callback")
                return
            
            # Interrupt TTS if AI is currently speaking
            if self.audio_player and self.audio_player.is_playing.is_set():
                try:
                    print(f"[Interrupt] User spoke while AI was talking. Interrupting: '{text}'")
                    
                    # Stop current audio playback
                    self.audio_player.stop()
                    
                    # Store interrupted response info
                    if self.current_response_id:
                        self.interrupted_response = {
                            "response_id": self.current_response_id,
                            "interrupted_by": {"nickname": nickname, "text": text},
                            "timestamp": time.time()
                        }
                        print(f"[Interrupt] Stored interrupted response: {self.current_response_id}")
                    
                    # Clear TTS queue to prevent queued speech
                    cleared_count = 0
                    while not self.tts_queue.empty():
                        try:
                            self.tts_queue.get_nowait()
                            cleared_count += 1
                        except queue.Empty:
                            break
                        except Exception as e:
                            print(f"[Interrupt] Error clearing TTS queue: {e}")
                            break
                    
                    if cleared_count > 0:
                        print(f"[Interrupt] Cleared {cleared_count} queued TTS tasks")
                    
                    # Clear LLM input queue except for the most recent items
                    try:
                        queued_items = []
                        while not self.llm_input_queue.empty():
                            try:
                                queued_items.append(self.llm_input_queue.get_nowait())
                            except queue.Empty:
                                break
                        
                        # Only keep the most recent 2 items to avoid processing outdated requests
                        recent_items = queued_items[-2:] if len(queued_items) > 2 else queued_items
                        for item in recent_items:
                            self.llm_input_queue.put(item)
                        
                        if len(queued_items) > len(recent_items):
                            print(f"[Interrupt] Cleared {len(queued_items) - len(recent_items)} outdated LLM requests")
                    
                    except Exception as e:
                        print(f"[Interrupt] Error clearing LLM queue: {e}")
                    
                    self.current_status = f"Interrupted by {nickname}: {text[:30]}..."
                    
                    # Add interruption info to conversation context
                    try:
                        if self.gemini_client:
                            interruption_context = f"[시스템: AI 응답이 사용자 '{nickname}'의 발언 '{text}'로 인해 중단되었습니다.]"
                            self.gemini_client.add_system_message(interruption_context)
                    except Exception as e:
                        print(f"[Interrupt] Error adding interruption context: {e}")
                        
                except Exception as e:
                    print(f"[STT Callback] Error during interruption handling: {e}")
                    self.current_status = f"Interrupt error: {e}"
            
            # Process the user's speech (whether it's an interruption or normal input)
            try:
                self.current_status = f"Processing: {text[:30]}..."
                
                # Refine text if gemini client is available
                if self.gemini_client:
                    try:
                        refined_text = self.gemini_client.refine_stt_text(text)
                    except Exception as e:
                        print(f"[STT Callback] Error refining text: {e}")
                        refined_text = text
                else:
                    refined_text = text

                self.current_status = f"User said: {refined_text}"
                
                # Add to LLM queue with high priority if it's an interruption
                llm_item = {
                    "source": "stt", 
                    "nickname": nickname, 
                    "content": refined_text,
                    "is_interruption": self.interrupted_response is not None,
                    "timestamp": time.time()
                }
                
                self.llm_input_queue.put(llm_item)
                self._update_interaction_time()
                print(f"[STT Callback] Added to LLM queue: {refined_text} (interruption: {llm_item['is_interruption']})")
                
            except Exception as e:
                print(f"[STT Callback] Error processing speech: {e}")
                self.current_status = f"Speech processing error: {e}"
                
        except Exception as e:
            print(f"[STT Callback] Critical error in callback: {e}")
            traceback.print_exc()
            self.current_status = f"Critical STT error: {e}"


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
        # 1. Initialize core components based on config
        print("[Orchestrator] Initializing components...")
        self.current_status = "Initializing components..."
        
        # Start Live2D Controller if enabled
        if self.live2d_controller:
            print("[Orchestrator] Starting Live2D Controller...")
            self.live2d_controller.start()

        # Initialize STT
        if self.config.get("stt", {}).get("enabled", False):
            print("[Orchestrator] Initializing RealTimeSTT...")
            self.stt_client = RealTimeSTT(device_config=self.config.get("stt", {}).get("devices", {}), on_text_transcribed=self._stt_callback, **self.config.get("stt", {}).get("params", {}))
        
        # Initialize GeminiAPI
        llm_cfg = self.config.get("llm", {})
        if llm_cfg.get("provider") == "gemini":
            print("[Orchestrator] Initializing GeminiAPI...")
            self.gemini_client = GeminiAPI(api_key=llm_cfg.get("api_key"), model_name=llm_cfg.get("model"), max_history_length=llm_cfg.get("max_history", 20))
        
        # Initialize LongTermMemory
        print("[Orchestrator] Initializing LongTermMemory...")
        self.long_term_memory = LongTermMemory(file_path=llm_cfg.get("memory_path", "long_term_memory.json"))
        
        # Initialize CoreMemoryProcessor
        print("[Orchestrator] Initializing CoreMemoryProcessor...")
        self.core_memory_processor = CoreMemoryProcessor(
            api_key=llm_cfg.get("api_key"),
            model_name=llm_cfg.get("model"),
            core_memory_file=llm_cfg.get("core_memory_path", "core_memory.json")
        )
        
        # Initialize ContextManager
        print("[Orchestrator] Initializing ContextManager...")
        self.context_manager = ContextManager(self.config, self.long_term_memory, self.gemini_client, self.core_memory_processor)
        
        # Initialize GPTSoVITSClient
        tts_cfg = self.config.get("tts", {})
        print("[Orchestrator] Initializing GPTSoVITSClient...")
        self.tts_client = GPTSoVITSClient(host=tts_cfg.get("host", "127.0.0.1"), port=tts_cfg.get("port", 9880))
        
        # Initialize ChatzzkChatScraper
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
                
                # Validate task structure
                if not isinstance(task, dict) or 'text' not in task:
                    print(f"[TTS Worker] Invalid task structure: {task}")
                    self.tts_queue.task_done()
                    continue
                
                response_id = task.get('response_id', 'unknown')
                text = task['text']
                
                # Check if this response is still current
                if response_id != self.current_response_id:
                    print(f"[TTS Worker] Skipping outdated response {response_id}")
                    self.tts_queue.task_done()
                    continue
                
                # Check if we're still running
                if not self.running.is_set():
                    print("[TTS Worker] Orchestrator stopped, exiting")
                    break
                
                self.current_status = f"Speaking: '{text[:40]}...'"
                self._update_interaction_time()
                
                try:
                    tts_cfg = self.config.get("tts", {})
                    print(f"[TTS Worker] Requesting TTS for response {response_id}: {text[:30]}...")
                    
                    # Check if we should skip this TTS due to interruption
                    if self.current_response_id == response_id and self.tts_client:
                        try:
                            audio_stream = self.tts_client.tts(text=text, **tts_cfg.get("params", {}))
                            if audio_stream and self.current_response_id == response_id:
                                print(f"[TTS Worker] Playing audio stream for response {response_id}")
                                
                                # Check if audio player is available
                                if self.audio_player:
                                    self.audio_player.play_stream(audio_stream)
                                else:
                                    print("[TTS Worker] Audio player not available")
                            else:
                                print(f"[TTS Worker] No audio stream or response {response_id} was interrupted")
                        except Exception as e:
                            print(f"[TTS Worker] Error during TTS/audio processing: {e}")
                            traceback.print_exc()
                    else:
                        print(f"[TTS Worker] Skipping TTS for response {response_id} due to interruption or missing client")
                
                except Exception as e:
                    print(f"[TTS Worker] Error in TTS processing: {e}")
                    traceback.print_exc()
                
                self.tts_queue.task_done()
                
                # Only update status if this response is still current
                if self.current_response_id == response_id:
                    self.current_status = "Finished speaking. Waiting for input."
                    self.current_response_id = None  # Clear after completion
                    print(f"[TTS Worker] Audio playback finished for response {response_id}")
                    
            except queue.Empty: 
                continue
            except Exception as e:
                print(f"[TTS Worker Error] An error occurred: {e}")
                traceback.print_exc()
                self.current_status = "TTS error occurred"
                
        print("[TTS Worker] TTS worker thread stopped.")

    def _idle_chatter_worker(self):
        print("[Idle Chatter Worker] Starting idle chatter thread.")
        idle_cfg = self.config.get("idle_chatter", {})
        if not idle_cfg.get("enabled", False): 
            print("[Idle Chatter Worker] Idle chatter is disabled.")
            return
        min_idle, max_idle = idle_cfg.get("min_interval_s", 30), idle_cfg.get("max_interval_s", 90)
        while self.running.is_set():
            # TTS가 재생 중일 때는 유휴 시간 카운트를 하지 않고, 마지막 상호작용 시간을 계속 갱신합니다.
            if self.audio_player and self.audio_player.is_playing.is_set():
                self._update_interaction_time()
                time.sleep(1)  # 1초마다 체크
                continue

            current_idle_time = time.time() - self.last_interaction_time
            if current_idle_time > random.uniform(min_idle, max_idle):
                # 오디오가 재생 중이지 않고, 처리할 다른 입력이 없을 때만 자율 발화 실행
                if self.llm_input_queue.empty():
                    self.current_status = "Idle. Thinking of something to say..."
                    self.llm_input_queue.put({"source": "idle"})
                    self._update_interaction_time()
                    print("[Idle Chatter Worker] Triggered idle talk.")
            
            time.sleep(5) # 5초마다 유휴 상태 체크
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

    def _core_memory_worker(self):
        """
        Core memory worker that processes long-term memories to extract core memories
        using Gemini API with function calling.
        """
        print("[Core Memory Worker] Starting core memory worker thread.")
        llm_cfg = self.config.get("llm", {})
        if not llm_cfg.get("enable_core_memory_processing", False):
            print("[Core Memory Worker] Core memory processing is disabled.")
            return
        
        # Core memory processing interval (default: 30 minutes)
        core_memory_interval = llm_cfg.get("core_memory_interval_s", 1800)
        
        while self.running.is_set():
            time.sleep(core_memory_interval)
            
            if self.long_term_memory and self.core_memory_processor:
                try:
                    self.current_status = "Processing core memories..."
                    print("[Core Memory Worker] Processing long-term memories for core memory extraction...")
                    
                    # Get all long-term memories
                    long_term_memories = self.long_term_memory.get_all_memories()
                    
                    if long_term_memories:
                        # Process memories to extract core memories
                        success = self.core_memory_processor.process_long_term_memories(long_term_memories)
                        
                        if success:
                            core_memories_count = len(self.core_memory_processor.get_core_memories())
                            print(f"[Core Memory Worker] Core memory processing completed. Total core memories: {core_memories_count}")
                        else:
                            print("[Core Memory Worker] Core memory processing failed.")
                    else:
                        print("[Core Memory Worker] No long-term memories to process.")
                    
                    self.current_status = "Waiting for input."
                    
                except Exception as e:
                    print(f"[Core Memory Worker] Error in core memory processing: {e}")
                    traceback.print_exc()
                    self.current_status = "Error in core memory processing."
        
        print("[Core Memory Worker] Core memory worker thread stopped.")

    def run_main_loop(self):
        print("[Main Loop] Starting main logic loop thread.")
        while self.running.is_set():
            try:
                # Wait for current audio to finish
                while self.audio_player and self.audio_player.is_playing.is_set():
                    if not self.running.is_set():
                        break
                    time.sleep(0.1) 

                if not self.running.is_set():
                    break

                item_to_process = None
                all_pending_items = []

                # Collect all pending items from the queue
                while not self.llm_input_queue.empty():
                    try:
                        item = self.llm_input_queue.get_nowait()
                        all_pending_items.append(item)
                        self.llm_input_queue.task_done()
                    except queue.Empty:
                        break
                    except Exception as e:
                        print(f"[Main Loop] Error getting item from queue: {e}")
                        break

                if all_pending_items:
                    try:
                        # Sort items by timestamp to process most recent first
                        all_pending_items.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
                        
                        # Find the most recent item, prioritizing interruptions
                        interruption_items = [item for item in all_pending_items if item.get('is_interruption', False)]
                        if interruption_items:
                            item_to_process = interruption_items[0]  # Most recent interruption
                            print(f"[Main Loop] Processing interruption: {item_to_process.get('content', '')[:30]}...")
                        else:
                            item_to_process = all_pending_items[0]  # Most recent item
                            print(f"[Main Loop] Processing most recent item: {item_to_process.get('content', '')[:30]}...")
                        
                        # Log skipped items
                        skipped_count = len(all_pending_items) - 1
                        if skipped_count > 0:
                            print(f"[Main Loop] Skipped {skipped_count} older items")
                    except Exception as e:
                        print(f"[Main Loop] Error processing pending items: {e}")
                        continue

                if item_to_process and self.running.is_set():
                    try:
                        # Generate response ID for tracking
                        import uuid
                        response_id = str(uuid.uuid4())[:8]
                        self.current_response_id = response_id
                        
                        # Handle interruption context
                        if item_to_process.get('is_interruption', False) and self.interrupted_response:
                            print(f"[Main Loop] Handling interruption for response {response_id}")
                            interruption_info = self.interrupted_response
                            self.interrupted_response = None  # Clear after processing
                            
                            # Add context about the interruption
                            try:
                                if self.gemini_client:
                                    context_msg = f"[시스템: 이전 응답이 '{interruption_info['interrupted_by']['nickname']}'의 발언으로 중단되었습니다. 이제 새로운 질문에 답변하세요.]"
                                    self.gemini_client.add_system_message(context_msg)
                            except Exception as e:
                                print(f"[Main Loop] Error adding interruption context: {e}")
                        
                        # Process the item
                        self.current_status = f"Generating response to: {item_to_process.get('content', '')[:30]}..."
                        
                        # Build context using context_manager
                        try:
                            if self.context_manager:
                                # TTS 실행 직전의 채팅을 저장
                                if not hasattr(self, 'seen_chats'):
                                    self.seen_chats = []
                                
                                # 현재 채팅 리스트를 previous_chats와 recent_chats로 분할
                                previous_chats = list(self.seen_chats)
                                
                                # seen_chats 이후 들어온 새로운 채팅을 recent_chats로 계산
                                current_chats = list(self.recent_chats)
                                if len(current_chats) > len(previous_chats):
                                    # 새로운 채팅이 있으면 그것을 recent_chats로 설정
                                    recent_chats = current_chats[len(previous_chats):]
                                else:
                                    # 새로운 채팅이 없으면 빈 리스트
                                    recent_chats = []
                                
                                # TTS 실행 직전(응답 생성 직전)에 seen_chats를 갱신
                                self.seen_chats = current_chats
                                
                                context = self.context_manager.build_context(
                                    item_to_process,
                                    previous_chats=previous_chats,
                                    recent_chats=recent_chats
                                )
                                self.last_full_prompt = context
                                print(f"[Main Loop] Generating response for: {item_to_process.get('content', '')[:30]}...")
                                print(f"[Main Loop] Previous chats: {len(previous_chats)}, Recent chats: {len(recent_chats)}")
                                
                                # Generate response using gemini_client
                                if self.gemini_client:
                                    task_prompt = self.context_manager._get_task_prompt(item_to_process)
                                    response = self.gemini_client.generate_response(context, task_prompt)
                                else:
                                    response = "LLM client not available"
                            else:
                                response = "Context manager not available"
                        except Exception as e:
                            print(f"[Main Loop] Error generating response: {e}")
                            response = f"Error generating response: {e}"
                        
                        if response and self.running.is_set() and self.current_response_id == response_id:
                            try:
                                # Queue for TTS
                                self.tts_queue.put({"text": response, "response_id": response_id})
                                print(f"[Main Loop] Response queued for TTS: {response[:50]}...")
                            except Exception as e:
                                print(f"[Main Loop] Error queuing TTS: {e}")
                        else:
                            print("[Main Loop] No response generated or response interrupted")
                            self.current_response_id = None
                            
                    except Exception as e:
                        print(f"[Main Loop] Error processing item: {e}")
                        traceback.print_exc()
                        self.current_response_id = None
                
                time.sleep(0.1)
                
            except Exception as e:
                print(f"[Main Loop Error] Critical error in main loop: {e}")
                traceback.print_exc()
                time.sleep(1)
        
        print("[Main Loop] Main loop thread stopped.")

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
        self.core_memory_thread = threading.Thread(target=self._core_memory_worker, daemon=True)
        
        self.main_loop_thread.start()
        self.tts_thread.start()
        self.idle_chatter_thread.start()
        self.chat_collector_thread.start()
        self.memory_thread.start()
        self.core_memory_thread.start()
        
        print("[Orchestrator] All orchestrator threads started.")
        print("AI Youtuber application orchestrated and started successfully.")

    def stop(self):
        print("[Orchestrator] Stopping AI Youtuber orchestrator...")
        if not self.running.is_set(): 
            print("[Orchestrator] Orchestrator is not running.")
            return
        self.running.clear()
        print("[Orchestrator] Stopping components...")
        self.current_status = "Shutting down..."

        # Stop Live2D Controller
        if self.live2d_controller:
            print("[Orchestrator] Stopping Live2D Controller...")
            self.live2d_controller.stop()

        # Stop STT clients
        if self.stt_client:
            print("[Orchestrator] Stopping STT clients...")
            self.stt_client.stop()
        
        # Stop Chat Collector
        if self.chat_collector:
            print("[Orchestrator] Stopping Chat Collector...")
            self.chat_collector.close()
        
        threads = [self.main_loop_thread, self.tts_thread, self.idle_chatter_thread, self.chat_collector_thread, self.memory_thread]
        for t in threads:
            if t and t.is_alive():
                print(f"[Orchestrator] Joining thread: {t.name}")
                t.join(timeout=5)
                if t.is_alive():
                    print(f"[Orchestrator] Warning: Thread {t.name} did not terminate gracefully.")
        
        self.audio_player.terminate()
        print("[Orchestrator] AI Youtuber orchestrator stopped.")

    def change_input_devices(self, devices_config: dict):
        """Change the input devices for STT (supports multiple devices)."""
        print(f"[Orchestrator] Changing input devices to: {devices_config}")
        
        try:
            # Stop current STT if running
            if self.stt_client and self.stt_client.running:
                print("[Orchestrator] Stopping current STT...")
                self.stt_client.stop()
            
            # Update configuration
            self.config["stt"]["devices"] = devices_config
            
            # Restart STT with new devices
            if self.config.get("stt", {}).get("enabled", False) and devices_config:
                print("[Orchestrator] Starting STT with new devices...")
                self.stt_client = RealTimeSTT(
                    device_config=devices_config,
                    on_text_transcribed=self._stt_callback,
                    **self.config["stt"].get("params", {})
                )
                self.stt_client.start()
                
                device_names = [info['nickname'] for info in devices_config.values()]
                self.current_status = f"Input devices: {', '.join(device_names)}"
                print(f"[Orchestrator] Input devices successfully changed to: {', '.join(device_names)}")
            else:
                self.current_status = "No input devices selected"
                print("[Orchestrator] No input devices selected")
            
        except Exception as e:
            error_msg = f"Failed to change input devices: {e}"
            print(f"[Orchestrator] {error_msg}")
            self.current_status = error_msg
            traceback.print_exc()

    def get_current_input_devices(self):
        """Get the current input device IDs."""
        try:
            devices = self.config.get("stt", {}).get("devices", {})
            return list(devices.keys())
        except Exception as e:
            print(f"[Orchestrator] Error getting current input devices: {e}")
            return []

    def change_output_device(self, device_id: int):
        """Change the output device for audio playback."""
        print(f"[Orchestrator] Changing output device to: {device_id}")
        
        try:
            # Get device info for display
            output_devices = AudioPlayer.get_available_devices()
            device_name = "Unknown Device"
            for device in output_devices:
                if device['id'] == device_id:
                    device_name = device['name']
                    break
            
            # Update audio player device
            if self.audio_player:
                self.audio_player.set_output_device(device_id)
                self.current_status = f"Output device changed to: {device_name}"
                print(f"[Orchestrator] Output device successfully changed to: {device_name}")
            else:
                raise Exception("Audio player not initialized")
                
        except Exception as e:
            error_msg = f"Failed to change output device: {e}"
            print(f"[Orchestrator] {error_msg}")
            self.current_status = error_msg
            traceback.print_exc()

    def get_current_input_device(self):
        """Get the current input device information (for backward compatibility)."""
        try:
            devices = self.config.get("stt", {}).get("devices", {})
            if devices:
                # Return the first device for backward compatibility
                device_id = list(devices.keys())[0]
                device_info = devices[device_id]
                return {"id": device_id, "name": device_info.get("nickname", "Unknown")}
            return None
        except Exception as e:
            print(f"[Orchestrator] Error getting current input device: {e}")
            return None

    def get_current_output_device(self):
        """Get the current output device information."""
        try:
            if self.audio_player and self.audio_player.output_device_index is not None:
                output_devices = AudioPlayer.get_available_devices()
                for device in output_devices:
                    if device['id'] == self.audio_player.output_device_index:
                        return device
            return None
        except Exception as e:
            print(f"[Orchestrator] Error getting current output device: {e}")
            return None