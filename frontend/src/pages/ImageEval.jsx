import { useState, useRef } from 'react'
import axios from 'axios'
import { Radar } from 'react-chartjs-2'
import {
  Chart as ChartJS,
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
  CategoryScale,
  LinearScale
} from 'chart.js'
import { UploadCloud, Zap, BarChart3, CheckCircle2, Microscope, GitCompare, Lightbulb, Image as ImageIcon, AlertTriangle, CheckCircle, Info, AlertCircle, Activity } from 'lucide-react'
import { clsx } from 'clsx'


ChartJS.register(
  RadialLinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
  CategoryScale,
  LinearScale
)

const SUBJECTS = [
  { value: '', label: '-- 请选择科目 --' },
  { value: 'science', label: '科学' },
  { value: 'physics', label: '物理' },
  { value: 'chemistry', label: '化学' },
  { value: 'biology', label: '生物' },
  { value: 'earth', label: '地理' },
  { value: 'it', label: '信息技术' },
]

const GRADES = [
  { value: '', label: '-- 请选择学段 --' },
  { value: '小学低年级', label: '小学低年级 (1-3年级)' },
  { value: '小学高年级', label: '小学高年级 (4-6年级)' },
  { value: '初中', label: '初中' },
  { value: '高中', label: '高中' },
]

