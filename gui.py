import customtkinter as ctk
import traceback

class AIYoutuberGUI(ctk.CTk):
    """
    Manages the GUI for the AI Youtuber application using CustomTkinter.
    Displays the internal state of the application in a modern, themed interface.
    """
    def __init__(self, orchestrator):
        super().__init__()
        self.orchestrator = orchestrator

        print("[GUI] Initializing GUI...")

        # --- Window Setup ---
        self.title("AI Youtuber Live Dashboard")
        self.geometry("1200x800")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        # --- Layout Setup ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # --- Widget Creation ---
        # Status Label (spans both columns)
        self.status_label = ctk.CTkLabel(self, text="Initializing...", font=ctk.CTkFont(size=16, weight="bold"))
        self.status_label.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="ew")

        # Left Column Widgets
        self.history_frame, self.history_text = self._create_labeled_textbox(self, "Conversation History", height=200)
        self.history_frame.grid(row=1, column=0, padx=(10, 5), pady=5, sticky="nsew")

        self.memory_frame, self.memory_text = self._create_labeled_textbox(self, "Long-Term Memory", height=200)
        self.memory_frame.grid(row=2, column=0, padx=(10, 5), pady=5, sticky="nsew")

        # Right Column Widgets
        self.chat_frame, self.chat_text = self._create_labeled_textbox(self, "Recent Live Chats", height=200)
        self.chat_frame.grid(row=1, column=1, padx=(5, 10), pady=5, sticky="nsew")

        self.prompt_frame, self.prompt_text = self._create_labeled_textbox(self, "Last Full Prompt to LLM", height=200)
        self.prompt_frame.grid(row=2, column=1, padx=(5, 10), pady=5, sticky="nsew")


        print("[GUI] GUI initialization complete. Starting update cycle.")
        self.update_gui()

    def _create_labeled_textbox(self, parent, label_text, height=150): # Default height for textboxes
        frame = ctk.CTkFrame(parent)
        frame.grid_rowconfigure(1, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        
        label = ctk.CTkLabel(frame, text=label_text, font=ctk.CTkFont(size=12, weight="bold"))
        label.grid(row=0, column=0, padx=10, pady=(10, 5), sticky="w")
        
        # Explicitly set height for CTkTextbox
        textbox = ctk.CTkTextbox(frame, wrap="word", font=ctk.CTkFont(size=11), height=height)
        textbox.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        textbox.configure(state="disabled")
        return frame, textbox # Return both the frame and the textbox

    def _update_textbox(self, textbox, new_content):
        """
        텍스트박스의 내용을 업데이트하되, 스크롤 위치를 유지합니다.
        내용에 변화가 없을 때만 업데이트를 수행하여 성능을 최적화합니다.
        """
        # 1. 현재 내용과 새 내용을 비교하여 변경이 없으면 업데이트하지 않음
        # get("1.0", "end-1c")는 마지막 줄바꿈 문자를 제외하고 텍스트를 가져옵니다.
        current_content = textbox.get("1.0", "end-1c")
        if current_content == new_content:
            return # 내용이 같으면 아무것도 하지 않음

        # 2. 내용이 다르다면, 업데이트 전에 현재 스크롤 위치를 저장
        scroll_pos = textbox.yview()

        # 3. 텍스트 내용 업데이트
        textbox.configure(state="normal")
        textbox.delete('1.0', "end")
        textbox.insert("end", new_content)
        textbox.configure(state="disabled")

        # 4. 저장했던 스크롤 위치로 복원
        # yview()는 (top_fraction, bottom_fraction) 튜플을 반환하므로 첫 번째 값을 사용합니다.
        textbox.yview_moveto(scroll_pos[0])

    def update_gui(self):
        """Periodically updates the GUI with the latest data from the orchestrator."""
        try:
            # print("[GUI] Updating GUI...") # Too frequent, uncomment for deep debugging
            self.status_label.configure(text=self.orchestrator.current_status)

            # Ensure components are initialized before accessing their attributes
            if self.orchestrator.gemini_client:
                history_content = self.orchestrator.gemini_client.get_formatted_history()
                self._update_textbox(self.history_text, history_content)

            if self.orchestrator.long_term_memory:
                memory_content = self.orchestrator.long_term_memory.get_all_memories_as_text()
                self._update_textbox(self.memory_text, memory_content)

            chat_content = "\n".join(self.orchestrator.recent_chats) or "(No recent chats)"
            self._update_textbox(self.chat_text, chat_content)

            prompt_content = self.orchestrator.last_full_prompt or "(No prompt sent yet)"
            self._update_textbox(self.prompt_text, prompt_content)

        except Exception as e:
            print(f"[GUI Error] Error updating GUI: {e}")
            traceback.print_exc() # Print full traceback for debugging

        self.after(1000, self.update_gui)
