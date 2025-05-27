import cv2
import numpy as np
from PIL import Image
import pytesseract
from io import BytesIO
from selenium.webdriver.common.by import By

def preprocess_with_morphology(png_data):
    pil_image = Image.open(BytesIO(png_data)).convert("L")
    img = np.array(pil_image)

    # 반전 (OCR에 유리하게)
    img = cv2.bitwise_not(img)

    # Threshold
    _, bin_img = cv2.threshold(img, 185, 255, cv2.THRESH_BINARY)

    # 수평 줄 제거용 커널 (30픽셀 이상인 줄만 제거)
    horiz_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 1))
    horiz_removed = cv2.morphologyEx(bin_img, cv2.MORPH_OPEN, horiz_kernel)

    N = 12  # 대각선 길이

    # ↘ (우하단)
    diag_kernel = np.eye(N, dtype=np.uint8)
    diag_removed = cv2.morphologyEx(bin_img, cv2.MORPH_OPEN, diag_kernel)

    # ↖ (좌상단)
    anti_diag_kernel = np.fliplr(diag_kernel)
    anti_diag_removed = cv2.morphologyEx(bin_img, cv2.MORPH_OPEN, anti_diag_kernel)

    # ↗ (우상단)
    up_diag_kernel = np.flipud(diag_kernel)
    up_diag_removed = cv2.morphologyEx(bin_img, cv2.MORPH_OPEN, up_diag_kernel)

    # ↙ (좌하단)
    down_diag_kernel = np.flipud(anti_diag_kernel)
    down_diag_removed = cv2.morphologyEx(bin_img, cv2.MORPH_OPEN, down_diag_kernel)

    # 모든 줄 제거
    all_removed = diag_removed | anti_diag_removed | up_diag_removed | down_diag_removed | horiz_removed
    clean = cv2.subtract(bin_img, all_removed)

    # 원본에서 줄만 제거
    no_lines = cv2.subtract(bin_img, all_removed)

    # 다시 반전 (검은 글자, 흰 배경)
    final = cv2.bitwise_not(no_lines)

    return Image.fromarray(final)

def extract_captcha_text(driver, attempt=0):
    try:
        img_elem = driver.find_element(By.ID, "captcha_img")
        png_data = img_elem.screenshot_as_png

        image = preprocess_with_morphology(png_data)

        #image.save(f"debug_captcha_morph_{attempt+1}.png")

        raw_text = pytesseract.image_to_string(
            image, config='--psm 7 -c tessedit_char_whitelist=0123456789'
        ).strip()

        digits = ''.join(filter(str.isdigit, raw_text))
        print(f"🔍 OCR 결과: {raw_text} → 추출된 숫자: {digits}")

        return digits if len(digits) == 6 else None
    except Exception as e:
        print(f"⚠️ 캡차 이미지 처리 실패: {e}")
        return None