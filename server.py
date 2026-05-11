from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from services_clip import ClipScorer
from services_qwen import QwenJudgeClient, QwenJudgeError
from services_xclip import XClipScorer


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as e:
        raise RuntimeError(f"Invalid float env var {name}={raw!r}") from e


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as e:
        raise RuntimeError(f"Invalid int env var {name}={raw!r}") from e


APP_DIR = Path(__file__).resolve().parent
# 只使用新的 React 前端编译目录
WEB_DIR = APP_DIR / "frontend" / "dist"

# 如果目录不存在（还没运行 npm run build），先创建一个空的，防止后端启动崩溃
if not WEB_DIR.exists():
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    (WEB_DIR / "index.html").write_text("<h1>React Front-end not built.</h1><p>Please run 'npm run build' in frontend directory.</p>", encoding="utf-8")

INDEX_HTML = WEB_DIR / "index.html"


app = FastAPI(
    title="AIGC 多维度评估系统（MVP）",
    version="0.1.0",
)

# 挂载静态资源（仅 /assets 目录，不挂载根路径，避免拦截 POST API）
if (WEB_DIR / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(WEB_DIR / "assets")), name="assets")

_clip = ClipScorer(
    model_name=os.getenv("CLIP_MODEL_NAME", "ViT-B/32"),
    model_weight_path=os.getenv("CLIP_WEIGHT_PATH", "checkpoints/clip_finetuned.pt"),
)

_xclip = XClipScorer(
    model_name=os.getenv("XCLIP_MODEL_NAME", "microsoft/xclip-base-patch32"),
    model_weight_path=os.getenv("XCLIP_WEIGHT_PATH", "checkpoints/xclip_finetuned.pt"),
)

_qwen = QwenJudgeClient(
    base_url=os.getenv("QWEN_BASE_URL", "http://127.0.0.1:8088/v1"),
    model=os.getenv("QWEN_MODEL", "qwen3.5"),
    timeout_s=_env_float("QWEN_TIMEOUT_S", 120.0),
)

_composite_w_clip = _env_float("COMPOSITE_W_CLIP", 0.5)
_composite_w_qwen = _env_float("COMPOSITE_W_QWEN", 0.5)



@app.get("/healthz", include_in_schema=False)
def healthz() -> dict[str, Literal["ok"]]:
    return {"status": "ok"}


