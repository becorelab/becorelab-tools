#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""이지어드민(ACG) 수동발주 자동화 — 파일 업로드 → step1~5 완주 → '발주 완료' 확인.

2026-07-16 실검증 완료: 에어밤20+가죽홀더10 사무실 실발주가 확장주문검색2에 정확 반영됨.

엔진 무관 (클로드/오퍼스/코덱스 공용). 파이썬 CLI 도구.

사용:
  python3 ezadmin_order.py <xls파일경로>                    # 수동판매처(10287)에 발주
  python3 ezadmin_order.py <파일> --seller-code 10287       # 판매처 코드 지정
  python3 ezadmin_order.py <파일> --dry-run                 # 업로드만(step1) 하고 완주 안 함

핵심 노하우 (2026-07-16 하루 종일 뚫은 것):
  - 캡차: Claude Vision (ezadmin_scraper._read_captcha_with_vision)
  - 발주페이지 진입: move_page35('DC10') JS함수 (URL 직접=mysqli에러)
  - 광고팝업: #pagecode-popup 등 MutationObserver 실시간 차단 (하나 닫으면 또 뜸)
  - 업로드 모달: .upload_file[rowid=N] span 클릭 → 모달 → input[type=file] set → '업로드'
    ⚠️ 광고차단 감시자가 .modal-dialog 지우면 업로드 모달도 죽음 → 광고 id만 콕 집어 제거
  - 완주: span#next (id로 클릭. 텍스트 '다 음 '은 특수공백이라 텍스트매칭 실패)
  - step3 매칭: 그리드에 데이터행 뜨면 = 미매칭 → 중단하고 사람 확인 (오배송 방지)

⚠️ 실제 물류 출고가 나감. 파일 내용(수취인·주소·수량) 반드시 사전 검수.
"""
import sys, os, time, argparse
sys.path.insert(0, "/Users/macmini_ky/ClaudeAITeam/logistics")
from playwright.sync_api import sync_playwright
import ezadmin_scraper as ez

# 판매처 코드 → DC10 그리드 rowid 매핑 (2026-07-16 기준, 판매처 추가되면 갱신)
SELLER_ROWID = {"10287": 15, "10289": 14}  # 수동판매처, 밀크런수동


def _ad_guard(page):
    """광고 팝업 실시간 차단 감시자 (업로드 모달 .modal-dialog는 보존)"""
    try:
        page.evaluate("""() => { if(window.__ad) return;
            const kill=()=>document.querySelectorAll('#pagecode-popup,.pagecode-popup-cont,[id^=modalRequired]').forEach(e=>e.remove());
            kill(); window.__ad=new MutationObserver(kill);
            window.__ad.observe(document.documentElement,{childList:true,subtree:true});}""")
    except Exception:
        pass


def place_order(xls_path, seller_code="10287", dry_run=False, headless=False):
    """반환: (성공여부, 메시지, 상태). 상태 ∈ {done, uploaded, unmatched, error}"""
    if not os.path.exists(xls_path):
        return False, f"파일 없음: {xls_path}", "error"
    rowid = SELLER_ROWID.get(seller_code)
    if rowid is None:
        return False, f"판매처코드 {seller_code} rowid 미등록 (SELLER_ROWID 갱신 필요)", "error"

    dialogs = []
    with sync_playwright() as p:
        browser, ctx, page = ez.get_browser(p)
        page.on("dialog", lambda d: (dialogs.append(d.message), d.accept()))
        try:
            ez.ezadmin_login(page)
            ez.wait_for_captcha(page, timeout_sec=60)
            time.sleep(2); ez.clear_popups(page); time.sleep(1)
            page.evaluate("move_page35('DC10')"); time.sleep(6)
            ez.clear_popups(page); _ad_guard(page); time.sleep(1)

            # ── step1: 업로드 모달 → 파일첨부 → 업로드 ──
            page.click(f'.upload_file[rowid="{rowid}"]', timeout=10000); time.sleep(2)
            fis = page.query_selector_all("input[type=file]")
            if not fis:
                return False, "업로드 모달 file input 없음", "error"
            fis[0].set_input_files(xls_path); time.sleep(1.5)
            page.evaluate("""() => {const b=[...document.querySelectorAll('.modal-dialog button,.modal-dialog a,.modal-dialog span')].find(e=>(e.innerText||'').trim()==='업로드'); if(b)b.click();}""")
            time.sleep(4)
            up_msg = next((d for d in dialogs if "발주하" in d or "업로드" in d), "")
            if dry_run:
                return True, f"업로드만 완료 (dry-run): {up_msg[:40]}", "uploaded"

            # ── step1~5 완주 (span#next 반복) ──
            ez.clear_popups(page); time.sleep(1)
            # 판매처 체크
            page.evaluate(f"""() => {{for(const tr of document.querySelectorAll('tr')){{if(tr.innerText.includes('_수동')&&tr.innerText.includes('{seller_code}')){{const cb=tr.querySelector('input[type=checkbox]');if(cb&&!cb.checked)cb.click();}}}}}}""")
            time.sleep(1)
            for i, label in enumerate(["발주확인", "메모", "매칭", "합포"], 1):
                # step3(매칭, i==3): 미매칭 데이터행 검사
                if i == 3:
                    unmatched = page.evaluate("""() => {
                        for(const t of document.querySelectorAll('table')){
                            const h=t.innerText.slice(0,200);
                            if(h.includes('관리번호')&&h.includes('매칭')){
                                return [...t.querySelectorAll('tr')].filter(r=>{const td=r.querySelectorAll('td');return td.length>3&&/\\d/.test(td[0]?.innerText||'')}).length;
                            }
                        }
                        return 0;
                    }""")
                    if unmatched and unmatched > 0:
                        return False, f"⛔ step3 매칭: 미매칭 상품 {unmatched}행 — 사람 확인 필요 (오배송 방지)", "unmatched"
                try:
                    page.click("#next", timeout=6000)
                except Exception as e:
                    return False, f"step{i}({label}) 다음 클릭 실패: {str(e)[:40]}", "error"
                time.sleep(2)
                try: page.wait_for_load_state("networkidle", timeout=12000)
                except Exception: pass
                time.sleep(2); _ad_guard(page); ez.clear_popups(page); time.sleep(1)

            time.sleep(2)
            done = any("완료" in d for d in dialogs)
            return done, ("발주 완료" if done else f"완주 후 완료 미확인. dialogs={dialogs[-2:]}"), ("done" if done else "error")
        except Exception as e:
            page.screenshot(path="/tmp/ezadmin_order_err.png")
            return False, f"예외: {str(e)[:80]}", "error"
        finally:
            time.sleep(1); browser.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("xls_path")
    ap.add_argument("--seller-code", default="10287")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--headless", action="store_true")
    a = ap.parse_args()
    ok, msg, state = place_order(a.xls_path, a.seller_code, a.dry_run, a.headless)
    print(("✅ " if ok else "❌ ") + f"[{state}] {msg}")
    sys.exit(0 if ok else 1)
