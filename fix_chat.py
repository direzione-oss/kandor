with open('core/utils_kandor_chat.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()
for i in range(len(lines)):
    if 'testo = \"' in lines[i] and '\".join(lines)' in lines[i+1]:
        lines[i] = '        testo = \"\\n\".join(lines)\n'
        lines[i+1] = ''
with open('core/utils_kandor_chat.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)
