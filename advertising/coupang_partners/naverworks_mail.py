"""네이버웍스 메일 I/O 레이어.

발송:   smtp.worksmobile.com:465 (SSL)
수신:   imap.worksmobile.com:993 (SSL)

자격증명: credentials/naverworks.json
  {"service":"naverworks","user":"info@becorelab.kr","password":"..."}

답장 스레딩: 발송 시 생성한 Message-ID를 Firestore thread에 저장 →
IMAP으로 받은 메일의 In-Reply-To 헤더를 thread_id와 매칭.
"""
import json
import ssl
import smtplib
import imaplib
import email
from email.header import decode_header
from email.message import EmailMessage
from email.utils import make_msgid, formatdate, parseaddr
from datetime import datetime, timezone
from typing import Optional

from config import (
    NAVERWORKS_SMTP_HOST, NAVERWORKS_SMTP_PORT,
    NAVERWORKS_IMAP_HOST, NAVERWORKS_IMAP_PORT,
    NAVERWORKS_CRED_PATH, NAVERWORKS_FROM_NAME,
)


def _load_cred() -> dict:
    with open(NAVERWORKS_CRED_PATH, "r", encoding="utf-8") as f:
        cred = json.load(f)
    if not cred.get("user") or not cred.get("password"):
        raise ValueError("naverworks.json에 user/password 필드 필요")
    return cred


# ── SMTP 발송 ──────────────────────────────────────────────────
def send_mail(to: str, subject: str, body_ko: str,
              in_reply_to: Optional[str] = None,
              references: Optional[list[str]] = None) -> dict:
    """메일 발송. 반환: {message_id, sent_at}"""
    cred = _load_cred()
    from_addr = cred["user"]

    msg = EmailMessage()
    msg["From"] = f"{NAVERWORKS_FROM_NAME} <{from_addr}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg["Date"] = formatdate(localtime=True)
    message_id = make_msgid(domain=from_addr.split("@", 1)[1])
    msg["Message-ID"] = message_id
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        refs = list(references or [])
        if in_reply_to not in refs:
            refs.append(in_reply_to)
        msg["References"] = " ".join(refs)
    msg.set_content(body_ko)

    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(NAVERWORKS_SMTP_HOST, NAVERWORKS_SMTP_PORT, context=ctx, timeout=30) as s:
        s.login(from_addr, cred["password"])
        s.send_message(msg)

    return {
        "message_id": message_id,
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "to": to,
        "subject": subject,
    }


# ── IMAP 수신 ──────────────────────────────────────────────────
def _decode(header_value: Optional[str]) -> str:
    if not header_value:
        return ""
    parts = decode_header(header_value)
    out = []
    for text, enc in parts:
        if isinstance(text, bytes):
            try:
                out.append(text.decode(enc or "utf-8", errors="replace"))
            except Exception:
                out.append(text.decode("utf-8", errors="replace"))
        else:
            out.append(text)
    return "".join(out)


def _extract_body(msg: email.message.Message) -> str:
    """멀티파트 중 text/plain 우선, 없으면 text/html 스트립."""
    if msg.is_multipart():
        plain, html = None, None
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "")
            if "attachment" in disp.lower():
                continue
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            charset = part.get_content_charset() or "utf-8"
            try:
                text = payload.decode(charset, errors="replace")
            except Exception:
                text = payload.decode("utf-8", errors="replace")
            if ctype == "text/plain" and not plain:
                plain = text
            elif ctype == "text/html" and not html:
                html = text
        return plain or html or ""
    payload = msg.get_payload(decode=True)
    if payload is None:
        return msg.get_payload() or ""
    charset = msg.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="replace")


