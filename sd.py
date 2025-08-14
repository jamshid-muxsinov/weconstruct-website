import os

def list_files(startpath):
    exclude = {"venv", "__pycache__"}  # папки для исключения
    for root, dirs, files in os.walk(startpath):
        dirs[:] = [d for d in dirs if d not in exclude]  # исключаем из обхода
        level = root.replace(startpath, '').count(os.sep)
        indent = ' ' * 4 * level
        print(f'{indent}{os.path.basename(root)}/')
        subindent = ' ' * 4 * (level + 1)
        for file in files:
            print(f'{subindent}{file}')

list_files('.')