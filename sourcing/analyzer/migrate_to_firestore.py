"""
SQLite → Firestore 마이그레이션 스크립트
기존 analyzer.db의 모든 데이터를 Firestore로 이관
"""
import os
import sys
import sqlite3
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analyzer.firestore_db import init_firestore, db

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'analyzer.db')


def migrate():
    print('=== SQLite → Firestore 마이그레이션 시작 ===\n')

    # Firestore 초기화
    init_firestore()
    fs = db()

    # SQLite 연결
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # ── 1. 카운터 초기화를 위해 최대 ID 조회 ──
    max_ids = {}
    for table in ['market_scans', 'rfqs', 'quotations']:
        row = conn.execute(f'SELECT MAX(id) as max_id FROM {table}').fetchone()
        max_ids[table] = row['max_id'] or 0
    print(f'최대 ID: {max_ids}')

    # 카운터 설정
    counter_ref = fs.collection('_meta').document('counters')
    counter_ref.set(max_ids)
    print('카운터 설정 완료\n')

    # ── 2. market_scans ──
    scans = conn.execute('SELECT * FROM market_scans').fetchall()
    print(f'market_scans: {len(scans)}건 마이그레이션 중...')
    batch = fs.batch()
    count = 0
    for s in scans:
        d = dict(s)
        doc_ref = fs.collection('market_scans').document(str(d['id']))
        batch.set(doc_ref, d)
        count += 1
        if count >= 400:
            batch.commit()
            batch = fs.batch()
            count = 0
    if count > 0:
        batch.commit()
    print(f'  → {len(scans)}건 완료')

    # ── 3. products ──
    products = conn.execute('SELECT * FROM products').fetchall()
    print(f'products: {len(products)}건 마이그레이션 중...')
    batch = fs.batch()
    count = 0
    for p in products:
        d = dict(p)
        doc_ref = fs.collection('products').document()
        batch.set(doc_ref, d)
        count += 1
        if count >= 400:
            batch.commit()
            batch = fs.batch()
            count = 0
    if count > 0:
        batch.commit()
    print(f'  → {len(products)}건 완료')

    # ── 4. inflow_keywords ──
    keywords = conn.execute('SELECT * FROM inflow_keywords').fetchall()
    print(f'inflow_keywords: {len(keywords)}건 마이그레이션 중...')
    batch = fs.batch()
    count = 0
    for k in keywords:
        d = dict(k)
        doc_ref = fs.collection('inflow_keywords').document()
        batch.set(doc_ref, d)
        count += 1
        if count >= 400:
            batch.commit()
            batch = fs.batch()
            count = 0
    if count > 0:
        batch.commit()
    print(f'  → {len(keywords)}건 완료')

    # ── 5. keyword_variants ──
    variants = conn.execute('SELECT * FROM keyword_variants').fetchall()
    print(f'keyword_variants: {len(variants)}건 마이그레이션 중...')
    batch = fs.batch()
    count = 0
    for v in variants:
        d = dict(v)
        doc_ref = fs.collection('keyword_variants').document()
        batch.set(doc_ref, d)
        count += 1
        if count >= 400:
            batch.commit()
            batch = fs.batch()
            count = 0
    if count > 0:
        batch.commit()
    print(f'  → {len(variants)}건 완료')

    # ── 6. rfqs ──
    rfqs = conn.execute('SELECT * FROM rfqs').fetchall()
    print(f'rfqs: {len(rfqs)}건 마이그레이션 중...')
    batch = fs.batch()
    count = 0
    for r in rfqs:
        d = dict(r)
        doc_ref = fs.collection('rfqs').document(str(d['id']))
        batch.set(doc_ref, d)
        count += 1
        if count >= 400:
            batch.commit()
            batch = fs.batch()
            count = 0
    if count > 0:
        batch.commit()
    print(f'  → {len(rfqs)}건 완료')

    # ── 7. quotations ──
    quotations = conn.execute('SELECT * FROM quotations').fetchall()
    print(f'quotations: {len(quotations)}건 마이그레이션 중...')
    batch = fs.batch()
    count = 0
    for q in quotations:
        d = dict(q)
        doc_ref = fs.collection('quotations').document(str(d['id']))
        batch.set(doc_ref, d)
        count += 1
        if count >= 400:
            batch.commit()
            batch = fs.batch()
            count = 0
    if count > 0:
        batch.commit()
    print(f'  → {len(quotations)}건 완료')

    # ── 8. sourcing_history ──
    history = conn.execute('SELECT * FROM sourcing_history').fetchall()
    print(f'sourcing_history: {len(history)}건 마이그레이션 중...')
    batch = fs.batch()
    count = 0
    for h in history:
        d = dict(h)
        doc_ref = fs.collection('sourcing_history').document(str(d['id']))
        batch.set(doc_ref, d)
        count += 1
        if count >= 400:
            batch.commit()
            batch = fs.batch()
            count = 0
    if count > 0:
        batch.commit()
    print(f'  → {len(history)}건 완료')

    # ── 9. goldbox_daily ──
    goldbox = conn.execute('SELECT * FROM goldbox_daily').fetchall()
    print(f'goldbox_daily: {len(goldbox)}건 마이그레이션 중...')
    batch = fs.batch()
    count = 0
    for g in goldbox:
        d = dict(g)
        doc_ref = fs.collection('goldbox_daily').document()
        batch.set(doc_ref, d)
        count += 1
        if count >= 400:
            batch.commit()
            batch = fs.batch()
            count = 0
    if count > 0:
        batch.commit()
    print(f'  → {len(goldbox)}건 완료')

    # ── 10. collected_reviews ──
    reviews = conn.execute('SELECT * FROM collected_reviews').fetchall()
    print(f'collected_reviews: {len(reviews)}건 마이그레이션 중...')
    batch = fs.batch()
    count = 0
    for r in reviews:
        d = dict(r)
        doc_ref = fs.collection('collected_reviews').document()
        batch.set(doc_ref, d)
        count += 1
        if count >= 400:
            batch.commit()
            batch = fs.batch()
            count = 0
    if count > 0:
        batch.commit()
    print(f'  → {len(reviews)}건 완료')

    # ── 11. review_analyses ──
    analyses = conn.execute('SELECT * FROM review_analyses').fetchall()
    print(f'review_analyses: {len(analyses)}건 마이그레이션 중...')
    batch = fs.batch()
    count = 0
    for a in analyses:
        d = dict(a)
        doc_ref = fs.collection('review_analyses').document()
        batch.set(doc_ref, d)
        count += 1
        if count >= 400:
            batch.commit()
            batch = fs.batch()
            count = 0
    if count > 0:
        batch.commit()
    print(f'  → {len(analyses)}건 완료')

    conn.close()

    # ── 검증 ──
    print('\n=== 검증 ===')
    for col_name in ['market_scans', 'products', 'inflow_keywords', 'keyword_variants',
                      'rfqs', 'quotations', 'sourcing_history', 'goldbox_daily',
                      'collected_reviews', 'review_analyses']:
        docs = list(fs.collection(col_name).limit(1).stream())
        count = len(list(fs.collection(col_name).stream()))
        print(f'  {col_name}: {count}건')

    print('\n=== 마이그레이션 완료! ===')


if __name__ == '__main__':
    migrate()
