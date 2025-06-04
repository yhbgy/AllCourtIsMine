import undetected_chromedriver as uc
from selenium.webdriver.chrome.options import Options
import datetime
import time
import schedule
import logging

import reservationStep
from reservationTarget import ReservationTarget

USER_ID = ""
USER_PW = ""

TEAM_MEMBERS = [
    {"name": "", "contact": ""},
]

logging.basicConfig(
    filename='reservation.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# 드라이버 전역 생성 (로그인 유지용)
options = Options()
# options.add_argument("--headless")
options.add_argument("--disable-gpu")   # (Windows에서 종종 필요)
options.add_argument("--window-size=1920x968")

driver = uc.Chrome(options=options)

def login_only():
    print(f"🔐 [6:55] 로그인 시도: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    reservationStep.login(driver, USER_ID, USER_PW)
    print("✅ 로그인 완료 (세션 유지 중)")

def ping_before_reservation():
    driver.get("https://res.isdc.co.kr/index.do")
    reservationStep.wait_for_netfunnel_release(driver)

# 타임 테이블 받아오기전까지 입력란 채우기
def prepare_reservation_form(driver, team_members):
    print("🚀 사전 준비 시작 (사용자 유형 + 팀원 + 캡차)")
    try:
        reservationStep.select_user_type_personal(driver)
        reservationStep.fill_team_member_info(driver, team_members)

        # OCR 실패해도 무시하고 계속 진행하도록 시도
        captcha_success = reservationStep.fill_captcha_answer(driver)
        if captcha_success:
            print("✅ 캡차 성공 (사전 입력 완료)")
        else:
            print("⚠️ 캡차 실패 (예약 시도 중 다시 입력)")
    except Exception as e:
        print(f"⚠️ 사전 준비 중 오류 발생: {e}")

# 타임 테이블 받아오기
def wait_for_time_slot_and_select(driver, preferred_time_keywords, timeout=30):
    print("⌛️ 시간 슬롯 대기 중...")
    start_time = time.time()

    while time.time() - start_time < timeout:
        try:
            slot = reservationStep.get_clickable_time_slots(driver, preferred_time_keywords)
            if slot:
                print(f"✅ 슬롯 선택됨: {slot['time']}")
                driver.execute_script("arguments[0].click();", slot['label'])
                return slot
        except:
            pass
        time.sleep(1)

    print("❌ 시간 슬롯 대기 실패 (timeout)")
    return None

def run_daily():
    print(f"🕖 예약 매크로 실행 시작: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    targets = [
        ReservationTarget("탄천", None, ["토"], ["9:00"]),
        ReservationTarget("탄천", None, ["일"], ["9:00"]),
        ReservationTarget("탄천", None, ["월"], ["19:00"]),
    ]
    run_macro(driver, targets)

def run_macro(driver, targets):
    logger.info("🎬 예약 매크로 run_macro() 진입")
    first_attempt = True  # 첫 시도 플래그

    for target in targets:
        logger.info(f"🎾 예약 시도: 그룹명={target.group_name}, 키워드={target.court_keyword}")
        print(f"\n🎾 [{target.group_name} / {target.court_keyword}] 예약 시도")
        if not target.fac_ids:
            logger.warning(f"❌ fac_ids 없음 → 스킵: {target.group_name}")
            continue

        for court_name, fac_id in target.fac_ids:
            logger.info(f"⛳️ 코트 시도: {court_name} (fac_id={fac_id})")
            print(f"  ⛳️ 코트 시도: {court_name}")

            try:
                logger.debug("🌐 홈페이지 진입 시작")
                if not first_attempt:
                    driver.get("https://res.isdc.co.kr/index.do")
                    reservationStep.wait_for_netfunnel_release(driver)
                else:
                    first_attempt = False  # 첫 시도 이후로 전환

                # 테니스장 선택
                print("📍 테니스 그룹 선택 시도")
                reservationStep.select_tennis_group(driver, target.group_id)
                reservationStep.wait_for_netfunnel_release(driver)

                # 코트 선택
                print("📍 코트 선택 시도")
                reservationStep.select_court(driver, court_name, fac_id)
                reservationStep.wait_for_netfunnel_release(driver)

                # 비어있는 날짜 선택
                logger.debug("📆 날짜 선택 시작")
                if not reservationStep.select_date_and_proceed(driver, target):
                    reservationStep.wait_for_netfunnel_release(driver)
                    logger.info("❌ 유효한 날짜 없음 → 다음 코트로")
                    continue

                # 사용자 정보 및 캡차 먼저 입력
                time.sleep(1)
                prepare_reservation_form(driver, TEAM_MEMBERS)

                # 시간 슬롯이 나타날 때까지 대기하면서 선택
                slot = wait_for_time_slot_and_select(driver, target.preferred_time_keywords)

                if slot:
                    result = reservationStep.submit_reservation(driver)
                    if result:
                        print("🎉 예약 성공!")
                        logger.info("🎉 예약 성공 → 종료")
                        return  # targets 반복문 완전히 종료
                    else:
                        print("❌ 예약 버튼 클릭 실패")
                        logger.warning("❌ 예약 버튼 클릭 실패")
                else:
                    print("❌ 예약 가능한 시간대가 없습니다.")
                    logger.info("❌ 예약 가능한 시간대 없음")

            except Exception as e:
                print(f"🚫 실패: {e}")
                logger.error(f"🚫 예외 발생: {e}", exc_info=True)
                continue

    logger.info("🛑 모든 대상 예약 시도 완료 → 종료 대기")
    input("\n⏸ 완료. Enter 누르면 종료됩니다.")
    driver.quit()

if __name__ == "__main__":
    # 로그인 먼저
    # schedule.every().day.at("06:55").do(login_only)

    # 새로고침
    # schedule.every().day.at("06:58").do(ping_before_reservation)

    # 예약은 7시부터
    # schedule.every().day.at("07:00").do(run_daily)

    TARGETS = [
        ReservationTarget("희망대", None, ["토"], ["20:00"]),
    ]
    login_only()
    ping_before_reservation()
    run_macro(driver, TARGETS)

    print("🔁 스케줄러가 실행 중입니다. 매일 07:00에 예약을 시도합니다.")
    while True:
        schedule.run_pending()
        time.sleep(1)