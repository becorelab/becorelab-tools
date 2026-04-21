"""
레나 도구 CLI 래퍼
사용:
  python lena_tool.py inbox
  python lena_tool.py read "Bard Cai"
  python lena_tool.py reply "Bard Cai" "답장 본문"
"""
import sys
import os
import json

MIO_DIR = r"C:\Users\User\ClaudeAITeam\sourcing\mio"
sys.path.insert(0, MIO_DIR)
sys.path.insert(0, r"C:\Users\User\ClaudeAITeam\sourcing")

from tools import (
    alibaba_check_inbox,
    alibaba_read_conversation,
    alibaba_reply,
)


def main():
    if len(sys.argv) < 2:
        print("usage: python lena_tool.py {inbox|read|reply} [args]")
        return 1

    cmd = sys.argv[1]

    if cmd == "inbox":
        result = alibaba_check_inbox()
    elif cmd == "read":
        if len(sys.argv) < 3:
            print("usage: python lena_tool.py read \"supplier name\"")
            return 1
        result = alibaba_read_conversation(sys.argv[2])
    elif cmd == "reply":
        if len(sys.argv) < 4:
            print("usage: python lena_tool.py reply \"supplier name\" \"message\"")
            return 1
        result = alibaba_reply(sys.argv[2], sys.argv[3])
    else:
        print(f"알 수 없는 명령: {cmd}")
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
