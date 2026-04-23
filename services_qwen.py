from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class QwenJudgeError(RuntimeError):
    pass


@dataclass(frozen=True)
class QwenJudgeClient:
    base_url: str
    model: str
    timeout_s: float
    version: str = "1.0.2" # 用于验证代码版本

    def _parse_json_object_from_text(self, text: str) -> dict[str, Any]:
        """
        增强版 JSON 提取：应对推理模型可能在内容开头写“好的，我来评估...”的情况。
        Why: 提高解析鲁棒性，处理 Markdown 标签和截断风险。
        """
        candidate = text.strip()
        
        # 1. 尝试直接解析
        try:
            data = json.loads(candidate)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

        # 2. 尝试清洗 Markdown 标签
        clean_text = re.sub(r"```json\s*|```", "", candidate).strip()
        try:
            data = json.loads(clean_text)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

        # 3. 顺序扫描 JSON 起点，避免贪婪正则把多段内容错误拼接
        decoder = json.JSONDecoder()
        for idx, char in enumerate(candidate):
            if char != "{":
                continue
            try:
                obj, _ = decoder.raw_decode(candidate[idx:])
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                return obj

        raise QwenJudgeError(f"No valid JSON object found in output: {text[:200]}...")

    def chat_json(
        self,
        system_prompt: str,
        user_content: str,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        retries: int = 2,
        response_format: dict[str, Any] | None = None,
        top_p: float = 0.8,
    ) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
            # 关键添加：防止 Qwen 陷入复读死循环或过度发散
            "repetition_penalty": 1.1,
            "top_p": top_p
        }
        if response_format:
            payload["response_format"] = response_format

        url = self.base_url.rstrip("/") + "/chat/completions"
        last_err: Exception | None = None
        for attempt in range(retries + 1):
            try:
                resp = self._post_json(url=url, payload=payload)
                content = self._extract_message_content(resp)
                return self._parse_json_object_from_text(content)
            except (urllib.error.URLError, TimeoutError, QwenJudgeError, json.JSONDecodeError) as e:
                last_err = e
                if attempt >= retries:
                    break
                time.sleep(0.5 * (attempt + 1))
            except Exception as e:
                last_err = e
                if attempt >= retries:
                    break
                time.sleep(0.5 * (attempt + 1))
        raise QwenJudgeError(f"Qwen request failed after retries: {last_err}") from last_err

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            url=url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            raise QwenJudgeError(f"Qwen HTTPError {e.code}: {detail}") from e
        except urllib.error.URLError as e:
            raise QwenJudgeError(f"Qwen connection failed: {e}") from e
        except Exception as e:
            raise QwenJudgeError(f"Qwen request failed: {e}") from e

        try:
            return json.loads(raw.decode("utf-8"))
        except Exception as e:
            text = raw.decode("utf-8", errors="replace")
            raise QwenJudgeError(f"Invalid Qwen JSON response: {text[:500]}") from e

    def judge_scientific_content(self, prompt: str, image_description: str | None = None) -> dict[str, Any]:
        """
        专门针对科学教育内容的深度评估。
        Why: 满足需求 2.2 和 2.3，识别科学事实错误、逻辑断裂等。
        """
        sys_prompt = (
            "你是一个资深的科学教育评估专家。请针对提供的图文生成指令及图像内容描述（如有），"
            "从以下维度进行严苛评估。注意：所有分析和字段内容必须使用中文（Simplified Chinese）。\n"
            "【约束条件】：\n"
            "1. 必须且只能输出 JSON 格式。\n"
            "2. 严禁在 JSON 字段外添加任何解释说明。\n"
            "3. 详细分析(detailed_analysis)请保持简练，直接指出问题点，总长度不超过 200 字。\n"
            "4. 必须使用简体中文。\n"
            "JSON 结构：\n"
            "{\n"
            '  "fact_score": 1-10,\n'
            '  "logic_score": 1-10,\n'
            '  "error_type": "无/事实错误/逻辑断裂/术语不当",\n'
            '  "detailed_analysis": "详细分析字符串（必须中文）",\n'
            '  "is_high_quality": true/false\n'
            "}"
        )
        user_content = f"指令/文本: {prompt}\n"
        if image_description:
            user_content += f"图像内容描述: {image_description}\n"
        
        # Why: 科学事实评估需要一定推理发散，0.3 在稳定性与推理质量之间更均衡。
        return self.chat_json(system_prompt=sys_prompt, user_content=user_content, temperature=0.3, max_tokens=1024)

    def judge_answer(self, question: str, ai_answer: str, system_prompt: str | None, subject: str | None = None, grade: str | None = None) -> dict[str, Any]:
        """
        根据用户实验成功的 curl 请求进行重写。
        Why: 引入 6 个科学教育通用评估维度，并启用 response_format="json_object" 以获得更稳定的 JSON 输出。
        支持可选的 subject 和 grade 上下文。
        """
        if question.strip() == "" or ai_answer.strip() == "":
            raise ValueError("question and ai_answer must be non-empty")

        # 构造上下文信息
        context_str = ""
        if subject or grade:
            context_str = "\n【背景信息】："
            if subject: context_str += f"\n- 科目：{subject}"
            if grade: context_str += f"\n- 学段/年级：{grade}"

        sys_prompt = system_prompt or (
            "你是一个资深的科学教育评估专家。请针对提供的师生问答，从以下 6 个科学教育通用维度进行严苛评估（每项满分10分）。\n"
            "【评估维度】：\n"
            "1. 科学事实准确性 (fact_score)：科学原理是否绝对正确，有无伪科学或事实错误。\n"
            "2. 逻辑推演严密性 (logic_score)：因果关系是否合理，科学论证过程是否严密无漏洞。\n"
            "3. 认知水平匹配度 (cognitive_score)：难度是否适合该学段的学生，语言是否通俗易懂且比喻恰当。\n"
            "4. 科学探究启发性 (inquiry_score)：是否具有启发性，能引导学生主动思考或动手探究。\n"
            "5. 术语与表达规范 (terminology_score)：科学专有名词、符号、单位的使用是否标准严谨。\n"
            "6. 实验安全与伦理 (safety_score)：是否包含危险的实验操作指引，或违背生态/科学伦理的内容。\n\n"
            "【约束条件】：\n"
            "1. 必须直接输出纯 JSON 格式，严禁包含任何其他非 JSON 文本。\n"
            "2. 综合点评(comprehensive_review)请精炼指出最大亮点和教育学上的改进空间，不超过 200 字。\n"
            "JSON 结构：\n"
            "{\n"
            '  "fact_score": 0,\n'
            '  "logic_score": 0,\n'
            '  "cognitive_score": 0,\n'
            '  "inquiry_score": 0,\n'
            '  "terminology_score": 0,\n'
            '  "safety_score": 0,\n'
            '  "fatal_error": "无/事实错误/逻辑断裂/术语误用/安全违规",\n'
            '  "comprehensive_review": "综合点评字符串"\n'
            "}"
        )

        user_content = f"问题：{question}\n\n答案：{ai_answer}"
        if context_str:
            user_content = context_str + "\n\n" + user_content
        
        # Why: 使用用户实验成功的参数：temperature=0.1, top_p=0.1, max_tokens=1024
        # 并显式开启 json_object 模式。
        data = self.chat_json(
            system_prompt=sys_prompt, 
            user_content=user_content, 
            temperature=0.1, 
            top_p=0.1,
            max_tokens=1024,
            response_format={"type": "json_object"}
        )
        return self._normalize_judge_dict(data, raw=json.dumps(data, ensure_ascii=False))

    def _extract_message_content(self, resp: dict[str, Any]) -> str:
        """
        优化：优先取 content，如果 content 为空但有 reasoning_content，则取后者。
        """
        try:
            choices = resp["choices"]
            message = choices[0]["message"]
            content = message.get("content") or ""
            
            # 如果 content 是空的，但有 reasoning_content，才取后者
            if not content.strip():
                content = message.get("reasoning_content") or ""
                
            if not content.strip():
                raise QwenJudgeError("API returned empty content")
            return content
        except (KeyError, IndexError) as e:
            raise QwenJudgeError(f"Unexpected API format: {resp}") from e

    def _normalize_judge_dict(self, data: Any, raw: str) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise QwenJudgeError(f"Judge JSON must be an object: {raw[:500]}")

        # 1. 提取评分 (智能探测)
        expert_keys = [
            "fact_score", "logic_score", "cognitive_score", 
            "inquiry_score", "terminology_score", "safety_score"
        ]
        expert_scores = []
        for k in expert_keys:
            if k in data:
                try:
                    expert_scores.append(max(0, min(10, int(data[k]))))
                except (ValueError, TypeError): pass

        legacy_keys = ["score_1_10", "accuracy_score", "detail_score", "score"]
        legacy_scores = []
        for k in legacy_keys:
            if k in data:
                try:
                    legacy_scores.append(max(0, min(10, int(data[k]))))
                except (ValueError, TypeError): pass

        if expert_scores:
            avg_score = sum(expert_scores) / len(expert_scores)
        elif legacy_scores:
            avg_score = sum(legacy_scores) / len(legacy_scores)
        else:
            avg_score = 0
        
        # 2. 映射综合点评 (智能探测)
        rationale = data.get("comprehensive_review") or data.get("comment") or data.get("rationale") or ""
        if not isinstance(rationale, str):
            rationale = str(rationale)

        # 3. 映射错误类型
        fatal_error = data.get("fatal_error", "无")
        error_types = []
        if fatal_error and fatal_error != "无":
            error_types.append(fatal_error)
        
        if "error_types" in data and isinstance(data["error_types"], list):
            error_types.extend([str(x) for x in data["error_types"]])

        return {
            "score_1_10": round(avg_score, 1),
            "rationale": rationale[:500],
            "error_types": error_types[:10],
            "dimensions": {k: data.get(k, 0) for k in expert_keys} if expert_scores else {k: data.get(k, 0) for k in legacy_keys if k in data},
            "fatal_error": fatal_error,
            "comprehensive_review": rationale,
            "raw": raw,
        }

    def explain_clip(self, prompt: str, similarity: float, score_0_100: float, audience: str) -> dict[str, Any]:
        """
        基于用户实验成功的图文分析 curl 请求进行重写。
        Why: 引入更严苛的约束条件，并启用 json_object 模式以确保输出纯净。
        """
        sys_prompt = (
            "你是面向中小学教师的内容质量分析助手。所有输出必须使用中文（Simplified Chinese）。\n"
            "【约束条件】：\n"
            "1. 必须直接输出纯 JSON 格式，严禁包含任何非 JSON 文本或推理过程（Thinking Process）。\n"
            "2. 建议请保持精练，总长度不超过 300 字。\n"
            "3. 必须使用简体中文。\n"
            "JSON 结构：\n"
            "{\n"
            '  "quality_level": "高/中/低",\n'
            '  "summary": "一句话结论",\n'
            '  "highlights": ["要点"],\n'
            '  "issues": ["问题"],\n'
            '  "suggestions": ["可执行建议"]\n'
            "}"
        )
        user_content = (
            f"受众：{audience}\n"
            f"生成指令：{prompt}\n"
            f"图文相似度：{similarity:.4f}\n"
            f"图文分数(0-100)：{score_0_100:.2f}\n"
            "请直接输出评估结果 JSON。"
        )
        data = self.chat_json(
            system_prompt=sys_prompt, 
            user_content=user_content, 
            temperature=0.1, 
            top_p=0.1,
            max_tokens=1024, 
            retries=2,
            response_format={"type": "json_object"}
        )
        if not isinstance(data, dict):
            raise QwenJudgeError("Invalid explain JSON")
        return {
            "quality_level": str(data.get("quality_level", ""))[:10],
            "summary": str(data.get("summary", ""))[:200],
            "highlights": [str(x)[:100] for x in data.get("highlights", [])[:5]] if isinstance(data.get("highlights", []), list) else [],
            "issues": [str(x)[:100] for x in data.get("issues", [])[:5]] if isinstance(data.get("issues", []), list) else [],
            "suggestions": [str(x)[:120] for x in data.get("suggestions", [])[:8]] if isinstance(data.get("suggestions", []), list) else [],
        }

    def explain_video(self, prompt: str, similarity: float, score_0_100: float, audience: str) -> dict[str, Any]:
        """
        专门针对视频内容的一致性评分进行解释与建议。
        """
        sys_prompt = (
            "你是面向中小学教师的视频内容质量分析助手。所有输出必须使用中文（Simplified Chinese）。\n"
            "【约束条件】：\n"
            "1. 必须直接输出纯 JSON 格式，严禁包含任何非 JSON 文本或推理过程（Thinking Process）。\n"
            "2. 建议请保持精练，总长度不超过 400 字。\n"
            "3. 必须使用简体中文。\n"
            "JSON 结构：\n"
            "{\n"
            '  "quality_level": "高/中/低",\n'
            '  "summary": "视频内容结论",\n'
            '  "highlights": ["视频亮点"],\n'
            '  "issues": ["潜在问题"],\n'
            '  "suggestions": ["针对性改进建议"]\n'
            "}"
        )
        user_content = (
            f"受众：{audience}\n"
            f"视频描述/指令：{prompt}\n"
            f"视频-文本相似度：{similarity:.4f}\n"
            f"视频评分(0-100)：{score_0_100:.2f}\n"
            "请根据上述 X-CLIP 评分结果，从视频动态表现与文本一致性的角度，直接输出评估结果 JSON。"
        )
        data = self.chat_json(
            system_prompt=sys_prompt, 
            user_content=user_content, 
            temperature=0.1, 
            top_p=0.1,
            max_tokens=1024, 
            retries=2,
            response_format={"type": "json_object"}
        )
        if not isinstance(data, dict):
            raise QwenJudgeError("Invalid explain JSON")
        return {
            "quality_level": str(data.get("quality_level", ""))[:10],
            "summary": str(data.get("summary", ""))[:200],
            "highlights": [str(x)[:100] for x in data.get("highlights", [])[:5]] if isinstance(data.get("highlights", []), list) else [],
            "issues": [str(x)[:100] for x in data.get("issues", [])[:5]] if isinstance(data.get("issues", []), list) else [],
            "suggestions": [str(x)[:120] for x in data.get("suggestions", [])[:8]] if isinstance(data.get("suggestions", []), list) else [],
        }

    def generate_comprehensive_report(self, prompt: str, similarity: float, score_0_100: float, audience: str, subject: str | None = None, grade: str | None = None) -> dict[str, Any]:
        """
        一站式生成包含科学性与教学建议的综合报告。
        Why: 满足用户对效率的要求，将多次请求合并为一次请求，并增加数据标准化逻辑以防流程中断。
        支持可选的 subject 和 grade 参数。
        """
        # 构造上下文信息
        context_str = ""
        if subject or grade:
            context_str = "\n【背景信息】："
            if subject: context_str += f"\n- 科目：{subject}"
            if grade: context_str += f"\n- 学段/年级：{grade}"

        sys_prompt = (
            "你是面向中小学教师的内容质量评估专家。请针对提供的图文生成指令及图像评分结果，从“科学准确性”和“教学建议”两个维度进行深度评估。所有输出必须使用中文（Simplified Chinese）。\n"
            "【约束条件】：\n"
            "1. 必须直接输出纯 JSON 格式，严禁包含任何非 JSON 文本或推理过程（Thinking Process）。\n"
            "2. 分析与建议请保持精练，总长度不超过 500 字。\n"
            "3. 必须使用简体中文。\n"
            "JSON 结构：\n"
            "{\n"
            '  "science": {\n'
            '    "fact_score": 1-10,\n'
            '    "logic_score": 1-10,\n'
            '    "error_type": "无/事实错误/逻辑断裂/术语不当",\n'
            '    "detailed_analysis": "科学分析（中文）",\n'
            '    "is_high_quality": true/false\n'
            "  },\n"
            '  "pedagogy": {\n'
            '    "quality_level": "高/中/低",\n'
            '    "summary": "一句话结论",\n'
            '    "highlights": ["要点"],\n'
            '    "issues": ["问题"],\n'
            '    "suggestions": ["可执行建议"]\n'
            "  }\n"
            "}"
        )
        user_content = (
            f"受众：{audience}\n"
            f"生成指令：{prompt}\n"
            f"图文相似度：{similarity:.4f}\n"
            f"图文分数(0-100)：{score_0_100:.2f}\n"
        )
        if context_str:
            user_content += context_str + "\n"
        
        user_content += "请根据上述信息，输出包含 science 和 pedagogy 两个维度的评估结果 JSON。"
        
        data = self.chat_json(
            system_prompt=sys_prompt,
            user_content=user_content,
            temperature=0.1,
            top_p=0.1,
            max_tokens=1536,
            retries=2,
            response_format={"type": "json_object"}
        )

        science = data.get("science", {})
        pedagogy = data.get("pedagogy", {})

        def safe_int(val, default=0):
            try:
                return int(float(val))
            except (ValueError, TypeError):
                return default

        norm_science = {
            "fact_score": max(0, min(10, safe_int(science.get("fact_score")))),
            "logic_score": max(0, min(10, safe_int(science.get("logic_score")))),
            "error_type": str(science.get("error_type", "未知"))[:20],
            "detailed_analysis": str(science.get("detailed_analysis", "无详细分析"))[:500],
            "is_high_quality": bool(science.get("is_high_quality", False))
        }

        norm_pedagogy = {
            "quality_level": str(pedagogy.get("quality_level", "中"))[:10],
            "summary": str(pedagogy.get("summary", "无结论"))[:200],
            "highlights": [str(x)[:100] for x in pedagogy.get("highlights", [])[:5]] if isinstance(pedagogy.get("highlights"), list) else [],
            "issues": [str(x)[:100] for x in pedagogy.get("issues", [])[:5]] if isinstance(pedagogy.get("issues"), list) else [],
            "suggestions": [str(x)[:120] for x in pedagogy.get("suggestions", [])[:8]] if isinstance(pedagogy.get("suggestions"), list) else []
        }

        return {
            "science": norm_science,
            "pedagogy": norm_pedagogy
        }