@app.post("/api/evals/clip")
async def eval_clip(
    image: UploadFile = File(...),
    text: Annotated[str, Form(...)] = "",
) -> dict[str, Any]:
    if text.strip() == "":
        raise HTTPException(status_code=422, detail="text is required")
    try:
        image_bytes = await image.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read image: {e}") from e

    try:
        result = _clip.score_image_text(image_bytes=image_bytes, text=text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CLIP scoring failed: {e}") from e

    return result


@app.post("/api/evals/xclip")
async def eval_xclip(
    video: UploadFile = File(...),
    text: Annotated[str, Form(...)] = "",
) -> dict[str, Any]:
    if text.strip() == "":
        raise HTTPException(status_code=422, detail="text is required")
    try:
        video_bytes = await video.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read video: {e}") from e

    try:
        result = _xclip.score_video_text(video_bytes=video_bytes, text=text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"X-CLIP scoring failed: {e}") from e

    return result


@app.post("/api/evals/qwen")
def eval_qwen(
    question: Annotated[str, Form(...)] = "",
    ai_answer: Annotated[str, Form(...)] = "",
    system_prompt: Annotated[str | None, Form()] = None,
    subject: Annotated[str | None, Form()] = None,
    grade: Annotated[str | None, Form()] = None,
) -> dict[str, Any]:
    if question.strip() == "" or ai_answer.strip() == "":
        raise HTTPException(status_code=422, detail="question and ai_answer are required")

    try:
        judge = _qwen.judge_answer(
            question=question,
            ai_answer=ai_answer,
            system_prompt=system_prompt,
            subject=subject,
            grade=grade,
        )
    except QwenJudgeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Qwen judge failed: {e}") from e

    return judge


@app.post("/api/evals/combined")
async def eval_combined(
    prompt: Annotated[str | None, Form()] = None,
    generated_text: Annotated[str | None, Form()] = None,
    image: UploadFile | None = File(default=None),
    question: Annotated[str | None, Form()] = None,
    ai_answer: Annotated[str | None, Form()] = None,
) -> JSONResponse:
    metrics: dict[str, Any] = {}

    clip_score_0_100: float | None = None
    if image is not None and prompt is not None and prompt.strip() != "":
        try:
            image_bytes = await image.read()
            clip_result = _clip.score_image_text(image_bytes=image_bytes, text=prompt)
            metrics["clip_image_prompt"] = clip_result
            clip_score_0_100 = float(clip_result["score_0_100"])
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"CLIP scoring failed: {e}") from e

    qwen_score_0_100: float | None = None
    if question is not None and ai_answer is not None and question.strip() != "" and ai_answer.strip() != "":
        try:
            judge = _qwen.judge_answer(question=question, ai_answer=ai_answer, system_prompt=None)
            metrics["qwen_judge"] = judge
            qwen_score_0_100 = float(judge["score_1_10"]) * 10.0
        except QwenJudgeError as e:
            raise HTTPException(status_code=502, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Qwen judge failed: {e}") from e

    if generated_text is not None and generated_text.strip() != "":
        metrics["generated_text"] = {"length": len(generated_text)}

    available_scores: list[dict[str, Any]] = []
    if clip_score_0_100 is not None:
        available_scores.append({"name": "clip", "weight": _composite_w_clip, "score_0_100": clip_score_0_100})
    if qwen_score_0_100 is not None:
        available_scores.append({"name": "qwen", "weight": _composite_w_qwen, "score_0_100": qwen_score_0_100})

    composite: dict[str, Any] | None = None
    if available_scores:
        weight_sum = sum(float(x["weight"]) for x in available_scores)
        if weight_sum <= 0:
            raise HTTPException(status_code=500, detail="Composite weights must sum to > 0")
        score_0_100 = sum(float(x["weight"]) * float(x["score_0_100"]) for x in available_scores) / weight_sum
        components = [
            {
                "name": str(x["name"]),
                "weight": float(x["weight"]),
                "normalized_weight": round(float(x["weight"]) / weight_sum, 6),
                "score_0_100": round(float(x["score_0_100"]), 2),
            }
            for x in available_scores
        ]
        composite = {
            "score_0_100": round(float(score_0_100), 2),
            "components": components,
        }

    return JSONResponse({"metrics": metrics, "composite": composite})

@app.post("/api/evals/clip_explain")
async def eval_clip_explain(
    image: UploadFile = File(...),
    text: Annotated[str, Form(...)] = "",
    audience: Annotated[str | None, Form()] = None,
) -> dict[str, Any]:
    if text.strip() == "":
        raise HTTPException(status_code=422, detail="text is required")
    try:
        image_bytes = await image.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read image: {e}") from e

    try:
        clip_result = _clip.score_image_text(image_bytes=image_bytes, text=text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CLIP scoring failed: {e}") from e

    try:
        advice = _qwen.explain_clip(
            prompt=text,
            similarity=float(clip_result.get("similarity", 0.0)),
            score_0_100=float(clip_result.get("score_0_100", 0.0)),
            audience=audience or "中小学教师",
        )
    except QwenJudgeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Qwen explain failed: {e}") from e

    return {"clip": clip_result, "advice": advice}


@app.post("/api/evals/video_report")
async def eval_video_report(
    video: UploadFile = File(...),
    text: Annotated[str, Form(...)] = "",
    audience: Annotated[str | None, Form()] = None,
    subject: Annotated[str | None, Form()] = None,
    grade: Annotated[str | None, Form()] = None,
) -> dict[str, Any]:
    """
    针对视频内容，在 X-CLIP 评分基础上增加 Qwen 的再评价建议。
    """
    if text.strip() == "":
        raise HTTPException(status_code=422, detail="text is required")
    try:
        video_bytes = await video.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read video: {e}") from e

    try:
        xclip_result = _xclip.score_video_text(video_bytes=video_bytes, text=text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"X-CLIP scoring failed: {e}") from e

    try:
        # 构造增强的受众信息
        target_audience = audience or "中小学教师"
        if subject or grade:
            context = []
            if subject: context.append(f"科目：{subject}")
            if grade: context.append(f"学段：{grade}")
            target_audience += f" (教学背景：{', '.join(context)})"

        advice = _qwen.explain_video(
            prompt=text,
            similarity=float(xclip_result.get("similarity", 0.0)),
            score_0_100=float(xclip_result.get("score_0_100", 0.0)),
            audience=target_audience,
        )
    except QwenJudgeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Qwen video explain failed: {e}") from e

    return {"xclip": xclip_result, "advice": advice}


@app.post("/api/evals/report")
async def generate_report(
    image: UploadFile = File(...),
    prompt: Annotated[str, Form(...)] = "",
    subject: Annotated[str | None, Form()] = None,
    grade: Annotated[str | None, Form()] = None,
) -> dict[str, Any]:
    """
    一键生成综合性评估报告。
    Why: 满足需求 3.3，将多维度指标整合为直观报告。
    支持可选的 subject 和 grade 参数。
    """
    if prompt.strip() == "":
        raise HTTPException(status_code=422, detail="prompt is required")
    
    try:
        image_bytes = await image.read()
        # 1. CLIP 评分
        clip_res = _clip.score_image_text(image_bytes=image_bytes, text=prompt)
        
        # 2. 合励请求：一次性获取科学评估与教师建议
        # Why: 优化请求效率，从多次 Qwen 调用合并为一次，降低延迟与成本。
        try:
            # 强制检查版本以确认代码已更新
            current_ver = getattr(_qwen, 'version', 'Unknown')
            print(f"DEBUG: Qwen Client Version: {current_ver}")
            
            # 如果版本过旧或方法缺失，尝试在此处重新实例化一个对象 (Hack: 解决热更新延迟)
            active_qwen = _qwen
            if not hasattr(_qwen, "generate_comprehensive_report"):
                print("Warning: generate_comprehensive_report missing, re-instantiating client...")
                active_qwen = QwenJudgeClient(
                    base_url=os.getenv("QWEN_BASE_URL", "http://127.0.0.1:8088/v1"),
                    model=os.getenv("QWEN_MODEL", "qwen3.5"),
                    timeout_s=_env_float("QWEN_TIMEOUT_S", 120.0),
                )

            report_func = getattr(active_qwen, "generate_comprehensive_report", None)
            if report_func:
                comp_res = report_func(
                    prompt=prompt,
                    similarity=float(clip_res.get("similarity", 0.0)),
                    score_0_100=float(clip_res.get("score_0_100", 0.0)),
                    audience="中小学教师",
                    subject=subject,
                    grade=grade,
                )
            else:
                # 最后的兜底：回退到旧逻辑，确保流程不中断
                print("Warning: Still missing generate_comprehensive_report, falling back to legacy methods")
                sci = active_qwen.judge_scientific_content(prompt=prompt)
                adv = active_qwen.explain_clip(
                    prompt=prompt,
                    similarity=float(clip_res.get("similarity", 0.0)),
                    score_0_100=float(clip_res.get("score_0_100", 0.0)),
                    audience="中小学教师"
                )
                comp_res = {"science": sci, "pedagogy": adv}
        except Exception as qe:
            # 即使 Qwen 失败，也要保证能返回 CLIP 的结果，而不是直接报错
            print(f"Qwen comprehensive report failed: {qe}")
            comp_res = {
                "science": {"fact_score": 0, "error_type": "评估服务不可用"},
                "pedagogy": {"summary": "建议服务暂时不可用", "quality_level": "中"}
            }
        
        science_res = comp_res.get("science", {})
        advice_res = comp_res.get("pedagogy", {})
        
        # 综合分计算：使用调和平均，避免“图文不符但文本本身科学”时总分仍偏高
        fact_score = float(science_res.get("fact_score", 0.0))
        clip_score = float(clip_res.get("score_0_100", 0.0))
        science_score_0_100 = max(0.0, min(100.0, fact_score * 10.0))
        if clip_score <= 0.0 or science_score_0_100 <= 0.0:
            total_score = 0.0
        else:
            total_score = 2.0 * clip_score * science_score_0_100 / (clip_score + science_score_0_100)

        return {
            "status": "success",
            "summary": {
                "total_score": round(total_score, 2),
                "is_high_quality": science_res.get("is_high_quality", False),
                "error_type": science_res.get("error_type", "无"),
            },
            "dimensions": {
                "consistency": clip_res,
                "scientific_accuracy": science_res,
                "pedagogical_advice": advice_res
            },
            "timestamp": os.getenv("CURRENT_TIME", "2026-04-12 16:00:00")
        }
    except Exception as e:
        # 捕获所有未预料的错误并返回 500
        print(f"Generate report error: {e}")
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")


@app.get("/api/config")
def get_config() -> dict[str, Any]:
    return {
        "qwen_base_url": _qwen.base_url,
        "clip_model_name": _clip.model_name,
        "qwen_timeout_s": _qwen.timeout_s,
        "clip_weight_path": str(_clip.model_weight_path) if _clip.model_weight_path is not None else None,
        "limits": {"max_upload_mb": _env_int("MAX_UPLOAD_MB", 20)},
    }


@app.get("/", include_in_schema=False)
@app.get("/{full_path:path}", include_in_schema=False)
def spa_fallback(full_path: str = "") -> FileResponse:
    """SPA fallback: 所有非 API 的 GET 请求返回 index.html，让 React Router 处理路由。"""
    if INDEX_HTML.exists():
        return FileResponse(INDEX_HTML)
    raise HTTPException(status_code=404, detail="Front-end not built")


