from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import UnexpectedAlertPresentException, NoAlertPresentException
import time
import datetime

from captcha_solver import extract_captcha_text
from reservationTarget import ReservationTarget

# 로딩 기다리기
def wait_for(driver, by, value, timeout=10):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))

# 대기화면 기다리기
def wait_for_netfunnel_release(driver, timeout=300):
    """NetFunnel 대기 팝업이 사라질 때까지 대기"""
    try:
        print("⏳ NetFunnel 접속 대기 감지됨 → 대기 시작")
        WebDriverWait(driver, timeout).until_not(
            EC.presence_of_element_located((By.ID, "NetFunnel_Loading_Popup"))
        )
        print("✅ NetFunnel 대기 종료 → 자동화 시작")
        return True
    except:
        print("❌ NetFunnel 대기가 timeout 내 종료되지 않음")
        return False

# 1. 로그인
def login(driver, user_id, user_pw):
    driver.get("https://res.isdc.co.kr/login.do")

    wait_for_netfunnel_release(driver)

    wait_for(driver, By.ID, "web_id")
    driver.find_element(By.ID, "web_id").send_keys(user_id)
    driver.find_element(By.ID, "web_pw").send_keys(user_pw)
    driver.find_element(By.ID, "btn_login").click()
    wait_for(driver, By.XPATH, "//a[contains(text(), '로그아웃')]")
    print("🔐 로그인 완료")

# 2. 테니스장 선택
def select_tennis_group(driver, group_id):
    xpath = f"//form[@id='tennisGroupForm' and .//input[@value='{group_id}']]"
    wait_for(driver, By.XPATH, xpath)
    driver.find_element(By.XPATH, xpath).submit()

# 3. 테니스 코트 선택
def select_court(driver, court_keyword, fac_id):
    xpath = f"//li[contains(@class, 'facilityInfo') and contains(., '{court_keyword}')]//form"
    wait_for(driver, By.XPATH, xpath)
    form = driver.find_element(By.XPATH, xpath)
    input_el = form.find_element(By.NAME, "facId")
    driver.execute_script("arguments[0].value = arguments[1];", input_el, fac_id)
    form.submit()

# 4-1. 비어있는 날짜 있는지 확인
def find_reservable_dates(driver, target: ReservationTarget):
    elements = driver.find_elements(By.XPATH,
        "//span[contains(@class, 'usedate') and " +
        "not(contains(@class, 'fulldate')) and " +
        "not(contains(@class, 'notusedate'))]"
    )

    results = []
    for el in elements:
        date_id = el.get_attribute("id")
        try:
            year, month, day = map(int, date_id.split('-'))
            dt = datetime.date(year, month, day)
            if dt.weekday() in target.target_weekdays:
                results.append((date_id, el.text, dt.strftime('%A')))
        except:
            continue
    return results

# 4-2. 비어있는 날짜 선택
def select_date_and_proceed(driver, target: ReservationTarget):
    valid_dates = find_reservable_dates(driver, target)
    print(f"🎯 [{target.group_name}/{target.court_keyword}] 타겟 요일: {target.raw_weekdays} → {target.target_weekdays}")

    if not valid_dates:
        print("❌ 일정한 요일에 적절한 날짜가 없습니다.")
        return False

    date_id = valid_dates[0][0]
    driver.execute_script("document.getElementById(arguments[0]).click();", date_id)
    wait_for(driver, By.ID, "move_reservation")
    driver.find_element(By.ID, "move_reservation").click()
    print(f"✅ 날짜 선택 + 예약하러가기 클릭 완료: {date_id} ({valid_dates[0][2]})")
    return True

# 5-1. 시간 파싱
def parse_time(text):
    try:
        return datetime.strptime(text.strip(), "%H:%M").time()
    except:
        return None

# 5-2. 시간 비어있는지 확인
def get_clickable_time_slots(driver, preferred_keywords):
    wait_for(driver, By.ID, "timeTable")
    rows = driver.find_elements(By.XPATH, '//*[@id="timeTable"]/table/tbody/tr[position()>1]')

    available_slots = []
    for row in rows:
        tds = row.find_elements(By.TAG_NAME, "td")
        reserver = tds[3].text.strip() if len(tds) > 3 else ""
        radio_inputs = tds[0].find_elements(By.XPATH, ".//input[@type='radio']")
        if not reserver and radio_inputs:
            input_elem = radio_inputs[0]
            label_elem = tds[0].find_element(By.TAG_NAME, "label")
            time_range = tds[2].text.strip()
            available_slots.append({
                "input_id": input_elem.get_attribute("id"),
                "value": input_elem.get_attribute("value"),
                "time": time_range,
                "label": label_elem
            })

    # 우선 정확 일치 시도
    for keyword in preferred_keywords:
        for slot in available_slots:
            start_time = slot["time"].split("~")[0].strip()
            if keyword == start_time:
                return slot

    # 범위 내 포함 시도
    for keyword in preferred_keywords:
        target_time = parse_time(keyword)
        for slot in available_slots:
            try:
                start, end = map(parse_time, slot["time"].split("~"))
                if start and end and start <= target_time <= end:
                    return slot
            except:
                continue

    return None

