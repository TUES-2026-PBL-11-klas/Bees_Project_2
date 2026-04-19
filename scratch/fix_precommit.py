import os

def fix_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Remove trailing whitespace from each line
    lines = content.splitlines()
    fixed_lines = [line.rstrip() for line in lines]

    # Ensure exactly one newline at end of file
    new_content = '\n'.join(fixed_lines) + '\n'

    if new_content != content:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Fixed: {path}")

for root, dirs, files in os.walk('src'):
    for file in files:
        if file.endswith('.py') or file.endswith('.yaml') or file.endswith('.yml'):
            fix_file(os.path.join(root, file))

for root, dirs, files in os.walk('tests'):
    for file in files:
        if file.endswith('.py'):
            fix_file(os.path.join(root, file))