def fetch_unseen(mailbox: str = "INBOX", mark_seen: bool = False) -> list[dict]:
    """미열람 메일 조회. 한글 폴더명 OK (내부에서 IMAP UTF-7 인코딩).
    반환: [{message_id, in_reply_to, from, subject, body, received_at}]
    """
    cred = _load_cred()
    out = []
    # 비 ASCII 문자 있으면 modified UTF-7로 인코딩 후 quote
    needs_encode = any(ord(c) > 127 for c in mailbox)
    selected = '"' + _imap_utf7_encode(mailbox) + '"' if needs_encode else mailbox
    with imaplib.IMAP4_SSL(NAVERWORKS_IMAP_HOST, NAVERWORKS_IMAP_PORT) as m:
        m.login(cred["user"], cred["password"])
        status, _ = m.select(selected)
        if status != "OK":
            raise RuntimeError(f"mailbox SELECT 실패: {mailbox!r} → {selected!r}")
        status, data = m.search(None, "UNSEEN")
        if status != "OK":
            return []
        for num in (data[0] or b"").split():
            fetch_cmd = "(RFC822)" if mark_seen else "(BODY.PEEK[])"
            status, parts = m.fetch(num, fetch_cmd)
            if status != "OK" or not parts:
                continue
            raw = parts[0][1]
            msg = email.message_from_bytes(raw)
            _, from_addr = parseaddr(msg.get("From", ""))
            out.append({
                "message_id": _decode(msg.get("Message-ID")),
                "in_reply_to": _decode(msg.get("In-Reply-To")),
                "references": _decode(msg.get("References")),
                "from": from_addr,
                "from_name": _decode(msg.get("From")),
                "to": _decode(msg.get("To")),
                "subject": _decode(msg.get("Subject")),
                "body": _extract_body(msg),
                "received_at": _decode(msg.get("Date")),
                "imap_uid": num.decode(),
            })
    return out


def _imap_utf7_decode(s: str) -> str:
    """IMAP modified UTF-7 디코드 (RFC 3501 §5.1.3).
    - & 문자는 literal이면 &-, 그 외엔 base64(UTF-16BE) 를 & ~ - 로 감싼 형태
    - base64의 '/'는 ','로 치환됨
    """
    out = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch != "&":
            out.append(ch)
            i += 1
            continue
        # & literal
        if s[i:i + 2] == "&-":
            out.append("&")
            i += 2
            continue
        # & ... -
        end = s.find("-", i + 1)
        if end == -1:
            out.append(s[i:])
            break
        b64 = s[i + 1:end].replace(",", "/")
        # pad to multiple of 4
        b64 += "=" * (-len(b64) % 4)
        import base64
        try:
            raw = base64.b64decode(b64)
            out.append(raw.decode("utf-16-be", errors="replace"))
        except Exception:
            out.append(s[i:end + 1])
        i = end + 1
    return "".join(out)


def _imap_utf7_encode(s: str) -> str:
    """UTF-8 문자열 → IMAP modified UTF-7 (폴더 선택 시 사용)."""
    import base64
    out = []
    buf = []

    def flush():
        if not buf:
            return
        raw = "".join(buf).encode("utf-16-be")
        enc = base64.b64encode(raw).decode("ascii").rstrip("=").replace("/", ",")
        out.append("&" + enc + "-")
        buf.clear()

    for ch in s:
        cp = ord(ch)
        if 0x20 <= cp <= 0x7E:
            flush()
            if ch == "&":
                out.append("&-")
            else:
                out.append(ch)
        else:
            buf.append(ch)
    flush()
    return "".join(out)


def list_mailboxes() -> list[str]:
    """IMAP 폴더 목록 반환. 원본(UTF-7)과 디코드된 이름 둘 다 반환."""
    cred = _load_cred()
    names = []
    with imaplib.IMAP4_SSL(NAVERWORKS_IMAP_HOST, NAVERWORKS_IMAP_PORT) as m:
        m.login(cred["user"], cred["password"])
        status, data = m.list()
        if status != "OK":
            return []
        for raw in data:
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
            if '"' in line:
                parts = line.rsplit('"', 2)
                if len(parts) >= 2:
                    enc = parts[-2]
                    decoded = _imap_utf7_decode(enc)
                    names.append(f"{enc}  →  {decoded}")
    return names


def smoke_test() -> dict:
    """자격증명 확인용: SMTP login + IMAP login만 시도 (발송 X)."""
    cred = _load_cred()
    results = {"smtp": False, "imap": False, "user": cred["user"]}
    ctx = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL(NAVERWORKS_SMTP_HOST, NAVERWORKS_SMTP_PORT, context=ctx, timeout=15) as s:
            s.login(cred["user"], cred["password"])
            results["smtp"] = True
    except Exception as e:
        results["smtp_error"] = str(e)
    try:
        with imaplib.IMAP4_SSL(NAVERWORKS_IMAP_HOST, NAVERWORKS_IMAP_PORT) as m:
            m.login(cred["user"], cred["password"])
            results["imap"] = True
    except Exception as e:
        results["imap_error"] = str(e)
    return results


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(smoke_test(), ensure_ascii=False, indent=2))
