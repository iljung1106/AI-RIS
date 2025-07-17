import customtkinter as ctk
import traceback
from STT.realtime_stt import RealTimeSTT
from audio_player import AudioPlayer

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
        self.grid_rowconfigure(2, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # --- Widget Creation ---
        # Status Label (spans both columns)
        self.status_label = ctk.CTkLabel(self, text="Initializing...", font=ctk.CTkFont(size=16, weight="bold"))
        self.status_label.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="ew")

        # Device Selection Frame
        self.device_frame = ctk.CTkFrame(self)
        self.device_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=5, sticky="ew")
        self.device_frame.grid_columnconfigure(0, weight=1)
        self.device_frame.grid_columnconfigure(1, weight=1)

        # Input Devices Frame (Left side)
        self.input_frame = ctk.CTkFrame(self.device_frame)
        self.input_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        self.input_label = ctk.CTkLabel(self.input_frame, text="입력 장치 (다중 선택 가능):", font=ctk.CTkFont(size=12, weight="bold"))
        self.input_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        
        # Scrollable frame for input devices
        self.input_scroll_frame = ctk.CTkScrollableFrame(self.input_frame, height=120)
        self.input_scroll_frame.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
        self.input_scroll_frame.grid_columnconfigure(0, weight=1)
        
        self.input_checkboxes = {}

        # Output Device Frame (Right side)
        self.output_frame = ctk.CTkFrame(self.device_frame)
        self.output_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        
        self.output_label = ctk.CTkLabel(self.output_frame, text="출력 장치:", font=ctk.CTkFont(size=12, weight="bold"))
        self.output_label.grid(row=0, column=0, padx=10, pady=5, sticky="w")
        
        self.output_combo = ctk.CTkComboBox(self.output_frame, values=["로딩 중..."], command=self.on_output_device_changed)
        self.output_combo.grid(row=1, column=0, padx=10, pady=5, sticky="ew")

        # Refresh devices button
        self.refresh_button = ctk.CTkButton(self.output_frame, text="장치 새로고침", command=self.refresh_devices, width=120)
        self.refresh_button.grid(row=2, column=0, padx=10, pady=10)

        # Left Column Widgets
        self.history_frame, self.history_text = self._create_labeled_textbox(self, "Conversation History", height=200)
        self.history_frame.grid(row=2, column=0, padx=(10, 5), pady=5, sticky="nsew")

        self.memory_frame, self.memory_text = self._create_labeled_textbox(self, "Long-Term Memory", height=200)
        self.memory_frame.grid(row=3, column=0, padx=(10, 5), pady=5, sticky="nsew")

        # Right Column Widgets
        self.chat_frame, self.chat_text = self._create_labeled_textbox(self, "Recent Live Chats", height=200)
        self.chat_frame.grid(row=2, column=1, padx=(5, 10), pady=5, sticky="nsew")

        self.prompt_frame, self.prompt_text = self._create_labeled_textbox(self, "Last Full Prompt to LLM", height=200)
        self.prompt_frame.grid(row=3, column=1, padx=(5, 10), pady=5, sticky="nsew")

        # Initialize device lists
        self._load_device_nicknames()  # Load nicknames first
        self._initialize_device_lists()
        
        # Store device nicknames (already loaded above)
        # self.device_nicknames = {}  # {device_id: nickname}


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
        try:
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
        except Exception as e:
            print(f"[GUI] Error updating textbox: {e}")
            traceback.print_exc()

    def update_gui(self):
        """Periodically updates the GUI with the latest data from the orchestrator."""
        try:
            # Update status
            self.status_label.configure(text=self.orchestrator.current_status)

            # Update conversation history
            if self.orchestrator.gemini_client:
                history_content = self.orchestrator.gemini_client.get_formatted_history()
                self._update_textbox(self.history_text, history_content)

            # Update long-term memory
            if self.orchestrator.long_term_memory:
                memory_content = self.orchestrator.long_term_memory.get_all_memories_as_text()
                self._update_textbox(self.memory_text, memory_content)

            # Update recent chats
            chat_content = "\n".join(self.orchestrator.recent_chats) or "(No recent chats)"
            self._update_textbox(self.chat_text, chat_content)

            # Update last full prompt
            prompt_content = self.orchestrator.last_full_prompt or "(No prompt sent yet)"
            self._update_textbox(self.prompt_text, prompt_content)

        except Exception as e:
            print(f"[GUI Error] Error updating GUI: {e}")
            traceback.print_exc()

        self.after(1000, self.update_gui)

    def _initialize_device_lists(self):
        """Initialize the device selection dropdowns with available devices."""
        print("[GUI] Initializing device lists...")
        
        # Clear existing input checkboxes
        for device_id, dev_info in self.input_checkboxes.items():
            if 'frame' in dev_info:
                dev_info['frame'].destroy()
            elif 'checkbox' in dev_info:
                dev_info['checkbox'].destroy()
        self.input_checkboxes.clear()
        
        # Initialize input devices with checkboxes
        try:
            input_devices = RealTimeSTT.get_available_devices()
            
            for i, device in enumerate(input_devices):
                device_id = device['id']
                device_name = device['name']
                
                # Check if device has a custom nickname
                display_name = self.device_nicknames.get(device_id, device_name)
                
                checkbox_var = ctk.BooleanVar()
                
                # Create frame for each device (checkbox + nickname button)
                device_frame = ctk.CTkFrame(self.input_scroll_frame)
                device_frame.grid(row=i, column=0, padx=5, pady=2, sticky="ew")
                device_frame.grid_columnconfigure(0, weight=1)
                
                checkbox = ctk.CTkCheckBox(
                    device_frame,
                    text=f"{device_id}: {display_name}",
                    variable=checkbox_var,
                    command=lambda dev_id=device_id, dev_name=device_name, var=checkbox_var: self.on_input_device_toggled(dev_id, dev_name, var)
                )
                checkbox.grid(row=0, column=0, padx=5, pady=2, sticky="w")
                
                # Nickname button
                nickname_btn = ctk.CTkButton(
                    device_frame,
                    text="별명",
                    width=50,
                    height=24,
                    command=lambda dev_id=device_id, dev_name=device_name: self.set_device_nickname(dev_id, dev_name)
                )
                nickname_btn.grid(row=0, column=1, padx=5, pady=2)
                
                self.input_checkboxes[device_id] = {
                    'checkbox': checkbox,
                    'variable': checkbox_var,
                    'name': device_name,
                    'frame': device_frame,
                    'nickname_btn': nickname_btn
                }
            
            # Set current input devices based on orchestrator config
            current_input_devices = self.orchestrator.get_current_input_devices()
            if current_input_devices:
                for device_id in current_input_devices:
                    if device_id in self.input_checkboxes:
                        self.input_checkboxes[device_id]['variable'].set(True)
            
            print(f"[GUI] Found {len(input_devices)} usable input devices")
        except Exception as e:
            print(f"[GUI] Error loading input devices: {e}")
            error_label = ctk.CTkLabel(self.input_scroll_frame, text="Error loading devices")
            error_label.grid(row=0, column=0, padx=5, pady=2)
        
        # Initialize output devices
        try:
            output_devices = AudioPlayer.get_available_devices()
            if output_devices:
                output_device_names = [f"{device['id']}: {device['name']}" for device in output_devices]
                self.output_combo.configure(values=output_device_names)
                
                # Set current output device based on orchestrator audio player
                current_output = self.orchestrator.get_current_output_device()
                if current_output:
                    for name in output_device_names:
                        if name.startswith(f"{current_output['id']}:"):
                            self.output_combo.set(name)
                            break
                elif output_device_names:
                    self.output_combo.set(output_device_names[0])
                
                print(f"[GUI] Found {len(output_devices)} usable output devices")
            else:
                self.output_combo.configure(values=["사용 가능한 출력 장치가 없습니다"])
                print("[GUI] No usable output devices found")
                
        except Exception as e:
            print(f"[GUI] Error loading output devices: {e}")
            self.output_combo.configure(values=["출력 장치 로드 오류"])

    def on_input_device_toggled(self, device_id, device_name, checkbox_var):
        """Handle input device checkbox toggle."""
        try:
            is_selected = checkbox_var.get()
            
            # Use nickname if available, otherwise use device name
            display_name = self.device_nicknames.get(device_id, device_name)
            
            print(f"[GUI] Input device {device_id} - {display_name} {'selected' if is_selected else 'deselected'}")
            
            # Get all currently selected devices
            selected_devices = {}
            for dev_id, dev_info in self.input_checkboxes.items():
                if dev_info['variable'].get():
                    nickname = self.device_nicknames.get(dev_id, dev_info['name'])
                    selected_devices[dev_id] = {
                        "nickname": nickname,
                        "amplification": 2.0  # Default amplification
                    }
            
            # Update orchestrator configuration
            if hasattr(self.orchestrator, 'change_input_devices'):
                self.orchestrator.change_input_devices(selected_devices)
            
            # Update status display
            if selected_devices:
                device_names = [info['nickname'] for info in selected_devices.values()]
                self.status_label.configure(text=f"입력 장치: {', '.join(device_names[:3])}")
            else:
                self.status_label.configure(text="입력 장치가 선택되지 않았습니다")
                
        except Exception as e:
            print(f"[GUI] Error toggling input device: {e}")
            self.status_label.configure(text=f"입력 장치 전환 오류: {e}")

    def on_output_device_changed(self, selection):
        """Handle output device selection change."""
        try:
            if (selection and ":" in selection and 
                selection != "Loading..." and 
                selection != "사용 가능한 출력 장치가 없습니다" and
                selection != "출력 장치 로드 오류"):
                
                device_id = int(selection.split(":")[0])
                device_name = selection.split(":", 1)[1].strip()
                
                print(f"[GUI] Output device changed to: {device_id} - {device_name}")
                
                # Update orchestrator configuration
                if hasattr(self.orchestrator, 'change_output_device'):
                    self.orchestrator.change_output_device(device_id)
                
                self.status_label.configure(text=f"출력 장치 변경: {device_name}")
                
        except Exception as e:
            print(f"[GUI] Error changing output device: {e}")
            self.status_label.configure(text=f"출력 장치 변경 오류: {e}")

    def refresh_devices(self):
        """Refresh the device lists."""
        print("[GUI] Refreshing device lists...")
        self.status_label.configure(text="장치 목록을 새로고침하는 중...")
        
        # Temporarily disable the refresh button
        self.refresh_button.configure(state="disabled", text="새로고침 중...")
        
        # Use after() to run the refresh in the next event loop cycle
        self.after(100, self._do_refresh_devices)
    
    def _do_refresh_devices(self):
        """Actually perform the device refresh."""
        try:
            self._initialize_device_lists()
            self.status_label.configure(text="장치 목록이 성공적으로 새로고침되었습니다.")
        except Exception as e:
            print(f"[GUI] Error refreshing devices: {e}")
            self.status_label.configure(text=f"장치 새로고침 오류: {e}")
        finally:
            # Re-enable the refresh button
            self.refresh_button.configure(state="normal", text="장치 새로고침")

    def set_device_nickname(self, device_id, device_name):
        """Set a custom nickname for a device."""
        try:
            # Create a dialog to get the nickname
            dialog = ctk.CTkInputDialog(
                text=f"'{device_name}' 장치의 별명을 입력하세요:",
                title="장치 별명 설정"
            )
            
            # Set current nickname as default
            current_nickname = self.device_nicknames.get(device_id, device_name)
            if current_nickname != device_name:
                dialog._entry.insert(0, current_nickname)
            
            nickname = dialog.get_input()
            
            if nickname and nickname.strip():
                nickname = nickname.strip()
                self.device_nicknames[device_id] = nickname
                
                # Update the checkbox text
                if device_id in self.input_checkboxes:
                    self.input_checkboxes[device_id]['checkbox'].configure(
                        text=f"{device_id}: {nickname}"
                    )
                
                # Update status
                self.status_label.configure(text=f"장치 {device_id}의 별명을 '{nickname}'으로 설정했습니다.")
                print(f"[GUI] Device {device_id} nickname set to: {nickname}")
                
                # Save nicknames to file
                self._save_device_nicknames()
                
        except Exception as e:
            print(f"[GUI] Error setting device nickname: {e}")
            self.status_label.configure(text=f"별명 설정 오류: {e}")

    def _save_device_nicknames(self):
        """Save device nicknames to a file."""
        try:
            import json
            with open("device_nicknames.json", "w", encoding="utf-8") as f:
                json.dump(self.device_nicknames, f, ensure_ascii=False, indent=2)
            print("[GUI] Device nicknames saved")
        except Exception as e:
            print(f"[GUI] Error saving device nicknames: {e}")

    def _load_device_nicknames(self):
        """Load device nicknames from a file."""
        try:
            import json
            with open("device_nicknames.json", "r", encoding="utf-8") as f:
                self.device_nicknames = json.load(f)
                # Convert string keys to int keys
                self.device_nicknames = {int(k): v for k, v in self.device_nicknames.items()}
            print(f"[GUI] Loaded {len(self.device_nicknames)} device nicknames")
        except FileNotFoundError:
            print("[GUI] No device nicknames file found, using defaults")
            self.device_nicknames = {}
        except Exception as e:
            print(f"[GUI] Error loading device nicknames: {e}")
            self.device_nicknames = {}