export default function ImageEval() {
  const [prompt, setPrompt] = useState('')
  const [subject, setSubject] = useState('')
  const [grade, setGrade] = useState('')
  const [imageFile, setImageFile] = useState(null)
  const [imagePreview, setImagePreview] = useState(null)
  const [imageMeta, setImageMeta] = useState('')
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [result, setResult] = useState(null)
  const [showCompare, setShowCompare] = useState(false)
  const fileInputRef = useRef(null)


  const handleFileChange = (e) => {
    const file = e.target.files[0]
    if (file) handleFileSelection(file)
  }

  const handleFileSelection = (file) => {
    setImageFile(file)
    const reader = new FileReader()
    reader.onload = (e) => {
      setImagePreview(e.target.result)
      const img = new Image()
      img.onload = () => {
        const sizeKB = (file.size / 1024).toFixed(1)
        setImageMeta(`${file.type.split('/')[1].toUpperCase()} • ${img.width}x${img.height} • ${sizeKB}KB`)
      }
      img.src = e.target.result
    }
    reader.readAsDataURL(file)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    e.stopPropagation()
    const file = e.dataTransfer.files[0]
    if (file && file.type.startsWith('image/')) {
      handleFileSelection(file)
    }
  }

  const handleDragOver = (e) => {
    e.preventDefault()
    e.stopPropagation()
  }

  const handleReport = async () => {
    if (!prompt || !imageFile) {
      setError('请填写生成指令并上传图片')
      return
    }

    setLoading(true)
    setError('')
    setStatus('AI 正在执行多维度评估...')

    const formData = new FormData()
    formData.append('prompt', prompt)
    formData.append('image', imageFile)
    if (subject) formData.append('subject', subject)
    if (grade) formData.append('grade', grade)

    try {
      const response = await axios.post('/api/evals/report', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      setResult(response.data)
      setStatus('')
      
      // 平滑滚动到报告区域
      setTimeout(() => {
        document.getElementById('reportArea')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }, 100)
    } catch (err) {
      console.error('Report failed:', err)
      setError(`报告生成失败: ${err.response?.data?.detail || err.message}`)
      setStatus('')
    } finally {
      setLoading(false)
    }
  }

  const getRadarData = (data, label, isHistory = false) => {
    const dims = data.dimensions || {}
    const consistencyScore = parseFloat(dims.consistency?.score_0_100 || 0) / 10
    const factScore = parseFloat(dims.scientific_accuracy?.fact_score || 0)
    const logicScore = parseFloat(dims.scientific_accuracy?.logic_score || 0)
    const pedagogyScore = dims.pedagogical_advice?.quality_level === '高' ? 9 : (dims.pedagogical_advice?.quality_level === '中' ? 6 : 3)

    const primaryColor = getComputedStyle(document.body).getPropertyValue('--primary').trim() || '#6366f1'
    const borderColor = isHistory ? '#94a3b8' : primaryColor
    const backgroundColor = isHistory ? 'rgba(148, 163, 184, 0.2)' : `${primaryColor}33`

    return {
      labels: ['图文一致性', '科学事实', '逻辑严密性', '术语专业度', '教学适用性'],
      datasets: [{
        label,
        data: [consistencyScore, factScore, logicScore, (factScore + logicScore) / 2, pedagogyScore],
        backgroundColor,
        borderColor,
        borderWidth: 2,
        pointBackgroundColor: borderColor,
        pointBorderColor: '#fff',
        pointHoverBackgroundColor: '#fff',
        pointHoverBorderColor: borderColor,
        fill: true
      }]
    }
  }

  const radarOptions = {
    responsive: true,
    maintainAspectRatio: false,
    scales: {
      r: {
        beginAtZero: true,
        max: 10,
        ticks: { display: false, stepSize: 2 },
        grid: { color: 'rgba(0, 0, 0, 0.05)' },
        angleLines: { color: 'rgba(0, 0, 0, 0.1)' },
        pointLabels: { font: { size: 12, weight: '700' }, color: '#475569' }
      }
    },
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: 'rgba(15, 23, 42, 0.9)',
        padding: 12,
        titleFont: { size: 14, weight: 'bold' },
        bodyFont: { size: 13 }
      }
    }
  }

  const dims = result?.dimensions || {}
  const advice = dims.pedagogical_advice || {}
  const summary = result?.summary || {}
  const [reportTime] = useState(() => new Date().toLocaleString())
  const currentReportTime = result ? new Date().toLocaleString() : reportTime

  // 计算动态指标
  const getMetrics = () => {
    if (!result?.dimensions) return null;
    const consistency = parseFloat(dims.consistency?.score_0_100 || 0) / 10;
    const fact = parseFloat(dims.scientific_accuracy?.fact_score || 0);
    const logic = parseFloat(dims.scientific_accuracy?.logic_score || 0);
    const pedagogy = dims.pedagogical_advice?.quality_level === '高' ? 9 : (dims.pedagogical_advice?.quality_level === '中' ? 6 : 3);
    
    const scores = [consistency, fact, logic, pedagogy];
    const minScore = Math.min(...scores);
    const potential = (10 - minScore).toFixed(1);
    
    return {
      potential: `+${potential}`,
      average: '7.2' // 模拟历史平均
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
          <ImageIcon size={28} />
        </div>
        <h1 className="page-banner-title">图像裁判</h1>
        <p className="page-banner-sub">通过 CLIP 视觉语义对齐 + Qwen 多维度裁判，评估 AIGC 图像的科学性与教学适用性</p>
      </div>

      <main style={{ position: 'relative', zIndex: 1, padding: '0 24px 48px', maxWidth: '1200px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <section className="card animate-in shimmer-effect">
        <h2 className="section-title">
          <UploadCloud size={20} />
          内容上传与指令输入
        </h2>
        <div className="grid">
          <div>
            <label htmlFor="prompt">生成指令 (Prompt) / 内容描述</label>
            <textarea
              id="prompt"
              rows={4}
              placeholder="例如：一张展示 NaCl 离子晶体结构的示意图，包含正负离子交替排列的细节"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
            />
            <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: '15px', marginTop: '15px' }}>
              <div>
                <label htmlFor="subject" style={{ fontSize: '13px' }}>评估科目 (可选)</label>
                <select
                  id="subject"
                  value={subject}
                  onChange={(e) => setSubject(e.target.value)}
                >
                  {SUBJECTS.map(s => (
                    <option key={s.value} value={s.value}>{s.label}</option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor="grade" style={{ fontSize: '13px' }}>目标学段 (可选)</label>
                <select
                  id="grade"
                  value={grade}
                  onChange={(e) => setGrade(e.target.value)}
                >
                  {GRADES.map(g => (
                    <option key={g.value} value={g.value}>{g.label}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>
          <div>
            <label htmlFor="image">生成图像</label>
            <div
              className={clsx('upload-area', { 'drag-over': false })}
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onClick={() => fileInputRef.current?.click()}
            >
              <input
                ref={fileInputRef}
                id="image"
                type="file"
                accept="image/*"
                style={{ display: 'none' }}
                onChange={handleFileChange}
              />
              {!imagePreview ? (
                <div id="uploadPlaceholder">
                  <ImageIcon style={{ width: '48px', height: '48px', color: '#94a3b8', marginBottom: '8px' }} />
                  <div className="muted">点击或拖拽图片到此处上传</div>
                </div>
              ) : (
                <div id="previewContainer">
                  <img
                    src={imagePreview}
                    alt="Preview"
                    style={{ maxWidth: '100%', maxHeight: '200px', borderRadius: '8px', boxShadow: 'var(--shadow-md)' }}
                  />
                  {imageMeta && <div className="preview-info">{imageMeta}</div>}
                </div>
              )}
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', marginTop: '24px' }}>
          {result && (
            <button
              className="primary-btn"
              style={{ 
                background: showCompare ? 'var(--primary)' : 'var(--fg-muted)', 
                boxShadow: 'none' 
              }}
              onClick={() => setShowCompare(!showCompare)}
            >
              {showCompare ? <Activity size={18} /> : <GitCompare size={18} />}
              <span>{showCompare ? '返回报告模式' : '开启对比分析'}</span>
            </button>
          )}
          <button id="btnReport" className="primary-btn" onClick={handleReport} disabled={loading}>
            {loading ? (
              <>
                <div className="science-loader">
                  <div className="dna-dot" /><div className="dna-dot" />
                  <div className="dna-dot" /><div className="dna-dot" />
                  <div className="dna-dot" />
                </div>
                <span>AI 深度评估中...</span>
              </>
            ) : (
              <>
                <ImageIcon size={18} />
                <span>开始图像评估</span>
              </>
            )}
          </button>
        </div>
        {status && <div id="status" className="muted" style={{ marginTop: '12px', textAlign: 'right' }}>{status}</div>}
        {error && <div className="error" style={{ marginTop: '12px', textAlign: 'right', fontWeight: '600', color: 'var(--danger)' }}>{error}</div>}
      </section>

      {result && (
        <div id="reportArea">
          {!showCompare ? (
            <>
              <section className="card report-card animate-in delay-1" style={{ marginBottom: '24px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <h2 className="section-title" style={{ marginBottom: '4px' }}>
                      <BarChart3 size={20} />
                      综合评估报告
                    </h2>
                    <p className="muted" style={{ fontSize: '13px' }}>评估时间: {currentReportTime}</p>
                  </div>
                  <div className="score-circle-container">
                    <svg className="score-circle-svg" viewBox="0 0 100 100">
                      <circle className="score-circle-bg" cx="50" cy="50" r="45" />
                      <circle
                        className="score-circle-progress"
                        cx="50" cy="50" r="45"
                        strokeDasharray="283"
                        strokeDashoffset={283 - ((summary.total_score || 0) / 10) * 283}
                      />
                    </svg>
                    <div className="score-text-container">
                      <span className="score-value">{summary.total_score || 0}</span>
                      <span className="score-label">Points</span>
                    </div>
                  </div>
                </div>

                <hr style={{ border: 0, borderTop: '1px solid var(--border)', margin: '24px 0' }} />

                <div className="grid" style={{ alignItems: 'stretch' }}>
                  <div style={{ minWidth: 0 }}>
                    <h3 className="section-title" style={{ fontSize: '16px' }}>
                      <CheckCircle2 size={16} />
                      核心结论
                    </h3>
                    <div style={{ padding: '18px', borderRadius: 'var(--radius-md)', background: '#f8fafc', border: '1px solid var(--border)', marginBottom: '20px' }}>
                      <p style={{ fontWeight: '600', color: '#1e293b', margin: 0, wordBreak: 'break-word' }}>
                        {advice.summary}
                      </p>
                      <div style={{ marginTop: '12px', display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                        <span className={clsx('badge', advice.quality_level === '高' ? 'high' : advice.quality_level === '低' ? 'low' : 'mid')}>
                          {advice.quality_level}
                        </span>
                        {summary.error_type && (
                          <span className={clsx('badge', summary.error_type === '无' ? 'high' : 'low')}>
                            {summary.error_type}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="metric-grid" style={{ marginTop: '15px' }}>
                      <div className="metric-item">
                        <div className="muted" style={{ fontSize: '12px', marginBottom: '4px' }}>CLIP 相似度</div>
                        <div style={{ fontSize: '20px', fontWeight: '800', color: 'var(--primary)' }}>
                          {dims.consistency?.similarity?.toFixed(4) || '-'}
                        </div>
                      </div>
                      <div className="metric-item">
                        <div className="muted" style={{ fontSize: '12px', marginBottom: '4px' }}>匹配等级</div>
                        <div style={{
                          fontSize: '16px', fontWeight: '700',
                          color: dims.consistency?.score_0_100 >= 75 ? 'var(--success)' : dims.consistency?.score_0_100 >= 45 ? 'var(--warning)' : 'var(--danger)'
                        }}>
                          {dims.consistency?.score_0_100 >= 75 ? '高度匹配' : dims.consistency?.score_0_100 >= 45 ? '部分匹配' : '匹配度低'}
                        </div>
                      </div>
                    </div>

                    <h4 style={{ fontSize: '14px', marginBottom: '10px', color: 'var(--fg-muted)', marginTop: '20px' }}>主要亮点</h4>
                    <ul className="list" style={{ fontSize: '14px' }}>
                      {(advice.highlights || []).map((h, i) => <li key={i}>{h}</li>)}
                    </ul>
                  </div>
                </div>
              </section>

              <div className="grid">
                <section className="card animate-in delay-2">
                  <h3 className="section-title">
                    <Microscope size={18} />
                    科学事实分析
                  </h3>
                  <div style={{ fontSize: '14px', lineHeight: '1.7', color: '#334155', whiteSpace: 'pre-wrap' }}>
                    {dims.scientific_accuracy?.detailed_analysis}
                  </div>
                </section>
                <section className="card animate-in delay-2">
                  <h3 className="section-title">
                    <GitCompare size={18} />
                    图文一致性详情
                  </h3>
                    <div className="metric-grid">
                      <div className="metric-item">
                        <div className="muted" style={{ fontSize: '12px', marginBottom: '4px' }}>CLIP 相似度</div>
                        <div style={{ fontSize: '20px', fontWeight: '800', color: 'var(--primary)' }}>
                          {dims.consistency?.similarity?.toFixed(4) || '-'}
                        </div>
                      </div>
                      <div className="metric-item">
                        <div className="muted" style={{ fontSize: '12px', marginBottom: '4px' }}>匹配等级</div>
                        <div style={{ fontSize: '18px', fontWeight: '800' }}>
                          {dims.consistency?.score_0_100 >= 75 ? '高度匹配' : dims.consistency?.score_0_100 >= 45 ? '部分匹配' : '匹配度低'}
                        </div>
                      </div>
                    </div>

                  <div style={{ marginTop: '20px' }}>
                    <h4 style={{ fontSize: '14px', marginBottom: '10px', color: 'var(--fg-muted)' }}>识别到的缺陷</h4>
                    <ul className="list" style={{ fontSize: '13px', color: 'var(--danger)' }}>
                      {(advice.issues || []).map((issue, i) => <li key={i}>{issue}</li>)}
                    </ul>
                  </div>
                </section>
              </div>

              <section className="card animate-in delay-3" style={{ marginTop: '24px' }}>
                <h3 className="section-title">
                  <Lightbulb size={18} />
                  可执行改进建议 (面向教师)
                </h3>
                <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
                  {(advice.suggestions || []).map((s, i) => (
                    <div key={i} className={clsx('suggestion-card', typeof s === 'string' ? 'info' : (s.type || 'info'))}>
                      <div className="suggestion-icon">
                        {(typeof s === 'string' ? 'info' : s.type) === 'warning' ? <AlertTriangle size={18} /> : (typeof s === 'string' ? 'info' : s.type) === 'success' ? <CheckCircle size={18} /> : <Info size={18} />}
                      </div>
                      <div className="suggestion-content">
                        <h4>{typeof s === 'string' ? '改进建议' : (s.title || '改进建议')}</h4>
                        <p>{typeof s === 'string' ? s : s.content}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            </>
          ) : (
            <div className="comparison-mode-container">
              <div className="row" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
                <h3 className="section-title" style={{ margin: 0 }}>
                  <GitCompare size={18} />
                  历史对比与趋势分析
                </h3>
              </div>
              
              <div className="metric-grid">
                <div className="metric-item">
                  <div className="metric-label" style={{ color: 'var(--primary)' }}>本次评估结果</div>
                  <div className="metric-value">{summary.total_score || 0}</div>
                  <div style={{ fontSize: '12px', color: 'var(--fg-subtle)', marginTop: '4px' }}>综合质量评分</div>
                </div>
                <div className="metric-item">
                  <div className="metric-label">历史平均参考</div>
                  <div className="metric-value" style={{ color: 'var(--fg-subtle)' }}>{metrics?.average}</div>
                  <div style={{ fontSize: '12px', color: 'var(--fg-subtle)', marginTop: '4px' }}>同类科目历史平均</div>
                </div>
                <div className="metric-item">
                  <div className="metric-label">改进潜力</div>
                  <div className="metric-value" style={{ color: 'var(--success)' }}>{metrics?.potential}</div>
                  <div style={{ fontSize: '12px', color: 'var(--fg-subtle)', marginTop: '4px' }}>相比最低评分维度</div>
                </div>
              </div>

              <div className="comparison-grid">
                <section className="card animate-in">
                  <h3 className="section-title" style={{ fontSize: '16px' }}>
                    <GitCompare size={16} /> 历史平均表现
                  </h3>
                  <div style={{ height: '300px' }}>
                    <Radar 
                      data={getRadarData({ dimensions: { consistency: { score_0_100: 75 }, scientific_accuracy: { fact_score: 8, logic_score: 7.8 }, pedagogical_advice: { quality_level: '中' } } }, '历史平均', true)} 
                      options={radarOptions} 
                    />
                  </div>
                </section>
                <section className="card animate-in delay-1">
                  <h3 className="section-title" style={{ fontSize: '16px' }}>
                    <GitCompare size={16} /> 本次评估详情
                  </h3>
                  <div style={{ height: '300px' }}>
                    <Radar 
                      data={getRadarData(result, '本次评估', false)} 
                      options={radarOptions} 
                    />
                  </div>
                </section>
              </div>
            </div>
          )}
        </div>
      )}
    </main>
  </div>
)
}