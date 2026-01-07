import os
import shutil

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANTRY_DIR = os.path.join(ROOT_DIR, 'static', 'pantry')
ORIGINALS_DIR = os.path.join(PANTRY_DIR, 'originals')

def migrate():
    # 1. Create directory
    if not os.path.exists(ORIGINALS_DIR):
        print(f"Creating {ORIGINALS_DIR}...")
        os.makedirs(ORIGINALS_DIR)
    
    # 2. List files
    files = [f for f in os.listdir(PANTRY_DIR) if f.lower().endswith('.png')]
    print(f"Found {len(files)} images in pantry.")
    
    count = 0
    skipped = 0
    
    # 3. Copy files
    for f in files:
        src = os.path.join(PANTRY_DIR, f)
        dst = os.path.join(ORIGINALS_DIR, f)
        
        # Determine if we skip
        if os.path.exists(dst):
            # We treat originals as LOCKED. If it exists, we don't overwrite.
            skipped += 1
            continue
            
        try:
            shutil.copy2(src, dst)
            count += 1
            if count % 50 == 0:
                print(f"Copied {count} files...")
        except Exception as e:
            print(f"Error copying {f}: {e}")
            
    print(f"Migration Complete.")
    print(f"Copied: {count}")
    print(f"Skipped (Already existed): {skipped}")

if __name__ == "__main__":
    migrate()