# 6. 개인 라디오 버튼 선택
def select_user_type_personal(driver):
    try:
        label = driver.find_element(By.CSS_SELECTOR, "label[for='userType-P']")
        driver.execute_script("arguments[0].click();", label)
        print("✅ 사용자 유형: 개인 선택 완료")
    except Exception as e:
        print(f"⚠️ 사용자 유형 선택 실패: {e}")

# 7. 멤버 정보 입력
def fill_team_member_info(driver, team_members):
    try:
        # team_members는 "user2"부터 입력할 인원만 포함해야 함
        headcount_input = driver.find_element(By.ID, "headcount")
        headcount_input.click()  # 사용자 클릭 시뮬레이션
        headcount_input.clear()
        headcount_input.send_keys(str(len(team_members) + 1))  # +1 for 예약자
        print(f"✅ 예상 인원 입력 완료: {len(team_members) + 1}명 (예약자 포함)")
        time.sleep(2)

        for idx, member in enumerate(team_members):
            i = idx + 2  # 시작을 user2부터
            name_field_id = f"user{i}"
            contact_field_id = f"user{i}_contact"

            try:
                name_input = driver.find_element(By.ID, name_field_id)
                contact_input = driver.find_element(By.ID, contact_field_id)

                name_input.clear()
                name_input.send_keys(member["name"])
                time.sleep(2)
                contact_input.clear()
                contact_input.send_keys(member["contact"])
                time.sleep(2)

                print(f"  - 팀원{i} 입력 완료: {member['name']} / {member['contact']}")
            except Exception as e:
                print(f"⚠️ 팀원{i} 입력 실패: {e}")
    except Exception as e:
        print(f"⚠️ 예상 인원 또는 팀원 입력 중 오류: {e}")

def fill_captcha_answer(driver):
    attempt = 0

    while True:
        digits = extract_captcha_text(driver, attempt)

        if digits and len(digits) == 6:
            answer_input = driver.find_element(By.ID, "answer")
            answer_input.clear()
            answer_input.send_keys(digits)
            print(f"✅ 캡차 입력: {digits}")

            # 확인 버튼 클릭
            driver.find_element(By.ID, "check").click()

            # 알림 기다리고 판단
            try:
                WebDriverWait(driver, 2).until(EC.alert_is_present())
                alert = driver.switch_to.alert
                alert_text = alert.text
                print(f"🔔 알림 감지: {alert_text}")

                if "일치하지 않습니다" in alert_text:
                    alert.accept()
                    print("❌ 캡차 틀림 → 새로고침 후 재시도")

                elif "확인되었습니다" in alert_text:
                    alert.accept()
                    print("✅ 캡차 성공 → 예약 버튼 클릭")
                    
                    time.sleep(2)

                    wait_for(driver, By.ID, "btnReservation1")
                    driver.find_element(By.ID, "btnReservation1").click()

                    # ✅ 예약 성공 알림 확인
                    try:
                        WebDriverWait(driver, 5).until(EC.alert_is_present())
                        final_alert = driver.switch_to.alert
                        final_msg = final_alert.text
                        print(f"🟢 최종 알림: {final_msg}")
                        final_alert.accept()

                        if "예약되었습니다" in final_msg:
                            return True
                        else:
                            return False
                    except Exception as e:
                        print(f"⚠️ 예약 알림 확인 실패: {e}")
                        return False

                else:
                    alert.accept()
                    print(f"⚠️ 예외적 알림 발생: '{alert_text}' → 중단")
                    return False

            except NoAlertPresentException:
                print("⚠️ 알림 없음 → 비정상 상태로 간주")
                return False

        else:
            print("🔁 OCR 실패 or 숫자 미일치 → 새로고침 진행")

        # 새로고침
        try:
            old_src = driver.find_element(By.ID, "captcha_img").get_attribute("src")
            driver.find_element(By.ID, "reload").click()

            WebDriverWait(driver, 5).until(
                lambda d: d.find_element(By.ID, "captcha_img").get_attribute("src") != old_src
            )
            time.sleep(0.5)
        except Exception as e:
            print(f"⚠️ 새로고침 실패: {e}")
            return False

        attempt += 1