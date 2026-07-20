import json

def extract_cells():
    with open('transjogja_CRISP_DM.ipynb', 'r', encoding='utf-8') as f:
        nb = json.load(f)
    
    with open('notebook_code_cells.py', 'w', encoding='utf-8') as f:
        for idx, cell in enumerate(nb['cells']):
            if cell['cell_type'] == 'code':
                f.write(f"# CELL_IDX: {idx}\n")
                f.write("".join(cell['source']))
                f.write("\n\n" + "#" * 40 + "\n\n")

if __name__ == '__main__':
    extract_cells()
