(() => {
  const els = {
    prompt: document.getElementById("prompt"),
    video: document.getElementById("video"),
    videoPreview: document.getElementById("videoPreview"),
    previewContainer: document.getElementById("previewContainer"),
    btnReport: document.getElementById("btnReport"),
    status: document.getElementById("status"),
    error: document.getElementById("error"),
    reportArea: document.getElementById("reportArea"),
    totalScore: document.getElementById("totalScore"),
    reportTime: document.getElementById("reportTime"),
    summaryText: document.getElementById("summaryText"),
    qualityBadge: document.getElementById("qualityBadge"),
    xclipSimilarity: document.getElementById("xclipSimilarity"),
    modelName: document.getElementById("modelName"),
    subject: document.getElementById("subject"),
    grade: document.getElementById("grade"),
    adviceArea: document.getElementById("adviceArea"),
    adviceSummary: document.getElementById("adviceSummary"),
    adviceHighlights: document.getElementById("adviceHighlights"),
    adviceIssues: document.getElementById("adviceIssues"),
    adviceSuggestions: document.getElementById("adviceSuggestions"),
  };

  // 预览视频
  els.video.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (file) {
      const url = URL.createObjectURL(file);
      els.videoPreview.src = url;
      els.previewContainer.style.display = "block";
    }
  });

  function setBusy(busy, msg) {
    els.btnReport.disabled = busy;
    els.status.textContent = msg || "";
    if (busy) {
      els.btnReport.style.opacity = "0.7";
      els.btnReport.innerHTML = `<span class="spinner"></span> 正在分析中...`;
    } else {
      els.btnReport.style.opacity = "1";
      els.btnReport.innerHTML = `<i data-lucide="zap"></i> 生成视频评估报告`;
      lucide.createIcons();
    }
  }

  function setError(msg) {
    els.error.textContent = msg || "";
  }

  async function generateReport() {
    setError("");
    const prompt = (els.prompt.value || "").trim();
    const file = els.video.files && els.video.files[0] ? els.video.files[0] : null;

    if (!prompt || !file) {
      setError("请填写视频描述并上传视频");
      return;
    }

    setBusy(true, "X-CLIP 正在执行视频一致性评估...");

    const fd = new FormData();
    fd.append("text", prompt);
    fd.append("video", file);
    if (els.subject.value) fd.append("subject", els.subject.value);
    if (els.grade.value) fd.append("grade", els.grade.value);

    try {
      const resp = await fetch("/api/evals/video_report", {
        method: "POST",
        body: fd
      });

      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || "请求失败");
      }

      const data = await resp.json();
      displayReport(data);
    } catch (e) {
      setError(`评估失败: ${e.message}`);
    } finally {
      setBusy(false, "");
    }
  }

  function displayReport(data) {
    const xclip = data.xclip;
    const advice = data.advice;

    els.reportArea.style.display = "block";
    els.totalScore.textContent = xclip.score_0_100;
    els.reportTime.textContent = `评估时间: ${new Date().toLocaleString()}`;
    els.xclipSimilarity.textContent = xclip.similarity;
    els.modelName.textContent = xclip.model_name;
    
    els.summaryText.textContent = `该视频与描述文本的匹配度评分为 ${xclip.score_0_100}。`;
    
    let quality = "中";
    let badgeClass = "mid";
    if (xclip.score_0_100 >= 80) {
      quality = "高";
      badgeClass = "high";
    } else if (xclip.score_0_100 < 60) {
      quality = "低";
      badgeClass = "low";
    }
    
    els.qualityBadge.textContent = `匹配质量: ${quality}`;
    els.qualityBadge.className = `badge ${badgeClass}`;

    // 显示 Qwen 建议
    if (advice) {
      els.adviceArea.style.display = "block";
      els.adviceSummary.textContent = advice.summary || "暂无总结";
      
      els.adviceHighlights.innerHTML = (advice.highlights || []).map(h => `<li>${h}</li>`).join("");
      els.adviceIssues.innerHTML = (advice.issues || []).map(i => `<li>${i}</li>`).join("");
      els.adviceSuggestions.innerHTML = (advice.suggestions || []).map(s => `<li>${s}</li>`).join("");
      
      // 重新渲染图标
      lucide.createIcons();
    } else {
      els.adviceArea.style.display = "none";
    }

    // 平滑滚动到报告区域
    els.reportArea.scrollIntoView({ behavior: "smooth" });
  }

  els.btnReport.addEventListener("click", generateReport);
})();
