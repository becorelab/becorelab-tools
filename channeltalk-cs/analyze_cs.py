#!/usr/bin/env python3
"""
채널톡 CS 상담 데이터 분석 스크립트
- 문의 유형별 분류 및 통계
- 대표 사례 추출
- manager/bot 응답 패턴 분석
"""

import json
import re
from collections import Counter, defaultdict
from datetime import datetime

INPUT_FILE = '/Users/macmini_ky/ClaudeAITeam/channeltalk-cs/all_chats.json'
OUTPUT_FILE = '/Users/macmini_ky/ClaudeAITeam/channeltalk-cs/analysis_result.json'

# ─── 문의 유형 분류 키워드 ───
CATEGORIES = {
    '배송': {
        'keywords': ['배송', '발송', '택배', '도착', '송장', '언제 오', '언제 도착', '안왔', '안 왔', '안와', '안 와', '못받', '못 받', '배달', '수령', '출고', '운송장', '추적', '배송지', '주소 변경', '주소변경', '배송중', '배송 중'],
        'examples': [],
        'responses': [],
        'count': 0
    },
    '교환/환불': {
        'keywords': ['교환', '환불', '반품', '취소', '반송', '취소하', '환불해', '교환해', '반품해', '주문취소', '주문 취소', '취소 요청', '취소요청', '환불 요청', '환불요청', '반품 요청', '반품요청', '취소하고', '환불하고', '교환하고'],
        'examples': [],
        'responses': [],
        'count': 0
    },
    '제품 문의': {
        'keywords': ['사용법', '호환', '성분', '용량', '어떻게 사용', '어떻게 쓰', '사용 방법', '사용방법', '몇개', '몇 개', '몇알', '몇 알', '넣어야', '얼마나', '세탁기', '식세기', '식기세척기', '건조기', '드럼', '통돌이', '삼성', 'LG', '밀레', '차이', '비교', '추천', '뭐가 좋', '어떤게', '어떤 게', '무슨 향', '향이', '코튼블루', '베이비크림', '바이올렛'],
        'examples': [],
        'responses': [],
        'count': 0
    },
    '불량/클레임': {
        'keywords': ['불량', '파손', '이상', '거품', '거품이', '냄새', '냄새가', '효과가 없', '효과없', '안녹', '안 녹', '녹지 않', '안풀', '안 풀', '찌꺼기', '잔여', '얼룩', '하얀', '뭐가 묻', '기포', '변색', '누렇', '때가', '끈적', '잘 안', '안되', '안 되', '문제', '하자', '훼손', '깨져', '깨진', '뿌옇', '표백이 안'],
        'examples': [],
        'responses': [],
        'count': 0
    },
    '주문/결제': {
        'keywords': ['주문', '결제', '카드', '입금', '계좌', '무통장', '가격', '할인', '쿠폰', '적립', '포인트', '금액', '원가', '가격이', '얼마', '비용', '결제 방법', '결제방법', '주문 방법', '주문방법', '전화주문', '전화 주문', '주문확인', '주문 확인', '품절', '품절인가', '재입고', '재 입고', '수량'],
        'examples': [],
        'responses': [],
        'count': 0
    },
    '배송지 변경': {
        'keywords': ['배송지 변경', '배송지변경', '주소 변경', '주소변경', '주소 바꿔', '주소바꿔', '주소를 변경', '배송 주소'],
        'examples': [],
        'responses': [],
        'count': 0
    },
    '이벤트/프로모션': {
        'keywords': ['이벤트', '사은품', '샘플', '체험', '무료', '공동구매', '공구', '첫구매', '첫 구매', '990원', '특가', '리셋위크', '프로모션', '증정', '테스트키트', '테스트 키트'],
        'examples': [],
        'responses': [],
        'count': 0
    },
}

# bot 알림 메시지 패턴 (분류에서 제외)
BOT_NOTIFICATION_PATTERNS = [
    r'회원가입', r'결제완료', r'배송시작', r'주문취소',
    r'님의 결제가 완료', r'님이 주문하신 상품의 배송',
    r'회원이 되신 것을'
]

def is_notification(text):
    """봇 알림 메시지인지 판별"""
    for p in BOT_NOTIFICATION_PATTERNS:
        if re.search(p, text):
            return True
    return False

def classify_message(text):
    """메시지를 유형별로 분류. 복수 분류 가능."""
    text_lower = text.lower()
    matched = []

    # 배송지 변경은 '배송' 보다 먼저 체크
    for cat_name, cat_info in CATEGORIES.items():
        for kw in cat_info['keywords']:
            if kw in text_lower:
                matched.append(cat_name)
                break

    # 중복 제거 + 배송지 변경이 있으면 배송 제거
    if '배송지 변경' in matched and '배송' in matched:
        matched.remove('배송')

    if not matched:
        matched = ['기타']

    return list(set(matched))

