# UTG Visualization Module

这个模块为Android Task Automation项目提供交互式UTG（User Transition Graph）可视化功能。

## 功能特点

- **交互式网络图**: 使用vis-network库渲染节点和边
- **节点详情**: 点击节点查看状态详细信息和截图
- **边详情**: 点击边查看事件和动作信息
- **搜索和过滤**: 按步骤、活动、状态ID搜索和筛选
- **本地服务器**: 自动启动HTTP服务器避免跨域问题
- **自动浏览器**: 生成后自动在浏览器中打开

## 使用方法

### 基本用法

```bash
# 在项目根目录运行
python visualize/generate_utg_view.py

# 指定输出目录
python visualize/generate_utg_view.py 1_exploration/output_test

# 指定端口
python visualize/generate_utg_view.py 1_exploration/output_test 8080
```

### 参数说明

1. `output_dir` (可选): UTG数据目录，默认为 `1_exploration/output_test`
2. `port` (可选): HTTP服务器端口，默认为 `8000`

### 输入文件要求

脚本会自动查找以下文件：

- `utg.json` 或 `utg.js` - UTG数据文件
- `states/s0001.png`, `states/s0002.png`, ... - 状态截图
- `states/s0001.xml`, `states/s0002.xml`, ... - 状态XML文件
- `events/*.json` - 事件文件（可选）

## 界面功能

### 工具栏控件

- **Fit All**: 缩放视图以显示所有节点
- **搜索框**: 按步骤、活动名、状态ID搜索节点
- **活动筛选**: 按Android活动类型筛选显示
- **节点/边计数**: 显示当前显示的节点和边数量

### 交互功能

- **点击节点**: 在右侧边栏显示状态详情和截图
- **点击边**: 显示事件详情和动作信息  
- **节点详情包含**:
  - 状态ID、步骤、活动名称
  - 状态截图（如果可用）
  - 查看XML按钮
  - 聚焦和高亮连接按钮
- **边详情包含**:
  - 事件ID、标签、步骤
  - 源和目标状态
  - 原始动作字符串

### 视觉效果

- 节点使用状态截图作为图像
- 边显示方向箭头
- 选中时高亮显示
- 悬停显示简短信息

## 技术实现

### 依赖项

- **Python 3**: 仅使用标准库，无需额外安装包
- **前端库**: vis-network (通过CDN引入)

### 核心模块

1. **UTGDataLoader**: 负责加载和转换UTG数据
   - 支持JSON和JS格式
   - 自动格式转换为vis-network兼容格式

2. **HTML生成器**: 创建交互式可视化页面
   - 内联UTG数据到HTML
   - 响应式布局和样式

3. **UTGHTTPServer**: 本地HTTP服务器
   - 多线程服务器避免阻塞
   - 自动处理静态文件服务

### 文件结构

```
visualize/
├── generate_utg_view.py    # 主脚本
├── utg_view.html          # 生成的可视化页面
└── README.md              # 本文档
```

## 故障排除

### 常见问题

1. **端口被占用**
   ```bash
   python visualize/generate_utg_view.py 1_exploration/output_test 8001
   ```

2. **找不到UTG数据**
   - 确认输出目录包含 `utg.js` 或 `utg.json`
   - 检查文件路径是否正确

3. **图片不显示**
   - 确认 `states/` 目录包含PNG文件
   - 检查文件名格式是否为 `s0001.png`

4. **浏览器不自动打开**
   - 手动访问控制台显示的URL
   - 通常为 `http://localhost:8000/visualize/utg_view.html`

### 停止服务器

按 `Ctrl+C` 停止HTTP服务器和脚本。

## 扩展功能

可以通过修改HTML模板添加更多功能：

- 导出图像功能
- 图层管理
- 路径分析工具
- 性能统计面板

## 兼容性

- 支持所有现代浏览器
- 兼容现有UTG数据格式
- 不影响现有解析和生成代码