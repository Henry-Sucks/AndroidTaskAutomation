import json

# 读取单行JSON文件
with open('C:\\Projects\\AndroidTaskAutomation\\1_exploration\\results\\NetEase Cloud Music\\com.netease.cloudmusic.json', 'r', encoding='utf-8') as f:
    data = json.load(f)  # 解析JSON

# 写入格式化后的JSON
with open('C:\\Projects\\AndroidTaskAutomation\\1_exploration\\results\\NetEase Cloud Music\\com.netease.cloudmusic.new.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=4, ensure_ascii=False)  # indent=4表示4空格缩进