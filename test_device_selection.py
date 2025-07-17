# test_device_selection.py - 장치 선택 기능 테스트
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from STT.realtime_stt import RealTimeSTT
from audio_player import AudioPlayer

def test_device_selection():
    print("=== 장치 선택 기능 테스트 ===")
    
    # 입력 장치 목록 테스트
    print("\n1. 입력 장치 목록:")
    try:
        input_devices = RealTimeSTT.get_available_devices()
        for device in input_devices:
            print(f"  - ID {device['id']}: {device['name']}")
    except Exception as e:
        print(f"  오류: {e}")
    
    # 출력 장치 목록 테스트
    print("\n2. 출력 장치 목록:")
    try:
        output_devices = AudioPlayer.get_available_devices()
        for device in output_devices:
            print(f"  - ID {device['id']}: {device['name']}")
    except Exception as e:
        print(f"  오류: {e}")
    
    # 오디오 플레이어 기본 장치 설정 테스트
    print("\n3. 오디오 플레이어 기본 장치 설정 테스트:")
    try:
        audio_player = AudioPlayer()
        if output_devices:
            audio_player.set_output_device(output_devices[0]['id'])
            print(f"  기본 출력 장치로 설정: {output_devices[0]['name']}")
        else:
            print("  출력 장치가 없습니다.")
    except Exception as e:
        print(f"  오류: {e}")

if __name__ == "__main__":
    test_device_selection()
