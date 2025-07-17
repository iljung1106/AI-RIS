# gemini_api.py
from google import genai # google.generativeai 대신 google.genai만 사용합니다.
from collections import deque
from google.genai import types

class GeminiAPI:
    """
    A client for interacting with the Google Gemini API using a stateful chat session,
    built exclusively with the google-genai SDK.
    """
    def __init__(self, api_key: str, model_name: str, max_history_length: int = 20):
        if not api_key:
            raise ValueError("API key for Gemini must be provided.")
        
        # google.genai 에서는 Client 객체를 직접 생성합니다.
        self.client = genai.Client(api_key=api_key)
        
        # API 호출 시 사용할 모델의 전체 경로를 문자열로 저장합니다.
        self.model_path = f"models/{model_name}"
        
        self.history = deque(maxlen=max_history_length)
        print(f"Gemini API client initialized with model: {model_name}")

    def add_system_message(self, message: str):
        """Add a system message to the conversation history."""
        self.history.append({'role': 'system', 'parts': [message]})
        print(f"[GeminiAPI] Added system message: {message}")

    def add_to_history(self, role: str, text: str):
        self.history.append({'role': role, 'parts': [text]})

    def get_formatted_history(self) -> str:
        if not self.history:
            return "(No conversation history yet)"
        return "\n".join([f"{msg['role']}: {msg['parts'][0]}" for msg in self.history])

    def refine_stt_text(self, raw_text: str) -> str:
        """
        Refines the raw text from STT using Gemini for better clarity and grammar.
        """
        try:
            # STT 결과물을 자연스럽게 다듬도록 요청하는 프롬프트
            prompt = f"""Please refine the following text, which was transcribed from speech. Correct any grammatical errors, make it more natural-sounding, but preserve the original meaning. Output only the refined text. Do not change the text if it is already correct.

            # Raw Text: "{raw_text}"
            # Refined Text:"""
            
            # generation_config = types.GenerateContentConfig(
            #     thinking_config=types.ThinkingConfig(
            #         thinking_budget=0
            #     )
            # )
            # response = self.client.models.generate_content(
            #     model=self.model_path,
            #     contents=prompt,
            #     config=generation_config,
            # )
            # refined_text = response.text.strip()
            refined_text = raw_text
            print(f"[GeminiAPI] STT Refinement: '{raw_text}' -> '{refined_text}'")
            return refined_text
        except Exception as e:
            print(f"Error refining STT text: {e}")
            return raw_text # 정제 실패 시 원본 텍스트 반환

    def generate_response(self, full_prompt: str, task_prompt: str) -> str:
        """
        Generates a response from the Gemini model with a thinking budget.
        """
        try:
            generation_config = types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(
                    thinking_budget=128
                )
            )
            
            # generate_content 호출 시 파라미터 이름은 generation_config 입니다.
            response = self.client.models.generate_content(
                model=self.model_path,
                contents=full_prompt,
                config=generation_config,
            )
            
            self.add_to_history('user', task_prompt)
            self.add_to_history('model', response.text)
            
            return response.text
        except Exception as e:
            print(f"Error generating response from Gemini: {e}")
            return "죄송해요, 지금은 답변을 생성할 수 없어요."

    def summarize_for_memory(self, text_to_summarize: str) -> str:
        """
        Asks Gemini to summarize text for long-term memory.
        """
        try:
            prompt = f"Please summarize the following text into a concise, one-sentence fact for my long-term memory. Focus on key information, names, or user preferences. Output only the summarized fact. Text to summarize: \n\n\"{text_to_summarize}\""
            
            response = self.client.models.generate_content(
                model=self.model_path,
                contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            print(f"Error summarizing text for memory: {e}")
            return None