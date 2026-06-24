#!/usr/bin/env python3
"""가디언 v1 — 자사몰 손님시점(모바일) 진단. 읽기 전용. 오탐 제거 버전."""
import sys, time, json, os
from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "https://becorelab2.cafe24.com/product/detail.html?product_no=113"
OUT = "/tmp/guardian"
os.makedirs(OUT, exist_ok=True)

R = {"url": URL, "checks": []}
def add(i, t, s, d): R["checks"].append({"id": i, "title": t, "status": s, "detail": d})

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(**p.devices["iPhone 13"], ignore_https_errors=True)
    page = ctx.new_page()
    js_err, bad_resp, mixed = [], [], []
    page.on("console", lambda m: js_err.append(m.text[:120]) if m.type == "error" else None)
    def on_resp(r):
        try:
            if r.status >= 400: bad_resp.append(f"{r.status} {r.url.split('/')[-1][:40]}")
            if r.url.startswith("http://"): mixed.append(r.url[:70])
        except Exception: pass
    page.on("response", on_resp)

    t0 = time.time()
    try:
        page.goto(URL, wait_until="load", timeout=30000); loaded = True
    except Exception as e:
        add("LOAD", "페이지 로드", "FAIL", str(e)[:100]); loaded = False
    load_ms = int((time.time() - t0) * 1000)

    if loaded:
        # 끝까지 스크롤(lazy 이미지 로드 유도) 후 점검
        page.evaluate("()=>new Promise(r=>{let y=0;const t=setInterval(()=>{window.scrollBy(0,1500);y+=1500;if(y>document.body.scrollHeight){clearInterval(t);r()}},80)})")
        page.wait_for_timeout(2500)
        page.screenshot(path=f"{OUT}/mobile.png", full_page=True)

        add("PERF-02", "총 로딩시간(모바일)", "PASS" if load_ms < 4000 else "WARN", f"{load_ms}ms")

        # IMG-01: 진짜 깨진 이미지만 (data URI/페이지URL/lazy미로드/안보이는 것 제외)
        broken = page.evaluate("""()=>{
          return [...document.querySelectorAll('img')].filter(e=>{
            const r=e.getBoundingClientRect();
            return e.complete && e.naturalWidth===0
              && e.src && !e.src.startsWith('data:')
              && !e.src.includes('detail.html') && !e.src.includes('/product/')
              && e.loading!=='lazy'
              && r.width>2 && r.height>2;
          }).map(e=>e.src.split('/').pop().slice(0,40)).slice(0,5);
        }""")
        add("IMG-01", "이미지 깨짐", "PASS" if not broken else "FAIL", (f"{len(broken)}개: {broken}" if broken else "정상 (모든 이미지 표시됨)"))

        # 이미지 리소스 실패만 추림(시각 영향 큰 것)
        img_fail = [x for x in bad_resp if any(k in x.lower() for k in [".jpg",".png",".gif",".webp","img","cafe24img","ecimg"])]
        add("IMG-02", "이미지 리소스 로드실패", "PASS" if not img_fail else "WARN", (f"{len(img_fail)}건: {img_fail[:3]}" if img_fail else "없음"))
        add("IMG-03", "혼합콘텐츠(http)", "PASS" if not mixed else "WARN", (f"{len(mixed)}건" if mixed else "없음"))

        # JS 에러 — 리소스(이미지) 실패성 에러는 IMG에서 봤으니 제외, 진짜 스크립트 에러만
        real_js = [e for e in js_err if "Failed to load resource" not in e and "ERR_FAILED" not in e]
        add("JS-01", "스크립트 JS 에러", "PASS" if not real_js else "WARN", (f"{len(real_js)}건: {real_js[:2]}" if real_js else "없음 (리소스 경고 제외)"))

        # BUY: 실제 클릭 가능 요소만 (a/button/input + role/onclick). 안내 텍스트 제외.
        buy = page.evaluate("""()=>{
          const txts=['장바구니','구매하기','바로구매','네이버페이','카카오','간편구매','담기','주문하기','결제'];
          const els=[...document.querySelectorAll('a,button,input[type="button"],input[type="submit"],input[type="image"],[role="button"],[onclick]')];
          const out=[];const seen=new Set();
          for(const e of els){
            const x=(e.innerText||e.value||e.getAttribute('alt')||'').trim();
            if(!txts.some(t=>x.includes(t)))continue;
            const key=x.slice(0,12); if(seen.has(key))continue; seen.add(key);
            const r=e.getBoundingClientRect();const s=getComputedStyle(e);
            out.push({txt:x.slice(0,14),visible:s.display!=='none'&&s.opacity!=='0'&&s.visibility!=='hidden'&&r.width>0&&r.height>0,w:Math.round(r.width),h:Math.round(r.height)});
          }
          return out.slice(0,10);
        }""")
        vis = [b for b in buy if b["visible"]]
        add("BUY-01", "구매/장바구니 버튼 가시성", "PASS" if vis else "FAIL", f"보이는 결제버튼 {len(vis)}개: {[b['txt'] for b in vis]}")
        small = [b for b in vis if (b["w"] < 44 or b["h"] < 44)]
        small_desc = [b["txt"] + " " + str(b["w"]) + "x" + str(b["h"]) for b in small]
        add("BUY-03", "버튼 터치영역(44px+)", "PASS" if not small else "WARN", (f"작은 버튼 {len(small)}개: {small_desc}" if small else "충분"))

        add("META-01", "페이지 타이틀", "PASS", (page.title() or "")[:50])

    browser.close()

print(json.dumps(R, ensure_ascii=False, indent=2))
fail=[c for c in R["checks"] if c["status"]=="FAIL"]; warn=[c for c in R["checks"] if c["status"]=="WARN"]; ok=[c for c in R["checks"] if c["status"]=="PASS"]
print(f"\n=== 요약: 🟢PASS {len(ok)} / 🟡WARN {len(warn)} / 🔴FAIL {len(fail)} ===")
