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
options.add_argument("--headless")
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

def run_daily():
    print(f"🕖 예약 매크로 실행 시작: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    targets = [
        # ReservationTarget("탄천", None, ["토"], ["9:00"]),
        # ReservationTarget("탄천", None, ["일"], ["9:00"]),
        ReservationTarget("수내", None, ["수"], ["18:00"]),
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

                slot = reservationStep.get_clickable_time_slots(driver, target.preferred_time_keywords)
                if slot:
                    print(f"✅ 예약 가능 시간대: {slot['time']}")
                    logger.info(f"✅ 예약 가능 시간대 발견: {slot['time']}")
                    # 시간 슬롯 선택
                    driver.execute_script("arguments[0].click();", slot['label'])
                    time.sleep(2)

                    # 사용자 유형: 개인 선택
                    reservationStep.select_user_type_personal(driver)
                    time.sleep(2)

                    # 팀원 정보 입력
                    reservationStep.fill_team_member_info(driver, TEAM_MEMBERS)

                    # 캡차 입력
                    logger.debug("🤖 캡차 처리 시작")
                    success = reservationStep.fill_captcha_answer(driver)
                    if success:
                        print("🎉 예약 성공!")
                        logger.info("🎉 예약 성공 → 종료")
                        return
                    else:
                        print("❌ 예약 실패")
                        logger.warning("❌ 예약 실패 → 다음 코트 시도")
                        
                    continue
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
    schedule.every().day.at("06:55").do(login_only)

    # 새로고침
    schedule.every().day.at("06:58").do(ping_before_reservation)

    # 예약은 7시부터
    schedule.every().day.at("07:00").do(run_daily)

    # TARGETS = [
    #     ReservationTarget("수내", None, ["수"], ["14:00"]),
    # ]
    # login_only()
    # ping_before_reservation()
    # run_macro(driver, TARGETS)

    print("🔁 스케줄러가 실행 중입니다. 매일 07:00에 예약을 시도합니다.")
    while True:
        schedule.run_pending()
        time.sleep(1)