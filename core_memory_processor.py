# core_memory_processor.py
import json
import os
from typing import List, Dict, Any
from google import genai
from google.genai import types
from datetime import datetime

class CoreMemoryProcessor:
    """
    Core Memory Processor that extracts and manages the most important memories
    from long-term memory using Gemini API with function calling.
    """
    
    def __init__(self, api_key: str, model_name: str, core_memory_file: str = "core_memory.json"):
        """
        Initialize the Core Memory Processor.
        
        Args:
            api_key (str): Google API key for Gemini
            model_name (str): Model name to use
            core_memory_file (str): Path to core memory JSON file
        """
        if not api_key:
            raise ValueError("API key for Gemini must be provided.")
        
        self.client = genai.Client(api_key=api_key)
        self.model_path = f"models/{model_name}"
        self.core_memory_file = core_memory_file
        self.core_memories = []
        
        # Function calling schema for saving core memories
        self.function_schema = {
            "name": "save_core_memory",
            "description": "Save an important core memory that should be remembered for a very long time",
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_text": {
                        "type": "string",
                        "description": "A concise summary of the important memory to save"
                    },
                    "importance_level": {
                        "type": "string",
                        "enum": ["critical", "high", "medium"],
                        "description": "The importance level of this memory"
                    },
                    "category": {
                        "type": "string",
                        "description": "Category of the memory (e.g., 'user_preference', 'personal_info', 'important_event', 'relationship', 'context')"
                    }
                },
                "required": ["memory_text", "importance_level", "category"]
            }
        }
        
        self._load_core_memories()
        print(f"Core Memory Processor initialized with model: {model_name}")

    def _load_core_memories(self):
        """Load existing core memories from JSON file."""
        if os.path.exists(self.core_memory_file):
            try:
                with open(self.core_memory_file, 'r', encoding='utf-8') as f:
                    self.core_memories = json.load(f)
                print(f"Core memories loaded from {self.core_memory_file}: {len(self.core_memories)} entries")
            except Exception as e:
                print(f"Error loading core memories: {e}")
                self.core_memories = []
        else:
            self.core_memories = []

    def _save_core_memories(self):
        """Save core memories to JSON file."""
        try:
            with open(self.core_memory_file, 'w', encoding='utf-8') as f:
                json.dump(self.core_memories, f, ensure_ascii=False, indent=2)
            print(f"Core memories saved to {self.core_memory_file}")
        except Exception as e:
            print(f"Error saving core memories: {e}")

    def _save_core_memory_function(self, memory_text: str, importance_level: str, category: str):
        """Function to be called by Gemini via function calling."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        core_memory_entry = {
            "memory_text": memory_text,
            "importance_level": importance_level,
            "category": category,
            "timestamp": timestamp
        }
        
        self.core_memories.append(core_memory_entry)
        self._save_core_memories()
        
        print(f"[CoreMemory] Saved: {memory_text} ({importance_level}, {category})")
        return f"Successfully saved core memory: {memory_text}"

    def process_long_term_memories(self, long_term_memories: List[str]) -> bool:
        """
        Process long-term memories to extract core memories using Gemini API.
        
        Args:
            long_term_memories (List[str]): List of long-term memory entries
            
        Returns:
            bool: True if processing was successful
        """
        if not long_term_memories:
            print("[CoreMemory] No long-term memories to process")
            return False
        
        try:
            # Create the prompt for extracting core memories
            memories_text = "\n".join([f"- {memory}" for memory in long_term_memories])
            
            prompt = f"""You are an AI assistant analyzing long-term memories to identify the most important information that should be preserved as core memories.

Please analyze the following long-term memories and identify information that should be remembered for a very long time:

{memories_text}

Look for:
1. Important user preferences or personality traits
2. Significant personal information about the user
3. Critical relationship details
4. Important events or milestones
5. Key context that affects how you should interact with the user

For each piece of information you think is important enough to be a core memory, use the save_core_memory function to save it.

Guidelines:
- Only save truly important information that would be valuable to remember long-term
- Summarize information concisely but preserve key details
- Choose appropriate importance levels (critical, high, medium)
- Categorize memories appropriately (user_preference, personal_info, important_event, relationship, context)
- Don't save duplicate or redundant information

Analyze the memories now and save any core memories you identify."""

            # Prepare function calling configuration
            generation_config = types.GenerateContentConfig(
                tools=[
                    types.Tool(
                        function_declarations=[self.function_schema]
                    )
                ],
                thinking_config=types.ThinkingConfig(
                    thinking_budget=256
                )
            )
            
            # Generate content with function calling
            response = self.client.models.generate_content(
                model=self.model_path,
                contents=prompt,
                config=generation_config
            )
            
            # Process function calls
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'function_call') and part.function_call:
                        function_call = part.function_call
                        if function_call.name == "save_core_memory":
                            args = function_call.args
                            self._save_core_memory_function(
                                memory_text=args.get("memory_text", ""),
                                importance_level=args.get("importance_level", "medium"),
                                category=args.get("category", "context")
                            )
            
            print(f"[CoreMemory] Processed {len(long_term_memories)} long-term memories")
            return True
            
        except Exception as e:
            print(f"[CoreMemory] Error processing memories: {e}")
            return False

    def get_core_memories(self) -> List[Dict[str, Any]]:
        """Get all core memories."""
        return self.core_memories.copy()

    def get_core_memories_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get core memories filtered by category."""
        return [memory for memory in self.core_memories if memory.get("category") == category]

    def get_core_memories_by_importance(self, importance_level: str) -> List[Dict[str, Any]]:
        """Get core memories filtered by importance level."""
        return [memory for memory in self.core_memories if memory.get("importance_level") == importance_level]

    def get_core_memories_summary(self) -> str:
        """Get a formatted summary of all core memories."""
        if not self.core_memories:
            return "No core memories stored yet."
        
        summary = "=== Core Memories ===\n"
        
        # Group by importance level
        critical_memories = self.get_core_memories_by_importance("critical")
        high_memories = self.get_core_memories_by_importance("high")
        medium_memories = self.get_core_memories_by_importance("medium")
        
        if critical_memories:
            summary += "\n🔴 Critical Memories:\n"
            for memory in critical_memories:
                summary += f"- {memory['memory_text']} ({memory['category']})\n"
        
        if high_memories:
            summary += "\n🟠 High Importance Memories:\n"
            for memory in high_memories:
                summary += f"- {memory['memory_text']} ({memory['category']})\n"
        
        if medium_memories:
            summary += "\n🟡 Medium Importance Memories:\n"
            for memory in medium_memories:
                summary += f"- {memory['memory_text']} ({memory['category']})\n"
        
        return summary

    def clear_core_memories(self):
        """Clear all core memories (use with caution)."""
        self.core_memories = []
        self._save_core_memories()
        print("[CoreMemory] All core memories cleared")

    def remove_core_memory(self, index: int) -> bool:
        """Remove a specific core memory by index."""
        if 0 <= index < len(self.core_memories):
            removed_memory = self.core_memories.pop(index)
            self._save_core_memories()
            print(f"[CoreMemory] Removed memory: {removed_memory['memory_text']}")
            return True
        return False
