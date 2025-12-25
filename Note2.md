# 2025/11/30

给自己留了一些坑：没有处理好原UTG中的重点、重边

我想干什么？写出edge_desc!
应该很简单：根据utg.js中的内容，构造


intent生成阶段
KG-RAG的工作似乎只是分析当前页面


intent generation
修改：对每个node：生成intent-页面内容-页面坐标键值对（是否需要bbox的context？大模型能否做到这一点？是否需要辅助？）


# 2025/12/18

整理进度：现在到哪了？？？什么都不想干啊！
现在的问题是，不知道该怎么生成Global Index和Local Index

Global Index
给定当前簇 + 目标簇，告诉你下一步该去哪一个簇

Local Index 
Local Index = 簇内“子任务 / 原子技能”的库
```py
Local Index L(c) = { τ1, τ2, ..., τn }

τ = (pre, actions, post)
```
pre：执行前状态条件（语义 + UI 结构）
actions：操作序列（click / input / scroll）
post：执行后达到的稳定状态


那就先实现Local Index吧！

