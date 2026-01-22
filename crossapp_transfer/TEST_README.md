# Guided Exploration Phase 0-3 测试说明

## 更新日志

**最新更新 (基于 grounder.py 改进)**:
- ✅ 改进 `_match_screen_to_target_tigs` 函数，基于 grounder.py 的实现
- ✅ 添加真实的 embedding API 支持（阿里云 DashScope）
- ✅ 实现 embedding 缓存机制，避免重复 API 调用
- ✅ 支持 VLM 分析截图生成更准确的 UI 描述
- ✅ 改进相似度计算：70% 语义相似度 + 30% 关键词匹配

## 概述

这个测试脚本用于验证 `guided_exploration` 函数中 Phase 0-3 的有效性：
- **Phase 0**: Context Perception (环境感知 & TIG 匹配)
- **Phase 1**: Decision Making (基于上下文的决策)
- **Phase 2**: Grounding (动作映射)
- **Phase 3**: Execution Analysis (执行分析)

## 数据源

测试使用真实数据：
- `data/example_prototype.json` - 功能原型定义
- `data/tig.json` - TIG 节点库
- 通过 `parse_current_screen()` 获取真实设备屏幕状态

## 前置条件

### 1. 设备准备
- Android 设备通过 USB 连接到电脑
- 已启用 USB 调试
- 运行 `adb devices` 确认设备可见

### 2. 应用准备
- 在设备上安装并打开目标音乐应用
- 确保应用处于可交互状态（如主页或歌曲列表页）

### 3. 环境配置
```bash
# 确认 ADB 可用
adb devices

# 进入项目目录
cd crossapp_transfer
```

## 运行测试

### 基础用法
```bash
# 自动检测设备并测试第一个原型的第一个步骤
python test_guided_exploration.py
```

### 指定参数
```bash
# 指定设备序列号
python test_guided_exploration.py --serial <DEVICE_SERIAL>

# 测试特定原型和步骤
python test_guided_exploration.py --prototype 0 --step 0

# 完整示例
python test_guided_exploration.py --serial emulator-5554 --prototype 0 --step 1
```

### 参数说明
- `--serial` / `-s`: ADB 设备序列号（可通过 `adb devices` 查看）
- `--prototype` / `-p`: 原型索引（从 0 开始，默认 0）
- `--step` / `-t`: 步骤索引（从 0 开始，默认 0）

## 测试输出

### Phase 0: Context Perception
```
✓ Extracted UI Description
✓ Matched TIG: TIG_LIBRARY_BROWSE
✓ Match Score: 0.752
✓ Top Candidates (按相似度排序)
```

**改进说明**：
- 现在使用真实的 embedding API（如果配置）
- 支持 VLM 分析截图生成更准确的描述
- 使用缓存机制避免重复计算

### Phase 1: Decision Making
```
✓ Capability Feasibility Check
✓ Selected Capability: Select_Track
✓ Decision Type: EXECUTION
✓ Confidence: 0.900
```

### Phase 2: Grounding
```
✓ Semantic Keywords: {select, track, song}
✓ UI Element Scoring (Top 5)
✓ Generated Actions: 1 action(s)
  - Type: CLICK
  - Target: Song Title
```

### Phase 3: Execution Analysis
```
✓ Click action is ready
✓ Would click at bounds: [100,500][980,600]
✓ Expected: Capture new state & validate change
```

## 测试场景

### 场景 1: 选择歌曲并播放
```bash
python test_guided_exploration.py --prototype 0 --step 0
```
测试能否在歌曲列表页正确识别并选择歌曲

### 场景 2: 开始播放
```bash
python test_guided_exploration.py --prototype 0 --step 1
```
测试能否正确触发播放控制

### 场景 3: 播放控制交互
```bash
python test_guided_exploration.py --prototype 0 --step 2
```
测试能否识别并操作暂停/跳过等控件

## 输出文件

测试会在 `test_output/` 目录生成：
- `<hash>.xml` - 屏幕 UI 层次结构
- `<hash>.png` - 屏幕截图

## 故障排查

### 问题 1: "No ADB devices found"
**解决方案:**
```bash
# 检查设备连接
adb devices

# 重启 ADB 服务
adb kill-server
adb start-server
```

### 问题 2: "Failed to capture screen"
**解决方案:**
- 确保设备已解锁
- 检查 USB 调试权限
- 确认应用在前台运行

### 问题 3: "No match found - may need navigation"
**说明:** 当前屏幕与目标 TIG 不匹配，这是正常的测试场景
- Phase 1 会生成导航决策
- 检查决策类型是否为 "NAVIGATION"

### 问题 4: 导入错误
**解决方案:**
```bash
# 确保在正确的目录
cd crossapp_transfer

# 检查 utils.py 中的函数是否存在
python -c "from utils import parse_current_screen; print('OK')"
```

## 测试数据说明

### Prototype 列表
0. PlayMusic - 播放音乐
1. ManagePlaylist - 管理播放列表
2. CustomizeTheme - 自定义主题
3. AdjustEqualizer - 调整均衡器
4. SearchAndPlay - 搜索并播放

### TIG 节点示例
- `TIG_LIBRARY_BROWSE` - 歌曲库浏览
- `TIG_PLAYBACK_CONTROL` - 播放控制
- `TIG_PLAYLIST_MANAGEMENT` - 播放列表管理
- `TIG_SEARCH` - 搜索界面
- 等等...

## 下一步

测试通过后，可以：
1. 实现 Phase 4: Verification（验证步骤完成）
2. 实现 Phase 5: Recovery（错误恢复）
3. 完善 `guided_exploration` 的实际执行逻辑
4. 添加端到端的完整流程测试

## 额外测试

### 测试 TIG 匹配改进
```bash
# 单独测试 TIG 匹配功能（包括缓存、API调用等）
python test_tig_matching.py
```

这个测试会验证：
- Embedding 缓存机制
- TIG 匹配准确性
- API fallback 机制
- 相似度计算逻辑
