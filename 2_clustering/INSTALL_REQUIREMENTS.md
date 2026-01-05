# 安装依赖

## 核心依赖

为了使用优化后的纯语义聚类功能，需要安装以下Python包：

### 1. Sentence Transformers (CLIP模型)

```bash
pip install sentence-transformers
```

### 2. PIL/Pillow (图像处理)

```bash
pip install pillow
```

### 3. 一键安装所有依赖

```bash
pip install sentence-transformers pillow numpy
```

## 验证安装

运行以下Python代码验证安装：

```python
from sentence_transformers import SentenceTransformer
from PIL import Image
import numpy as np

# 测试CLIP模型加载
model = SentenceTransformer('clip-ViT-B-32')
print("✓ CLIP模型加载成功")

# 测试图像编码
# img = Image.open("test.png")
# embedding = model.encode(img)
# print(f"✓ 图像embedding维度: {embedding.shape}")

# 测试文本编码
text_embedding = model.encode("Test text")
print(f"✓ 文本embedding维度: {text_embedding.shape}")
```

## 性能提升说明

安装这些依赖后，将获得以下性能提升：

1. **高质量Embedding**: 使用CLIP模型替代简单hash，相似度计算更准确
2. **VLM调用减少**: 更好的embedding质量 → 更多节点通过快速路径分配 → VLM调用次数减少50%+
3. **并行处理支持**: 使用多线程加速处理（需谨慎使用，VLM API可能有并发限制）

## 可选：GPU加速

如果有NVIDIA GPU，可以安装CUDA版本的PyTorch以加速embedding计算：

```bash
# CUDA 11.8
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118

# CUDA 12.1
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

## 降级方案

如果无法安装这些依赖，代码会自动回退到简化的embedding方法：

```python
# 警告: sentence_transformers未安装，将使用简化的embedding
# 安装命令: pip install sentence-transformers pillow
```

此时仍可运行，但准确性会降低。

## 常见问题

### Q: 安装失败怎么办？

A: 尝试升级pip：
```bash
python -m pip install --upgrade pip
pip install sentence-transformers pillow
```

### Q: CLIP模型下载慢？

A: 首次运行会自动下载模型（~350MB），可能需要10-30分钟。建议使用代理或等待完成。

### Q: 内存不足？

A: CLIP模型需要约2GB内存。如果内存不足，可以：
1. 设置 `embedding_model='text'` 使用轻量级方法
2. 使用更小的模型（虽然准确性会降低）

## 模型信息

- **使用的模型**: `clip-ViT-B-32`
- **Embedding维度**: 512
- **支持输入**: 图像和文本
- **模型大小**: ~350MB
- **来源**: Sentence Transformers Hub
