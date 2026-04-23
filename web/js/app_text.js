document.addEventListener("DOMContentLoaded", () => {
  // Why: 确保 DOM 完全加载后再绑定事件，并增加健壮性检查。
  const getEl = (id) => {
    const el = document.getElementById(id);
    if (!el) console.warn(`Element with id "${id}" not found.`);
    return el;
  };

  const els = {
    btnEval: getEl("btnEval"),
    status: getEl("status"),
    error: getEl("error"),
    raw: getEl("raw"),
    question: getEl("question"),
    aiAnswer: getEl("aiAnswer"),
    resultArea: getEl("resultArea"),
    scoreDisplay: getEl("scoreDisplay"),
    qualityLabel: getEl("qualityLabel"),
    rationaleText: getEl("rationaleText"),
    errorTypes: getEl("errorTypes"),
    subject: getEl("subject"),
    grade: getEl("grade"),
  };

  function setBusy(busy, msg) {
    if (!els.btnEval) return;
    els.btnEval.disabled = busy;
    if (els.status) els.status.textContent = msg || "";
    if (busy) {
        els.btnEval.innerHTML = `<span class="spinner"></span> 正在裁判中...`;
        els.btnEval.style.opacity = "0.7";
    } else {
        els.btnEval.innerHTML = `<i data-lucide="search"></i> 开始文本评估`;
        els.btnEval.style.opacity = "1";
        try { if (window.lucide) lucide.createIcons(); } catch(e) {}
    }
  }

  function setError(msg) {
    if (els.error) els.error.textContent = msg || "";
  }

  async function evaluate() {
    if (!els.question || !els.aiAnswer) return;
    
    setError("");
    const q = (els.question.value || "").trim();
    const a = (els.aiAnswer.value || "").trim();

    if (!q || !a) {
      setError("请填写问题和 AI 回答");
      return;
    }

    setBusy(true, "AI 裁判正在审阅...");
    
    const fd = new FormData();
    fd.append("question", q);
    fd.append("ai_answer", a);
    if (els.subject && els.subject.value) fd.append("subject", els.subject.value);
    if (els.grade && els.grade.value) fd.append("grade", els.grade.value);

    try {
      const resp = await fetch("/api/evals/qwen", { method: "POST", body: fd });
      const data = await resp.json().catch(() => ({}));
      
      if (!resp.ok) {
        throw new Error(data.detail || `请求失败 (HTTP ${resp.status})`);
      }
      
      displayResult(data);
    } catch (e) {
      setError(`评估失败: ${e.message}`);
    } finally {
      setBusy(false, "");
    }
  }

  let radarChartInstance = null;
  let barChartInstance = null;

  function displayResult(data) {
    if (!els.resultArea) return;
    
    // 重置并触发入场动画
    els.resultArea.style.display = "block";
    els.resultArea.querySelectorAll('.card').forEach((c, idx) => {
        c.style.animation = 'none';
        void c.offsetWidth; // 触发回流以重置动画
        c.style.animation = `slideInUp 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards ${idx * 0.15}s`;
    });

    if (els.scoreDisplay) {
        els.scoreDisplay.textContent = data.score_1_10 || "0";
        // 增加分值脉冲动画
        els.scoreDisplay.classList.remove('pulse');
        void els.scoreDisplay.offsetWidth;
        els.scoreDisplay.classList.add('pulse');
    }
    if (els.rationaleText) els.rationaleText.textContent = data.comprehensive_review || data.rationale || "";
    if (els.raw) els.raw.textContent = JSON.stringify(data, null, 2);

    const score = data.score_1_10 || 0;
    let label = "低";
    let cls = "low";
    if (score >= 8) { label = "优"; cls = "high"; }
    else if (score >= 6) { label = "良"; cls = "mid"; }
    
    if (els.qualityLabel) {
        els.qualityLabel.textContent = label;
        els.qualityLabel.className = `badge ${cls}`;
    }

    if (els.errorTypes) {
        els.errorTypes.innerHTML = (data.error_types || []).map(t => `
          <span class="badge low" style="margin-right: 6px; margin-bottom: 6px;">
            <i data-lucide="alert-circle" style="width: 12px; height: 12px; vertical-align: middle; margin-right: 4px;"></i> ${t}
          </span>
        `).join("");
    }
    
    renderCharts(data.dimensions || {});

    try { if (window.lucide) lucide.createIcons(); } catch(e) {}
    
    setTimeout(() => {
        els.resultArea.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 100);
  }

  function renderCharts(dims) {
    // 1. 定义标准维度及其映射
    const expertMapping = {
      fact_score: "事实准确性",
      logic_score: "逻辑严密性",
      cognitive_score: "认知匹配度",
      inquiry_score: "探究启发性",
      terminology_score: "术语规范性",
      safety_score: "实验安全性"
    };

    const legacyMapping = {
      accuracy_score: "准确性",
      detail_score: "详实度",
      score_1_10: "综合分",
      score: "评分"
    };

    let labels = [];
    let values = [];

    // 2. 智能提取数据：优先提取专家 6 维度
    const expertKeys = Object.keys(expertMapping);
    const hasExpertData = expertKeys.some(k => k in dims);

    if (hasExpertData) {
      labels = expertKeys.map(k => expertMapping[k]);
      values = expertKeys.map(k => parseFloat(dims[k] || 0));
    } else {
      // 如果没有专家数据，则提取所有可用的 legacy 维度
      const availableLegacyKeys = Object.keys(legacyMapping).filter(k => k in dims);
      if (availableLegacyKeys.length > 0) {
        labels = availableLegacyKeys.map(k => legacyMapping[k]);
        values = availableLegacyKeys.map(k => parseFloat(dims[k] || 0));
      } else {
        // 最后的保底
        labels = expertKeys.map(k => expertMapping[k]);
        values = labels.map(() => 0);
      }
    }

    // 雷达图
    const ctxRadar = document.getElementById('radarChart');
    if (ctxRadar) {
      if (radarChartInstance) radarChartInstance.destroy();
      radarChartInstance = new Chart(ctxRadar, {
        type: 'radar',
        data: {
          labels: labels,
          datasets: [{
            label: '维度得分',
            data: values,
            backgroundColor: 'rgba(59, 130, 246, 0.2)',
            borderColor: 'rgba(59, 130, 246, 1)',
            pointBackgroundColor: 'rgba(59, 130, 246, 1)',
            pointBorderColor: '#fff',
            pointHoverBackgroundColor: '#fff',
            pointHoverBorderColor: 'rgba(59, 130, 246, 1)',
            fill: true
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            r: {
              min: 0,
              max: 10,
              beginAtZero: true,
              angleLines: { color: 'rgba(0, 0, 0, 0.1)' },
              grid: { color: 'rgba(0, 0, 0, 0.1)' },
              pointLabels: { 
                font: { size: 12, family: "system-ui", weight: 'bold' },
                color: '#475569'
              },
              ticks: { 
                display: true, 
                stepSize: 5, // 强制在 5 处显示中圈
                font: { size: 10 },
                backdropColor: 'transparent',
                z: 10
              }
            }
          },
          plugins: { legend: { display: false } }
        }
      });
    }

    // 柱状图 (始终同步更新数据)
    const ctxBar = document.getElementById('barChart');
    if (ctxBar) {
      if (barChartInstance) barChartInstance.destroy();
      barChartInstance = new Chart(ctxBar, {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [{
            label: '分值 (满分10)',
            data: values,
            backgroundColor: values.map(v => {
              if (v >= 8) return 'rgba(34, 197, 94, 0.7)';
              if (v >= 6) return 'rgba(234, 179, 8, 0.7)';
              return 'rgba(239, 68, 68, 0.7)';
            }),
            borderWidth: 0,
            borderRadius: 4
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: { beginAtZero: true, max: 10, ticks: { stepSize: 2 } }
          },
          plugins: { legend: { display: false } }
        }
      });
    }
  }

  if (els.btnEval) {
    els.btnEval.addEventListener("click", evaluate);
  }
});
