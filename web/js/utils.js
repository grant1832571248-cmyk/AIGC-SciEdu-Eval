/**
 * 科学教育 AIGC 评估系统 - 通用工具函数
 */

/**
 * @typedef {Object} Particle
 * @property {number} x
 * @property {number} y
 * @property {number} vx
 * @property {number} vy
 * @property {number} r
 * @property {number} alpha
 */

/**
 * 初始化低干扰粒子背景
 * @param {string} canvasId 
 */
export function initSubtleParticles(canvasId = "particleLayer") {
  try {
    const canvas = document.getElementById(canvasId);
    if (!(canvas instanceof HTMLCanvasElement)) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const particles = [];
    
    let w, h;
    function resize() {
      w = window.innerWidth;
      h = window.innerHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx.scale(dpr, dpr);
      
      // 重新生成粒子
      particles.length = 0;
      const count = Math.floor((w * h) / 15000); // 适中密度
      for (let i = 0; i < count; i++) {
        particles.push({
          x: Math.random() * w,
          y: Math.random() * h,
          vx: (Math.random() - 0.5) * 0.3,
          vy: (Math.random() - 0.5) * 0.3,
          r: Math.random() * 1.5 + 0.5,
          alpha: Math.random() * 0.4 + 0.1
        });
      }
    }

    window.addEventListener("resize", resize);
    resize();

    function draw() {
      ctx.clearRect(0, 0, w, h);
      
      particles.forEach(p => {
        p.x += p.vx;
        p.y += p.vy;

        if (p.x < 0) p.x = w;
        if (p.x > w) p.x = 0;
        if (p.y < 0) p.y = h;
        if (p.y > h) p.y = 0;

        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(59, 130, 246, ${p.alpha})`;
        ctx.fill();
      });

      if (!reducedMotion) {
        requestAnimationFrame(draw);
      }
    }

    draw();
  } catch (e) {
    console.error("Failed to init particles:", e);
  }
}

/**
 * 初始化头部视差效果
 * @param {string} selector 
 */
export function initHeaderParallax(selector = "header") {
  const header = document.querySelector(selector);
  if (!header) return;

  header.addEventListener("mousemove", (e) => {
    const rect = header.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width - 0.5;
    const y = (e.clientY - rect.top) / rect.height - 0.5;
    header.style.setProperty("--header-parallax-x", (x * 4) + "px");
    header.style.setProperty("--header-parallax-y", (y * 4) + "px");
  });

  header.addEventListener("mouseleave", () => {
    header.style.setProperty("--header-parallax-x", "0px");
    header.style.setProperty("--header-parallax-y", "0px");
  });
}

/**
 * 数字滚动增长效果
 * @param {HTMLElement} el 
 * @param {number} target 
 * @param {number} duration 
 */
export function animateNumber(el, target, duration = 1000) {
    if (!el) return;
    const start = parseFloat(el.textContent) || 0;
    const startTime = performance.now();
    
    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const easeOutQuart = 1 - Math.pow(1 - progress, 4);
        const current = start + (target - start) * easeOutQuart;
        
        el.textContent = current.toFixed(1);
        
        if (progress < 1) {
            requestAnimationFrame(update);
        } else {
            el.textContent = target.toFixed(1);
        }
    }
    
    requestAnimationFrame(update);
}

/**
 * 获取学科主色
 * @param {string} subject 
 */
export function getSubjectColor(subject) {
  const colors = {
    physics: '#0891b2', // 深青色
    chemistry: '#7c3aed', // 深紫色
    biology: '#059669', // 深绿色
    earth: '#b45309', // 琥珀色
    default: '#3b82f6'  // 蓝色
  };
  return colors[subject] || colors.default;
}

/**
 * 为 Chart.js 创建雷达图渐变背景
 * @param {CanvasRenderingContext2D} ctx 
 * @param {string} color 
 * @returns {CanvasGradient}
 */
export function createChartGradient(ctx, color) {
  const gradient = ctx.createRadialGradient(
    ctx.canvas.width / 2 / (window.devicePixelRatio || 1), 
    ctx.canvas.height / 2 / (window.devicePixelRatio || 1), 
    0,
    ctx.canvas.width / 2 / (window.devicePixelRatio || 1), 
    ctx.canvas.height / 2 / (window.devicePixelRatio || 1), 
    Math.min(ctx.canvas.width, ctx.canvas.height) / 2 / (window.devicePixelRatio || 1)
  );
  
  // 安全地处理颜色转换
  let r = 59, g = 130, b = 246; // 默认蓝色
  if (color && color.startsWith('#')) {
    try {
      r = parseInt(color.slice(1, 3), 16);
      g = parseInt(color.slice(3, 5), 16);
      b = parseInt(color.slice(5, 7), 16);
    } catch (e) {
      console.warn("Color parsing failed, using default.");
    }
  } else if (color && color.startsWith('rgb')) {
    const match = color.match(/\d+/g);
    if (match && match.length >= 3) {
      r = parseInt(match[0]);
      g = parseInt(match[1]);
      b = parseInt(match[2]);
    }
  }
  
  gradient.addColorStop(0, `rgba(${r}, ${g}, ${b}, 0.8)`);
  gradient.addColorStop(1, `rgba(${r}, ${g}, ${b}, 0.1)`);
  return gradient;
}

/**
 * 文本纠错高亮处理
 * @param {string} text 
 * @param {Array<{word: string, suggestion: string}>} errors 
 * @returns {string}
 */
export function highlightScientificErrors(text, errors = []) {
  let highlighted = text;
  errors.forEach(err => {
    const regex = new RegExp(err.word, 'g');
    highlighted = highlighted.replace(regex, `<span class="error-highlight" data-suggestion="建议修改为: ${err.suggestion}">${err.word}</span>`);
  });
  return highlighted;
}

/**
 * 格式化文件大小
 * @param {number} bytes 
 */
export function formatFileSize(bytes) {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}
