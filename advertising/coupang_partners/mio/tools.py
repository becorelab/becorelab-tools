"""미오 파트너스 커스텀 툴 — Firestore/YouTube/네이버웍스 I/O 포트.

Step 4 진행 중: 네이버웍스 SMTP 발송 배선 완료.
Step 5: YouTube Data API 연동 예정.
"""
import os
import sys
import json
from datetime import datetime, timezone

_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_dir, ".."))

from google.cloud import firestore as fs

from firestore_client import (
    upsert_candidate, get_candidate, update_candidate_status,
    append_thread_message, get_thread,
    add_to_ghost_queue, list_ghost_queue,
    db,
)
from naverworks_mail import send_mail
from youtube_crawler import (
    search_channels_by_keyword, enrich_channels, enrich_full, recent_uploads,
    _find_contact_email, is_in_tier, is_fresh_channel,
)
from screener import screen_channel
from config import (
    COLL_CANDIDATES, COLL_THREADS,
    STATUS_CONTACTED, STATUS_SCREENED, STATUS_APPROVED, STATUS_REJECTED,
    DAILY_SEND_LIMIT, BASE_DIR,
    MIN_SUBSCRIBERS, MAX_SUBSCRIBERS,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ok(**kw) -> dict:
    return {"ok": True, "timestamp": _now(), **kw}


def _err(msg: str, **kw) -> dict:
    return {"ok": False, "error": msg, "timestamp": _now(), **kw}


# ── 일일 발송 쿼터 (워밍업) ────────────────────────────────────
_SEND_COUNTER_PATH = str(BASE_DIR / "credentials" / "daily_send_counter.json")


def _today_kst() -> str:
    # KST = UTC+9. 자정 기준은 대표님 현지 시각으로.
    from datetime import timedelta
    return (datetime.now(timezone.utc) + timedelta(hours=9)).date().isoformat()


def _read_counter() -> dict:
    if not os.path.exists(_SEND_COUNTER_PATH):
        return {}
    try:
        with open(_SEND_COUNTER_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_counter(state: dict) -> None:
    os.makedirs(os.path.dirname(_SEND_COUNTER_PATH), exist_ok=True)
    with open(_SEND_COUNTER_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def _check_and_increment_quota() -> tuple[bool, int, int]:
    """오늘 발송 수 체크. 한도 도달이면 (False, sent, limit) 반환.
    여유 있으면 카운터 증가 후 (True, new_sent, limit).
    """
    today = _today_kst()
    state = _read_counter()
    sent = int(state.get(today, 0))
    if sent >= DAILY_SEND_LIMIT:
        return False, sent, DAILY_SEND_LIMIT
    state[today] = sent + 1
    _write_counter(state)
    return True, sent + 1, DAILY_SEND_LIMIT


# ── 1. yt_channel_enrich ──────────────────────────────────────
def yt_channel_enrich(channel_id: str) -> dict:
    """YouTube Data API로 채널 stats + 최근 영상 5개 + 설명 이메일 수집."""
    try:
        ch = enrich_full(channel_id)
    except Exception as e:
        return _err(f"YouTube enrich 실패: {e}", channel_id=channel_id)

    payload = {
        "title": ch.get("title"),
        "description": ch.get("description"),
        "email": ch.get("contact_email"),
        "subscriber_count": ch.get("subscriber_count"),
        "video_count": ch.get("video_count"),
        "view_count": ch.get("view_count"),
        "country": ch.get("country"),
        "custom_url": ch.get("custom_url"),
        "recent_videos": ch.get("recent_videos") or [],
        "is_in_tier": ch.get("is_in_tier"),
        "is_fresh": ch.get("is_fresh"),
        "enriched_at": _now(),
    }
    upsert_candidate(channel_id, payload)
    return _ok(
        channel_id=channel_id,
        title=ch.get("title"),
        subscriber_count=ch.get("subscriber_count"),
        contact_email=ch.get("contact_email"),
        is_in_tier=ch.get("is_in_tier"),
        is_fresh=ch.get("is_fresh"),
        recent_videos_count=len(ch.get("recent_videos") or []),
    )


# ── 1b. yt_discover ───────────────────────────────────────────
def yt_discover(keyword: str, target_approved: int = 5,
                max_candidates: int = 30, save_all: bool = True) -> dict:
    """키워드로 채널 검색 → tier 필터 → Haiku 스크리닝 → Firestore 저장.
    target_approved 만큼 approved 확보하거나 max_candidates 소진 시 종료.
    """
    try:
        channel_ids = search_channels_by_keyword(keyword)
    except Exception as e:
        return _err(f"search 실패: {e}", keyword=keyword)

    if not channel_ids:
        return _ok(keyword=keyword, found=0, approved=[], rejected=[], maybe=[])

    try:
        enriched = enrich_channels(channel_ids[:max_candidates])
    except Exception as e:
        return _err(f"enrich 실패: {e}", keyword=keyword)

    approved, rejected, maybe = [], [], []

    for ch in enriched:
        cid = ch.get("channel_id")
        if not cid:
            continue

        ch["recent_videos"] = recent_uploads(ch.get("uploads_playlist") or "")
        ch["contact_email"] = _find_contact_email(ch.get("description") or "")
        ch["is_in_tier"] = is_in_tier(ch)
        ch["is_fresh"] = is_fresh_channel(ch)

        # tier 벗어나면 스크리닝 스킵 (비용 절감)
        if not ch["is_in_tier"]:
            if save_all:
                upsert_candidate(cid, {
                    **{k: ch.get(k) for k in [
                        "title", "description", "subscriber_count", "video_count",
                        "view_count", "country", "custom_url", "recent_videos",
                        "is_in_tier", "is_fresh"
                    ]},
                    "email": ch["contact_email"],
                    "enriched_at": _now(),
                    "tier_reject_reason": f"subs={ch.get('subscriber_count')} out of [{MIN_SUBSCRIBERS}, {MAX_SUBSCRIBERS}]",
                })
                update_candidate_status(cid, STATUS_REJECTED, {"reason": "out_of_tier"})
            rejected.append({"channel_id": cid, "title": ch.get("title"),
                              "subs": ch.get("subscriber_count"), "reason": "out_of_tier"})
            continue

        screen = screen_channel(ch)

        base_payload = {
            "title": ch.get("title"),
            "description": ch.get("description"),
            "email": ch["contact_email"],
            "subscriber_count": ch.get("subscriber_count"),
            "video_count": ch.get("video_count"),
            "view_count": ch.get("view_count"),
            "country": ch.get("country"),
            "custom_url": ch.get("custom_url"),
            "recent_videos": ch["recent_videos"],
            "is_in_tier": ch["is_in_tier"],
            "is_fresh": ch["is_fresh"],
            "screen": screen,
            "enriched_at": _now(),
            "discovery_keyword": keyword,
        }
        upsert_candidate(cid, base_payload)

        verdict = screen.get("verdict", "maybe")
        summary = {
            "channel_id": cid,
            "title": ch.get("title"),
            "subs": ch.get("subscriber_count"),
            "match_score": screen.get("match_score"),
            "matched_products": screen.get("matched_products"),
            "contact_email": ch["contact_email"],
        }
        if verdict == "approved":
            update_candidate_status(cid, STATUS_APPROVED, screen)
            approved.append(summary)
            if len(approved) >= target_approved:
                break
        elif verdict == "rejected":
            update_candidate_status(cid, STATUS_REJECTED, screen)
            rejected.append({**summary, "reason": screen.get("rationale")})
        else:
            update_candidate_status(cid, STATUS_SCREENED, screen)
            maybe.append(summary)

    return _ok(
        keyword=keyword,
        total_searched=len(channel_ids),
        total_enriched=len(enriched),
        approved=approved,
        maybe=maybe,
        rejected=rejected,
        approved_count=len(approved),
    )


# ── 2. yt_pitch_write ─────────────────────────────────────────
def yt_pitch_write(channel_id: str, matched_products: list,
                   subject: str, body_ko: str,
                   to_email: str = None,
                   dry_run: bool = True,
                   references: list = None) -> dict:
    """아웃리치 초안 저장.
    dry_run=True → Firestore 초안만, False → 네이버웍스 SMTP 실발송.
    to_email 생략 시 candidate.email 조회.
    """
    thread_id = f"thread_{channel_id}"
    cand = get_candidate(channel_id)
    if not cand:
        # yt_channel_enrich 안 돌려도 최소 스켈레톤 생성 (후속 update_status 404 방지)
        upsert_candidate(channel_id, {"email": to_email} if to_email else {})
        cand = get_candidate(channel_id) or {}
    resolved_to = to_email or cand.get("email")

    sent_info = None
    if not dry_run:
        if not resolved_to:
            return _err("메일 주소 없음: dry_run=False면 to_email 또는 candidate.email 필요",
                        channel_id=channel_id)
        ok, sent_today, limit = _check_and_increment_quota()
        if not ok:
            return _err(
                f"오늘 발송 한도 {limit}통 도달 (sent={sent_today}). 내일 재시도.",
                channel_id=channel_id,
                daily_quota_exceeded=True,
            )
        try:
            sent_info = send_mail(resolved_to, subject, body_ko, references=references)
        except Exception as e:
            # 발송 실패 시 카운터 되돌림
            state = _read_counter()
            today = _today_kst()
            if state.get(today, 0) > 0:
                state[today] -= 1
                _write_counter(state)
            return _err(f"네이버웍스 발송 실패: {e}", channel_id=channel_id)

    msg = {
        "direction": "outbound_sent" if sent_info else "outbound_draft",
        "subject": subject,
        "body_ko": body_ko,
        "matched_products": matched_products,
        "references": references or [],
        "to": resolved_to,
    }
    if sent_info:
        msg["message_id"] = sent_info["message_id"]
        msg["sent_at"] = sent_info["sent_at"]
    append_thread_message(thread_id, msg)

    update_candidate_status(channel_id, STATUS_CONTACTED, {
        "subject": subject,
        "products": matched_products,
        "sent": bool(sent_info),
    })
    return _ok(
        channel_id=channel_id,
        thread_id=thread_id,
        sent=bool(sent_info),
        message_id=sent_info["message_id"] if sent_info else None,
        to=resolved_to,
    )


# ── 3. yt_reply_classify ──────────────────────────────────────
def yt_reply_classify(thread_id: str, email_body: str,
                      category: str, summary_ko: str,
                      suggested_action: str) -> dict:
    """답장 3분류 결과를 스레드에 기록. escalate면 텔레그램 플래그만 표시."""
    if category not in ("auto", "approval", "escalate"):
        return _err(f"invalid category: {category}")
    append_thread_message(thread_id, {
        "direction": "inbound",
        "body": email_body,
        "classification": category,
        "summary_ko": summary_ko,
        "suggested_action": suggested_action,
    })
    # TODO Step 4: escalate면 텔레그램 봇으로 대표님에게 즉시 알림
    needs_telegram = category == "escalate"
    return _ok(
        thread_id=thread_id,
        category=category,
        needs_telegram=needs_telegram,
        note="텔레그램 에스컬은 Step 4에서 주입" if needs_telegram else "",
    )


# ── 4. yt_conversation ────────────────────────────────────────
def _find_last_inbound(thread: dict) -> dict:
    """스레드에서 가장 최근 inbound 메시지 반환 (스레딩 헤더용)."""
    for m in reversed(thread.get("messages") or []):
        if m.get("direction") == "inbound" and m.get("message_id"):
            return m
    return {}


def yt_conversation(thread_id: str, subject: str, body_ko: str,
                    approved: bool = False,
                    to_email: str = None) -> dict:
    """답장 초안 저장. approved=True면 네이버웍스로 즉시 발송, False면 결재 대기."""
    thread = get_thread(thread_id) or {}
    last_in = _find_last_inbound(thread)

    sent_info = None
    if approved:
        # 수신자 결정: 인자 > 마지막 inbound 발신자 > 스레드 내 첫 outbound의 to
        resolved_to = to_email or last_in.get("from")
        if not resolved_to:
            for m in thread.get("messages") or []:
                if m.get("direction") in ("outbound_sent", "outbound_draft") and m.get("to"):
                    resolved_to = m["to"]
                    break
        if not resolved_to:
            return _err("수신자 없음: to_email 또는 스레드 내 inbound 필요",
                        thread_id=thread_id)

        in_reply_to = last_in.get("message_id")
        refs_str = last_in.get("references") or ""
        refs = [r for r in refs_str.split() if r]
        try:
            sent_info = send_mail(resolved_to, subject, body_ko,
                                  in_reply_to=in_reply_to, references=refs)
        except Exception as e:
            return _err(f"네이버웍스 발송 실패: {e}", thread_id=thread_id)

    msg = {
        "direction": "outbound_sent" if sent_info else "outbound_draft",
        "subject": subject,
        "body_ko": body_ko,
        "approved": approved,
    }
    if sent_info:
        msg["message_id"] = sent_info["message_id"]
        msg["sent_at"] = sent_info["sent_at"]
        msg["to"] = sent_info["to"]
        msg["in_reply_to"] = last_in.get("message_id")
    append_thread_message(thread_id, msg)

    return _ok(
        thread_id=thread_id,
        sent=bool(sent_info),
        message_id=sent_info["message_id"] if sent_info else None,
        queued_for_approval=not approved,
    )


# ── 5. yt_video_review ────────────────────────────────────────
def yt_video_review(video_url: str, channel_id: str,
                    ad_disclosure_ok: bool, product_name_ok: bool,
                    partners_link_ok: bool,
                    competitor_exposure: bool = False,
                    issues_ko: list = None) -> dict:
    """영상 검수 체크리스트 기록. 이슈 있으면 대표님 알림 플래그."""
    issues = issues_ko or []
    all_ok = ad_disclosure_ok and product_name_ok and partners_link_ok and not competitor_exposure
    review = {
        "video_url": video_url,
        "reviewed_at": _now(),
        "checks": {
            "ad_disclosure": ad_disclosure_ok,
            "product_name": product_name_ok,
            "partners_link": partners_link_ok,
            "competitor_exposure": competitor_exposure,
        },
        "issues": issues,
        "all_ok": all_ok,
    }
    db().collection(COLL_CANDIDATES).document(channel_id).update({
        "video_reviews": fs.ArrayUnion([review]),
    })
    return _ok(channel_id=channel_id, all_ok=all_ok, needs_fix_request=not all_ok)


# ── 6. yt_ghost_report ────────────────────────────────────────
def yt_ghost_report(week_start_iso: str, notes_ko: str = "") -> dict:
    """잠수 큐 조회 → 주간 결재 리포트 본문 조립."""
    pending = list_ghost_queue(resolved=False)
    lines = [f"# 쿠팡 파트너스 잠수 결재함 (week of {week_start_iso})"]
    lines.append(f"\n대기 {len(pending)}건\n")
    for g in pending:
        lines.append(f"- {g.get('channel_id')} / reason: {g.get('reason')} / added: {g.get('added_at')}")
    if notes_ko:
        lines.append(f"\n관전 포인트: {notes_ko}")
    report = "\n".join(lines)
    # TODO Step 4: 텔레그램으로 대표님 발송
    return _ok(report_text=report, count=len(pending))


# ── dispatch ─────────────────────────────────────────────────
_DISPATCH = {
    "yt_channel_enrich": yt_channel_enrich,
    "yt_discover": yt_discover,
    "yt_pitch_write": yt_pitch_write,
    "yt_reply_classify": yt_reply_classify,
    "yt_conversation": yt_conversation,
    "yt_video_review": yt_video_review,
    "yt_ghost_report": yt_ghost_report,
}


def dispatch_tool(name: str, tool_input: dict) -> str:
    """미오 Managed Agent가 툴 호출 → 여기서 실행 후 JSON 문자열 반환."""
    fn = _DISPATCH.get(name)
    if not fn:
        return json.dumps(_err(f"unknown tool: {name}"), ensure_ascii=False)
    try:
        result = fn(**tool_input)
        return json.dumps(result, ensure_ascii=False)
    except TypeError as e:
        return json.dumps(_err(f"arg error in {name}: {e}"), ensure_ascii=False)
    except Exception as e:
        return json.dumps(_err(f"{name} failed: {e}"), ensure_ascii=False)
