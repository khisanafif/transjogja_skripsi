import os
import shutil

src_web = "c:/Users/User/Downloads/transjogja_skripsi/notebook/web_artifacts"
src_mod = "c:/Users/User/Downloads/transjogja_skripsi/notebook/model"
dst = "c:/Users/User/Downloads/transjogja_skripsi/app/backend/data"

print(f"Copying artifacts to {dst}...")

# Copy web_artifacts
for f in os.listdir(src_web):
    if f.endswith('.json') or f.endswith('.csv'):
        shutil.copy(os.path.join(src_web, f), os.path.join(dst, f))
        print(f"Copied {f}")

# Copy model artifacts
for f in os.listdir(src_mod):
    if f.endswith('.json') or f.endswith('.csv'):
        shutil.copy(os.path.join(src_mod, f), os.path.join(dst, f))
        print(f"Copied {f}")

print("All artifacts copied successfully!")
