python agent.py --tig "../3_intent_graph/utg/Music_Player/tig.json" --task "打开设置" --screenshot "test.jpeg" --verbose



python agent.py --tig "../3_intent_graph/utg/NetEase Cloud Music/tig.json" --task "搜索周杰伦的音乐" --screenshot "main_menu.jpeg" --verbose



python test_shortest_path.py --tig "utg/NetEase Cloud Music/tig.json" --start TIG_PLAYLIST_DISCOVERY --end TIG_SETTINGS_MENU