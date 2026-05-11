## 根目录

- `server.py`：后端入口（FastAPI），统一提供评测相关接口。
- `services_clip.py`：CLIP 图文一致性评分服务。
- `services_xclip.py`：X-CLIP 视频文本一致性评分服务。
- `services_qwen.py`：Qwen 裁判模型调用与结果整理。
- `train.py`：CLIP 训练脚本。
- `inference.py`：CLIP 推理脚本。
- `dataset.py`：CLIP 训练数据读取与预处理。
- `qwen_train.py`：Qwen 指令微调训练脚本。
- `qwen_sft_dataset.py`：Qwen SFT 数据集与数据整理逻辑。
- `README.md`：项目说明文档。
- `project_map.md`：原版项目地图（详细版）。
- `project_map_simple.md`：当前这份简版项目地图。
- `test.jpg`：接口/推理测试用图片。
- `.python-version`：Python 版本声明。
- `uv.lock`：依赖锁文件。
- `.gitignore`：Git 忽略规则。
- `.inference.py.swp`：编辑器生成的临时交换文件。
- `add_dataset_from_folder.py`：向数据集添加新的数据，具体使用方法见文件内部的描述。

## 前端目录

- `web/`：前端页面 JS 实现版本（HTML + JS）。
- `frontend/`：前端页面 React 实现版本（Vite + React 工程）。
