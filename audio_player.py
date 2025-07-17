# audio_player.py
import threading
import pyaudio
import wave
import io
import numpy as np

class AudioPlayer:
    def __init__(self, output_device_index=None, on_volume_update=None):
        self._p = pyaudio.PyAudio()
        self._stream = None
        self.is_playing = threading.Event()
        self.output_device_index = output_device_index
        self.on_volume_update = on_volume_update # 볼륨 업데이트 콜백

    @staticmethod
    def get_available_devices():
        """Returns a list of available audio output devices that are actually usable."""
        p = pyaudio.PyAudio()
        devices = []
        
        for i in range(p.get_device_count()):
            try:
                device_info = p.get_device_info_by_index(i)
                
                # Check if device has output channels and is not a disabled/virtual device
                if (device_info.get('maxOutputChannels', 0) > 0 and
                    device_info.get('hostApi', -1) >= 0 and  # Valid host API
                    'Microsoft Sound Mapper' not in device_info.get('name', '') and  # Skip generic mappers
                    'Primary Sound' not in device_info.get('name', '') and  # Skip primary sound devices
                    device_info.get('name', '').strip()):  # Skip devices with empty names
                    
                    # Test if device is actually accessible
                    try:
                        test_stream = p.open(
                            format=pyaudio.paInt16,
                            channels=1,
                            rate=16000,
                            output=True,
                            output_device_index=i,
                            frames_per_buffer=1024
                        )
                        test_stream.close()
                        
                        devices.append({
                            'id': i, 
                            'name': device_info.get('name', '').strip(),
                            'hostapi_name': p.get_host_api_info_by_index(device_info.get('hostApi', 0)).get('name', ''),
                            'max_output_channels': device_info.get('maxOutputChannels', 0),
                            'default_samplerate': device_info.get('defaultSampleRate', 0)
                        })
                    except Exception as e:
                        print(f"[AudioPlayer] Device {i} ({device_info.get('name', '')}) is not accessible: {e}")
                        continue
                        
            except Exception as e:
                print(f"[AudioPlayer] Error checking device {i}: {e}")
                continue
        
        p.terminate()
        return devices

    def set_output_device(self, device_index: int):
        """Sets the output device index."""
        print(f"[AudioPlayer] Setting output device to index: {device_index}")
        self.output_device_index = device_index

    def play_stream(self, audio_stream_generator):
        if self.is_playing.is_set(): return
        self.is_playing.set()
        try:
            first_chunk = next(audio_stream_generator)
            if not first_chunk: return

            # 첫 청크는 헤더를 포함한 wav 파일이므로, 파싱해서 스트림을 열어야 함
            with io.BytesIO(first_chunk) as wav_file:
                with wave.open(wav_file, 'rb') as wf:
                    channels = wf.getnchannels()
                    sampwidth = wf.getsampwidth()
                    framerate = wf.getframerate()
                    
                    self._stream = self._p.open(format=self._p.get_format_from_width(sampwidth),
                                                channels=channels,
                                                rate=framerate,
                                                output=True,
                                                output_device_index=self.output_device_index)
                    
                    # 헤더를 제외한 실제 오디오 데이터 읽기
                    audio_data = wf.readframes(wf.getnframes())
                    self._process_and_play_chunk(audio_data, sampwidth, channels)

            # 두 번째 청크부터는 순수 오디오 데이터
            for chunk in audio_stream_generator:
                if not self.is_playing.is_set() or not self._stream:
                    print("[AudioPlayer] Playback was stopped. Breaking loop.")
                    break
                if chunk and self._stream:
                    self._process_and_play_chunk(chunk, sampwidth, channels)

        except StopIteration:
            pass # 스트림 정상 종료
        except Exception as e:
            print(f"Error during audio playback: {e}")
        finally:
            if self._stream:
                self._stream.stop_stream()
                self._stream.close()
                self._stream = None
            self.is_playing.clear()
            # 재생이 끝나면 입을 닫도록 볼륨 0을 전달
            if self.on_volume_update:
                self.on_volume_update(0.0)

    def _process_and_play_chunk(self, chunk, sampwidth, channels):
        """오디오 청크를 재생하고 볼륨을 계산하여 콜백을 호출합니다."""
        # 볼륨 계산
        if self.on_volume_update:
            try:
                # 바이트 데이터를 numpy 배열로 변환
                dtype = np.int16 # GPT-SoVITS는 보통 16비트 오디오를 생성
                audio_np = np.frombuffer(chunk, dtype=dtype)
                
                # RMS(Root Mean Square) 계산으로 볼륨 측정
                rms = np.sqrt(np.mean(audio_np.astype(np.float32)**2))
                
                # 정규화 (int16의 최대값으로 나누어 0~1 범위로 만듦)
                # 실제로는 소리가 작을 수 있으므로, 적절한 증폭 계수(예: 10)를 곱해줌
                normalized_volume = (rms / 32768) * 10 
                
                self.on_volume_update(normalized_volume)
            except Exception as e:
                print(f"[AudioPlayer] 볼륨 계산 중 오류: {e}")
                self.on_volume_update(0.0) # 오류 발생 시 0으로

        # 오디오 재생
        self._stream.write(chunk)

    def stop(self):
        """Stop the current audio playback safely."""
        try:
            print("[AudioPlayer] Stopping audio playback...")
            
            # Clear the playing flag first to prevent race conditions
            self.is_playing.clear()
            
            if self._stream:
                try:
                    # Stop the stream first
                    if hasattr(self._stream, 'is_active') and self._stream.is_active():
                        self._stream.stop_stream()
                    
                    # Close the stream
                    if hasattr(self._stream, 'is_stopped') and not self._stream.is_stopped():
                        self._stream.close()
                    
                    print("[AudioPlayer] Audio stream stopped and closed successfully")
                except Exception as e:
                    print(f"[AudioPlayer] Error stopping stream: {e}")
                finally:
                    self._stream = None
            
            print("[AudioPlayer] Audio playback stopped safely")
            
        except Exception as e:
            print(f"[AudioPlayer] Error in stop method: {e}")
            # Always clear the playing flag, even if there's an error
            self.is_playing.clear()
            if self._stream:
                self._stream = None
            # 입 모양을 닫기 위해 볼륨 0을 전달
            if self.on_volume_update:
                self.on_volume_update(0.0)

    def terminate(self): self._p.terminate()