def extract_conversations_with_context(data):
    """
    각 상담에서 user-manager/bot 쌍을 추출.
    user 질문 → 그 직후의 manager 또는 bot 응답을 매칭.
    """
    conversations = []

    for chat in data:
        msgs = chat['messages']
        chat_id = chat['chat_id']

        for i, msg in enumerate(msgs):
            if msg['person_type'] == 'user' and msg.get('text', '').strip():
                user_text = msg['text'].strip()

                # 봇 알림 메시지이면 건너뛰기
                if is_notification(user_text):
                    continue

                # 너무 짧은 메시지 (1글자) 건너뛰기
                if len(user_text) <= 1:
                    continue

                # 이후 응답 찾기
                response_text = ''
                response_type = ''
                for j in range(i+1, min(i+5, len(msgs))):
                    if msgs[j]['person_type'] in ('manager', 'bot') and msgs[j].get('text', '').strip():
                        resp = msgs[j]['text'].strip()
                        if not is_notification(resp) and len(resp) > 10:
                            response_text = resp
                            response_type = msgs[j]['person_type']
                            break

                conversations.append({
                    'chat_id': chat_id,
                    'user_text': user_text,
                    'response_text': response_text,
                    'response_type': response_type,
                    'created_at': chat.get('created_at', ''),
                    'categories': classify_message(user_text)
                })

    return conversations

def analyze_response_patterns(data):
    """manager/bot 응답 패턴 분석"""
    greeting_patterns = Counter()
    closing_patterns = Counter()
    tone_examples = []

    for chat in data:
        for msg in chat['messages']:
            if msg['person_type'] == 'manager' and msg.get('text', '').strip():
                text = msg['text'].strip()
                if is_notification(text):
                    continue

                # 인사말 패턴
                if text.startswith('안녕하세요'):
                    first_line = text.split('\n')[0]
                    greeting_patterns[first_line[:50]] += 1

                # 마무리 패턴
                if '감사합니다' in text or '행복한 하루' in text or '좋은 하루' in text:
                    lines = text.split('\n')
                    last_meaningful = [l for l in lines if l.strip()]
                    if last_meaningful:
                        closing_patterns[last_meaningful[-1].strip()[:60]] += 1

                # 좋은 톤 예시 (적절한 길이)
                if 50 < len(text) < 500 and ('감사' in text or '죄송' in text or '도와드리' in text):
                    tone_examples.append(text)

    return greeting_patterns, closing_patterns, tone_examples

def analyze_product_mentions(conversations):
    """제품별 문의 빈도"""
    product_keywords = {
        '건조기 시트': ['건조기 시트', '건조기시트', '드라이 시트', '드라이시트', '시트지'],
        '식기세척기 세제': ['식기세척기', '식세기', '식세기세제', '하트', '타블렛', '세제'],
        '캡슐 세제': ['캡슐 세제', '캡슐세제', '세탁 캡슐', '캡슐형 세제'],
        '캡슐 표백제': ['캡슐 표백제', '캡슐표백제', '과탄산', '표백', '표백제'],
        '얼룩 제거제': ['얼룩 제거', '얼룩제거', '기름때', '때제거'],
        '집게': ['집게'],
        '틴케이스': ['틴케이스', '케이스', '하트케이스', '하트 케이스', '하트틴'],
    }

    product_counts = Counter()
    product_examples = defaultdict(list)

    for conv in conversations:
        text = conv['user_text'].lower()
        for product, keywords in product_keywords.items():
            for kw in keywords:
                if kw in text:
                    product_counts[product] += 1
                    if len(product_examples[product]) < 5:
                        product_examples[product].append(conv)
                    break

    return product_counts, product_examples

def analyze_channel_mentions(conversations):
    """유통 채널별 문의 빈도"""
    channel_keywords = {
        '쿠팡': ['쿠팡'],
        '네이버 스마트스토어': ['네이버', '스마트스토어', '스토어팜'],
        '자사몰(카페24)': ['카페24', '자사몰', '일비아 홈페이지', '공식몰'],
        '11번가': ['11번가'],
        'G마켓': ['g마켓', '지마켓', 'gmarket'],
        '옥션': ['옥션'],
        '오늘의집': ['오늘의집'],
    }

    channel_counts = Counter()
    for conv in conversations:
        text = conv['user_text'].lower()
        for channel, keywords in channel_keywords.items():
            for kw in keywords:
                if kw in text:
                    channel_counts[channel] += 1
                    break

    return channel_counts

