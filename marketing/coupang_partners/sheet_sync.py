"""구글 시트 ↔ 파이프라인 동기화 모듈.

'후보 리스트' 시트를 읽고 쓰는 함수 모음.
열 구조: A=번호, B=채널명, C=구독자, D=카테고리, E=추천제품,
         F=선정이유, G=채널URL, H=이메일, I=쿠팡파트너스,
         J=승인, K=메모, L=상태, M=발송일, N=Message-ID
"""
from __future__ import annotations

import sys

sys.stdout.reconfigure(encoding="utf-8")

import logging
from datetime import datetime

import gspread
from google.oauth2.service_account import Credentials

from config import (
    STATUS_CONTACTED,
    STATUS_REPLIED,
    STATUS_SCREENED,
)

logger = logging.getLogger(__name__)

# ── 시트 상수 ──────────────────────────────────────────────
SHEET_ID = "1x3uiTImNWPoS03HRfzHDeNSeKa2PynpzdShbgY5hOSs"
SHEET_NAME = "후보 리스트"
KEY_PATH = (
    r"C:\Users\info\claudeaiteam\sourcing\analyzer"
    r"\becorelab-tools-firebase-adminsdk-fbsvc-c665234c8b.json"
)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# 열 인덱스 (0-based, 시트 A열 = 0)
COL = {
    "번호": 0,
    "채널명": 1,
    "구독자": 2,
    "카테고리": 3,
    "추천제품": 4,
    "선정이유": 5,
    "채널URL": 6,
    "이메일": 7,
    "쿠팡파트너스": 8,
    "승인": 9,
    "메모": 10,
    "상태": 11,
    "발송일": 12,
    "Message-ID": 13,
}

HEADER_LABELS = list(COL.keys())


