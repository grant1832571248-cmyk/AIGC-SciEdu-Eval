# 多模态 AIGC 内容自动评估系统 (Multimodal AIGC Evaluation System)

本项目是一个面向 **科学教育场景** 的多模态 AIGC 内容自动评估系统。系统通过集成深度学习模型与大语言模型，实现了对文本问答、图像生成、视频生成结果的自动化、结构化评价。

## 🌟 核心特性

- **全模态覆盖**：支持文本 (Qwen 3.5)、图像 (CLIP + Qwen)、视频 (X-CLIP + Qwen) 三类 AIGC 内容评估。
- **感知-认知双阶架构**：
    - **感知层**：利用 CLIP/X-CLIP 计算图文/影文的余弦相似度，量化视觉一致性。
    - **认知层**：利用 Qwen 3.5 裁判模型，结合教学背景（科目、学段）提供语义级的深度分析与改进建议。
- **教育专家级反馈**：输出包含 6 维质量评估、科学性分析、逻辑严密性校验及针对性教师建议。
- **工业级后端**：基于 FastAPI 构建，支持模型懒加载与单例模式，有效规避 OOM。
- **现代化 UI**：提供极具科技感的 Web 交互界面，支持雷达图、维度柱状图与报告实时渲染。

## 🏗️ 系统架构

系统采用分层解耦设计，确保了算法逻辑与业务接口的分离：

1.  **数据接入层**：负责异构输入（文本、图像、视频流）的标准化预处理。
2.  **视觉感知层**：部署 CLIP (ViT-B/32) 与 X-CLIP 模型，执行跨模态特征提取与相似度度量。
3.  **大模型认知层**：通过本地 API (127.0.0.1:8088) 调用 Qwen 3.5，对量化结果进行二次评价。
4.  **交互展现层**：基于 Vanilla JS + Chart.js 实现数据可视化与结构化报告输出。

## 📂 项目结构

```text
├── server.py              # FastAPI 后端入口与 API 路由编排
├── services_*.py          # 核心服务逻辑 (CLIP, X-CLIP, Qwen 客户端)
├── train.py               # CLIP 对比学习微调脚本
├── qwen_train.py          # Qwen LoRA 指令微调脚本
├── dataset/               # 训练与验证数据集 (Images, JSONL)
├── web/                   # 前端静态资源 (HTML, CSS, JS)
├── project_map.md         # 详细的项目模块映射手册
└── README.md              # 本说明文档
```

## 🚀 快速开始

### 1. 环境准备
确保系统安装了 Python 3.10+，并推荐使用 `uv` 或 `pip` 安装依赖：
```bash
pip install -r requirements.txt  # 或使用项目中的 uv.lock
```

### 2. 启动大模型后端
确保本地已启动兼容 OpenAI 接口的 Qwen 服务：
- 地址：`http://127.0.0.1:8088/v1`
- 模型名：`qwen-max` (或自定义)

### 3. 运行 Web 服务
```bash
python server.py
```
访问地址：`http://127.0.0.1:8000`

## 📊 业务链路

- **文本评价**：用户输入问题与回答 -> Qwen 执行 6 维打分 -> 输出结构化 JSON。
- **图像评价**：上传图片与提示词 -> CLIP 计算一致性 -> Qwen 生成科学性建议 -> 渲染雷达图报告。
- **视频评价**：上传视频与描述 -> X-CLIP 关键帧采样与匹配 -> Qwen 二次评价 -> 输出教学改进卡片。

## 🛠️ 技术栈

- **后端**：Python, FastAPI, PyTorch, Decord, Transformers, PEFT
- **模型**：Qwen 3.5, OpenAI CLIP, Microsoft X-CLIP
- **前端**：HTML5, CSS3 (Modern Tech Style), JavaScript (ES6+), Chart.js, Lucide Icons

---
*本项目适用于科学教育场景下的 AIGC 内容质量管控与辅助教学决策。*
