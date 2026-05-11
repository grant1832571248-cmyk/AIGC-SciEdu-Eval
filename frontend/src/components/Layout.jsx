import { Link, useLocation, Outlet } from 'react-router-dom'
import { Sparkles, LayoutDashboard, FileText, Video, Home } from 'lucide-react'

const navItems = [
  { path: '/', label: '首页', icon: Home },
  { path: '/image', label: '图像裁判', icon: LayoutDashboard },
  { path: '/text', label: '文本裁判', icon: FileText },
  { path: '/video', label: '视频裁判', icon: Video },
]

export default function Layout() {
  const location = useLocation()
  const currentPath = location.pathname

  return (
    <div className="app-shell">
      <div className="tech-bg-grid" />
      <div className="tech-bg-scanline" />
      <div className="tech-bg-noise" />

      {/* 顶部导航栏 */}
      <header className="topbar">
        <div className="topbar-inner">
          <Link to="/" className="topbar-brand">
            <div className="topbar-brand-icon">
              <Sparkles size={16} />
            </div>
            <span>AIGC 评估</span>
          </Link>

          <nav className="topbar-nav">
            {navItems.map(({ path, label, icon: Icon }) => (
              <Link
                key={path}
                to={path}
                className="nav-tab"
                data-active={currentPath === path || (path !== '/' && currentPath.startsWith(path)) ? 'true' : undefined}
              >
                <Icon size={14} />
                <span>{label}</span>
              </Link>
            ))}
          </nav>

          <div className="topbar-badge">
            <span className="pulse-dot" />
            <span>系统运行中</span>
          </div>
        </div>
      </header>

      {/* 页面内容 */}
      <main className="page-content">
        <Outlet />
      </main>

      <footer className="app-footer">
        <p>© 2024 科学教育 AIGC 评估系统 · 基于多模态大模型技术</p>
      </footer>
    </div>
  )
}
