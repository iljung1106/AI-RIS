# context_manager.py

class ContextManager:
    """
    Manages the assembly of context to be sent to the language model.
    It gathers information from various sources like memory, chat, and persona
    to create a comprehensive prompt.
    """
    def __init__(self, config: dict, long_term_memory, gemini_client):
        self.config = config.get("llm", {})
        self.long_term_memory = long_term_memory
        self.gemini_client = gemini_client

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

    def build_prompt(self, item: dict, recent_chats: list) -> tuple[str, str]:
        """
        Constructs the final, comprehensive prompt to be sent to the Gemini model.

        Args:
            item (dict): The input item from the queue (stt, chat, or idle).
            recent_chats (list): A list of recent chat messages.

        Returns:
            tuple[str, str]: A tuple containing the fully formatted prompt and the task prompt.
        """
        persona = self.config.get("persona_prompt", "")
        memory = self.long_term_memory.get_all_memories_as_text()
        chats = "\n".join(recent_chats) or "(No recent chats)"
        history = self.gemini_client.get_formatted_history()
        task_prompt = self._get_task_prompt(item)

        # The final prompt structure that combines all context elements
        full_prompt = f"""# System Persona
{persona}

# Long-Term Memory
{memory}

# Recent Live Chat Log
{chats}

# Conversation History
{history}

# Current Task
{task_prompt}
"""
        return full_prompt, task_prompt
