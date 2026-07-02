"""
Patch script untuk mempercepat Grid Search di transjogja_CRISP_DM_stable.ipynb
Grid search sebelumnya mengevaluasi 240 kombinasi x 5 fold = 1200 iterasi.
Ini memakan waktu > 25 menit.
Kita akan kurangi ruang pencarian ke parameter di sekitar yang terbaik:
- bin_size: [3, 5, 10]
- K: [1.0, 3.0, 5.0, 10.0]
- min_bin_n: [1, 3, 5]
Total: 3 * 4 * 3 = 36 kombinasi x 5 fold = 180 iterasi (akan 6x lebih cepat)
"""
import json
from pathlib import Path

nb_path = Path('transjogja_CRISP_DM_stable.ipynb')
nb = json.loads(nb_path.read_text(encoding='utf-8'))

for i, cell in enumerate(nb['cells']):
    if cell.get('cell_type') == 'code':
        source = ''.join(cell['source'])
        if 'for bin_size in [' in source and 'grid_search_cv' in source:
            source = source.replace('for bin_size in [3, 5, 10, 15, 20, 30]:', 'for bin_size in [3, 5, 10]:')
            source = source.replace('for K in [1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 20.0, 50.0]:', 'for K in [1.0, 3.0, 5.0, 10.0]:')
            source = source.replace('for min_bin_n in [1, 2, 3, 5, 10]:', 'for min_bin_n in [1, 3, 5]:')
            source = source.replace('total = 6 * 8 * 5', 'total = 3 * 4 * 3')
            
            # reconstruct lines
            new_source = [line + '\n' for line in source.split('\n')][:-1]
            nb['cells'][i]['source'] = new_source
            print("Grid search cell berhasil dipercepat.")
            break

with open(nb_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print("Notebook berhasil disimpan dengan Grid Search cepat.")
