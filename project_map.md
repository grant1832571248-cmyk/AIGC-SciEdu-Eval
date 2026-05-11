# Project Map

## 项目概览

- 项目定位：面向科学教育场景的多模态 AIGC 内容自动评估系统，覆盖文本问答、图像生成结果、视频生成结果三类输入。
- 核心技术路线：
  - 文本评测：调用 Qwen 裁判模型，对师生问答进行 6 维质量评估并输出结构化结果。
  - 图像评测：先由 CLIP 计算图文一致性，再由 Qwen 生成科学性分析、教学建议与综合报告。
  - 视频评测：由 X-CLIP 对视频与文本提示词进行跨模态匹配，再由 Qwen 生成教学向解释建议。
- 系统结构：`FastAPI` 作为后端编排入口，`web/` 提供三类业务页面与首页导航，训练与推理脚本位于根目录，数据集位于 `dataset/`。
- 模型服务端点：Qwen 裁判模型默认通过本地接口 `http://127.0.0.1:8088/v1/chat/completions` 进行访问。

## Root Directory

- `server.py`: [server.py](file:///c:/Users/wh/Desktop/projects/clip_project/server.py) FastAPI 后端入口与 API 路由。
  - 核心功能：挂载 `/web` 静态资源；根路由直接返回首页 `index.html`；统一接入 CLIP、Qwen、X-CLIP 三类评估服务；提供图文解释、综合报告、视频报告、组合评分与配置查询接口。
  - 对外接口：
    - `GET /`：返回 `web/index.html`。
    - `GET /healthz`：健康检查。
    - `GET /api/config`：返回模型名、超时、权重路径、上传限制等运行配置。
    - `POST /api/evals/clip`：图像 + 文本提示词的一致性评分。
    - `POST /api/evals/xclip`：视频 + 文本提示词的一致性评分。
    - `POST /api/evals/video_report`：视频综合报告接口，联合 X-CLIP 与 Qwen 输出匹配评分与教学建议。
    - `POST /api/evals/qwen`：文本问答质量评估。
    - `POST /api/evals/combined`：按实际提交内容聚合 CLIP/Qwen 分数，返回综合评分。
    - `POST /api/evals/clip_explain`：基于 CLIP 分数生成教学向解释建议。
    - `POST /api/evals/report`：图像综合报告接口，联合 CLIP 与 Qwen 输出多维评估结果。
- `services_clip.py`: [services_clip.py](file:///c:/Users/wh/Desktop/projects/clip_project/services_clip.py) CLIP 图文一致性评分服务。
  - 核心功能：单例懒加载 CLIP 模型；支持加载微调权重；对图像与文本做编码、归一化和余弦相似度计算；输出 `similarity` 与 `score_0_100`。
  - 对外接口：`ClipScorer.score_image_text()`。
- `services_qwen.py`: [services_qwen.py](file:///c:/Users/wh/Desktop/projects/clip_project/services_qwen.py) Qwen 裁判客户端（OpenAI 兼容接口）。
  - 核心功能：调用 `/v1/chat/completions`（默认为 `127.0.0.1:8088`）；内置增强型 JSON 提取与异常重试；支持 `response_format={"type":"json_object"}`；支持科目与学段上下文。
  - 主要能力：
    - `judge_answer()`：文本问答 6 维度评分与归一化输出。
    - `judge_scientific_content()`：面向科学教育内容的事实性/逻辑性分析。
    - `explain_clip()`：对 CLIP 图文一致性结果做教学向解释。
    - `explain_video()`：对 X-CLIP 视频一致性结果做教学向解释与建议。
    - `generate_comprehensive_report()`：一次性生成 `science + pedagogy` 双维度综合报告。
  - 对外接口：`QwenJudgeClient.chat_json()`、`QwenJudgeClient.judge_scientific_content()`、`QwenJudgeClient.judge_answer()`、`QwenJudgeClient.explain_clip()`、`QwenJudgeClient.explain_video()`、`QwenJudgeClient.generate_comprehensive_report()`。
- `services_xclip.py`: [services_xclip.py](file:///c:/Users/wh/Desktop/projects/clip_project/services_xclip.py) X-CLIP 视频文本一致性评分服务。
  - 核心功能：懒加载 `XCLIPModel` 与 `XCLIPProcessor`；支持微调权重；通过 `decord` 或 `av` 抽取关键帧；构造视频帧输入并完成视频文本匹配。
  - 实现要点：新增多级兜底逻辑，避免 `pixel_values is None` 导致的推理失败；支持标准 `videos=` 调用、`images=` 回退调用以及手动 `image_processor` 编码；对原始 `logits_per_video` 做 `logit_scale` 还原后映射到 `0-100` 分。
  - 对外接口：`XClipScorer.score_video_text()`。
- `inference.py`: [inference.py](file:///c:/Users/wh/Desktop/projects/clip_project/inference.py) CLIP 模型推理脚本。
  - 核心功能：支持加载微调后的 CLIP 权重执行零样本推理。
  - 对外接口：`run_inference()`。
- `train.py`: [train.py](file:///c:/Users/wh/Desktop/projects/clip_project/train.py) CLIP 微调训练脚本。
  - 核心功能：基于对比学习在训练集上微调 CLIP，并在验证集输出损失和准确率指标。
  - 对外接口：`train()`。
- `dataset.py`: [dataset.py](file:///c:/Users/wh/Desktop/projects/clip_project/dataset.py) CLIP 训练数据封装模块。
  - 核心功能：定义 `CLIPDataset`，负责 JSONL 解析、图像预处理和文本 Tokenization。
  - 对外接口：`CLIPDataset`。
- `qwen_train.py`: [qwen_train.py](file:///c:/Users/wh/Desktop/projects/clip_project/qwen_train.py) Qwen LoRA SFT 训练脚本。
  - 核心功能：基于 Transformers + PEFT 对 Qwen2.5 进行指令微调，支持分布式训练。
  - 对外接口：`main()`。
- `qwen_sft_dataset.py`: [qwen_sft_dataset.py](file:///c:/Users/wh/Desktop/projects/clip_project/qwen_sft_dataset.py) Qwen 指令微调数据集与 Collator。
  - 核心功能：读取 Alpaca JSONL，按照 chat template 构造输入与 labels，仅在 assistant 片段计算损失。
  - 对外接口：`QwenSFTDataset`、`CausalLMCollator`。
- `README.md`: [README.md](file:///c:/Users/wh/Desktop/projects/clip_project/README.md) 项目说明文档。
- `test.jpg`: [test.jpg](file:///c:/Users/wh/Desktop/projects/clip_project/test.jpg) 图像推理与接口联调用测试样例。
- `uv.lock`: [uv.lock](file:///c:/Users/wh/Desktop/projects/clip_project/uv.lock) Python 依赖锁文件。
- `.python-version`: [.python-version](file:///c:/Users/wh/Desktop/projects/clip_project/.python-version) Python 版本声明。
- `.gitignore`: [.gitignore](file:///c:/Users/wh/Desktop/projects/clip_project/.gitignore) Git 忽略配置。

## Web Directory

- `web/index.html`: [index.html](file:///c:/Users/wh/Desktop/projects/clip_project/web/index.html) 系统首页与业务导航中心。
  - 核心功能：统一展示系统定位、核心能力与三个评测入口；集成动态网格背景、扫描线、轨道光环、粒子层、卡片交互与快捷导航。
- `web/image.html`: [image.html](file:///c:/Users/wh/Desktop/projects/clip_project/web/image.html) 图像评测页面。
  - 核心功能：上传图像并输入提示词；可选输入科目与学段；调用 `/api/evals/report` 一键生成综合评估报告。
  - 页面输出：综合分、雷达图、科学事实分析、图文一致性详情、主要亮点、问题列表、教师可执行建议。
- `web/text.html`: [text.html](file:///c:/Users/wh/Desktop/projects/clip_project/web/text.html) 文本问答评测页面。
  - 核心功能：录入 `question` 与 `AI answer`；可选输入科目与学段；调用 `/api/evals/qwen` 完成问答质量评估。
  - 页面输出：综合得分、等级标签、错误类型标签、雷达图、柱状图、原始 JSON 响应。
- `web/video.html`: [video.html](file:///c:/Users/wh/Desktop/projects/clip_project/web/video.html) 视频评测页面。
  - 核心功能：上传视频并输入文本描述；本地预览视频；调用 `/api/evals/video_report` 执行视频文本一致性评估与再评价建议生成。
  - 页面输出：视频匹配评分、X-CLIP 相似度、所用模型名称、匹配质量标签、Qwen 教学评价建议（亮点、问题、建议卡片）。
- `web/styles.css`: [styles.css](file:///c:/Users/wh/Desktop/projects/clip_project/web/styles.css) 全局样式表。
  - 核心功能：统一首页与三类业务页的视觉规范；提供科技背景系统、布局系统、卡片组件、徽标样式、动画效果和响应式支持。

### `web/js`

- `web/js/app_image.js`: [app_image.js](file:///c:/Users/wh/Desktop/projects/clip_project/web/js/app_image.js) 图像评测前端脚本。
  - 核心功能：处理图片预览、表单提交、加载态切换、错误提示、综合报告渲染、雷达图绘制与建议卡片展示。
- `web/js/app_text.js`: [app_text.js](file:///c:/Users/wh/Desktop/projects/clip_project/web/js/app_text.js) 文本评测前端脚本。
  - 核心功能：收集问答输入、调用 `/api/evals/qwen`、渲染评分结果、错误标签、雷达图与柱状图，并展示原始 JSON。
- `web/js/app_video.js`: [app_video.js](file:///c:/Users/wh/Desktop/projects/clip_project/web/js/app_video.js) 视频评测前端脚本。
  - 核心功能：处理视频本地预览、调用 `/api/evals/video_report`、渲染 `score_0_100`、`similarity`、模型名、匹配质量结论与 Qwen 教学评价卡片。


## Data Directory

- `dataset/`: 项目数据目录。
  - `all.jsonl`: [all.jsonl](file:///c:/Users/wh/Desktop/projects/clip_project/dataset/all.jsonl) 全量样本清单。
  - `benchmark.jsonl`: [benchmark.jsonl](file:///c:/Users/wh/Desktop/projects/clip_project/dataset/benchmark.jsonl) 基准评测数据。
  - `mapping.csv`: [mapping.csv](file:///c:/Users/wh/Desktop/projects/clip_project/dataset/mapping.csv) 图像与文本映射表的 CSV 版本。
  - `mapping.jsonl`: [mapping.jsonl](file:///c:/Users/wh/Desktop/projects/clip_project/dataset/mapping.jsonl) 图像与中文描述的映射关系。
  - `train.csv`: [train.csv](file:///c:/Users/wh/Desktop/projects/clip_project/dataset/train.csv) 训练集 CSV。
  - `train.jsonl`: [train.jsonl](file:///c:/Users/wh/Desktop/projects/clip_project/dataset/train.jsonl) 训练集 JSONL。
  - `val.csv`: [val.csv](file:///c:/Users/wh/Desktop/projects/clip_project/dataset/val.csv) 验证集 CSV。
  - `val.jsonl`: [val.jsonl](file:///c:/Users/wh/Desktop/projects/clip_project/dataset/val.jsonl) 验证集 JSONL。

## 主要业务链路

- 文本问答评测链路：
  - `web/text.html` + `web/js/app_text.js` 收集问题、回答、科目、学段。
  - `server.py:/api/evals/qwen` 接收表单并调用 `QwenJudgeClient.judge_answer()`。
  - `services_qwen.py` 返回 6 维分数、综合点评、错误类型与归一化结果。
- 图像综合评测链路：
  - `web/image.html` + `web/js/app_image.js` 上传图像与提示词。
  - `server.py:/api/evals/report` 先调用 `ClipScorer.score_image_text()` 计算图文一致性。
  - 随后调用 `QwenJudgeClient.generate_comprehensive_report()` 输出科学分析与教学建议。
  - 前端最终渲染综合得分、雷达图和结构化报告。
- 视频一致性评测链路：
  - `web/video.html` + `web/js/app_video.js` 上传视频与文本描述。
  - `server.py:/api/evals/video_report` 先调用 `XClipScorer.score_video_text()` 计算基础分。
  - 随后调用 `QwenJudgeClient.explain_video()` 基于 X-CLIP 分数生成教学建议。
  - 前端最终渲染视频匹配分、相似度、质量标签以及 Qwen 评价卡片。

## 输出与权重目录

- `checkpoints/`: 存放 CLIP 与 X-CLIP 等微调模型权重。
