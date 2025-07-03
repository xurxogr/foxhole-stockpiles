import os
import shutil

ICONS_DIR = os.path.join(os.path.dirname(__file__), 'infantry-61', 'icons')

for filename in os.listdir(ICONS_DIR):
    if not filename.lower().endswith('.png'):
        continue
    file_path = os.path.join(ICONS_DIR, filename)
    if not os.path.isfile(file_path):
        continue
    class_name = filename[:-4]  # Remove .png
    class_dir = os.path.join(ICONS_DIR, class_name)
    os.makedirs(class_dir, exist_ok=True)
    dest_path = os.path.join(class_dir, filename)
    shutil.move(file_path, dest_path)
    print(f"Moved {filename} -> {class_dir}/")

print("Reorganization complete.") 