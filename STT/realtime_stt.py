import time
import threading
import numpy as np
import sounddevice as sd
from funasr_onnx import SenseVoiceSmall
from funasr_onnx.utils.postprocess_utils import rich_transcription_postprocess
import torch
from collections import deque

class RealTimeSTT:
    """
    VAD(음성 감지), 마이크별 증폭 기능을 포함한 실시간 STT 클래스.
    (상태 기반 VAD 로직으로 개선된 버전)
    """
    def __init__(self,
                 device_config: dict,
                 on_text_transcribed: callable,
                 model_size: str = "iic/SenseVoiceSmall",
                 language: str = "auto",
                 silence_duration_s: float = 0.5, # 침묵 시간을 약간 줄여 반응성 개선
                 max_buffer_seconds: int = 30,
                 vad_threshold: float = 0.01): # RMS 임계값

        self.device_config = device_config
        self.on_text_transcribed = on_text_transcribed
        self.model_size = model_size
        self.language = language
        self.silence_duration_s = silence_duration_s
        self.max_buffer_seconds = max_buffer_seconds
        self.vad_threshold = vad_threshold # RMS 임계값으로 사용

        self.samplerate = 16000
        self.chunk_samples = 1024 # 약 64ms
        self.running = False
        self.threads = []
        self.model = None

    @staticmethod
    def get_available_devices():
        """Get available input devices that are actually usable."""
        devices = sd.query_devices()
        input_devices = []
        
        for i, device in enumerate(devices):
            # Check if device has input channels and is not a disabled/virtual device
            if (device['max_input_channels'] > 0 and 
                device['hostapi'] >= 0 and  # Valid host API
                'Microsoft Sound Mapper' not in device['name'] and  # Skip generic mappers
                'Primary Sound' not in device['name'] and  # Skip primary sound devices
                device['name'].strip()):  # Skip devices with empty names
                
                try:
                    # Test if device is actually accessible
                    with sd.InputStream(device=i, channels=1, samplerate=16000, blocksize=1024):
                        pass
                    input_devices.append({
                        'id': i, 
                        'name': device['name'].strip(),
                        'hostapi_name': sd.query_hostapis(device['hostapi'])['name'],
                        'max_input_channels': device['max_input_channels'],
                        'default_samplerate': device['default_samplerate']
                    })
                except Exception as e:
                    print(f"[STT] Device {i} ({device['name']}) is not accessible: {e}")
                    continue
        
        return input_devices

    def _load_model(self):
        print(f"[STT] '{self.model_size}' 모델을 로드하는 중...")
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        quantize = True if device == "cpu" else False
        self.model = SenseVoiceSmall(self.model_size, quantize=quantize, device=device)
        print(f"[STT] 모델 로드 완료. (장치: {device}, 양자화: {quantize})")

    def _process_mic_input(self, device_index: int, config: dict):
        """
        개선된 상태 기반 VAD 로직을 사용하는 스레드 워커 함수.
        """
        nickname = config["nickname"]
        amplification = config.get("amplification", 1.0)
        
        # --- 상태 관리를 위한 변수 ---
        speaking = False
        audio_buffer = deque()
        # 말이 시작되기 전의 오디오를 저장하여 문맥을 확보 (0.5초)
        pre_buffer = deque(maxlen=int(0.5 * self.samplerate / self.chunk_samples))
        silence_chunks_counter = 0
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
                    
                    chunk *= amplification
                    is_speech = np.sqrt(np.mean(chunk**2)) > self.vad_threshold

                    # --- 상태 기반 로직 ---
                    if speaking:
                        # 2. 말하는 중 상태
                        audio_buffer.append(chunk)
                        
                        if not is_speech:
                            silence_chunks_counter += 1
                        else:
                            silence_chunks_counter = 0 # 말이 다시 감지되면 침묵 카운터 초기화
                        
                        # 말이 끝났다고 판단 (충분한 침묵이 지속) 또는 버퍼가 꽉 찼을 때
                        if silence_chunks_counter > max_silence_chunks or len(audio_buffer) > max_buffer_chunks:
                            speaking = False # 상태를 '대기 중'으로 변경
                            
                            # STT 처리
                            full_audio = np.concatenate(list(audio_buffer)).flatten()
                            audio_buffer.clear()
                            pre_buffer.clear() # 버퍼 초기화
                            
                            print(f"[STT] 변환 시작 (오디오 길이: {len(full_audio)/self.samplerate:.2f}초)...")
                            res = self.model(full_audio, language=self.language, use_itn=True)
                            transcribed_text = rich_transcription_postprocess(res[0]).strip() if res and res[0] else ""

                            if transcribed_text:
                                try:
                                    self.on_text_transcribed(nickname, transcribed_text)
                                except Exception as e:
                                    print(f"[STT] Error in callback: {e}")
                                    import traceback
                                    traceback.print_exc()
                            else:
                                print("[STT] 변환된 텍스트가 없습니다.")
                    else:
                        # 1. 대기 상태
                        if is_speech:
                            # 말이 시작됨 -> '말하는 중' 상태로 변경
                            speaking = True
                            print(f"[{nickname}] 음성 감지됨, 녹음 시작...")
                            # pre-buffer에 있던 오디오와 현재 청크를 메인 버퍼에 추가
                            audio_buffer.extend(pre_buffer)
                            audio_buffer.append(chunk)
                            silence_chunks_counter = 0
                        else:
                            # 말이 없을 때는 pre-buffer에만 오디오를 저장
                            pre_buffer.append(chunk)

        except Exception as e:
            print(f"❌ [{nickname}] 스레드에서 오류 발생: {e}")
        finally:
            print(f"🛑 [{nickname}] 마이크(장치 #{device_index}) 청취 중지.")

    def start(self):
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
        if not self.running:
            return
        print("[STT] STT 처리를 중지하는 중...")
        self.running = False
        for thread in self.threads:
            thread.join()
        self.threads = []
        self.model = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        print("[STT] 모든 STT 처리가 안전하게 종료되었습니다.")

# --- 사용 예시 ---
if __name__ == '__main__':
    def handle_transcription(nickname, text):
        print(f"\n>> [{nickname}] 최종 결과: {text}\n")

    print("사용 가능한 오디오 장치:")
    available_devices = RealTimeSTT.get_available_devices()
    for device in available_devices:
        print(f"  - ID {device['id']}: {device['name']} ({device['hostapi_name']})")
    
    if available_devices:
        mic_id = available_devices[0]['id']
        mic_name = available_devices[0]['name']

        MY_DEVICE_CONFIG = { mic_id: {"nickname": mic_name, "amplification": 1.5} }

        stt_system = RealTimeSTT(
            device_config=MY_DEVICE_CONFIG,
            on_text_transcribed=handle_transcription,
            model_size="iic/SenseVoiceSmall",
            language="ko",
            silence_duration_s=1.5, # 1.5초 침묵 시 처리
            vad_threshold=0.01      # 마이크 환경에 따라 0.005 ~ 0.02 사이로 조절해보세요.
        )

        stt_system.start()
        try:
            print("\nSTT 시스템이 실행 중입니다. 종료하려면 Ctrl+C를 누르세요.")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n종료 신호를 받았습니다...")
        finally:
            stt_system.stop()
    else:
        print("\n사용 가능한 입력 오디오 장치가 없습니다. 프로그램을 종료합니다.")