# 사무실 PC 마켓 파인더 설치 가이드

## 방법 A: 집 PC에서 원격 접속 (추천 — 설치 불필요)

집 PC가 켜져 있을 때 인터넷 어디서든 접속 가능.

### 설정 (집 PC에서 1회만)
1. **공유기 설정 접속**: 브라우저에서 `192.168.0.1` 또는 `192.168.1.1`
2. **포트포워딩 추가**:
   - 외부 포트: `8090`
   - 내부 IP: (이 PC의 내부 IP — `ipconfig`로 확인)
   - 내부 포트: `8090`
   - 프로토콜: TCP
3. **집 공인 IP 확인**: https://www.whatismyip.com 에서 확인

### 접속 (사무실에서)
```
http://[집 공인 IP]:8090
```
예: `http://123.456.789.10:8090`

> **주의**: 공인 IP는 재부팅 시 바뀔 수 있음. 바뀌면 다시 확인.
> 고정IP/DDNS 설정 시 항상 같은 주소로 접속 가능.

---

## 방법 B: 사무실 PC에 직접 설치

### 1. Python 설치
- https://python.org → Python 3.11 이상 설치
- 설치 시 "Add Python to PATH" 체크 필수!

### 2. 코드 받기
```bash
git clone https://github.com/becorelab/becorelab-tools.git
cd becorelab-tools/sourcing
```
> Git 없으면: GitHub에서 ZIP 다운로드 후 압축 해제

### 3. 의존성 설치
```bash
cd analyzer
pip install -r requirements.txt
playwright install chromium
```

### 4. 환경변수 파일 생성
`sourcing/analyzer/.env` 파일 생성 (집 PC에서 복사):
```
ANTHROPIC_API_KEY=sk-ant-...
HELPSTORE_ID=becorelab
HELPSTORE_PW=qlzhdjfoq2023!!
```

### 5. 실행
```bash
cd C:\path\to\becorelab-tools\sourcing
python analyzer\app.py
```

### 6. 자동 시작 등록
`register_autostart.bat` 우클릭 → 관리자 권한으로 실행

---

## 현재 PC 내부 IP 확인 방법
```
Win + R → cmd → ipconfig
IPv4 주소 항목 (192.168.x.x)
```
