(() => {
  const els = {
    prompt: document.getElementById("prompt"),
    image: document.getElementById("image"),
    imagePreview: document.getElementById("imagePreview"),
    previewContainer: document.getElementById("previewContainer"),
    btnReport: document.getElementById("btnReport"),
    status: document.getElementById("status"),
    error: document.getElementById("error"),
    reportArea: document.getElementById("reportArea"),
    totalScore: document.getElementById("totalScore"),
    reportTime: document.getElementById("reportTime"),
    summaryText: document.getElementById("summaryText"),
    qualityBadge: document.getElementById("qualityBadge"),
    errorTypeBadge: document.getElementById("errorTypeBadge"),
    reportHighlights: document.getElementById("reportHighlights"),
    reportIssues: document.getElementById("reportIssues"),
    reportSuggestions: document.getElementById("reportSuggestions"),
    scienceAnalysis: document.getElementById("scienceAnalysis"),
    clipSimilarity: document.getElementById("clipSimilarity"),
    matchLevel: document.getElementById("matchLevel"),
    radarCanvas: document.getElementById("radarChart"),
    subject: document.getElementById("subject"),
    grade: document.getElementById("grade"),
  };

  let radarChart = null;

  // 预览图片
  els.image.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = (re) => {
        els.imagePreview.src = re.target.result;
        els.previewContainer.style.display = "block";
      };
      reader.readAsDataURL(file);
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
        els.btnReport.textContent = "生成多维评估报告";
    }
  }

  function setError(msg) {
    els.error.textContent = msg || "";
  }

  function renderRadarChart(data) {
    const ctx = els.radarCanvas.getContext("2d");
    if (radarChart) radarChart.destroy();

    // Why: 增加兜底与类型转换，确保图文分数与科学分数正确映射到 0-10 坐标系。
    const consistencyScore = parseFloat(data.consistency?.score_0_100 || 0) / 10;
    const factScore = parseFloat(data.scientific_accuracy?.fact_score || 0);
    const logicScore = parseFloat(data.scientific_accuracy?.logic_score || 0);
    const pedagogyScore = data.pedagogical_advice?.quality_level === "高" ? 9 : (data.pedagogical_advice?.quality_level === "中" ? 6 : 3);

    radarChart = new Chart(ctx, {
      type: "radar",
      data: {
        labels: ["图文一致性", "科学事实", "逻辑严密性", "术语专业度", "教学适用性"],
        datasets: [{
          label: "内容质量评分",
          data: [
            consistencyScore,
            factScore,
            logicScore,
            (factScore + logicScore) / 2,
            pedagogyScore
          ],
          fill: true,
          backgroundColor: "rgba(37, 99, 235, 0.15)",
          borderColor: "rgb(37, 99, 235)",
          pointBackgroundColor: "rgb(37, 99, 235)",
          pointBorderColor: "#fff",
          pointHoverBackgroundColor: "#fff",
          pointHoverBorderColor: "rgb(37, 99, 235)"
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          r: {
            beginAtZero: true,
            max: 10,
            min: 0,
            ticks: { 
              display: true,
              stepSize: 5, // 强制显示 0, 5, 10 刻度
              font: { size: 10 },
              backdropColor: 'transparent',
              z: 10
            },
            grid: { color: "rgba(0, 0, 0, 0.1)" },
            angleLines: { color: "rgba(0, 0, 0, 0.1)" },
            pointLabels: { font: { size: 12, weight: '700' }, color: "#475569" }
          }
        },
        plugins: { 
            legend: { display: false },
            tooltip: {
                backgroundColor: "rgba(15, 23, 42, 0.9)",
                padding: 12,
                cornerRadius: 8,
                titleFont: { size: 13 },
                bodyFont: { size: 13 }
            }
        }
      }
    });
  }

  async function generateReport() {
    setError("");
    const prompt = (els.prompt.value || "").trim();
    const file = els.image.files && els.image.files[0] ? els.image.files[0] : null;

    if (!prompt || !file) {
      setError("请填写生成指令并上传图片");
      return;
    }

    setBusy(true, "AI 正在执行多维度评估...");
    
    const fd = new FormData();
    fd.append("prompt", prompt);
    fd.append("image", file);
    if (els.subject && els.subject.value) fd.append("subject", els.subject.value);
    if (els.grade && els.grade.value) fd.append("grade", els.grade.value);

    try {
      const resp = await fetch("/api/evals/report", { method: "POST", body: fd });
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || "请求失败");
      }
      
      const data = await resp.json();
      displayReport(data);
    } catch (e) {
      setError(`报告生成失败: ${e.message}`);
    } finally {
      setBusy(false, "");
    }
  }

  function displayReport(data) {
    if (!els.reportArea) return;
    
    // 重置并触发入场动画
    els.reportArea.style.display = "block";
    els.reportArea.querySelectorAll('.card').forEach((c, idx) => {
        c.style.animation = 'none';
        void c.offsetWidth; // 触发回流
        c.style.animation = `slideInUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards ${idx * 0.1}s`;
    });

    const summary = data.summary || {};
    const dims = data.dimensions || {};
    const consistency = dims.consistency || {};
    const science = dims.scientific_accuracy || {};
    const advice = dims.pedagogical_advice || {};

    if (els.totalScore) {
        els.totalScore.textContent = summary.total_score || "0";
        // 增加分值脉冲动画
        els.totalScore.classList.remove('pulse');
        void els.totalScore.offsetWidth;
        els.totalScore.classList.add('pulse');
    }

    if (els.reportTime) {
        els.reportTime.textContent = `评估时间: ${data.timestamp || new Date().toLocaleString()}`;
    }

    const clip = consistency;

    els.summaryText.textContent = advice.summary;
    
    // 状态标签
    els.qualityBadge.textContent = `质量: ${advice.quality_level}`;
    els.qualityBadge.className = `badge ${advice.quality_level === "高" ? "high" : advice.quality_level === "低" ? "low" : "mid"}`;
    
    els.errorTypeBadge.textContent = `错误类型: ${data.summary.error_type}`;
    els.errorTypeBadge.className = `badge ${data.summary.error_type === "无" ? "high" : "low"}`;

    // 列表渲染
    renderList(els.reportHighlights, advice.highlights);
    renderList(els.reportIssues, advice.issues);
    
    // 建议卡片
    els.reportSuggestions.innerHTML = advice.suggestions.map((s, idx) => `
      <div class="animate-in" style="animation-delay: ${0.4 + idx * 0.1}s; background: white; border: 1px solid var(--border); padding: 16px; border-radius: var(--radius-md); font-size: 14px; box-shadow: var(--shadow-sm);">
        <div style="color: var(--primary); font-weight: bold; margin-bottom: 4px;">建议 ${idx + 1}</div>
        ${s}
      </div>
    `).join("");

    // 科学分析
    els.scienceAnalysis.innerHTML = `<p style="white-space: pre-wrap;">${science.detailed_analysis}</p>`;
    
    // CLIP 详情
    els.clipSimilarity.textContent = clip.similarity.toFixed(4);
    els.matchLevel.textContent = clip.score_0_100 > 70 ? "高度匹配" : clip.score_0_100 > 40 ? "基本匹配" : "匹配度低";
    els.matchLevel.style.color = clip.score_0_100 > 70 ? "var(--success)" : clip.score_0_100 > 40 ? "var(--warning)" : "var(--danger)";

    // 可视化图表
    renderRadarChart(data.dimensions);
    
    // 平滑滚动
    setTimeout(() => {
        els.reportArea.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 100);
  }

  function renderList(container, items) {
    container.innerHTML = (items || []).map(i => `<li>${i}</li>`).join("");
  }

  els.btnReport.addEventListener("click", generateReport);

})();
