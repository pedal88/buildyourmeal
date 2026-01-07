import os
from PIL import Image

pantry_dir = 'static/pantry'
files = sorted([f for f in os.listdir(pantry_dir) if f.endswith('.png')])[:10]  # Check first 10

print(f"{'File':<15} {'Format':<10} {'Size (WxH)':<15} {'Mode':<10}")
print("-" * 50)

for f in files:
    path = os.path.join(pantry_dir, f)
    try:
        with Image.open(path) as img:
            print(f"{f:<15} {img.format:<10} {img.size[0]}x{img.size[1]:<10} {img.mode:<10}")
    except Exception as e:
        print(f"{f:<15} ERROR: {e}")
