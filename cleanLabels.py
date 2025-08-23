import os

label_dirs = [
    './baseball_rubber_home_glove/baseball_rubber_home_glove/train/labels',
    './baseball_rubber_home_glove/baseball_rubber_home_glove/valid/labels',
    './baseball_rubber_home_glove/baseball_rubber_home_glove/test/labels'
]

removed_count = 0
for label_dir in label_dirs:
    for fname in os.listdir(label_dir):
        if fname.endswith('.txt'):
            path = os.path.join(label_dir, fname)
            with open(path, 'r') as f:
                lines = f.readlines()
            new_lines = [line for line in lines if not line.strip().startswith('4 ')]
            removed = len(lines) - len(new_lines)
            if removed > 0:
                with open(path, 'w') as f:
                    f.writelines(new_lines)
                removed_count += removed
                print(f"Removed {removed} class 4 label(s) from: {path}")
print(f"Total class 4 labels removed: {removed_count}")