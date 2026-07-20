import os
import shutil
from pathlib import Path

def sync():
    base_dir = Path(r"c:\Users\User\Downloads\transjogja_skripsi")
    
    src_dirs = [
        base_dir / "notebook" / "preprocessed",
        base_dir / "notebook" / "model",
        base_dir / "notebook" / "web_artifacts"
    ]
    
    dest_dirs = [
        base_dir / "deploy_backend" / "data",
        base_dir / "app" / "backend" / "data"
    ]
    
    # Gather all files from src_dirs
    files_to_copy = []
    for src in src_dirs:
        if src.exists():
            for f in src.iterdir():
                if f.is_file():
                    files_to_copy.append(f)
                    
    print(f"Ditemukan {len(files_to_copy)} file dari notebook untuk disinkronisasi.")
    
    # Copy to destinations
    for dest in dest_dirs:
        if not dest.exists():
            print(f"Direktori tujuan {dest} tidak ditemukan, membuat direktori...")
            dest.mkdir(parents=True, exist_ok=True)
            
        print(f"Menyalin data ke: {dest}")
        count = 0
        for f in files_to_copy:
            dest_file = dest / f.name
            shutil.copy2(f, dest_file)
            count += 1
        print(f"Berhasil menyalin {count} file ke {dest.name}")

if __name__ == "__main__":
    sync()
