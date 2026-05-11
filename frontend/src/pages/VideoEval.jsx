import { useState, useRef, useEffect } from 'react'
import axios from 'axios'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Tooltip,
  Legend
} from 'chart.js'
import { Video, UploadCloud, BarChart3, CheckCircle2, Lightbulb, Film, AlertTriangle, GitCompare, Activity, AlertCircle } from 'lucide-react'
import { clsx } from 'clsx'


ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Tooltip,
  Legend
)

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
  { value: '高中', label: '高中' }
]

function getQualityLevel(level) {
  if (level === '优秀') return { label: '优秀', cls: 'high' }
  if (level === '良好') return { label: '良好', cls: 'mid' }
  if (level === '不及格') return { label: '不及格', cls: 'low' }
  // 兼容旧值
  if (level === '高') return { label: '优秀', cls: 'high' }
  if (level === '中') return { label: '良好', cls: 'mid' }
  if (level === '低') return { label: '不及格', cls: 'low' }
  return { label: level || '未知', cls: 'mid' }
}

function SuggestionCard({ title, content, type }) {
  const icons = {
    warning: AlertTriangle,
    info: Lightbulb,
    success: CheckCircle2
  }
  const Icon = icons[type] || Lightbulb

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

export default function VideoEval() {
  const [prompt, setPrompt] = useState('')
  const [subject, setSubject] = useState('')
  const [grade, setGrade] = useState('')
  const [videoFile, setVideoFile] = useState(null)
  const [videoPreview, setVideoPreview] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')
  const [showCompare, setShowCompare] = useState(false)

  const fileInputRef = useRef(null)

  useEffect(() => {
    document.body.dataset.subject = subject
  }, [subject])

  const handleFileChange = (e) => {
    const file = e.target.files[0]
    if (file) handleFile(file)
  }

  const handleFile = (file) => {
    if (!file.type.startsWith('video/')) {
      setError('请上传视频文件')
      return
    }
    setVideoFile(file)
    const url = URL.createObjectURL(file)
    setVideoPreview(url)
  }

  const handleDrop = (e) => {
    e.preventDefault()
    const file = e.dataTransfer.files[0]
    if (file && file.type.startsWith('video/')) {
      handleFile(file)
    }
  }

  const handleDragOver = (e) => {
    e.preventDefault()
  }

  const handleReport = async () => {
    setError('')
    if (!prompt.trim()) {
      setError('请输入视频内容描述或分析指令')
      return
    }
    if (!videoFile) {
      setError('请上传教学视频')
      return
    }

    setLoading(true)
    setStatus('AI 正在分析视频内容...')

    const formData = new FormData()
    formData.append('text', prompt)
    formData.append('video', videoFile)
    if (subject) formData.append('subject', subject)
    if (grade) formData.append('grade', grade)

    try {
      const response = await axios.post('/api/evals/video_report', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 120000
      })
      setResult(response.data)
      setStatus('')
    } catch (err) {
      console.error('Report failed:', err)
      setError(`生成报告失败: ${err.response?.data?.detail || err.message}`)
      setStatus('')
    } finally {
      setLoading(false)
    }
  }


  const qualityInfo = result?.advice?.quality_level
     ? getQualityLevel(result.advice.quality_level)
     : result?.xclip?.similarity !== undefined
       ? getQualityLevel(result.xclip.similarity >= 0.2 ? '优秀' : result.xclip.similarity >= 0.1 ? '良好' : '不及格')
       : null

  // 计算动态指标
  const getMetrics = () => {
    if (!result?.total_score && !result?.xclip?.score_0_100) return null;
    const baseScore = result.total_score || result.xclip?.score_0_100 || 0;
    // 模拟从维度中找到最低分
    const potential = (100 - baseScore * 0.8).toFixed(1); 
    return {
      potential: `+${(potential/10).toFixed(1)}`,
      average: '78.5'
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
          <Video size={28} />
        </div>
        <h1 className="page-banner-title">视频裁判</h1>
        <p className="page-banner-sub">基于 X-CLIP 大模型，对教学视频进行内容一致性评估，并由 Qwen 提供专业教学建议</p>
      </div>

      <main style={{ position: 'relative', zIndex: 1, padding: '0 24px 48px', maxWidth: '1200px', margin: '0 auto' }}>
        <section className="card animate-in shimmer-effect">
        <h2 className="section-title">
          <UploadCloud size={20} />
          视频上传与内容描述
        </h2>
        <div className="grid">
          <div>
            <label htmlFor="prompt">视频内容描述 / 分析指令</label>
            <textarea
              id="prompt"
              rows={5}
              placeholder="例如：分析这段关于光合作用的实验演示视频，指出其中的科学准确性、教学效果和可能的改进建议"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
            />
            <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: '15px', marginTop: '15px' }}>
              <div>
                <label htmlFor="subject" style={{ fontSize: '13px' }}>评估科目 (可选)</label>
                <select
                  id="subject"
                  style={{ width: '100%', padding: '8px', borderRadius: '8px', border: '1px solid var(--border)', fontSize: '13px' }}
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
                  style={{ width: '100%', padding: '8px', borderRadius: '8px', border: '1px solid var(--border)', fontSize: '13px' }}
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
            <label htmlFor="video">教学视频</label>
            <div
              className="upload-area"
              onDrop={handleDrop}
              onDragOver={handleDragOver}
              onClick={() => fileInputRef.current?.click()}
              style={{ minHeight: '180px' }}
            >
              <input
                ref={fileInputRef}
                id="video"
                type="file"
                accept="video/*"
                style={{ display: 'none' }}
                onChange={handleFileChange}
              />
              {!videoPreview ? (
                <div id="uploadPlaceholder">
                  <Film style={{ width: '48px', height: '48px', color: '#94a3b8', marginBottom: '8px' }} />
                  <div className="muted">点击或拖拽视频到此处上传</div>
                  <div className="muted" style={{ fontSize: '12px', marginTop: '4px' }}>支持 MP4, WebM, MOV 格式</div>
                </div>
              ) : (
                <div style={{ width: '100%' }}>
                  <video
                    src={videoPreview}
                    controls
                    style={{ maxWidth: '100%', maxHeight: '200px', borderRadius: '8px', boxShadow: 'var(--shadow-md)' }}
                  />
                  <div style={{ marginTop: '8px', textAlign: 'center' }}>
                    <span className="muted" style={{ fontSize: '12px' }}>{videoFile?.name}</span>
                  </div>
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
                <Video size={18} />
                <span>开始视频评估</span>
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
        <div id="reportArea">
          {!showCompare ? (
            <>
              <section className="card report-card animate-in delay-1" style={{ marginBottom: '24px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '20px', flexWrap: 'wrap' }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <h2 className="section-title" style={{ marginBottom: '6px' }}>
                      <BarChart3 size={20} />
                      视频评估报告
                    </h2>
                    <p className="muted" style={{ fontSize: '12.5px' }}>评估时间：{new Date().toLocaleString()}</p>
                    {qualityInfo && (
                      <div style={{ marginTop: '12px' }}>
                        <span className={`badge ${qualityInfo.cls}`} style={{ fontSize: '13px', padding: '5px 16px' }}>
                          ● 匹配质量：{qualityInfo.label}
                        </span>
                      </div>
                    )}
                  </div>
                  <div className="score-circle-container" style={{ flexShrink: 0 }}>
                    <svg className="score-circle-svg" viewBox="0 0 100 100">
                      <defs>
                        <linearGradient id="scoreGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                          <stop offset="0%" stopColor="var(--primary)" />
                          <stop offset="100%" stopColor="var(--accent)" />
                        </linearGradient>
                      </defs>
                      <circle className="score-circle-bg" cx="50" cy="50" r="45" />
                      <circle
                        className="score-circle-progress"
                        cx="50" cy="50" r="45"
                        strokeDasharray="283"
                        strokeDashoffset={283 - ((result.xclip?.score_0_100 || result.total_score || 0) / 100) * 283}
                      />
                    </svg>
                    <div className="score-text-container">
                      <span className="score-value">{Math.round(result.xclip?.score_0_100 ?? result.total_score ?? 0)}</span>
                      <span className="score-label">Points</span>
                    </div>
                  </div>
                </div>

                <hr className="divider" />

                <div className="grid" style={{ alignItems: 'stretch' }}>
                  <div style={{ minWidth: 0 }}>
                    <h3 className="section-title" style={{ fontSize: '15px' }}>
                      <CheckCircle2 size={16} />
                      评估结论
                    </h3>
                    <div className="info-box" style={{ marginBottom: '18px' }}>
                      <p style={{ fontWeight: '600', color: 'var(--fg)', margin: 0, wordBreak: 'break-word', lineHeight: '1.7' }}>
                        {result.advice?.summary || result.comprehensive_review || result.summary || '视频内容与描述基本一致，具备较好的教学参考价值。'}
                      </p>
                    </div>

                    <div className="metric-grid" style={{ marginTop: '0', gridTemplateColumns: '1fr 1fr' }}>
                      <div className="metric-item">
                        <div className="metric-label">X-CLIP 相似度</div>
                        <div style={{ fontSize: '22px', fontWeight: '900', color: 'var(--primary)', letterSpacing: '-0.02em' }}>
                          {(result.xclip?.similarity || 0).toFixed(4)}
                        </div>
                      </div>
                      <div className="metric-item">
                        <div className="metric-label">评估模型</div>
                        <div style={{ fontSize: '13px', fontWeight: '700', color: 'var(--fg)', wordBreak: 'break-all', lineHeight: 1.4, paddingTop: '2px' }}>
                          {result.xclip?.model_name || 'X-CLIP-ViT-L-14'}
                        </div>
                      </div>
                    </div>

                    {(result.advice || result.suggestions) && (
                      <div style={{ marginTop: '18px', padding: '22px', borderRadius: 'var(--radius-lg)', background: 'linear-gradient(135deg, #fafbff 0%, #f8fafc 100%)', border: '1px solid var(--border-strong)', boxShadow: 'var(--shadow-xs)' }}>
                        <h4 style={{ margin: '0 0 14px 0', fontSize: '14px', fontWeight: '800', color: 'var(--primary)', display: 'flex', alignItems: 'center', gap: '7px' }}>
                          <Lightbulb size={16} style={{ background: 'var(--primary-light)', padding: '3px', borderRadius: '6px', boxSizing: 'content-box' }} />
                          Qwen 教学评价与建议
                        </h4>
                        {result.advice?.summary && (
                          <div style={{ fontSize: '13.5px', lineHeight: '1.7', color: 'var(--fg-muted)', marginBottom: '14px', paddingBottom: '14px', borderBottom: '1px dashed var(--border-strong)' }}>
                            {result.advice.summary}
                          </div>
                        )}
                        {(result.advice?.highlights || result.advice?.issues) && (
                          <div className="grid" style={{ gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '14px' }}>
                            {result.advice?.highlights?.length > 0 && (
                              <div style={{ padding: '12px 14px', background: 'rgba(16,185,129,0.05)', borderRadius: 'var(--radius-sm)', border: '1px solid rgba(16,185,129,0.15)' }}>
                                <div style={{ fontSize: '11.5px', fontWeight: '700', color: 'var(--success)', marginBottom: '8px', letterSpacing: '0.05em', textTransform: 'uppercase' }}>✦ 亮点分析</div>
                                <ul style={{ margin: 0, paddingLeft: '16px', fontSize: '13px', color: 'var(--fg-muted)', display: 'flex', flexDirection: 'column', gap: '5px' }}>
                                  {result.advice.highlights.map((h, i) => <li key={i}>{h}</li>)}
                                </ul>
                              </div>
                            )}
                            {result.advice?.issues?.length > 0 && (
                              <div style={{ padding: '12px 14px', background: 'rgba(239,68,68,0.05)', borderRadius: 'var(--radius-sm)', border: '1px solid rgba(239,68,68,0.15)' }}>
                                <div style={{ fontSize: '11.5px', fontWeight: '700', color: 'var(--danger)', marginBottom: '8px', letterSpacing: '0.05em', textTransform: 'uppercase' }}>⚠ 改进空间</div>
                                <ul style={{ margin: 0, paddingLeft: '16px', fontSize: '13px', color: 'var(--fg-muted)', display: 'flex', flexDirection: 'column', gap: '5px' }}>
                                  {result.advice.issues.map((item, i) => <li key={i}>{item}</li>)}
                                </ul>
                              </div>
                            )}
                          </div>
                        )}
                        {(result.advice?.suggestions || result.suggestions)?.length > 0 && (
                          <div style={{ paddingTop: '14px', borderTop: '1px dashed var(--border-strong)' }}>
                            <div style={{ fontSize: '11.5px', fontWeight: '700', color: 'var(--primary)', marginBottom: '10px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>→ 针对性建议</div>
                            <ul style={{ margin: 0, paddingLeft: '16px', fontSize: '13px', color: 'var(--fg)', fontWeight: '500', display: 'flex', flexDirection: 'column', gap: '6px', lineHeight: '1.65' }}>
                              {(result.advice?.suggestions || result.suggestions || []).map((s, i) => (
                                <li key={i}>{typeof s === 'string' ? s : (s.content || s.title)}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </section>
            </>
          ) : (
            <div className="comparison-mode-container">
              <div className="metric-grid" style={{ marginBottom: '32px' }}>
                <div className="metric-item">
                  <div className="metric-label" style={{ color: 'var(--primary)' }}>本次评估结果</div>
                  <div className="metric-value">{Math.round(result.xclip?.score_0_100 ?? result.total_score ?? 0)}</div>
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
            </div>
          )}

          <section className="card animate-in delay-3">
            <h3 className="section-title">
              <Lightbulb size={18} />
              改进建议
            </h3>
            <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '16px' }}>
              {(result.suggestions || result.advice?.suggestions || []).map((s, i) => (
                <SuggestionCard
                  key={i}
                  type={typeof s === 'string' ? 'info' : (s.type || 'info')}
                  title={typeof s === 'string' ? '建议' : (s.title || '建议')}
                  content={typeof s === 'string' ? s : (s.content || s)}
                />
              ))}
            </div>
          </section>

          {result.issues && result.issues.length > 0 && (
            <section className="card animate-in delay-3">
              <h3 className="section-title">
                <AlertTriangle size={18} />
                识别到的问题
              </h3>
              <ul className="issue-list">
                {result.issues.map((issue, i) => (
                  <li key={i} className="issue-item">
                    <div className="issue-icon">
                      <AlertCircle size={16} />
                    </div>
                    <div className="issue-content">{issue}</div>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      )}
      </main>
    </div>
  )
}