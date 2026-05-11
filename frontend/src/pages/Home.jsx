import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { LayoutDashboard, FileText, Video, ArrowRight, Brain, Sparkles, Zap, ShieldCheck, Code, Globe, Mail } from 'lucide-react'
import { useParticles, useAnimateNumber, useHeaderParallax } from '../hooks/useScienceEffects'

const navCards = [
  {
    to: '/image',
    icon: LayoutDashboard,
    title: '图像裁判',
    desc: '评估图文生成的一致性，通过 CLIP 与 Qwen 提供多维度的科学性与教学建议报告。',
    footer: '进入模块',
  },
  {
    to: '/text',
    icon: FileText,
    title: '文本裁判',
    desc: '深度剖析师生问答，从科学事实、逻辑严密性等 6 个专业维度进行严苛打分。',
    footer: '进入模块',
  },
  {
    to: '/video',
    icon: Video,
    title: '视频裁判',
    desc: '基于 X-CLIP 视频大模型，针对教学视频、实验动画进行内容一致性评估。',
    footer: '进入模块',
  },
]

export default function Home() {
  const cardsRef = useRef([])
  const canvasRef = useRef(null)
  const headerRef = useRef(null)
  
  useParticles(canvasRef)
  useHeaderParallax(headerRef)

  // 动画数字
  const dimensionCount = useAnimateNumber(6, 1500)
  const modelCount = useAnimateNumber(2, 2000)

  useEffect(() => {
    // 3D 视差交互
    const handleMouseMove = (e, card) => {
      const rect = card.getBoundingClientRect()
      const x = e.clientX - rect.left
      const y = e.clientY - rect.top
      const rx = ((y / rect.height) - 0.5) * -10
      const ry = ((x / rect.width) - 0.5) * 10
      card.style.transform = `translateY(-16px) scale(1.02) rotateX(${rx.toFixed(2)}deg) rotateY(${ry.toFixed(2)}deg)`
    }

    const handleMouseLeave = (card) => {
      card.style.transform = ''
    }

    const currentCards = cardsRef.current
    currentCards.forEach(card => {
      if (!card) return
      const moveHandler = (e) => handleMouseMove(e, card)
      const leaveHandler = () => handleMouseLeave(card)
      card.addEventListener('mousemove', moveHandler)
      card.addEventListener('mouseleave', leaveHandler)
      card._handlers = { moveHandler, leaveHandler }
    })

    // 键盘导航
    const handleKeyDown = (e) => {
      if (e.key === '1') window.location.href = '/image'
      if (e.key === '2') window.location.href = '/text'
      if (e.key === '3') window.location.href = '/video'
    }
    window.addEventListener('keydown', handleKeyDown)

    return () => {
      currentCards.forEach(card => {
        if (!card || !card._handlers) return
        card.removeEventListener('mousemove', card._handlers.moveHandler)
        card.removeEventListener('mouseleave', card._handlers.leaveHandler)
      })
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [])

  return (
    <div className="hero-section">
      {/* 科技感背景层 */}
      <div className="tech-grid" />
      <div className="scanline-layer" />
      <div className="noise-layer" />
      <canvas ref={canvasRef} className="particle-layer" aria-hidden="true" />
      
      {/* 装饰背景动画 */}
      <div className="bg-blob" style={{ top: '-10%', right: '-10%' }} />
      <div className="bg-blob" style={{ bottom: '-10%', left: '-10%', animationDelay: '-5s' }} />
      <div className="orbital-ring" style={{ top: '12%', left: '8%', animationDuration: '24s' }} />
      <div className="orbital-ring" style={{ bottom: '8%', right: '6%', animationDuration: '34s', animationDirection: 'reverse' }} />
      
      <div className="animate-in" ref={headerRef} style={{ 
        transform: 'translate(var(--header-parallax-x, 0), var(--header-parallax-y, 0))',
        transition: 'transform 0.1s ease-out'
      }}>
        <div className="status-pill">
          <div className="status-dot" />
          SYSTEM OPERATIONAL · CORE MODELS READY
        </div>

        <h1 className="main-title">
          科学教育 AIGC 评估系统
        </h1>
        
        <p className="sub-title">
          专业的科学教育 AIGC 内容质量筛查平台，融合视觉一致性与大模型语义裁判。
          <br />
          支持快捷键：按 <strong>1, 2, 3</strong> 分别进入图像、文本与视频裁判。
        </p>
      </div>

      <div className="nav-grid">
        {navCards.map(({ to, icon: Icon, title, desc, footer }, index) => (
          <Link 
            key={to} 
            to={to} 
            className="nav-card animate-in" 
            style={{ animationDelay: `${(index + 1) * 0.1}s` }}
            ref={el => cardsRef.current[index] = el}
          >
            <div className="icon-box">
              <Icon size={48} />
            </div>
            <h2 className="card-title">{title}</h2>
            <p className="card-desc">{desc}</p>
            <div className="card-footer">
              <span className="footer-btn">
                {footer}
                <ArrowRight size={16} />
              </span>
            </div>
          </Link>
        ))}
      </div>

      <div className="system-stats animate-in" style={{ animationDelay: '0.4s' }}>
        <div className="stat-item">
          <span className="stat-value">{modelCount.toFixed(0)}</span>
          <span className="stat-label">双引擎驱动</span>
        </div>
        <div className="stat-item">
          <span className="stat-value">{dimensionCount.toFixed(0)}+</span>
          <span className="stat-label">评估维度</span>
        </div>
        <div className="stat-item">
          <span className="stat-value">JSON</span>
          <span className="stat-label">结构化输出</span>
        </div>
      </div>

      <footer className="home-footer animate-in" style={{ animationDelay: '0.6s' }}>
        <div className="footer-content">
          <div className="footer-section">
            <h4>关于系统</h4>
            <p>本系统旨在为科学教育从业者提供客观、多维的 AIGC 内容质量评估服务，助力提升教学资源的科学性与适用性。</p>
          </div>
          <div className="footer-section">
            <h4>快速链接</h4>
            <div className="footer-links">
              <Link to="/image">图像裁判</Link>
              <Link to="/text">文本裁判</Link>
              <Link to="/video">视频裁判</Link>
            </div>
          </div>
          <div className="footer-section">
            <h4>联系我们</h4>
            <div className="footer-social">
              <a href="#" title="GitHub"><Code size={20} /></a>
              <a href="#" title="Website"><Globe size={20} /></a>
              <a href="#" title="Email"><Mail size={20} /></a>
            </div>
          </div>
        </div>
        <div className="footer-bottom">
          <p>&copy; 2024 科学教育 AIGC 评估系统. All rights reserved.</p>
        </div>
      </footer>
    </div>
  )
}