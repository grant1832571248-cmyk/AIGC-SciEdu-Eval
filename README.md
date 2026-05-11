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

## 命令行

### qwen 启动：

conda activate qwen_env

export CUDA_VISIBLE_DEVICES=0,1（这里换成空闲的卡）

export SGLANG_DISABLE_CUDNN_CHECK=1

python -m sglang.launch_server

--model-path ~/models/qwen3.5-9b

--port 8088

--tensor-parallel-size 2

--mem-fraction-static 0.7

--context-length 8192

--attention-backend triton

--trust-remote-code

--disable-custom-all-reduce

--sampling-backend pytorch

### 启动服务

uv run python -m uvicorn server:app --host 0.0.0.0 --port 8087(8088被qwen

占用了不能用，可以改为其它的)

### clip训练

uv run python -c "import train; train.train(preferred_device='cpu')"（说明：这里指定了CPU，也可以指定GPU）

### Qwen训练

python qwen_train.py
    --model_name_or_path "Qwen/Qwen2.5-7B-Instruct"
    --train_jsonl "data/train.jsonl"
    --output_dir "checkpoints/qwen_lora_output"
    --num_train_epochs 3
    --per_device_train_batch_size 4
    --gradient_accumulation_steps 4
    --learning_rate 2e-4
    --lora_r 16
    --bf16 

### 数据集添加文件

见 `add_dataset_from_folder.py`文件中的具体描述
