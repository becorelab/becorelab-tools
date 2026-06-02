#!/usr/bin/env python3
"""
PTY 래퍼 — launchd 헤드리스 환경에서 claude --channels를 실행할 때
stdout/stdin이 TTY가 아니어서 claude가 --print 모드로 빠지는 문제를 해결.

실제 pseudo-TTY를 만들어 claude에게 TTY처럼 보이게 한다.
"""
import os
import sys
import pty
import signal
import select
import time
import logging

# ──────────────────────────────────────────────
# 설정
# ──────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

CLAUDE_BIN   = '/opt/homebrew/bin/claude'
CHANNEL_ARG  = 'plugin:telegram@claude-plugins-official'
MODEL        = 'claude-opus-4-8'
WORKDIR      = SCRIPT_DIR   # Channel_doori/ — CLAUDE.md 있는 곳
STATE_DIR    = '/Users/macmini_ky/.claude/channels/telegram-doori'
HOME_DIR     = '/Users/macmini_ky'
BUN_HOME     = '/Users/macmini_ky/.bun'

LOG_FILE     = '/tmp/doori_pty.log'
PID_FILE     = '/tmp/doori_pty.pid'

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.DEBUG,
    format='%(asctime)s [PTY] %(levelname)s %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
log = logging.getLogger('pty_launcher')

# stdout에도 출력 (launchd가 /tmp/doori.log로 잡아감)
console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter('[DOORI-PTY] %(message)s'))
log.addHandler(console)


def build_env():
    """launchd용 최소 환경변수 구성 (TELEGRAM_BOT_TOKEN은 .env에서 로드)"""
    env = {}
    # 기본 경로
    env['HOME']        = HOME_DIR
    env['BUN_INSTALL'] = BUN_HOME
    env['PATH']        = f"{BUN_HOME}/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
    # 두리 전용 State 디렉토리
    env['TELEGRAM_STATE_DIR'] = STATE_DIR
    # .env 파일에서 토큰 로드 (server.ts도 같은 방식으로 로드함)
    env_file = os.path.join(STATE_DIR, '.env')
    try:
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                m_eq = line.split('=', 1)
                if len(m_eq) == 2 and not line.startswith('#'):
                    env[m_eq[0].strip()] = m_eq[1].strip()
    except FileNotFoundError:
        log.warning(f".env 파일 없음: {env_file}")
    # 상위 환경에서 토큰이 있으면 우선 적용
    if 'TELEGRAM_BOT_TOKEN' in os.environ:
        env['TELEGRAM_BOT_TOKEN'] = os.environ['TELEGRAM_BOT_TOKEN']
    # 색상/터미널 설정
    env['TERM']       = 'xterm-256color'
    env['COLORTERM']  = 'truecolor'
    env['LANG']       = 'ko_KR.UTF-8'
    env['LC_ALL']     = 'ko_KR.UTF-8'
    return env


def write_pid(pid: int):
    try:
        with open(PID_FILE, 'w') as f:
            f.write(str(pid))
    except Exception as e:
        log.warning(f"PID 파일 쓰기 실패: {e}")


def cleanup_pid():
    try:
        os.unlink(PID_FILE)
    except:
        pass


def run():
    log.info(f"두리 PTY 런처 시작 (pid={os.getpid()})")
    log.info(f"claude: {CLAUDE_BIN}")
    log.info(f"workdir: {WORKDIR}")

    env = build_env()
    if not env.get('TELEGRAM_BOT_TOKEN'):
        log.error("TELEGRAM_BOT_TOKEN이 없습니다! .env 파일 확인 필요.")
        sys.exit(1)

    cmd = [
        CLAUDE_BIN,
        '--channels', CHANNEL_ARG,
        '--dangerously-skip-permissions',
        '--model', MODEL,
    ]
    log.info(f"실행 명령: {' '.join(cmd)}")

    # PTY 할당
    master_fd, slave_fd = pty.openpty()

    child_pid = os.fork()
    if child_pid == 0:
        # ── 자식 프로세스 ──────────────────────────
        os.close(master_fd)
        os.chdir(WORKDIR)
        os.setsid()
        import fcntl
        import termios
        fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)
        os.dup2(slave_fd, 0)   # stdin  → pty slave
        os.dup2(slave_fd, 1)   # stdout → pty slave
        os.dup2(slave_fd, 2)   # stderr → pty slave
        if slave_fd > 2:
            os.close(slave_fd)
        os.execve(cmd[0], cmd, env)
        sys.exit(1)   # execve 실패 시

    # ── 부모 프로세스 ──────────────────────────────
    os.close(slave_fd)
    write_pid(child_pid)
    log.info(f"claude child PID={child_pid}")

    trust_sent    = False
    startup_done  = False

    def on_sigterm(signo, frame):
        log.info(f"SIGTERM 수신 → claude(pid={child_pid}) 종료")
        try:
            os.kill(child_pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        cleanup_pid()
        sys.exit(0)

    signal.signal(signal.SIGTERM, on_sigterm)
    signal.signal(signal.SIGINT,  on_sigterm)

    # 출력 중계 루프
    while True:
        # 자식이 죽었는지 확인
        try:
            wpid, wstatus = os.waitpid(child_pid, os.WNOHANG)
            if wpid == child_pid:
                code = os.waitstatus_to_exitcode(wstatus)
                log.warning(f"claude 프로세스 종료 (exit={code})")
                cleanup_pid()
                sys.exit(code if code >= 0 else 1)
        except ChildProcessError:
            log.warning("child already reaped")
            cleanup_pid()
            sys.exit(0)

        r, _, _ = select.select([master_fd], [], [], 1.0)
        if not r:
            continue

        try:
            data = os.read(master_fd, 8192)
        except OSError:
            log.info("master_fd 닫힘 — claude 종료")
            break

        if not data:
            break

        text = data.decode('utf-8', errors='replace')

        # ── 워크스페이스 신뢰 다이얼로그 자동 응답 ──
        if not trust_sent and ('trust' in text.lower() or 'workspace' in text.lower()):
            log.info("워크스페이스 신뢰 다이얼로그 감지 → '1' 전송")
            try:
                os.write(master_fd, b'1\r')
                trust_sent = True
            except OSError:
                pass

        # ── 채널 모드 시작 확인 ──
        if not startup_done and ('channel' in text.lower() or 'telegram' in text.lower()
                                  or 'claude' in text.lower()):
            log.info("Claude 채널 모드 시작 확인됨")
            startup_done = True

        # launchd StandardOutPath로 원시 출력 전달
        try:
            sys.stdout.buffer.write(data)
            sys.stdout.buffer.flush()
        except Exception:
            pass

    cleanup_pid()
    log.info("PTY 런처 종료")


if __name__ == '__main__':
    run()
