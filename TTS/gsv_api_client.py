# gsv_api_client.py
import requests
import json

class GPTSoVITSClient:
    """
    GPT-SoVITS WebAPI와 상호작용하기 위한 Python 클라이언트입니다.
    """
    def __init__(self, host: str = "127.0.0.1", port: int = 9880):
        """
        클라이언트를 초기화합니다.

        Args:
            host (str): API 서버의 호스트 주소.
            port (int): API 서버의 포트 번호.
        """
        self.base_url = f"http://{host}:{port}"
        print(f"GPT-SoVITS 클라이언트가 다음 주소로 초기화되었습니다: {self.base_url}")

    def _make_request(self, method: str, endpoint: str, params: dict = None, json_data: dict = None, stream: bool = False):
        """내부적으로 API 요청을 처리하는 헬퍼 함수"""
        url = self.base_url + endpoint
        try:
            if method.upper() == 'GET':
                response = requests.get(url, params=params, stream=stream)
            elif method.upper() == 'POST':
                response = requests.post(url, json=json_data, stream=stream)
            else:
                raise ValueError("지원되지 않는 HTTP 메소드입니다.")

            # 실패 시 예외 발생 (4xx, 5xx 상태 코드)
            response.raise_for_status()
            return response

        except requests.exceptions.RequestException as e:
            print(f"API 요청 중 오류 발생: {e}")
            # 서버에서 보낸 JSON 오류 메시지가 있다면 출력
            try:
                error_details = response.json()
                print(f"서버 응답: {error_details.get('message', error_details)}")
            except (json.JSONDecodeError, AttributeError):
                pass
            return None

    def tts(self,
            text: str,
            text_lang: str,
            ref_audio_path: str,
            prompt_lang: str,
            prompt_text: str = "",
            output_path: str = None,
            streaming_mode: bool = False,
            **kwargs):
        """
        TTS(Text-to-Speech)를 실행하여 오디오를 생성합니다.

        Args:
            text (str): 음성으로 변환할 텍스트 (필수).
            text_lang (str): `text`의 언어 (예: "zh", "en", "ja") (필수).
            ref_audio_path (str): 음색을 참고할 오디오 파일의 *서버 내 경로* (필수).
            prompt_lang (str): `prompt_text`의 언어 (필수).
            prompt_text (str): 참고 오디오의 텍스트 (선택).
            output_path (str): 생성된 오디오를 저장할 파일 경로. 지정하지 않으면 오디오 데이터를 바이트로 반환합니다.
                                 (스트리밍 모드에서는 무시됩니다)
            streaming_mode (bool): 스트리밍 응답을 받을지 여부.
            **kwargs: top_k, top_p, temperature, speed_factor 등 API에서 지원하는 추가 파라미터.

        Returns:
            - output_path가 지정된 경우: 성공 시 True, 실패 시 False.
            - output_path가 없고 streaming_mode=False인 경우: 오디오 데이터 (bytes).
            - streaming_mode=True인 경우: 오디오 청크를 반환하는 제너레이터.
            - 오류 발생 시: None.
        """
        payload = {
            "text": text,
            "text_lang": text_lang.lower(),
            "ref_audio_path": ref_audio_path,
            "prompt_text": prompt_text,
            "prompt_lang": prompt_lang.lower(),
            "streaming_mode": streaming_mode,
            **kwargs
        }
        
        # 기본값과 다른 파라미터만 출력하여 간결하게 표시
        print(f"/tts 요청: text='{text[:20]}...', ref='{ref_audio_path}'")
        
        response = self._make_request('POST', '/tts', json_data=payload, stream=streaming_mode)

        if response is None:
            return None if streaming_mode else (False if output_path else None)

        if streaming_mode:
            print("스트리밍 모드로 오디오 데이터를 수신합니다...")
            return response.iter_content(chunk_size=4096)
        else:
            print("오디오 데이터를 다운로드합니다...")
            audio_data = response.content
            if output_path:
                try:
                    with open(output_path, 'wb') as f:
                        f.write(audio_data)
                    print(f"오디오가 '{output_path}'에 성공적으로 저장되었습니다.")
                    return True
                except IOError as e:
                    print(f"파일 저장 중 오류 발생: {e}")
                    return False
            else:
                return audio_data

    def control(self, command: str) -> bool:
        """
        서버를 제어합니다 ('restart' 또는 'exit').

        Args:
            command (str): 실행할 명령어 ("restart" 또는 "exit").

        Returns:
            bool: 성공 여부.
        """
        print(f"/control 요청: command='{command}'")
        if command not in ["restart", "exit"]:
            print("오류: command는 'restart' 또는 'exit'여야 합니다.")
            return False
        
        response = self._make_request('GET', '/control', params={"command": command})
        return response is not None

    def set_gpt_weights(self, weights_path: str) -> bool:
        """
        GPT 모델 가중치를 변경합니다.

        Args:
            weights_path (str): 새로운 GPT 모델 가중치 파일의 *서버 내 경로*.

        Returns:
            bool: 성공 여부.
        """
        print(f"/set_gpt_weights 요청: path='{weights_path}'")
        response = self._make_request('GET', '/set_gpt_weights', params={"weights_path": weights_path})
        if response and response.status_code == 200:
            print("GPT 가중치가 성공적으로 변경되었습니다.")
            return True
        return False

    def set_sovits_weights(self, weights_path: str) -> bool:
        """
        SoVITS 모델 가중치를 변경합니다.

        Args:
            weights_path (str): 새로운 SoVITS 모델 가중치 파일의 *서버 내 경로*.

        Returns:
            bool: 성공 여부.
        """
        print(f"/set_sovits_weights 요청: path='{weights_path}'")
        response = self._make_request('GET', '/set_sovits_weights', params={"weights_path": weights_path})
        if response and response.status_code == 200:
            print("SoVITS 가중치가 성공적으로 변경되었습니다.")
            return True
        return False