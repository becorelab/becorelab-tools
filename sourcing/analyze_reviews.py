#!/usr/bin/env python3
"""리뷰 분석 파이프라인 — 수집된 JSON에서 JTBD/불만/만족/포지셔닝 추출"""

import json, os, glob, sys, re
from collections import Counter, defaultdict

def load_reviews(keyword_dir):
    """키워드 디렉토리의 모든 리뷰 JSON 로드"""
    files = [f for f in glob.glob(os.path.join(keyword_dir, "*.json")) if "_summary" not in f and "_analysis" not in f]
    all_products = []
    for f in files:
        try:
            data = json.load(open(f, encoding="utf-8"))
            all_products.append(data)
        except:
            pass
    return all_products

def analyze_keyword(keyword, keyword_dir):
    products = load_reviews(keyword_dir)
    if not products:
        return None

    total_reviews = 0
    total_text = 0
    all_reviews = []
    brand_data = defaultdict(lambda: {"reviews": [], "ratings": [], "name": "", "count": 0})

    for p in products:
        reviews = p.get("reviews", [])
        pid = p.get("product_id", "")
        title = p.get("product_title", "")
        total_reviews += len(reviews)

        brand = extract_brand(title)
        brand_data[brand]["name"] = brand
        brand_data[brand]["count"] += 1

        for r in reviews:
            content = r.get("content", "") or ""
            rating = r.get("rating", 0)
            brand_data[brand]["ratings"].append(rating)

            if content and len(content) > 3:
                total_text += 1
                all_reviews.append({
                    "content": content,
                    "rating": rating,
                    "headline": r.get("headline", ""),
                    "option": r.get("option", ""),
                    "product": title,
                    "brand": brand,
                    "helpful": r.get("helpful_count", 0),
                })
                brand_data[brand]["reviews"].append({
                    "content": content,
                    "rating": rating,
                })

    complaints = [r for r in all_reviews if r["rating"] <= 2]
    satisfied = [r for r in all_reviews if r["rating"] >= 4]

    complaint_themes = extract_themes(complaints, "complaint")
    satisfaction_themes = extract_themes(satisfied, "satisfaction")
    jtbd = extract_jtbd(all_reviews)
    brand_map = analyze_brands(brand_data)
    positioning = suggest_positioning(keyword, complaint_themes, satisfaction_themes, jtbd, brand_map)

    analysis = {
        "keyword": keyword,
        "total_products": len(products),
        "total_reviews": total_reviews,
        "text_reviews": total_text,
        "complaint_themes": complaint_themes[:8],
        "satisfaction_themes": satisfaction_themes[:8],
        "jtbd": jtbd[:10],
        "brand_map": brand_map[:10],
        "positioning": positioning,
        "top_complaints": get_top_quotes(complaints, 5),
        "top_praises": get_top_quotes(satisfied, 5),
    }

    out_file = os.path.join(keyword_dir, "_analysis.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(analysis, f, ensure_ascii=False, indent=2)

    return analysis

def extract_brand(title):
    parts = title.split()
    if not parts:
        return "기타"
    brand = parts[0]
    if brand in ["NEW", "new", "세일", "무료배송", "1+1"]:
        brand = parts[1] if len(parts) > 1 else "기타"
    return brand

COMPLAINT_KEYWORDS = {
    "향 약함": ["향이 약", "향 약", "냄새 안", "냄새가 안", "향이 안", "향 없", "무향"],
    "효과 없음": ["효과 없", "효과가 없", "소용없", "안 되", "안되", "별로", "기대 이하"],
    "가격 비쌈": ["비싸", "가성비", "비싼", "가격이"],
    "양 적음": ["양이 적", "적은", "몇개 안", "양 적"],
    "녹음/변질": ["녹", "물러", "변질", "곰팡이", "습기"],
    "포장 불량": ["포장", "배송", "파손", "깨져", "터져"],
    "피부 자극": ["자극", "두드러기", "알레르기", "피부", "가려"],
    "지속 안됨": ["오래 안", "금방", "빨리 없어", "지속", "유지"],
    "냄새 불쾌": ["역한", "화학", "인공", "찝찝", "이상한 냄새"],
    "사이즈 문제": ["크기", "사이즈", "작아", "커서"],
}

SATISFACTION_KEYWORDS = {
    "향 좋음": ["향이 좋", "향 좋", "좋은 향", "냄새 좋", "향기"],
    "효과 좋음": ["효과 좋", "효과가 좋", "잘 되", "잘되", "깨끗"],
    "가성비": ["가성비", "가격 대비", "저렴", "싸"],
    "재구매 의사": ["재구매", "또 사", "또 살", "다시 구매", "계속"],
    "선물/추천": ["선물", "추천", "소개"],
    "편리함": ["편리", "편해", "간편", "쉽"],
    "디자인": ["예쁘", "디자인", "깔끔", "이쁘", "인테리어"],
    "양 많음": ["양이 많", "넉넉", "오래 쓸", "많이"],
}

JTBD_KEYWORDS = {
    "화장실": ["화장실", "욕실", "변기", "샤워"],
    "주방": ["주방", "부엌", "싱크대", "설거지"],
    "빨래": ["빨래", "세탁", "옷", "의류"],
    "건조기": ["건조기", "드라이어"],
    "아이/유아": ["아이", "아기", "유아", "어린이", "아들", "딸"],
    "반려동물": ["강아지", "고양이", "반려", "펫"],
    "선물": ["선물", "집들이", "이사"],
    "캠핑/여행": ["캠핑", "여행", "차박", "휴가"],
    "사무실": ["사무실", "회사", "직장"],
    "자취/원룸": ["자취", "원룸", "혼자", "1인"],
}

def extract_themes(reviews, mode):
    if mode == "complaint":
        kw_map = COMPLAINT_KEYWORDS
    else:
        kw_map = SATISFACTION_KEYWORDS

    counts = Counter()
    for r in reviews:
        text = r["content"] + " " + r.get("headline", "")
        for theme, keywords in kw_map.items():
            for kw in keywords:
                if kw in text:
                    counts[theme] += 1
                    break

    total = max(len(reviews), 1)
    result = []
    for theme, count in counts.most_common():
        result.append({"theme": theme, "count": count, "pct": round(count / total * 100, 1)})
    return result

def extract_jtbd(reviews):
    counts = Counter()
    for r in reviews:
        text = r["content"] + " " + r.get("headline", "")
        for jtbd, keywords in JTBD_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    counts[jtbd] += 1
                    break

    total = max(len(reviews), 1)
    result = []
    for jtbd, count in counts.most_common():
        result.append({"jtbd": jtbd, "count": count, "pct": round(count / total * 100, 1)})
    return result

def analyze_brands(brand_data):
    result = []
    for brand, data in brand_data.items():
        ratings = data["ratings"]
        if not ratings:
            continue
        avg = round(sum(ratings) / len(ratings), 1)
        total = len(ratings)
        text_count = len(data["reviews"])
        low = len([r for r in ratings if r <= 2])
        high = len([r for r in ratings if r >= 4])
        complaint_rate = round(low / max(total, 1) * 100, 1)

        sat_themes = Counter()
        comp_themes = Counter()
        for r in data["reviews"]:
            text = r["content"]
            for theme, keywords in SATISFACTION_KEYWORDS.items():
                for kw in keywords:
                    if kw in text:
                        sat_themes[theme] += 1
                        break
            for theme, keywords in COMPLAINT_KEYWORDS.items():
                for kw in keywords:
                    if kw in text:
                        comp_themes[theme] += 1
                        break

        top_strength = sat_themes.most_common(1)[0][0] if sat_themes else "-"
        top_weakness = comp_themes.most_common(1)[0][0] if comp_themes else "-"

        result.append({
            "brand": brand,
            "reviews": total,
            "text_reviews": text_count,
            "avg_rating": avg,
            "complaint_rate": complaint_rate,
            "top_strength": top_strength,
            "top_weakness": top_weakness,
            "products": data["count"],
        })

    result.sort(key=lambda x: x["reviews"], reverse=True)
    return result

def suggest_positioning(keyword, complaints, satisfactions, jtbd, brands):
    top_complaints = [c["theme"] for c in complaints[:3]]
    top_satisfactions = [s["theme"] for s in satisfactions[:3]]
    top_jtbd = [j["jtbd"] for j in jtbd[:3]]

    return {
        "opportunity": f"경쟁사 주요 불만({', '.join(top_complaints)})을 해결하는 포지셔닝",
        "must_have": f"고객이 가장 중시하는 가치: {', '.join(top_satisfactions)}",
        "use_context": f"주요 사용 상황: {', '.join(top_jtbd)}",
    }

def get_top_quotes(reviews, n=5):
    sorted_reviews = sorted(reviews, key=lambda r: r.get("helpful", 0), reverse=True)
    result = []
    for r in sorted_reviews[:n]:
        text = r["content"][:200]
        result.append({
            "text": text,
            "rating": r["rating"],
            "product": r.get("product", "")[:30],
            "helpful": r.get("helpful", 0),
        })
    return result

if __name__ == "__main__":
    keyword = sys.argv[1] if len(sys.argv) > 1 else None
    base = "/Users/macmini_ky/ClaudeAITeam/sourcing/review_output"

    if keyword:
        d = os.path.join(base, keyword)
        result = analyze_keyword(keyword, d)
        if result:
            print(f"[{keyword}] 분석 완료: {result['total_products']}개 상품, {result['total_reviews']}건 리뷰, {result['text_reviews']}건 텍스트")
            comps = [c['theme'] + '(' + str(c['pct']) + '%)' for c in result['complaint_themes'][:3]]
            sats = [s['theme'] + '(' + str(s['pct']) + '%)' for s in result['satisfaction_themes'][:3]]
            jtbds = [j['jtbd'] + '(' + str(j['pct']) + '%)' for j in result['jtbd'][:3]]
            print(f"  불만 TOP3: {', '.join(comps)}")
            print(f"  만족 TOP3: {', '.join(sats)}")
            print(f"  JTBD TOP3: {', '.join(jtbds)}")
        else:
            print(f"[{keyword}] 데이터 없음")
    else:
        keywords = ["캡슐표백제", "건조기시트", "얼룩제거제", "식기세척기 세제", "캡슐세제", "섬유탈취제"]
        for kw in keywords:
            d = os.path.join(base, kw)
            if os.path.isdir(d):
                result = analyze_keyword(kw, d)
                if result:
                    print(f"[{kw}] ✅ {result['total_products']}개 상품, {result['text_reviews']}/{result['total_reviews']}건")
