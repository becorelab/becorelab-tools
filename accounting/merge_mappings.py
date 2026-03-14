import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 대표님이 주신 매핑 파일 읽기
new_maps = {}
with open('new_mappings3.txt', 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line or '\t' not in line:
            continue
        parts = line.split('\t')
        if len(parts) >= 2:
            src = parts[0].strip()
            tgt = parts[-1].strip()
            if src and tgt:
                new_maps[src] = tgt

print(f'대표님 제공 매핑: {len(new_maps)}개')

# 기존 DEFAULT_NAME_MAP 읽기
with open('매출정산.html', 'r', encoding='utf-8') as f:
    content = f.read()

marker = 'const DEFAULT_NAME_MAP = '
start = content.index(marker) + len(marker)
depth = 0
end = start
for i in range(start, len(content)):
    if content[i] == '{':
        depth += 1
    elif content[i] == '}':
        depth -= 1
    if depth == 0:
        end = i + 1
        break

existing = json.loads(content[start:end])
print(f'기존: {len(existing)}개')

# 병합
merged = dict(existing)
new_count = sum(1 for k in new_maps if k not in merged)
merged.update(new_maps)
print(f'신규: {new_count}개 → 최종: {len(merged)}개')

# HTML에 반영
if content[end] == ';':
    end += 1
new_json = json.dumps(merged, ensure_ascii=False, separators=(',', ':'))
new_content = content[:content.index(marker)] + f'const DEFAULT_NAME_MAP = {new_json};' + content[end:]

with open('매출정산.html', 'w', encoding='utf-8') as f:
    f.write(new_content)
print('매출정산.html 반영 완료!')
