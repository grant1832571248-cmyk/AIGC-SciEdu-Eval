import { useState, useRef, useEffect } from 'react'
import axios from 'axios'
import { Radar, Bar } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  RadialLinearScale,
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend
} from 'chart.js'
import { Edit3, Zap, Activity, Hexagon, Copy, AlertTriangle, Info, CheckCircle, Search, BarChart3, GitCompare, Code } from 'lucide-react'
import { clsx } from 'clsx'

ChartJS.register(
  RadialLinearScale,
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend
)

const DIMENSION_LABELS = {
  fact_score: { label: "事实准确性", def: "评估内容是否符合已知的科学事实与定律。" },
  logic_score: { label: "逻辑严密性", def: "评估推导过程是否符合逻辑，是否存在漏洞。" },
  cognitive_score: { label: "认知匹配度", def: "评估内容是否符合目标学段学生的认知水平。" },
  inquiry_score: { label: "探究启发性", def: "评估是否能引导学生进行深入思考与探究。" },
  terminology_score: { label: "术语规范性", def: "评估科学术语的使用是否准确、规范。" },
  safety_score: { label: "实验安全性", def: "评估涉及的实验操作是否符合安全规范。" }
}

const SUBJECTS = [
  { value: '', label: '-- 请选择科目 --' },
  { value: 'science', label: '科学' },
  { value: 'physics', label: '物理' },
  { value: 'chemistry', label: '化学' },
  { value: 'biology', label: '生物' },
  { value: 'earth', label: '地理' },
  { value: 'it', label: '信息技术' }
]

const GRADES = [
  { value: '', label: '-- 请选择学段 --' },
  { value: '小学低年级', label: '小学低年级 (1-3年级)' },
  { value: '小学高年级', label: '小学高年级 (4-6年级)' },
  { value: '初中', label: '初中' },
  { value: '高中', label: '高中' },
]

function getQualityInfo(score) {
  if (score >= 8) return { label: '优', cls: 'high' }
  if (score >= 6) return { label: '良', cls: 'mid' }
  return { label: '低', cls: 'low' }
}

function SuggestionCard({ type, title, content }) {
  const icons = {
    warning: AlertTriangle,
    info: Info,
    success: CheckCircle
  }
  const Icon = icons[type] || Info

  return (
    <div className={clsx('suggestion-card', type)}>
      <div className="suggestion-icon">
        <Icon size={18} />
      </div>
      <div className="suggestion-content">
        <h4>{title}</h4>
        <p>{content}</p>
      </div>
    </div>
  )
}