def main():
    print("📊 채널톡 CS 데이터 분석 시작...")

    with open(INPUT_FILE, 'r') as f:
        data = json.load(f)

    print(f"  총 상담 수: {len(data)}")
    total_msgs = sum(len(c['messages']) for c in data)
    print(f"  총 메시지 수: {total_msgs}")

    # 1. 대화 추출 및 분류
    print("\n🔍 대화 추출 및 분류 중...")
    conversations = extract_conversations_with_context(data)
    print(f"  분류 대상 user 메시지: {len(conversations)}")

    # 2. 유형별 통계
    category_stats = defaultdict(lambda: {'count': 0, 'examples': [], 'responses': []})

    for conv in conversations:
        for cat in conv['categories']:
            category_stats[cat]['count'] += 1
            if len(category_stats[cat]['examples']) < 10:
                category_stats[cat]['examples'].append({
                    'user': conv['user_text'][:300],
                    'response': conv['response_text'][:500] if conv['response_text'] else '',
                    'response_type': conv['response_type']
                })
            # 좋은 응답 (manager가 작성한 50자 이상)
            if conv['response_type'] == 'manager' and len(conv.get('response_text', '')) > 50:
                if len(category_stats[cat]['responses']) < 5:
                    category_stats[cat]['responses'].append(conv['response_text'][:500])

    print("\n📈 유형별 통계:")
    for cat, stats in sorted(category_stats.items(), key=lambda x: -x[1]['count']):
        print(f"  {cat}: {stats['count']}건")

    # 3. 응답 패턴 분석
    print("\n🎯 응답 패턴 분석 중...")
    greeting_patterns, closing_patterns, tone_examples = analyze_response_patterns(data)

    print("  인사말 TOP 5:")
    for p, c in greeting_patterns.most_common(5):
        print(f"    [{c}회] {p}")

    print("  마무리 TOP 5:")
    for p, c in closing_patterns.most_common(5):
        print(f"    [{c}회] {p}")

    # 4. 제품별 분석
    print("\n📦 제품별 문의 빈도:")
    product_counts, product_examples = analyze_product_mentions(conversations)
    for product, count in product_counts.most_common():
        print(f"  {product}: {count}건")

    # 5. 채널별 분석
    print("\n🏪 유통 채널별 문의 빈도:")
    channel_counts = analyze_channel_mentions(conversations)
    for channel, count in channel_counts.most_common():
        print(f"  {channel}: {count}건")

    # 6. 시간대별 분석
    print("\n⏰ 시간대별 문의 분포:")
    hour_counts = Counter()
    for chat in data:
        if chat.get('created_at'):
            try:
                dt = datetime.strptime(chat['created_at'][:19], '%Y-%m-%d %H:%M:%S')
                hour_counts[dt.hour] += 1
            except:
                pass
    for h in range(24):
        bar = '█' * (hour_counts.get(h, 0) // 10)
        print(f"  {h:02d}시: {hour_counts.get(h, 0):4d}건 {bar}")

    # 7. 에스컬레이션 패턴 분석 (사람이 개입해야 하는 케이스)
    print("\n🚨 에스컬레이션 패턴 분석...")
    escalation_keywords = ['전화', '통화', '법적', '소비자보호', '소보원', '신고', '고소', '변호사', '화나', '화가', '짜증', '실망', '최악', '사기', '거짓', '다시는', '절대', '말이 안']
    escalation_cases = []
    for conv in conversations:
        text = conv['user_text'].lower()
        for kw in escalation_keywords:
            if kw in text:
                escalation_cases.append(conv)
                break
    print(f"  감정적/법적 에스컬레이션 가능 건수: {len(escalation_cases)}건")

    # 결과 저장
    result = {
        'summary': {
            'total_chats': len(data),
            'total_messages': total_msgs,
            'classified_user_messages': len(conversations),
        },
        'category_stats': {k: {'count': v['count'], 'examples': v['examples'], 'responses': v['responses']} for k, v in category_stats.items()},
        'greeting_patterns': greeting_patterns.most_common(10),
        'closing_patterns': closing_patterns.most_common(10),
        'tone_examples': tone_examples[:20],
        'product_counts': dict(product_counts.most_common()),
        'product_examples': {k: [{'user': e['user_text'][:200], 'response': e['response_text'][:300]} for e in v] for k, v in product_examples.items()},
        'channel_counts': dict(channel_counts.most_common()),
        'hour_distribution': {str(h): hour_counts.get(h, 0) for h in range(24)},
        'escalation_examples': [{'user': e['user_text'][:200], 'response': e['response_text'][:300]} for e in escalation_cases[:15]],
    }

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 분석 결과 저장: {OUTPUT_FILE}")
    return result

if __name__ == '__main__':
    main()
