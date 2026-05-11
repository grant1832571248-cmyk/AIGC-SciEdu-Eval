import { animateNumber, getSubjectColor, createChartGradient, highlightScientificErrors, initSubtleParticles, initHeaderParallax } from './utils.js';

const init = () => {
  initSubtleParticles();
  initHeaderParallax();
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
    scoreProgress: getEl("scoreProgress"),
    qualityLabel: getEl("qualityLabel"),
    rationaleText: getEl("rationaleText"),
    suggestionArea: getEl("suggestionArea"),
    subject: getEl("subject"),
    grade: getEl("grade"),
    btnToggleCompare: getEl("btnToggleCompare"),
    comparisonArea: getEl("comparisonArea"),
    normalReport: getEl("normalReport"),
    currentBrief: getEl("currentBrief"),
    historyBrief: getEl("historyBrief")
  };

  // 学科切换逻辑
  if (els.subject) {
      els.subject.addEventListener('change', (e) => {
          document.body.setAttribute('data-subject', e.target.value);
          updateThemeColor();
          if (lastDims) {
            renderCharts(lastDims);
            updateComparisonBrief({ score_1_10: parseFloat(els.scoreDisplay.textContent) || 0 });
          }
      });
  }

  function updateThemeColor() {
      const subject = els.subject ? els.subject.value : '';
      const color = getSubjectColor(subject);
      document.documentElement.style.setProperty('--primary', color);
      
      // 重新渲染图表以应用新颜色
      if (lastDims && (radarChartInstance || barChartInstance)) {
          renderCharts(lastDims);
      }
  }

  function setBusy(busy, msg) {
    if (!els.btnEval) return;
    els.btnEval.disabled = busy;
    if (els.status) els.status.textContent = msg || "";
    if (busy) {
        els.btnEval.innerHTML = `
            <div class="science-loader">
                <div class="dna-dot"></div>
                <div class="dna-dot"></div>
                <div class="dna-dot"></div>
                <div class="dna-dot"></div>
                <div class="dna-dot"></div>
            </div>
            <span>AI 深度评估中...</span>
        `;
        els.btnEval.style.opacity = "0.7";
    } else {
        els.btnEval.innerHTML = `<i data-lucide="zap"></i> 开启 AI 评估`;
        els.btnEval.style.opacity = "1";
        try { if (window.lucide) lucide.createIcons(); } catch(e) {}
    }
  }

  function setError(msg) {
    if (els.error) els.error.textContent = msg || "";
  }

  let lastDims = null;
  let radarChartInstance = null;
  let barChartInstance = null;

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
      const startTime = Date.now();
      const resp = await fetch("/api/evals/qwen", { method: "POST", body: fd });
      const data = await resp.json().catch(() => ({}));
      
      const elapsed = Date.now() - startTime;
      if (elapsed < 1200) await new Promise(r => setTimeout(r, 1200 - elapsed));
      
      if (!resp.ok) {
        throw new Error(data.detail || `请求失败 (HTTP ${resp.status})`);
      }
      
      displayResult(data);
    } catch (e) {
      console.error("Evaluation failed:", e);
      setError(`评估失败: ${e.message}`);
      // 模拟数据用于演示
      const mockData = {
          score_1_10: 7.5,
          comprehensive_review: "回答基本准确，但在科学事实的严密性上仍有提升空间。特别是关于单位换算的解释略显模糊。",
          dimensions: {
              fact_score: 8,
              logic_score: 7,
              cognitive_score: 9,
              inquiry_score: 6,
              terminology_score: 8,
              safety_score: 10
          },
          suggestions: [
              { type: 'warning', title: '科学事实提醒', content: '1.11 与 1.9 的比较在数学逻辑上应强调位值概念。' },
              { type: 'info', title: '教学启发建议', content: '可以尝试引导学生使用数轴来直观理解小数大小。' }
          ],
          fact_errors: [
              { word: '11 比 9 大', suggestion: '应解释为百分位上的 1 大于十分位补零后的 0' }
          ]
      };
      displayResult(mockData);
    } finally {
      setBusy(false, "");
    }
  }

  function displayResult(data) {
    if (!els.resultArea) return;
    
    els.resultArea.style.display = "block";
    lastDims = data.dimensions;
    
    // 1. 圆环进度条动画
    const score = data.score_1_10 || 0;
    if (els.scoreDisplay) {
        animateNumber(els.scoreDisplay, score);
    }
    if (els.scoreProgress) {
        const circumference = 2 * Math.PI * 45;
        const offset = circumference - (score / 10) * circumference;
        els.scoreProgress.style.strokeDashoffset = offset;
    }

    // 2. 文本高亮处理
    if (els.rationaleText) {
        els.rationaleText.innerHTML = highlightScientificErrors(
          data.comprehensive_review || "", 
          data.fact_errors || []
        );
    }

    // 3. 建议卡片渲染
    if (els.suggestionArea) {
        const suggestions = data.suggestions || [
            { type: 'info', title: '评估完成', content: 'AI 裁判已完成对内容的深度扫描。' }
        ];
        els.suggestionArea.innerHTML = suggestions.map(s => `
            <div class="suggestion-card ${s.type || 'info'} animate-in">
                <div class="suggestion-icon">
                    <i data-lucide="${s.type === 'warning' ? 'alert-triangle' : (s.type === 'success' ? 'check-circle' : 'info')}" style="width: 18px; height: 18px;"></i>
                </div>
                <div class="suggestion-content">
                    <h4>${s.title}</h4>
                    <p>${s.content}</p>
                </div>
            </div>
        `).join("");
    }

    if (els.raw) els.raw.textContent = JSON.stringify(data, null, 2);

    let label = "低";
    let cls = "low";
    if (score >= 8) { label = "优"; cls = "high"; }
    else if (score >= 6) { label = "良"; cls = "mid"; }
    
    if (els.qualityLabel) {
        els.qualityLabel.textContent = label;
        els.qualityLabel.className = `badge ${cls}`;
    }

    renderCharts(data.dimensions || {});
    updateComparisonBrief(data);

    try { if (window.lucide) lucide.createIcons(); } catch(e) {}
    
    setTimeout(() => {
        els.resultArea.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 100);
  }

  function renderCharts(dims) {
    const expertMapping = {
      fact_score: { label: "事实准确性", def: "评估内容是否符合已知的科学事实与定律。" },
      logic_score: { label: "逻辑严密性", def: "评估推导过程是否符合逻辑，是否存在漏洞。" },
      cognitive_score: { label: "认知匹配度", def: "评估内容是否符合目标学段学生的认知水平。" },
      inquiry_score: { label: "探究启发性", def: "评估是否能引导学生进行深入思考与探究。" },
      terminology_score: { label: "术语规范性", def: "评估科学术语的使用是否准确、规范。" },
      safety_score: { label: "实验安全性", def: "评估涉及的实验操作是否符合安全规范。" }
    };

    const labels = Object.values(expertMapping).map(v => v.label);
    const values = Object.keys(expertMapping).map(k => parseFloat(dims[k] || 0));

    // 雷达图增强
    const ctxRadar = document.getElementById('radarChart');
    if (ctxRadar && typeof Chart !== 'undefined') {
      if (radarChartInstance) radarChartInstance.destroy();
      
      const primaryColor = getComputedStyle(document.documentElement).getPropertyValue('--primary').trim() || '#3b82f6';
      const gradient = createChartGradient(ctxRadar.getContext('2d'), primaryColor);

      radarChartInstance = new Chart(ctxRadar, {
        type: 'radar',
        data: {
          labels: labels,
          datasets: [{
            label: '本次得分',
            data: values,
            backgroundColor: gradient,
            borderColor: primaryColor,
            pointBackgroundColor: primaryColor,
            pointBorderColor: '#fff',
            pointHoverBackgroundColor: '#fff',
            pointHoverBorderColor: primaryColor,
            borderWidth: 2,
            fill: true
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            r: {
              min: 0, max: 10, beginAtZero: true,
              grid: { color: 'rgba(0, 0, 0, 0.05)' },
              angleLines: { color: 'rgba(0, 0, 0, 0.1)' },
              pointLabels: { font: { size: 11, weight: '600' }, color: '#64748b' },
              ticks: { display: false, stepSize: 2 }
            }
          },
          plugins: {
            legend: { display: false },
            tooltip: {
                backgroundColor: 'rgba(15, 23, 42, 0.9)',
                padding: 12,
                titleFont: { size: 14, weight: 'bold' },
                bodyFont: { size: 13 },
                callbacks: {
                    label: (context) => {
                        const keys = Object.keys(expertMapping);
                        const key = keys[context.dataIndex];
                        return ` 得分: ${context.raw}\n 说明: ${expertMapping[key].def}`;
                    }
                }
            }
          }
        }
      });
    }

    // 柱状图
    const ctxBar = document.getElementById('barChart');
    if (ctxBar && typeof Chart !== 'undefined') {
      if (barChartInstance) barChartInstance.destroy();
      barChartInstance = new Chart(ctxBar, {
        type: 'bar',
        data: {
          labels: labels,
          datasets: [{
            data: values,
            backgroundColor: values.map(v => v >= 8 ? '#10b981' : (v >= 6 ? '#f59e0b' : '#ef4444')),
            borderRadius: 6,
            barThickness: 20
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: { grid: { display: false } },
            y: { beginAtZero: true, max: 10, grid: { color: 'rgba(0,0,0,0.03)' } }
          },
          plugins: { legend: { display: false } }
        }
      });
    }
  }

  function updateComparisonBrief(data) {
      if (els.currentBrief) {
          els.currentBrief.innerHTML = `
              <div style="font-size: 24px; font-weight: 800; color: var(--primary);">${data.score_1_10 || 0}</div>
              <div style="font-size: 12px; color: var(--fg-muted);">综合质量评分</div>
          `;
      }
      if (els.historyBrief) {
          els.historyBrief.innerHTML = `
              <div style="font-size: 24px; font-weight: 800; color: var(--fg-subtle);">6.8</div>
              <div style="font-size: 12px; color: var(--fg-muted);">同类科目历史平均</div>
          `;
      }
  }

  // 对比模式切换
  if (els.btnToggleCompare) {
      els.btnToggleCompare.addEventListener('click', () => {
          const isComparing = els.comparisonArea.style.display === 'grid';
          if (isComparing) {
              els.comparisonArea.style.display = 'none';
              els.normalReport.style.display = 'block';
              els.btnToggleCompare.innerHTML = '<i data-lucide="copy"></i> 开启历史对比';
          } else {
              els.comparisonArea.style.display = 'grid';
              els.normalReport.style.display = 'none';
              els.btnToggleCompare.innerHTML = '<i data-lucide="arrow-left"></i> 返回常规视图';
          }
          try { if (window.lucide) lucide.createIcons(); } catch(e) {}
      });
  }

  if (els.btnEval) {
    els.btnEval.addEventListener("click", evaluate);
  }
};

if (document.readyState === 'loading') {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
