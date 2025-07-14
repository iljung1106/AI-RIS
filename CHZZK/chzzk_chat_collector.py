import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

class ChzzkChatScraper:
    """
    치지직(Chzzk) 방송의 오버레이 채팅을 주기적으로 수집하는 클래스.

    Selenium을 사용하여 백그라운드(헤드리스)에서 웹페이지를 동적으로 로드하고,
    BeautifulSoup으로 채팅 내용을 파싱합니다.

    사용 예시:
        url = "https://chzzk.naver.com/widget/chat/{channelId}"
        scraper = ChzzkChatScraper(url)
        
        try:
            while True:
                chats = scraper.get_latest_chats()
                for chat in chats:
                    print(f"[{chat['user']}] {chat['message']}")
                time.sleep(1)
        finally:
            scraper.close()
    """

    def __init__(self, url: str):
        """
        스크레이퍼를 초기화하고 웹 드라이버를 설정합니다.

        :param url: 치지직 채팅 오버레이 URL (예: https://chzzk.naver.com/widget/chat/{channelId})
        """
        self.url = url
        
        # Selenium 웹 드라이버 옵션 설정
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")  # 브라우저 창을 띄우지 않는 헤드리스 모드
        options.add_argument("--disable-gpu")  # GPU 가속 비활성화 (헤드리스에서 권장)
        options.add_argument("--no-sandbox")   # 샌드박스 비활성화 (리눅스/도커 환경에서 필요할 수 있음)
        options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

        print("웹 드라이버를 초기화하는 중입니다...")
        
        # webdriver-manager를 통해 ChromeDriver를 자동으로 설치하고 서비스 시작
        service = ChromeService(executable_path=ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        
        print(f"'{self.url}' 페이지에 연결 중...")
        self.driver.get(self.url)
        
        # 페이지가 완전히 로드될 때까지 잠시 대기
        time.sleep(3)
        print("연결 완료. 채팅 수집을 시작할 수 있습니다.")

    def get_latest_chats(self, limit: int = 20) -> list[dict]:
        """
        현재 페이지에서 최신 채팅 메시지를 가져옵니다.

        :param limit: 가져올 최대 채팅 개수
        :return: 사용자 이름과 메시지가 담긴 딕셔너리의 리스트
                 예: [{'user': '한가운데', 'message': '안녕하세요'}, ...]
        """
        try:
            # 현재 페이지의 HTML 소스를 가져옴
            html = self.driver.page_source
            soup = BeautifulSoup(html, "html.parser")
            
            # 채팅 메시지가 담긴 컨테이너 요소를 모두 찾음
            # HTML 구조를 분석하여 클래스 이름("live_chatting_message_container__vrI-y")을 특정
            chat_items = soup.select("div.live_chatting_message_container__vrI-y")
            
            parsed_chats = []
            # 찾은 요소들을 순회하며 닉네임과 채팅 내용을 추출
            for item in chat_items:
                try:
                    # 닉네임 추출 (클래스 이름으로 검색)
                    username_elem = item.select_one("span.live_chatting_username_nickname__dDbbj .name_text__yQG50")
                    # 메시지 내용 추출 (클래스 이름으로 검색)
                    message_elem = item.select_one("span.live_chatting_message_text__DyleH")
                    
                    # 닉네임과 메시지가 모두 존재할 경우에만 리스트에 추가
                    if username_elem and message_elem:
                        user = username_elem.get_text(strip=True)
                        message = message_elem.get_text(strip=True)
                        parsed_chats.append({"user": user, "message": message})
                
                except Exception as e:
                    # 개별 채팅 파싱 중 오류 발생 시 건너뛰고 로그 출력
                    print(f"개별 채팅 파싱 중 오류: {e}")

            # 최신 채팅이 HTML 상단에 위치하므로, 원하는 개수만큼 잘라서 반환
            return parsed_chats[:limit]

        except Exception as e:
            print(f"채팅을 가져오는 중 오류가 발생했습니다: {e}")
            return []

    def close(self):
        """
        웹 드라이버를 종료하고 모든 리소스를 해제합니다.
        프로그램 종료 시 반드시 호출해야 합니다.
        """
        if self.driver:
            self.driver.quit()
            print("웹 드라이버가 성공적으로 종료되었습니다.")


# --- 이 모듈을 직접 실행했을 때의 예제 코드 ---
if __name__ == "__main__":
    # 여기에 실제 방송의 채팅 위젯 URL을 입력하세요.
    # URL은 'https://chzzk.naver.com/widget/chat/채널ID' 형식입니다.
    # 예시: 풍월량 님의 채널 ID는 'hanryang1125' 입니다.
    # URL: https://chzzk.naver.com/widget/chat/hanryang1125
    
    # ※ 실제 유효한 채널 ID로 변경해야 합니다.
    TARGET_URL = "https://chzzk.naver.com/chat/aa954e33851f4ecda45ff964305ed59d" 

    # 스크레이퍼 객체 생성
    scraper = ChzzkChatScraper(TARGET_URL)

    # Ctrl+C로 종료 시에도 close()가 호출되도록 try...finally 사용
    try:
        while True:
            # 최신 채팅 20개를 가져옴
            latest_chats = scraper.get_latest_chats(limit=20)
            
            # 가져온 채팅이 있을 경우에만 출력
            if latest_chats:
                print("\n--- 최신 채팅 (최대 20개) ---")
                # 최신 채팅이 맨 위로 오도록 리스트를 뒤집어서 출력
                for chat in reversed(latest_chats):
                    print(f"[{chat['user']}] {chat['message']}")
            else:
                print("수집된 채팅이 없습니다.")
            
            # 1초 대기
            time.sleep(2)

    except KeyboardInterrupt:
        print("\n사용자에 의해 프로그램이 중단되었습니다.")
    finally:
        # 스크레이퍼 종료 (브라우저 종료)
        scraper.close()