# example_realtime_playback.py
import pyaudio
import wave
import io
from TTS.gsv_api_client import GPTSoVITSClient # gsv_api_client.py 가 같은 폴더에 있다고 가정

def play_audio_stream(audio_stream):
    """
    스트리밍 오디오 데이터를 받아 실시간으로 재생합니다.
    서버는 첫 번째 청크에 WAV 헤더를 포함하여 보내줍니다.
    """
    p = None
    stream = None
    try:
        # 첫 번째 청크를 받아옵니다. 여기에는 WAV 헤더가 포함되어 있습니다.
        first_chunk = next(audio_stream)
        if not first_chunk:
            print("오디오 스트림이 비어있습니다.")
            return

        # BytesIO를 사용하여 메모리 내에서 WAV 파일을 엽니다.
        with io.BytesIO(first_chunk) as wav_file_in_memory:
            with wave.open(wav_file_in_memory, 'rb') as wf:
                # 오디오 속성(채널, 샘플링 레이트 등)을 가져옵니다.
                channels = wf.getnchannels()
                sample_width = wf.getsampwidth()
                rate = wf.getframerate()
                
                print(f"오디오 정보: {channels} 채널, {rate} Hz, {sample_width*8}-bit")

                # PyAudio 스트림을 엽니다.
                p = pyaudio.PyAudio()
                stream = p.open(format=p.get_format_from_width(sample_width),
                                channels=channels,
                                rate=rate,
                                output=True)
                
                # 첫 번째 청크의 오디오 데이터를 스트림에 씁니다.
                first_audio_data = wf.readframes(wf.getnframes())
                stream.write(first_audio_data)

        # 나머지 오디오 청크들을 받아와서 스트림에 씁니다.
        # 이 청크들은 순수한 raw 오디오 데이터입니다.
        print("실시간 재생 시작...")
        for chunk in audio_stream:
            if chunk:
                stream.write(chunk)
        
        print("재생 완료.")

    except StopIteration:
        print("스트림이 예상보다 일찍 종료되었습니다.")
    except Exception as e:
        print(f"오디오 재생 중 오류 발생: {e}")
    finally:
        # 리소스를 정리합니다.
        if stream:
            stream.stop_stream()
            stream.close()
        if p:
            p.terminate()


def run_realtime_example():
    # 클라이언트 초기화
    client = GPTSoVITSClient("127.0.0.1", 9880)

    print("\n--- 실시간 스트리밍 TTS 요청 ---")
    try:
        # ⚠️ ref_audio_path는 반드시 '서버'에 있는 파일 경로여야 합니다.
        # ⚠️ prompt_lang은 text_lang과 다를 수 있습니다. 여기서는 prompt_text가 영어이므로 'en'으로 설정합니다.
        audio_stream = client.tts(
            text="이것은 스트리밍 예제입니다. 긴 문장도 실시간처럼 조금씩 스피커로 들을 수 있습니다.",
            text_lang="ko",
            ref_audio_path="C:\Works\projects\AI-RIS\SampleVoices\SampleEvilNeuro.mp3", # ⚠️ 서버에 있는 참조 오디오 경로
            prompt_text="So much for subsribing. I feel so warm and fuzzy inside. And no it's not because of my cat ears.",
            prompt_lang="en",
            streaming_mode=True,
            media_type="wav"  # 스트리밍 시 wav 헤더가 먼저 오고 raw 데이터가 따름
        )
        
        if audio_stream:
            play_audio_stream(audio_stream)
        else:
            print("TTS 요청 실패: 오디오 스트림을 받지 못했습니다.")

    except Exception as e:
        print(f"예제 실행 중 예외 발생: {e}")


if __name__ == "__main__":
    # 먼저 터미널에서 api_v2.py를 실행해야 합니다.
    # python api_v2.py -a 127.0.0.1 -p 9880 -c ...
    run_realtime_example()