export default function TextEval() {
  const [question, setQuestion] = useState('')
  const [aiAnswer, setAiAnswer] = useState('')
  const [subject, setSubject] = useState('')
  const [grade, setGrade] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')
  const [showCompare, setShowCompare] = useState(false)

  const scoreDisplayRef = useRef(null)
  const radarChartRef = useRef(null)
  const barChartRef = useRef(null)

  useEffect(() => {
    document.body.dataset.subject = subject
  }, [subject])

  const handleSubjectChange = (e) => {
    setSubject(e.target.value)
  }

  const handleEvaluate = async () => {
    setError('')
    const q = question.trim()
    const a = aiAnswer.trim()

    if (!q || !a) {
      setError('请填写问题和 AI 回答')
      return
    }

    setLoading(true)
    setStatus('AI 裁判正在审阅...')

    const formData = new FormData()
    formData.append('question', q)
    formData.append('ai_answer', a)
    if (subject) formData.append('subject', subject)
    if (grade) formData.append('grade', grade)

    try {
      const startTime = Date.now()
      const response = await axios.post('/api/evals/qwen', formData)
      const data = response.data

      const elapsed = Date.now() - startTime
      if (elapsed < 1200) {
        await new Promise(r => setTimeout(r, 1200 - elapsed))
      }

      setResult(data)
      setStatus('')
    } catch (err) {
      console.error('Evaluation failed:', err)
      setError(`评估失败: ${err.response?.data?.detail || err.message}`)
      setStatus('')
    } finally {
      setLoading(false)
    }
  }

  // 文本错误高亮处理
  const highlightErrors = (text, errors = []) => {
    if (!errors || errors.length === 0) return text
    let result = text
    errors.forEach(err => {
      if (!err.word) return
      result = result.replace(
        new RegExp(err.word, 'g'),
        `<span class="error-highlight" title="建议: ${err.suggestion}">${err.word}</span>`
      )
    })
    return result
  }

  const qualityInfo = result ? getQualityInfo(result.score_1_10) : null

  const getRadarData = () => {
    if (!result?.dimensions) return null;
    const primaryColor = getComputedStyle(document.body).getPropertyValue('--primary').trim() || '#3b82f6';
    return {
      labels: Object.keys(DIMENSION_LABELS).map(k => DIMENSION_LABELS[k].label),
      datasets: [{
        label: '本次得分',
        data: Object.keys(DIMENSION_LABELS).map(k => parseFloat(result.dimensions[k] || 0)),
        backgroundColor: `${primaryColor}33`,
        borderColor: primaryColor,
        borderWidth: 2,
        pointBackgroundColor: primaryColor,
        pointBorderColor: '#fff',
        pointHoverBackgroundColor: '#fff',
        pointHoverBorderColor: primaryColor,
        fill: true
      }]
    }
  }

  const barData = result?.dimensions ? {
    labels: Object.keys(DIMENSION_LABELS).map(k => DIMENSION_LABELS[k].label),
    datasets: [{
      label: '维度得分',
      data: Object.keys(DIMENSION_LABELS).map(k => parseFloat(result.dimensions[k] || 0)),
      backgroundColor: Object.keys(DIMENSION_LABELS).map(k => {
        const v = parseFloat(result.dimensions[k] || 0)
        return v >= 8 ? '#10b981' : (v >= 6 ? '#f59e0b' : '#ef4444')
      }),
      borderRadius: 6
    }]
  } : null

  const radarOptions = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      r: {
        min: 0,
        max: 10,
        beginAtZero: true,
        ticks: { display: false, stepSize: 2 },
        grid: { color: 'rgba(0, 0, 0, 0.05)' },
        angleLines: { color: 'rgba(0, 0, 0, 0.1)' },
        pointLabels: {
          font: { size: 11, weight: '600' },
          color: '#64748b'
        }
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
            const keys = Object.keys(DIMENSION_LABELS)
            const key = keys[context.dataIndex]
            return ` 得分: ${context.raw}\n 说明: ${DIMENSION_LABELS[key].def}`
          }
        }
      }
    }
  }

  const barOptions = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      y: {
        beginAtZero: true,
        max: 10,
        grid: { color: 'rgba(0, 0, 0, 0.04)' }
      },
      x: {
        grid: { display: false }
      }
    },
    plugins: {
      legend: { display: false }
    }
  }

  // 计算动态指标
  const getMetrics = () => {
    if (!result?.dimensions) return null;
    const scores = Object.values(result.dimensions).map(v => parseFloat(v));
    const minScore = Math.min(...scores);
    const potential = (10 - minScore).toFixed(1);
    return {
      potential: `+${potential}`,
      average: '6.8' // 模拟历史平均
    };
  }

  const metrics = getMetrics();

  return (
    <div className="tech-page">
      <div className="tech-bg-grid" />
      <div className="tech-bg-scanline" />
      <div className="tech-bg-noise" />

      {/* 页面 Banner */}
      <div className="page-banner animate-in">
        <div className="page-banner-icon">
          <Edit3 size={28} />
        </div>
        <h1 className="page-banner-title">文本裁判</h1>
        <p className="page-banner-sub">深度剖析师生问答，从科学事实、逻辑严密性等 6 个专业维度进行严苛打分</p>
      </div>
      
      <main style={{ position: 'relative', zIndex: 1, padding: '0 24px 48px', maxWidth: '1200px', margin: '0 auto' }}>
        <section className="card animate-in shimmer-effect">
        <h2 className="section-title">
          <Edit3 size={20} />
          输入评估内容
        </h2>
        <div className="grid">
          <div>
            <label htmlFor="question">科学问题 / 指令</label>
            <textarea
              id="question"
              rows={5}
              placeholder="例如：1.11 和 1.9 哪个大？并解释原因。"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
            />
          </div>
          <div>
            <label htmlFor="aiAnswer">AI 生成的内容</label>
            <textarea
              id="aiAnswer"
              rows={5}
              placeholder="例如：1.11 更大，因为 11 比 9 大。"
              value={aiAnswer}
              onChange={(e) => setAiAnswer(e.target.value)}
            />
          </div>
        </div>

        <div className="grid" style={{ marginTop: '20px' }}>
          <div>
            <label htmlFor="subject">评估科目 (可选)</label>
            <select id="subject" value={subject} onChange={handleSubjectChange}>
              {SUBJECTS.map(s => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="grade">目标学段 (可选)</label>
            <select id="grade" value={grade} onChange={(e) => setGrade(e.target.value)}>
              {GRADES.map(g => (
                <option key={g.value} value={g.value}>{g.label}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="row" style={{ marginTop: '24px', display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
          <button
            id="btnEval"
            className="primary-btn"
            onClick={handleEvaluate}
            disabled={loading}
          >
            {loading ? (
              <>
                <div className="science-loader">
                  <div className="dna-dot" />
                  <div className="dna-dot" />
                  <div className="dna-dot" />
                  <div className="dna-dot" />
                  <div className="dna-dot" />
                </div>
                <span>AI 深度评估中...</span>
              </>
            ) : (
              <>
                <Search size={18} />
                <span>开始文本评估</span>
              </>
            )}
          </button>
        </div>

        <div id="status" className="muted" style={{ marginTop: '12px', textAlign: 'right' }}>
          {status}
        </div>
        {error && (
          <div className="error" style={{ marginTop: '12px', textAlign: 'right', fontWeight: '600', color: 'var(--danger)' }}>
            {error}
          </div>
        )}
      </section>

      {result && (
        <section id="resultArea">
          <div className="grid">
            <section className="card report-card animate-in">
              <h3 className="section-title">
                <Activity size={18} />
                综合评分与点评
              </h3>

              <div className="score-circle-container">
                <svg className="score-circle-svg" viewBox="0 0 100 100">
                  <circle className="score-circle-bg" cx="50" cy="50" r="45" />
                  <circle
                    className="score-circle-progress"
                    cx="50"
                    cy="50"
                    r="45"
                    strokeDasharray="283"
                    strokeDashoffset={283 - (result.score_1_10 / 10) * 283}
                  />
                </svg>
                <div className="score-text-container">
                  <span className="score-value">
                    {result.score_1_10?.toFixed(1) || '0.0'}
                  </span>
                  <span className="score-label">Total Score</span>
                </div>
              </div>

              <div style={{ textAlign: 'center', margin: '20px 0' }}>
                <div className={clsx('badge', qualityInfo?.cls)}>{qualityInfo?.label}</div>
              </div>

              <h4 style={{ fontSize: '14px', marginBottom: '12px', color: 'var(--fg-muted)', fontWeight: '700' }}>
                判定理由 / 综合点评
              </h4>
              <p
                style={{ fontSize: '14px', lineHeight: '1.7', color: 'var(--fg)', marginBottom: '24px' }}
                dangerouslySetInnerHTML={{ __html: highlightErrors(result.comprehensive_review || '', result.fact_errors || []) }}
              />

              <h4 style={{ fontSize: '14px', marginBottom: '12px', color: 'var(--fg-muted)', fontWeight: '700' }}>
                核心建议
              </h4>
              <div id="suggestionArea">
                {result.suggestions?.map((s, i) => (
                  <SuggestionCard key={i} type={s.type} title={s.title} content={s.content} />
                )) || (
                  <SuggestionCard
                    type="info"
                    title="评估完成"
                    content="AI 裁判已完成对内容的深度扫描。"
                  />
                )}
              </div>
            </section>

            <section className="card report-card animate-in" style={{ animationDelay: '0.1s' }}>
              <h3 className="section-title">
                <Hexagon size={18} />
                多维度评估
              </h3>
              <div style={{ position: 'relative', width: '100%', height: '340px' }}>
                {result && getRadarData() && <Radar ref={radarChartRef} data={getRadarData()} options={radarOptions} />}
              </div>
              <div style={{ marginTop: '20px', fontSize: '12px', color: 'var(--fg-subtle)', textAlign: 'center' }}>
                * 鼠标悬停在雷达图点上查看维度定义
              </div>
            </section>
          </div>

          <section className="card report-card animate-in" style={{ marginTop: '24px', animationDelay: '0.2s' }}>
            <div className="row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
              <h3 className="section-title" style={{ margin: 0 }}>
                <Copy size={18} />
                分析与对比
              </h3>
              <button
                className="primary-btn"
                style={{ 
                  padding: '6px 16px', 
                  fontSize: '13px', 
                  background: showCompare ? 'var(--primary)' : 'var(--fg-muted)',
                  boxShadow: 'none',
                  height: 'auto'
                }}
                onClick={() => setShowCompare(!showCompare)}
              >
                {showCompare ? <BarChart3 size={16} /> : <GitCompare size={16} />}
                <span>{showCompare ? '查看趋势图表' : '开启对比分析'}</span>
              </button>
            </div>

            {!showCompare ? (
              <>
                <h4 style={{ fontSize: '14px', marginBottom: '16px', color: 'var(--fg-muted)', fontWeight: '700' }}>
                  维度得分详情
                </h4>
                <div style={{ position: 'relative', width: '100%', height: '280px' }}>
                  {barData && <Bar ref={barChartRef} data={barData} options={barOptions} />}
                </div>
              </>
            ) : (
              <div className="comparison-grid">
                <div>
                  <h4 style={{ fontSize: '13px', color: 'var(--primary)', marginBottom: '10px' }}>本次评估结果</h4>
                  <div id="currentBrief">
                    <div style={{ fontSize: '32px', fontWeight: '800', color: 'var(--primary)' }}>{result.score_1_10?.toFixed(1) || 0}</div>
                    <div style={{ fontSize: '12px', color: 'var(--fg-muted)', marginBottom: '16px' }}>综合质量评分</div>
                    <div className="metric-grid" style={{ gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                      {Object.entries(result.dimensions || {}).map(([k, v]) => (
                        <div key={k} className="metric-item" style={{ padding: '10px' }}>
                          <div style={{ fontSize: '11px', color: 'var(--fg-muted)', marginBottom: '4px' }}>{DIMENSION_LABELS[k]?.label || k}</div>
                          <div style={{ fontSize: '18px', fontWeight: '700', color: parseFloat(v) >= 8 ? 'var(--success)' : parseFloat(v) >= 6 ? 'var(--warning)' : 'var(--danger)' }}>{parseFloat(v).toFixed(1)}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
                <div>
                  <h4 style={{ fontSize: '13px', color: 'var(--fg-subtle)', marginBottom: '10px' }}>历史平均参考</h4>
                  <div id="historyBrief">
                    <div style={{ fontSize: '32px', fontWeight: '800', color: 'var(--fg-subtle)' }}>6.8</div>
                    <div style={{ fontSize: '12px', color: 'var(--fg-muted)', marginBottom: '16px' }}>同类科目历史平均</div>
                    <div className="metric-grid" style={{ gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                      {Object.keys(DIMENSION_LABELS).map((k) => (
                        <div key={k} className="metric-item" style={{ padding: '10px' }}>
                          <div style={{ fontSize: '11px', color: 'var(--fg-muted)', marginBottom: '4px' }}>{DIMENSION_LABELS[k].label}</div>
                          <div style={{ fontSize: '18px', fontWeight: '700', color: 'var(--fg-subtle)' }}>6.5</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

            <details style={{ marginTop: '20px', borderTop: '1px solid var(--border)', paddingTop: '16px' }}>
              <summary className="muted" style={{ 
                cursor: 'pointer', 
                fontSize: '13px', 
                display: 'flex', 
                alignItems: 'center', 
                gap: '8px',
                userSelect: 'none'
              }}>
                <Code size={14} />
                <span>查看原始模型响应 (JSON数据)</span>
              </summary>
              <pre
                style={{
                  background: 'rgba(0,0,0,0.02)',
                  padding: '12px',
                  borderRadius: '8px',
                  fontSize: '12px',
                  overflow: 'auto',
                  maxHeight: '200px',
                  marginTop: '10px',
                  border: '1px solid var(--border)'
                }}
              >
                {JSON.stringify(result, null, 2)}
              </pre>
            </details>
          </section>
        </section>
      )}
    </main>
    </div>
  )
}