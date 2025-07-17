# test_device_selection_improved.py - 개선된 장치 선택 테스트
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from STT.realtime_stt import RealTimeSTT
from audio_player import AudioPlayer

def test_improved_device_selection():
    print("=== 개선된 장치 선택 기능 테스트 ===")
    
    # 입력 장치 목록 테스트
    print("\n1. 사용 가능한 입력 장치 목록:")
    try:
        input_devices = RealTimeSTT.get_available_devices()
        print(f"총 {len(input_devices)}개의 사용 가능한 입력 장치를 찾았습니다.")
        
        for device in input_devices:
            print(f"  - ID {device['id']}: {device['name']}")
            print(f"    Host API: {device['hostapi_name']}")
            print(f"    최대 입력 채널: {device['max_input_channels']}")
            print(f"    기본 샘플레이트: {device['default_samplerate']}")
            print()
            
    except Exception as e:
        print(f"  입력 장치 오류: {e}")
    
    # 출력 장치 목록 테스트
    print("\n2. 사용 가능한 출력 장치 목록:")
    try:
        output_devices = AudioPlayer.get_available_devices()
        print(f"총 {len(output_devices)}개의 사용 가능한 출력 장치를 찾았습니다.")
        
        for device in output_devices:
            print(f"  - ID {device['id']}: {device['name']}")
            print(f"    Host API: {device['hostapi_name']}")
            print(f"    최대 출력 채널: {device['max_output_channels']}")
            print(f"    기본 샘플레이트: {device['default_samplerate']}")
            print()
            
    except Exception as e:
        print(f"  출력 장치 오류: {e}")
    
    print("\n테스트 완료!")

if __name__ == "__main__":
    test_improved_device_selection()
