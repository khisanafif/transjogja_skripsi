import re

def fix_examples(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Query and Path
    content = content.replace('examples=[-7.7797]', 'example=-7.7797')
    content = content.replace('examples=[110.3752]', 'example=110.3752')
    content = content.replace('examples=["HT_194"]', 'example="HT_194"')
    content = content.replace('examples=[10]', 'example=10')
    content = content.replace('examples=["1A"]', 'example="1A"')
    content = content.replace('examples=["1A_0"]', 'example="1A_0"')
    content = content.replace('examples=["HT_001"]', 'example="HT_001"')

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Fixed {path}")

fix_examples(r'c:\Users\User\Downloads\transjogja_skripsi\deploy_backend\routers\all.py')
try:
    fix_examples(r'c:\Users\User\Downloads\transjogja_skripsi\app\backend\routers\all.py')
except Exception as e:
    print(e)
