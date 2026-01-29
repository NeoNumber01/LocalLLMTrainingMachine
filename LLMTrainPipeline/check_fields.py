import json
with open(r'backend/storage/datasets/stage2 version2/test02-01.jsonl','r',encoding='utf-8') as f:
    d=json.loads(f.readline())
    
print('All fields:')
for k in sorted(d.keys()):
    v = d[k]
    t = type(v).__name__
    if isinstance(v, str):
        print(f'{k}: str, len={len(v)}')
    elif isinstance(v, list):
        print(f'{k}: list, len={len(v)}')
    else:
        print(f'{k}: {t}')
