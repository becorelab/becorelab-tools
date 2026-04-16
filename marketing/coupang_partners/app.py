"""쿠팡 파트너스 유튜버 컨택 파이프라인 — Flask 서버 (포트 8083)

대시보드 화면 (PRD §8):
  /                — 퍼널 홈
  /candidates      — Stage 3 확정 (후보 리스트)
  /approvals       — Stage 5 결재함 (일일 17:00)
  /shipping        — Stage 6 샘플 발송함 (월/목)
  /reviews         — Stage 7 영상 검수
  /ghost           — Stage 8 잠수 결재함 (월요일 09:00)
"""
from flask import Flask, jsonify, render_template
from config import PORT

app = Flask(__name__)


@app.route("/")
def home():
    return jsonify({
        "service": "coupang_partners",
        "status": "scaffold",
        "port": PORT,
        "stages": {
            "candidates": "/candidates",
            "approvals": "/approvals",
            "shipping": "/shipping",
            "reviews": "/reviews",
            "ghost": "/ghost",
        },
    })


@app.route("/health")
def health():
    return jsonify({"ok": True})


@app.route("/candidates")
def candidates():
    return jsonify({"stage": 3, "todo": "후보 리스트 (체크박스 확정)"})


@app.route("/approvals")
def approvals():
    return jsonify({"stage": 5, "todo": "일일 결재함"})


@app.route("/shipping")
def shipping():
    return jsonify({"stage": 6, "todo": "샘플 발송함"})


@app.route("/reviews")
def reviews():
    return jsonify({"stage": 7, "todo": "영상 검수"})


@app.route("/ghost")
def ghost():
    return jsonify({"stage": 8, "todo": "잠수 결재함"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False)