# ── 인증 & 워크시트 ────────────────────────────────────────
def _get_worksheet() -> gspread.Worksheet:
    """서비스 계정으로 인증 후 '후보 리스트' 워크시트 반환."""
    creds = Credentials.from_service_account_file(KEY_PATH, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(SHEET_ID)
    return sh.worksheet(SHEET_NAME)


def _row_to_dict(row: list[str], row_num: int) -> dict:
    """시트 한 행(list)을 dict로 변환. row_num은 시트 기준 행번호(1-based)."""
    # 열이 부족하면 빈 문자열로 패딩
    padded = row + [""] * (len(HEADER_LABELS) - len(row))
    d = {label: padded[i] for i, label in enumerate(HEADER_LABELS)}
    d["_row_num"] = row_num  # 업데이트용
    return d


# ── 공개 API ───────────────────────────────────────────────


def get_approved_unsent() -> list[dict]:
    """J열='승인' AND (L열 비어있거나 'screened')인 행을 반환.

    승인됐지만 아직 메일 발송 안 된 유튜버 목록.
    """
    ws = _get_worksheet()
    rows = ws.get_all_values()

    results = []
    for i, row in enumerate(rows):
        if i == 0:  # 헤더 스킵
            continue
        row_num = i + 1  # 시트 행번호 (1-based)
        padded = row + [""] * (len(HEADER_LABELS) - len(row))
        approval = padded[COL["승인"]].strip()
        status = padded[COL["상태"]].strip()

        if approval == "승인" and (status == "" or status == STATUS_SCREENED):
            results.append(_row_to_dict(row, row_num))

    logger.info("get_approved_unsent: %d건", len(results))
    return results


def update_status(
    row_num: int,
    status: str,
    sent_at: str | None = None,
    message_id: str | None = None,
) -> None:
    """특정 행의 L열(상태), M열(발송일), N열(Message-ID) 업데이트.

    Args:
        row_num: 시트 행번호 (1-based, 헤더=1이므로 데이터는 2~)
        status: 새 상태 값 (e.g. 'contacted')
        sent_at: 발송 일시 문자열 (e.g. '2026-04-17 14:30')
        message_id: 이메일 Message-ID 헤더 값
    """
    ws = _get_worksheet()

    # L열 = 12번째(1-based), M열 = 13, N열 = 14
    col_status = COL["상태"] + 1   # gspread는 1-based
    col_sent = COL["발송일"] + 1
    col_msgid = COL["Message-ID"] + 1

    ws.update_cell(row_num, col_status, status)
    if sent_at is not None:
        ws.update_cell(row_num, col_sent, sent_at)
    if message_id is not None:
        ws.update_cell(row_num, col_msgid, message_id)

    logger.info("update_status: row %d → %s", row_num, status)


def append_candidates(candidates: list[dict]) -> None:
    """후보 리스트 시트에 새 후보들을 추가.

    Args:
        candidates: dict 리스트. 각 dict 키:
            name, subscriber_count, category, products,
            rationale, channel_url, email, has_coupang_partners
    """
    ws = _get_worksheet()
    existing = ws.get_all_values()

    # 다음 번호 계산 (헤더 제외, 빈 행 대비)
    max_num = 0
    for row in existing[1:]:
        try:
            max_num = max(max_num, int(row[COL["번호"]]))
        except (ValueError, IndexError):
            pass

    new_rows = []
    for idx, c in enumerate(candidates, start=max_num + 1):
        products = c.get("products", "")
        if isinstance(products, list):
            products = ", ".join(products)

        new_rows.append([
            str(idx),                                     # A 번호
            c.get("name", ""),                            # B 채널명
            str(c.get("subscriber_count", "")),           # C 구독자
            c.get("category", ""),                        # D 카테고리
            products,                                     # E 추천제품
            c.get("rationale", ""),                       # F 선정이유
            c.get("channel_url", ""),                     # G 채널URL
            c.get("email", ""),                           # H 이메일
            c.get("has_coupang_partners", ""),             # I 쿠팡파트너스
            "",                                           # J 승인 (빈칸)
            "",                                           # K 메모
            STATUS_SCREENED,                              # L 상태
            "",                                           # M 발송일
            "",                                           # N Message-ID
        ])

    if not new_rows:
        logger.info("append_candidates: 추가할 후보 없음")
        return

    # 기존 데이터 마지막 행 다음에 추가
    start_row = len(existing) + 1
    end_col = chr(ord("A") + len(HEADER_LABELS) - 1)  # 'N'
    cell_range = f"A{start_row}:{end_col}{start_row + len(new_rows) - 1}"
    ws.update(values=new_rows, range_name=cell_range)

    logger.info("append_candidates: %d건 추가 (행 %d~)", len(new_rows), start_row)


def get_all_contacted() -> list[dict]:
    """L열='contacted'인 행 전부 반환 (발송했으나 미답변)."""
    ws = _get_worksheet()
    rows = ws.get_all_values()

    results = []
    for i, row in enumerate(rows):
        if i == 0:
            continue
        row_num = i + 1
        padded = row + [""] * (len(HEADER_LABELS) - len(row))
        status = padded[COL["상태"]].strip()

        if status == STATUS_CONTACTED:
            results.append(_row_to_dict(row, row_num))

    logger.info("get_all_contacted: %d건", len(results))
    return results


def update_reply_status(row_num: int, replied_at: str) -> None:
    """L열을 'replied'로, 메모에 답변 일시 추가.

    Args:
        row_num: 시트 행번호 (1-based)
        replied_at: 답변 수신 일시 문자열
    """
    ws = _get_worksheet()

    col_status = COL["상태"] + 1
    col_memo = COL["메모"] + 1

    # 기존 메모 읽고 뒤에 추가
    existing_memo = ws.cell(row_num, col_memo).value or ""
    separator = " | " if existing_memo else ""
    new_memo = f"{existing_memo}{separator}답변수신: {replied_at}"

    ws.update_cell(row_num, col_status, STATUS_REPLIED)
    ws.update_cell(row_num, col_memo, new_memo)

    logger.info("update_reply_status: row %d → replied (%s)", row_num, replied_at)


# ── CLI 테스트 ─────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    print("=== 승인-미발송 목록 ===")
    for c in get_approved_unsent():
        print(f"  [{c['_row_num']}] {c['채널명']} ({c['구독자']}) — {c['상태']}")

    print("\n=== 컨택 완료(미답변) 목록 ===")
    for c in get_all_contacted():
        print(f"  [{c['_row_num']}] {c['채널명']} — 발송: {c['발송일']}")

    print("\n완료!")
