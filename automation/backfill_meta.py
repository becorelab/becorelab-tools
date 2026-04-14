import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from meta_daily_report import run_single

dates = ['2026-04-09', '2026-04-10', '2026-04-11', '2026-04-12']
for d in dates:
    try:
        p = run_single(d)
        print(f'OK: {p}')
    except Exception as e:
        print(f'FAIL {d}: {e}')
