# long_term_memory.py
import json
import os
from collections import deque

class LongTermMemory:
    """
    Manages the long-term memory of the AI, stored in a JSON file.
    It saves key facts, user preferences, and important conversation summaries.
    """
    def __init__(self, file_path: str, max_entries: int = 100):
        """
        Initializes the long-term memory manager.

        Args:
            file_path (str): The path to the JSON file for storing memories.
            max_entries (int): The maximum number of memory entries to keep.
        """
        self.file_path = file_path
        self.memories = deque(maxlen=max_entries)
        self._load_memories()

    def _load_memories(self):
        """Loads memories from the JSON file if it exists."""
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.memories.extend(data)
                print(f"Long-term memory loaded from {self.file_path}")
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading long-term memory: {e}. Starting with a fresh memory.")
        else:
            print("No long-term memory file found. A new one will be created.")

    def _save_memories(self):
        """Saves the current memories to the JSON file."""
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(list(self.memories), f, ensure_ascii=False, indent=4)
        except IOError as e:
            print(f"Error saving long-term memory: {e}")

    def add_memory(self, memory: str):
        """
        Adds a new memory and saves it to the file.

        Args:
            memory (str): The new piece of information to remember.
        """
        if memory and memory not in self.memories:
            print(f"[Memory] Adding new long-term memory: '{memory}'")
            self.memories.append(memory)
            self._save_memories()

    def get_memories(self, limit: int = 10) -> list:
        """
        Retrieves the most recent memories.

        Args:
            limit (int): The maximum number of memories to retrieve.

        Returns:
            list: A list of the most recent memory strings.
        """
        return list(self.memories)[-limit:]

    def get_all_memories_as_text(self) -> str:
        """
        Returns all memories formatted as a single string.
        """
        if not self.memories:
            return "No long-term memories yet."
        return "\n".join(f"- {m}" for m in self.memories)
