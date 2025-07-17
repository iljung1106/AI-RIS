# live2d_controller.py
import asyncio
import pyvts
import threading
import time

class Live2DController:
    """
    VTube Studio와 연동하여 Live2D 모델을 제어하는 클래스.
    - 비동기(asyncio)로 VTube Studio API와 통신합니다.
    - 별도의 스레드에서 이벤트 루프를 실행하여 메인 앱의 블로킹을 방지합니다.
    - 입 모양(MouthOpen) 파라미터를 실시간으로 조절하는 기능을 제공합니다.
    """
    def __init__(self, plugin_name="AI-RIS", plugin_developer="User"):
        self.plugin_info = {
            "plugin_name": plugin_name,
            "developer": plugin_developer,
            "authentication_token_path": "./token.json",
        }
        self.vts = pyvts.vts(plugin_info=self.plugin_info)
        self.is_connected = False
        self.is_running = False
        self.loop = None
        self.thread = None

    async def _connect(self):
        """VTube Studio에 연결하고 인증을 시도합니다."""
        try:
            await self.vts.connect()
            self.is_connected = True
            print("[Live2D] VTube Studio에 성공적으로 연결되었습니다.")
        except Exception as e:
            self.is_connected = False
            print(f"[Live2D] VTube Studio 연결 실패: {e}")
            print("[Live2D] VTube Studio가 실행 중인지, API가 활성화되어 있는지 확인하세요.")

    async def _disconnect(self):
        """VTube Studio와의 연결을 종료합니다."""
        if self.is_connected:
            await self.vts.close()
            self.is_connected = False
            print("[Live2D] VTube Studio 연결이 종료되었습니다.")

    async def set_mouth_open(self, value: float):
        """
        Live2D 모델의 입 벌리기(MouthOpen) 파라미터를 설정합니다.

        Args:
            value (float): 입 벌리기 정도 (0.0 ~ 1.0).
        """
        if not self.is_connected:
            return

        try:
            # pyvts 0.3.3 문서에 따라 인자 이름을 parameter와 value로 수정
            await self.vts.request(
                self.vts.vts_request.requestSetParameterValue(
                    parameter="MouthOpen",
                    value=max(0.0, min(1.0, value)) # 값을 0~1 사이로 제한
                )
            )
        except Exception as e:
            print(f"[Live2D] 입 모양 파라미터 설정 중 오류: {e}")
            # 연결이 끊겼을 수 있으므로 상태 업데이트
            self.is_connected = False


    def _run_loop(self):
        """비동기 이벤트 루프를 실행합니다."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        # 루프가 실행되는 동안 connect를 먼저 시도
        self.loop.run_until_complete(self._connect())
        
        # 루프를 계속 실행하여 다른 비동기 함수 호출을 처리
        self.loop.run_forever()

    def start(self):
        """별도의 스레드에서 Live2D 컨트롤러를 시작합니다."""
        if self.is_running:
            print("[Live2D] 컨트롤러가 이미 실행 중입니다.")
            return
            
        print("[Live2D] 컨트롤러 스레드를 시작합니다.")
        self.is_running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        time.sleep(2) # 스레드가 시작되고 연결을 시도할 시간을 줍니다.

    def stop(self):
        """Live2D 컨트롤러를 중지합니다."""
        if not self.is_running:
            return
            
        print("[Live2D] 컨트롤러 스레드를 중지합니다.")
        self.is_running = False
        if self.loop:
            # 루프에 _disconnect를 스케줄링하고 루프를 중지
            self.loop.call_soon_threadsafe(
                lambda: asyncio.ensure_future(self._disconnect(), loop=self.loop)
            )
            self.loop.call_soon_threadsafe(self.loop.stop)
        
        if self.thread:
            self.thread.join(timeout=2)

# --- 테스트용 코드 ---
if __name__ == '__main__':
    controller = Live2DController()
    controller.start()

    try:
        if controller.is_connected:
            print("\n[테스트] 5초 동안 입을 열었다 닫습니다.")
            for i in range(50):
                # sin 함수를 사용하여 부드럽게 입을 움직임
                mouth_value = (1 + 1) / 2 * abs(i % 20 - 10) / 10
                # 비동기 함수를 스레드 안전하게 호출
                asyncio.run_coroutine_threadsafe(
                    controller.set_mouth_open(mouth_value),
                    controller.loop
                )
                time.sleep(0.1)
            
            # 마지막에 입을 닫음
            asyncio.run_coroutine_threadsafe(
                controller.set_mouth_open(0),
                controller.loop
            )
            print("[테스트] 테스트 완료.")
        else:
            print("\n[테스트] VTube Studio에 연결되지 않아 테스트를 스킵합니다.")

    except KeyboardInterrupt:
        print("사용자에 의해 중단됨.")
    finally:
        controller.stop()
        print("프로그램 종료.")
