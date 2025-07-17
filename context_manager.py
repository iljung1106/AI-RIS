# context_manager.py
import datetime

class ContextManager:
    """
    Manages the assembly of context to be sent to the language model.
    It gathers information from various sources like memory, chat, and persona
    to create a comprehensive prompt.
    """
    def __init__(self, config: dict, long_term_memory, gemini_client, core_memory_processor=None):
        self.config = config.get("llm", {})
        self.long_term_memory = long_term_memory
        self.gemini_client = gemini_client
        self.core_memory_processor = core_memory_processor

    def _get_task_prompt(self, item: dict) -> str:
        """
        Generates the specific task prompt based on the input item.
        """
        source = item.get("source")
        if source == "idle":
            return self.config.get("idle_prompt", "Say something interesting.")
        elif source in ["stt", "chat"]:
            return self.config.get("user_prompt_template", "{nickname}: {user_input}").format(
                nickname=item.get("nickname", "Someone"),
                user_input=item.get("content", "")
            )
        return ""

    def build_prompt(self, item: dict, previous_chats: list, recent_chats: list) -> tuple[str, str]:
        """
        Constructs the final, comprehensive prompt to be sent to the Gemini model.

        Args:
            item (dict): The input item from the queue (stt, chat, or idle).
            previous_chats (list): 채팅 중 '본 적 있는 채팅'.
            recent_chats (list): 채팅 중 '본 적 없는 채팅'.

        Returns:
            tuple[str, str]: A tuple containing the fully formatted prompt and the task prompt.
        """
        persona = self.config.get("persona_prompt", "")
        memory = self.long_term_memory.get_all_memories_as_text()
        
        # Core memory 정보 추가
        core_memory_info = ""
        if self.core_memory_processor:
            core_memory_summary = self.core_memory_processor.get_core_memories_summary()
            if core_memory_summary != "No core memories stored yet.":
                core_memory_info = f"\n# Core Memory (Most Important Information)\n{core_memory_summary}\n"
        
        previous = "\n".join(previous_chats) or "(No previous chats)"
        chats = "\n".join(recent_chats) or "(No recent chats)"
        history = self.gemini_client.get_formatted_history()
        task_prompt = self._get_task_prompt(item)
        
        # 현재 날짜와 시간 정보 추가
        current_datetime = datetime.datetime.now()
        current_time_str = current_datetime.strftime("%Y년 %m월 %d일 %H시 %M분 %S초")
        weekday_korean = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
        weekday_str = weekday_korean[current_datetime.weekday()]
        datetime_info = f"{current_time_str} ({weekday_str})"

        # 새로운 프롬프트 구조
        full_prompt = f"""# System Persona
{persona}

# Current Date and Time
{datetime_info}
{core_memory_info}
# Long-Term Memory
{memory}

# Previous Live Chat Log
{previous}

# Conversation History
{history}

# Recent Live Chat Log
{chats}

# Current Task
{task_prompt}
"""
        return full_prompt, task_prompt

    def build_context(self, item: dict, previous_chats: list, recent_chats: list) -> str:
        """
        Constructs the context for the Gemini model (simplified version).
        Args:
            item (dict): The input item from the queue.
            previous_chats (list): 본 적 있는 채팅.
            recent_chats (list): 본 적 없는 채팅.
        Returns:
            str: The formatted context string.
        """
        full_prompt, _ = self.build_prompt(item, previous_chats, recent_chats)
        return full_prompt
