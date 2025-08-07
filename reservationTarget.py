from dataclasses import dataclass, field
from typing import Optional
import datetime

from tennis_mapping import KOREAN_DAY_TO_WEEKDAY, WEEKDAY_TO_CATEGORY, COURT_FAC_ID_MAP, TENNIS_GROUP_ID_MAP

# 예약 클래스
# group_name: 테니스장. ex) "양지", "탄천", "수내"
# court_keyword: 코트 번호. ex) "1번 코트"
# raw_weekdays: 요일 목록. ex)["금"]
# preferred_time_keywords: 예약 시간대. 시작시간이 입력값이거나 입력값이 포함된 시간대를 선택한다. ex) "16:00"
@dataclass
class ReservationTarget:
    group_name: str
    court_keyword: Optional[str]  # None이면 전체 순회
    raw_weekdays: list[str]
    preferred_time_keywords: list[str] = field(default_factory=list)

    # 내부에서 설정됨
    # 밖에서 입력된 값에 대한 ID
    fac_ids: list[str] = field(init=False)
    group_id: str = field(init=False)
    target_weekdays: list[int] = field(init=False)

    def __post_init__(self):
        self.target_weekdays = [KOREAN_DAY_TO_WEEKDAY[d] for d in self.raw_weekdays]
        self.group_id = TENNIS_GROUP_ID_MAP.get(self.group_name)
        if not self.group_id:
            raise ValueError(f"Group ID를 찾을 수 없습니다: {self.group_name}")

        # 예약 가능 범위: 오늘 ~ 3일 후
        today = datetime.date.today()
        available_dates = [today + datetime.timedelta(days=i) for i in range(4)]
        available_weekdays = {d.weekday() for d in available_dates}
        
        # 예약 가능한 요일만 필터
        self.target_weekdays = [w for w in self.target_weekdays if w in available_weekdays]
        if not self.target_weekdays:
            print(f"⏭ {self.group_name} / {self.court_keyword or '전체'}: 3일 내 예약 가능한 요일 없음 → 건너뜀")
            self.fac_ids = []
            return

        # 18시 이후 시간만 있는 코트 필터링
        evening_only = False
        for time_str in self.preferred_time_keywords:
            try:
                hour = int(time_str.split(":")[0])
                if hour >= 18:
                    evening_only = True
                    break
            except:
                continue

        self.fac_ids = []
        for weekday in self.target_weekdays:
            category = WEEKDAY_TO_CATEGORY[weekday]
            for (group, court, cat), fac in COURT_FAC_ID_MAP.items(): 
                if group != self.group_name:
                    continue

                if self.court_keyword is not None and self.court_keyword not in court:
                    continue

                if cat != category and cat != "any":
                    continue

                # 평일 저녁(18시 이후)인 경우에만 그룹별 제한 적용, 주말엔 제한이 없다
                if evening_only and category == "평일":
                    if self.group_name == "수내":
                        allowed = ["1번 코트", "2번 코트", "3번 코트"]
                    elif self.group_name == "양지":
                        allowed = ["4번 코트", "5번 코트", "6번 코트"]
                    elif self.group_name == "탄천":
                        allowed = ["1번 코트", "2번 코트"]
                    elif self.group_name == "희망대":
                        allowed = ["2번 코트"]
                    else:
                        allowed = None

                    # allowed 리스트가 정의되어 있고, 현재 court가 그 안에 없으면 스킵
                    if allowed is not None and court not in allowed:
                        continue

                self.fac_ids.append((court, fac))
            
        if not self.fac_ids:
            raise ValueError(f"FAC ID를 찾을 수 없습니다: ({self.group_name}, {self.court_keyword}, {self.raw_weekdays})")