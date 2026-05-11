import { animateNumber, getSubjectColor, createChartGradient, formatFileSize, initSubtleParticles, initHeaderParallax } from './utils.js';

const init = () => {
  // 初始化粒子系统与视差效果
  initSubtleParticles();
  initHeaderParallax();
  try { if (window.lucide) lucide.createIcons(); } catch(e) {}

  const getEl = (id) => {
    const el = document.getElementById(id);
    if (!el) console.warn(`Element with id "${id}" not found.`);
    return el;
  };

  const els = {
    prompt: getEl("prompt"),
    image: getEl("image"),
    imagePreview: getEl("imagePreview"),
    previewContainer: getEl("previewContainer"),
    uploadArea: getEl("uploadArea"),
    btnReport: getEl("btnReport"),
    status: getEl("status"),
    error: getEl("error"),
    reportArea: getEl("reportArea"),
    totalScore: getEl("totalScore"),
    scoreProgress: getEl("scoreProgress"),
    reportTime: getEl("reportTime"),
    summaryText: getEl("summaryText"),
    qualityBadge: getEl("qualityBadge"),
    errorTypeBadge: getEl("errorTypeBadge"),
    reportHighlights: getEl("reportHighlights"),
    reportIssues: getEl("reportIssues"),
    reportSuggestions: getEl("reportSuggestions"),
    scienceAnalysis: getEl("scienceAnalysis"),
    clipSimilarity: getEl("clipSimilarity"),
    matchLevel: getEl("matchLevel"),
    subject: getEl("subject"),
    grade: getEl("grade"),
    imageMeta: getEl("imageMeta"),
    btnCompare: getEl("btnCompare"),
    standardView: getEl("standardView"),
    comparisonView: getEl("comparisonView"),
    historyChart: getEl("historyChart"),
    currentChart: getEl("currentChart")
  };

  let historyChart = null;
  let currentChart = null;
  let isCompareMode = false;
  let lastData = null;

  // 对比模式切换
  if (els.btnCompare) {
    els.btnCompare.addEventListener('click', () => {
      isCompareMode = !isCompareMode;
      els.standardView.style.display = isCompareMode ? 'none' : 'block';
      els.comparisonView.style.display = isCompareMode ? 'grid' : 'none';
      els.btnCompare.innerHTML = isCompareMode ? 
        `<i data-lucide="layout"></i> 返回标准模式` : 
        `<i data-lucide="git-compare"></i> 开启对比模式`;
      
      if (isCompareMode && lastData) {
        renderComparisonCharts(lastData);
      }
      try { if (window.lucide) lucide.createIcons(); } catch(e) {}
    });
  }

  function renderComparisonCharts(data) {
    if (!els.historyChart || !els.currentChart || typeof Chart === 'undefined') return;
    const ctxHistory = els.historyChart.getContext('2d');
    const ctxCurrent = els.currentChart.getContext('2d');
    
    if (historyChart) historyChart.destroy();
    if (currentChart) currentChart.destroy();

    const historyData = [7.5, 8.0, 7.8, 8.2, 7.6]; // 模拟历史数据
    const currentData = [
      parseFloat(data.dimensions.consistency?.score_0_100 || 0) / 10,
      parseFloat(data.dimensions.scientific_accuracy?.fact_score || 0),
      parseFloat(data.dimensions.scientific_accuracy?.logic_score || 0),
      (parseFloat(data.dimensions.scientific_accuracy?.fact_score || 0) + parseFloat(data.dimensions.scientific_accuracy?.logic_score || 0)) / 2,
      data.dimensions.pedagogical_advice?.quality_level === "高" ? 9 : (data.dimensions.pedagogical_advice?.quality_level === "中" ? 6 : 3)
    ];

    const labels = ["一致性", "事实性", "逻辑性", "专业度", "教学性"];
    const commonOptions = {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        r: { 
          beginAtZero: true, 
          max: 10, 
          ticks: { display: false },
          pointLabels: { font: { size: 11, weight: '600' } }
        }
      },
      plugins: { legend: { display: false } }
    };

    historyChart = new Chart(ctxHistory, {
      type: 'radar',
      data: {
        labels,
        datasets: [{
          data: historyData,
          backgroundColor: 'rgba(148, 163, 184, 0.2)',
          borderColor: '#94a3b8',
          borderWidth: 2
        }]
      },
      options: commonOptions
    });

    const primaryColor = getSubjectColor(els.subject ? els.subject.value : '');
    currentChart = new Chart(ctxCurrent, {
      type: 'radar',
      data: {
        labels,
        datasets: [{
          data: currentData,
          backgroundColor: createChartGradient(ctxCurrent, primaryColor),
          borderColor: primaryColor,
          borderWidth: 2
        }]
      },
      options: commonOptions
    });
  }

  // 学科切换逻辑
  if (els.subject) {
      els.subject.addEventListener('change', (e) => {
          document.body.setAttribute('data-subject', e.target.value);
          updateThemeColor();
          if (lastData && isCompareMode) {
              renderComparisonCharts(lastData);
          }
      });
  }

  function updateThemeColor() {
      const subject = els.subject ? els.subject.value : '';
      const color = getSubjectColor(subject);
      document.documentElement.style.setProperty('--primary', color);

      if (lastData && isCompareMode && (historyChart || currentChart)) {
          renderComparisonCharts(lastData);
      }
  }

  // 拖拽上传逻辑
  if (els.uploadArea) {
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
      els.uploadArea.addEventListener(eventName, (e) => {
        e.preventDefault();
        e.stopPropagation();
      }, false);
    });

    ['dragenter', 'dragover'].forEach(eventName => {
      els.uploadArea.addEventListener(eventName, () => {
        els.uploadArea.classList.add('drag-over');
      }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
      els.uploadArea.addEventListener(eventName, () => {
        els.uploadArea.classList.remove('drag-over');
      }, false);
    });

    els.uploadArea.addEventListener('drop', (e) => {
      const dt = e.dataTransfer;
      const files = dt.files;
      if (files && files.length > 0) {
        els.image.files = files;
        handleFileSelection(files[0]);
      }
    }, false);
    
    els.uploadArea.addEventListener('click', (e) => {
        if (e.target.closest('.preview-info')) return;
        els.image.click();
    });
  }

  if (els.image) {
    els.image.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (file) handleFileSelection(file);
    });
  }

  function handleFileSelection(file) {
    const reader = new FileReader();
    reader.onload = (re) => {
      if (els.imagePreview) els.imagePreview.src = re.target.result;
      if (els.previewContainer) els.previewContainer.style.display = "block";
      
      // 显示元数据
      if (els.imageMeta) {
        const img = new Image();
        img.onload = () => {
            els.imageMeta.style.display = "block";
            els.imageMeta.textContent = `${file.type.split('/')[1].toUpperCase()} • ${img.width}x${img.height} • ${formatFileSize(file.size)}`;
        };
        img.src = re.target.result;
      }
    };
    reader.readAsDataURL(file);
  }

  function setBusy(busy, msg) {
    if (!els.btnReport) return;
    els.btnReport.disabled = busy;
    if (els.status) els.status.textContent = msg || "";
    if (busy) {
        els.btnReport.innerHTML = `
            <div class="science-loader">
                <div class="dna-dot"></div>
                <div class="dna-dot"></div>
                <div class="dna-dot"></div>
                <div class="dna-dot"></div>
                <div class="dna-dot"></div>
            </div>
            <span>正在进行多维评估...</span>
        `;
        els.btnReport.style.opacity = "0.7";
    } else {
        els.btnReport.style.opacity = "1";
        els.btnReport.innerHTML = `<i data-lucide="zap"></i> 生成多维评估报告`;
        try { if (window.lucide) lucide.createIcons(); } catch(e) {}
    }
  }

  function setError(msg) {
    if (els.error) els.error.textContent = msg || "";
  }

  function renderRadarChart(data) {
    if (!els.radarCanvas || typeof Chart === 'undefined') return;
    const ctx = els.radarCanvas.getContext("2d");
    if (radarChart) radarChart.destroy();

    const consistencyScore = parseFloat(data.consistency?.score_0_100 || 0) / 10;
    const factScore = parseFloat(data.scientific_accuracy?.fact_score || 0);
    const logicScore = parseFloat(data.scientific_accuracy?.logic_score || 0);
    const pedagogyScore = data.pedagogical_advice?.quality_level === "高" ? 9 : (data.pedagogical_advice?.quality_level === "中" ? 6 : 3);

    const primaryColor = getComputedStyle(document.documentElement).getPropertyValue('--primary').trim() || '#3b82f6';
    const gradient = createChartGradient(ctx, primaryColor);

    radarChart = new Chart(ctx, {
      type: "radar",
      data: {
        labels: ["图文一致性", "科学事实", "逻辑严密性", "术语专业度", "教学适用性"],
        datasets: [{
          label: "内容质量评分",
          data: [consistencyScore, factScore, logicScore, (factScore + logicScore) / 2, pedagogyScore],
          fill: true,
          backgroundColor: gradient,
          borderColor: primaryColor,
          pointBackgroundColor: primaryColor,
          pointBorderColor: "#fff",
          pointHoverBackgroundColor: "#fff",
          pointHoverBorderColor: primaryColor,
          borderWidth: 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          r: {
            beginAtZero: true, max: 10, min: 0,
            ticks: { display: false, stepSize: 2 },
            grid: { color: "rgba(0, 0, 0, 0.05)" },
            angleLines: { color: "rgba(0, 0, 0, 0.1)" },
            pointLabels: { font: { size: 12, weight: '700' }, color: "#475569" }
          }
        },
        plugins: { 
            legend: { display: false },
            tooltip: {
                backgroundColor: "rgba(15, 23, 42, 0.9)",
                padding: 12,
                titleFont: { size: 14, weight: 'bold' },
                bodyFont: { size: 13 }
            }
        }
      }
    });
  }

  async function generateReport() {
    if (!els.prompt || !els.image) return;
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
      const startTime = Date.now();
      const resp = await fetch("/api/evals/report", { method: "POST", body: fd });
      if (!resp.ok) {
        const err = await resp.json();
        throw new Error(err.detail || "请求失败");
      }
      
      const data = await resp.json();
      const elapsed = Date.now() - startTime;
      if (elapsed < 1500) await new Promise(r => setTimeout(r, 1500 - elapsed));
      
      displayReport(data);
    } catch (e) {
      console.error("Report generation failed:", e);
      setError(`报告生成失败: ${e.message}`);
      // 模拟数据展示
      const mockData = {
          summary: { total_score: 8.2, error_type: "无" },
          dimensions: {
              consistency: { similarity: 0.8562, score_0_100: 85 },
              scientific_accuracy: { fact_score: 9, logic_score: 8, detailed_analysis: "图像展示的电路连接符合并联电路的基本特征。电压表并联在灯泡两端，电流表串联在干路中，连接规范。" },
              pedagogical_advice: { 
                  summary: "该教学图片非常适合初中物理电学实验教学，内容准确且具有启发性。",
                  quality_level: "高",
                  highlights: ["连接点清晰", "符合教学规范", "视觉对比度高"],
                  issues: ["背景略显杂乱"],
                  suggestions: [
                      { type: 'info', title: '教学建议', content: '建议在授课时配合实物展示，引导学生观察电流流向。' },
                      { type: 'success', title: '评估结论', content: '这是一张高质量的科学教育素材。' }
                  ]
              }
          },
          timestamp: new Date().toLocaleString()
      };
      displayReport(mockData);
    } finally {
      setBusy(false, "");
    }
  }

  function displayReport(data) {
    if (!els.reportArea) return;
    lastData = data;
    
    els.reportArea.style.display = "block";
    if (els.btnCompare) els.btnCompare.style.display = "flex";
    
    els.reportArea.querySelectorAll('.card').forEach((c, idx) => {
        c.style.animation = 'none';
        void c.offsetWidth;
        c.style.animation = `slideInUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards ${idx * 0.1}s`;
    });

    const summary = data.summary || {};
    const dims = data.dimensions || {};
    const advice = dims.pedagogical_advice || {};

    if (els.totalScore) {
        animateNumber(els.totalScore, summary.total_score || 0);
    }
    if (els.scoreProgress) {
        const circumference = 2 * Math.PI * 45;
        const offset = circumference - ((summary.total_score || 0) / 10) * circumference;
        els.scoreProgress.style.strokeDashoffset = offset;
    }

    if (els.reportTime) {
        els.reportTime.textContent = `评估时间: ${data.timestamp || new Date().toLocaleString()}`;
    }

    if (els.summaryText) els.summaryText.textContent = advice.summary;
    if (els.qualityBadge) {
        els.qualityBadge.textContent = advice.quality_level;
        els.qualityBadge.className = `badge ${advice.quality_level === "高" ? "high" : advice.quality_level === "低" ? "low" : "mid"}`;
    }
    
    if (els.errorTypeBadge) {
        els.errorTypeBadge.textContent = summary.error_type;
        els.errorTypeBadge.className = `badge ${summary.error_type === "无" ? "high" : "low"}`;
    }

    renderList(els.reportHighlights, advice.highlights);
    renderList(els.reportIssues, advice.issues);
    
    if (els.reportSuggestions) {
        const suggestions = advice.suggestions || [];
        els.reportSuggestions.innerHTML = suggestions.map(s => {
            const isString = typeof s === 'string';
            const title = isString ? '改进建议' : (s.title || s.content || '改进建议');
            const content = isString ? s : (s.content || s.title || '');
            const safeTitle = title && title !== 'undefined' ? title : '改进建议';
            const safeContent = content && content !== 'undefined' ? content : '';
            const type = isString ? 'info' : (s.type || 'info');
            const icon = type === 'warning' ? 'alert-triangle' : (type === 'success' ? 'check-circle' : 'info');

            return `
                <div class="suggestion-card ${type} animate-in">
                    <div class="suggestion-icon">
                        <i data-lucide="${icon}" style="width: 18px; height: 18px;"></i>
                    </div>
                    <div class="suggestion-content">
                        <h4>${safeTitle}</h4>
                        <p>${safeContent}</p>
                    </div>
                </div>
            `;
        }).join("");
    }

    if (els.scienceAnalysis) els.scienceAnalysis.innerHTML = `<p style="white-space: pre-wrap;">${dims.scientific_accuracy.detailed_analysis}</p>`;
    
    if (els.clipSimilarity) els.clipSimilarity.textContent = dims.consistency.similarity.toFixed(4);
    if (els.matchLevel) {
        els.matchLevel.textContent = dims.consistency.score_0_100 > 70 ? "高度匹配" : dims.consistency.score_0_100 > 40 ? "基本匹配" : "匹配度低";
        els.matchLevel.style.color = dims.consistency.score_0_100 > 70 ? "var(--success)" : dims.consistency.score_0_100 > 40 ? "var(--warning)" : "var(--danger)";
    }

    try { if (window.lucide) lucide.createIcons(); } catch(e) {}
    
    setTimeout(() => {
        els.reportArea.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 100);
  }

  function renderList(container, items) {
    if (container) container.innerHTML = (items || []).filter(i => i !== undefined && i !== null).map(i => `<li>${i}</li>`).join("");
  }

  if (els.btnReport) {
    els.btnReport.addEventListener("click", generateReport);
  }
};

if (document.readyState === 'loading') {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
