import json
data = json.load(open('data/words.json', encoding='utf-8'))
freqs = [w.get('frequency', 0) for w in data]
for threshold in [0, 1, 2, 3, 5, 10]:
    count = sum(1 for f in freqs if f >= threshold)
    print(f'frequency >= {threshold}: {count} words')
