import time
import threading
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel
import torch
from collections import deque

class RealTimeSTT:
    """
    VAD(음성 감지), 마이크별 증폭 기능을 포함한 실시간 STT 클래스.
    사용자가 말을 멈추면 녹음된 음성을 텍스트로 변환합니다.

    Args:
        device_config (dict): 마이크 장치 설정.
            - 형식: {device_index: {"nickname": str, "amplification": float}}
            - 예: {0: {"nickname": "마이크1", "amplification": 1.5}}
        on_text_transcribed (callable): 텍스트 변환 시 호출될 콜백 함수.
            - 인자: (nickname, text)
        model_size (str): Whisper 모델 크기 또는 HuggingFace 저장소 ID.
        language (str): 인식할 언어 코드 (e.g., "ko", "en").
        silence_duration_s (float): 음성으로 간주하지 않을 침묵의 시간 (초).
        max_buffer_seconds (int): 최대 녹음 버퍼 크기 (초). 이 시간을 초과하면 자동으로 처리.
        vad_threshold (float): VAD의 음성 감지 민감도 (0.0 ~ 1.0). 낮을수록 민감.
    """
    def __init__(self,
                 device_config: dict,
                 on_text_transcribed: callable,
                 model_size: str = "deepdml/faster-whisper-large-v3-turbo-ct2",
                 language: str = "ko",
                 silence_duration_s: float = 2.0,
                 max_buffer_seconds: int = 30,
                 vad_threshold: float = 0.5):

        self.device_config = device_config
        self.on_text_transcribed = on_text_transcribed
        self.model_size = model_size
        self.language = language
        self.silence_duration_s = silence_duration_s
        self.max_buffer_seconds = max_buffer_seconds
        self.vad_threshold = vad_threshold

        self.samplerate = 16000  # Whisper 모델의 요구사항
        self.chunk_samples = 1024  # 작은 오디오 조각 크기
        self.running = False
        self.threads = []
        self.model = None

    @staticmethod
    def get_available_devices():
        """Returns a list of available audio input devices."""
        devices = sd.query_devices()
        input_devices = []
        for i, device in enumerate(devices):
            # Check if it's an input device (has input channels)
            if device['max_input_channels'] > 0:
                input_devices.append({'id': i, 'name': device['name'], 'hostapi_name': device['hostapi']})
        return input_devices

    def _load_model(self):
        """Whisper 모델을 로드합니다."""
        print(f"[STT] '{self.model_size}' 모델을 로드하는 중...")
        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_type = "float16" if device == "cuda" else "int8"
        
        if device == "cpu" and compute_type == "float16":
            print("[STT] 경고: CPU에서는 float16을 지원하지 않습니다. compute_type을 'int8'로 변경합니다.")
            compute_type = "int8"
            
        self.model = WhisperModel(self.model_size, device=device, compute_type=compute_type)
        print(f"[STT] 모델 로드 완료. (장치: {device}, 계산 타입: {compute_type})")

    def _process_mic_input(self, device_index: int, config: dict):
        """
        개별 마이크 입력을 실시간으로 처리하는 스레드 워커 함수.
        """
        nickname = config["nickname"]
        amplification = config.get("amplification", 1.0)
        
        audio_buffer = deque()
        silence_chunks = 0
        max_silence_chunks = int(self.silence_duration_s * self.samplerate / self.chunk_samples)
        max_buffer_chunks = int(self.max_buffer_seconds * self.samplerate / self.chunk_samples)

        try:
            with sd.InputStream(samplerate=self.samplerate,
                                device=device_index,
                                channels=1,
                                blocksize=self.chunk_samples,
                                dtype='float32') as stream:
                print(f"✅ [{nickname}] 마이크(장치 #{device_index}, 증폭: {amplification}x) 청취 시작...")
                
                while self.running:
                    chunk, overflowed = stream.read(self.chunk_samples)
                    if overflowed:
                        print(f"⚠️ [{nickname}] 오디오 버퍼 오버플로우 발생!")
                    
                    # 1. 소리 증폭
                    chunk *= amplification
                    
                    # 2. 음성 활동 감지 (간단한 RMS 기반)
                    # VAD 필터는 긴 오디오에 더 효과적이므로, 실시간 청크는 RMS로 판단
                    is_speech = np.sqrt(np.mean(chunk**2)) > 0.01  # 임계값, 환경에 따라 조절
                    
                    if is_speech:
                        silence_chunks = 0
                        audio_buffer.append(chunk)
                        # print(f"[STT] Speech detected. Buffer size: {len(audio_buffer)} ") # Too noisy
                    else:
                        silence_chunks += 1
                    
                    # 3. STT 처리 조건 확인
                    # 조건 A: 말이 끝나고 일정 시간 침묵이 흐른 경우
                    # 조건 B: 버퍼가 너무 길어진 경우 (중간 결과 출력)
                    should_transcribe = (len(audio_buffer) > 0 and silence_chunks > max_silence_chunks) or \
                                        (len(audio_buffer) > max_buffer_chunks)

                    if should_transcribe:
                        print(f"[STT] Transcribing audio buffer (size: {len(audio_buffer)} chunks).")
                        # 버퍼의 오디오 데이터를 하나로 합침
                        full_audio = np.concatenate(list(audio_buffer)).flatten()
                        audio_buffer.clear()
                        silence_chunks = 0
                        
                        # faster-whisper 모델로 STT 수행
                        segments, _ = self.model.transcribe(
                            full_audio,
                            language=self.language,
                            vad_filter=True,
                            vad_parameters={"threshold": self.vad_threshold}
                        )
                        
                        transcribed_text = "".join(segment.text for segment in segments).strip()

                        if transcribed_text:
                            print(f"[STT] Transcribed text: '{transcribed_text}'. Calling callback.")
                            self.on_text_transcribed(nickname, transcribed_text)
                        else:
                            print("[STT] Transcribed text is empty or only whitespace.")

        except Exception as e:
            print(f"❌ [{nickname}] 스레드에서 오류 발생: {e}")
        finally:
            print(f"🛑 [{nickname}] 마이크(장치 #{device_index}) 청취 중지.")


    def start(self):
        """STT 처리를 시작합니다."""
        if self.running:
            print("[STT] 이미 STT가 실행 중입니다.")
            return

        self._load_model()
        self.running = True

        for device_index, config in self.device_config.items():
            thread = threading.Thread(target=self._process_mic_input, args=(device_index, config))
            self.threads.append(thread)
            thread.start()
        
        print(f"[STT] 총 {len(self.threads)}개의 마이크에 대한 STT 처리를 시작했습니다.")


    def stop(self):
        """STT 처리를 중지합니다."""
        if not self.running:
            return

        print("[STT] STT 처리를 중지하는 중...")
        self.running = False
        for thread in self.threads:
            thread.join()
        
        self.threads = []
        self.model = None
        print("[STT] 모든 STT 처리가 안전하게 종료되었습니다.")
