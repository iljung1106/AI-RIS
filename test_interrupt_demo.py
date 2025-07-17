# test_interrupt_demo.py - TTS 중단 기능 테스트
import sys
import os
import time
import threading
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from audio_player import AudioPlayer
from TTS.gsv_api_client import GPTSoVITSClient

def test_interrupt_demo():
    print("=== TTS 중단 기능 테스트 ===")
    
    # 오디오 플레이어 초기화
    audio_player = AudioPlayer()
    
    # 사용 가능한 출력 장치 확인
    output_devices = AudioPlayer.get_available_devices()
    if output_devices:
        audio_player.set_output_device(output_devices[0]['id'])
        print(f"출력 장치 설정: {output_devices[0]['name']}")
    else:
        print("출력 장치를 찾을 수 없습니다.")
        return
    
    # 중단 기능 테스트
    print("\n중단 기능 테스트:")
    print("1. 오디오 재생 시작")
    audio_player.is_playing.set()
    print(f"재생 상태: {audio_player.is_playing.is_set()}")
    
    print("2. 3초 후 중단")
    time.sleep(3)
    audio_player.stop()
    print(f"중단 후 재생 상태: {audio_player.is_playing.is_set()}")
    
    print("\n테스트 완료!")

if __name__ == "__main__":
    test_interrupt_demo()
