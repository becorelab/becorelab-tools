from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

results = []   # 검색 결과
pending = None  # 쿠팡에서 추출한 상품 정보 (폴링용)

@app.route('/')
def index():
    return send_from_directory('.', 'test.html')

@app.route('/api/result', methods=['POST'])
def receive_result():
    data = request.json
    data['received_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    results.append(data)
    print(f"\n✅ 결과 수신: {data.get('query_url', '')}")
    print(f"   공급업체 {len(data.get('suppliers', []))}개")
    return jsonify({'ok': True, 'count': len(results)})

@app.route('/api/results', methods=['GET'])
def get_results():
    return jsonify(results)

@app.route('/api/clear', methods=['POST'])
def clear_results():
    results.clear()
    return jsonify({'ok': True})

@app.route('/api/product-info', methods=['POST'])
def receive_product_info():
    global pending
    pending = request.json
    print(f"\n📦 쿠팡 상품 수신: {pending.get('name', '')}")
    return jsonify({'ok': True})

@app.route('/api/pending', methods=['GET'])
def get_pending():
    global pending
    data = pending
    pending = None  # 읽으면 초기화
    return jsonify(data or {})

if __name__ == '__main__':
    print("🚀 알리바바 이미지 검색 테스트 서버 시작")
    print("   http://localhost:8095/")
    app.run(port=8095, debug=True)
