# audio_player.py
import threading
import pyaudio
import wave
import io

class AudioPlayer:
    def __init__(self, output_device_index=None):
        self._p = pyaudio.PyAudio()
        self._stream = None
        self.is_playing = threading.Event()
        self.output_device_index = output_device_index

    @staticmethod
    def get_available_devices():
        """Returns a list of available audio output devices."""
        p = pyaudio.PyAudio()
        devices = []
        for i in range(p.get_device_count()):
            device_info = p.get_device_info_by_index(i)
            if device_info.get('maxOutputChannels') > 0:
                devices.append({'id': i, 'name': device_info.get('name')})
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
            with io.BytesIO(first_chunk) as wav_file, wave.open(wav_file, 'rb') as wf:
                self._stream = self._p.open(format=self._p.get_format_from_width(wf.getsampwidth()),
                                            channels=wf.getnchannels(),
                                            rate=wf.getframerate(),
                                            output=True,
                                            output_device_index=self.output_device_index)
                self._stream.write(wf.readframes(wf.getnframes()))
            for chunk in audio_stream_generator:
                if chunk and self._stream: self._stream.write(chunk)
        except StopIteration: pass
        except Exception as e: print(f"Error during audio playback: {e}")
        finally:
            if self._stream: self._stream.stop_stream(); self._stream.close(); self._stream = None
            self.is_playing.clear()

    def terminate(self): self._p.terminate()
