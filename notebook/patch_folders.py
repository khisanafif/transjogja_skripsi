"""
Script untuk memodifikasi folder output di notebook menjadi*_stable.
"""
import json
from pathlib import Path

nb_path = Path('transjogja_CRISP_DM_stable.ipynb')
nb = json.loads(nb_path.read_text(encoding='utf-8'))

for i, cell in enumerate(nb['cells']):
    if cell.get('id') == 'setup_cell':
        source = ''.join(cell['source'])
        source = source.replace("BASE_DIR / 'preprocessed'", "BASE_DIR / 'preprocessed_stable'")
        source = source.replace("BASE_DIR / 'model'", "BASE_DIR / 'model_stable'")
        source = source.replace("BASE_DIR / 'report'", "BASE_DIR / 'report_stable'")
        source = source.replace("BASE_DIR / 'web_artifacts'", "BASE_DIR / 'web_artifacts_stable'")
        
        # reconstruct lines
        new_source = [line + '\n' for line in source.split('\n')][:-1]
        
        nb['cells'][i]['source'] = new_source
        print("Setup cell berhasil di-patch dengan folder *_stable.")
        break

with open(nb_path, 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print("Notebook berhasil disimpan.")
