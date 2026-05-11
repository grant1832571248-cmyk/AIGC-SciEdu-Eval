import { useEffect, useRef, useState } from 'react';

/**
 * 低干扰粒子背景 Hook
 * @param {React.RefObject} canvasRef
 */
export function useParticles(canvasRef) {
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const particles = [];
    let animationFrameId;
    
    let w, h;
    function resize() {
      w = window.innerWidth;
      h = window.innerHeight;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = `${w}px`;
      canvas.style.height = `${h}px`;
      ctx.scale(dpr, dpr);
      
      particles.length = 0;
      const count = Math.floor((w * h) / 15000);
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

    window.addEventListener('resize', resize);
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
        animationFrameId = requestAnimationFrame(draw);
      }
    }

    draw();

    return () => {
      window.removeEventListener('resize', resize);
      cancelAnimationFrame(animationFrameId);
    };
  }, [canvasRef]);
}

/**
 * 头部视察效果 Hook
 * @param {React.RefObject} elementRef 
 */
export function useHeaderParallax(elementRef) {
  useEffect(() => {
    const element = elementRef.current;
    if (!element) return;

    const handleMouseMove = (e) => {
      const rect = element.getBoundingClientRect();
      const x = (e.clientX - rect.left) / rect.width - 0.5;
      const y = (e.clientY - rect.top) / rect.height - 0.5;
      element.style.setProperty('--header-parallax-x', (x * 4) + 'px');
      element.style.setProperty('--header-parallax-y', (y * 4) + 'px');
    };

    const handleMouseLeave = () => {
      element.style.setProperty('--header-parallax-x', '0px');
      element.style.setProperty('--header-parallax-y', '0px');
    };

    element.addEventListener('mousemove', handleMouseMove);
    element.addEventListener('mouseleave', handleMouseLeave);

    return () => {
      element.removeEventListener('mousemove', handleMouseMove);
      element.removeEventListener('mouseleave', handleMouseLeave);
    };
  }, [elementRef]);
}

/**
 * 数字滚动动画 Hook
 * @param {number} target
 * @param {number} duration
 * @returns {number}
 */
export function useAnimateNumber(target, duration = 1000) {
  const [value, setValue] = useState(0);
  const startTimeRef = useRef(null);
  const rafRef = useRef(null);

  useEffect(() => {
    const startValue = value;
    startTimeRef.current = performance.now();

    function update(currentTime) {
      const elapsed = currentTime - startTimeRef.current;
      const progress = Math.min(elapsed / duration, 1);
      const easeOutQuart = 1 - Math.pow(1 - progress, 4);
      const nextValue = startValue + (target - startValue) * easeOutQuart;

      setValue(nextValue);

      if (progress < 1) {
        rafRef.current = requestAnimationFrame(update);
      } else {
        setValue(target);
      }
    }

    rafRef.current = requestAnimationFrame(update);

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [target, duration]);

  return value;
}

/**
 * 为 Chart.js 创建雷达图渐变背景
 * @param {CanvasRenderingContext2D} ctx 
 * @param {string} color 
 * @returns {CanvasGradient}
 */
export function createChartGradient(ctx, color) {
  if (!ctx || !ctx.canvas) return color;
  
  const dpr = window.devicePixelRatio || 1;
  const gradient = ctx.createRadialGradient(
    ctx.canvas.width / 2 / dpr, 
    ctx.canvas.height / 2 / dpr, 
    0,
    ctx.canvas.width / 2 / dpr, 
    ctx.canvas.height / 2 / dpr, 
    Math.min(ctx.canvas.width, ctx.canvas.height) / 2 / dpr
  );
  
  let r = 59, g = 130, b = 246;
  if (color && color.startsWith('#')) {
    try {
      r = parseInt(color.slice(1, 3), 16);
      g = parseInt(color.slice(3, 5), 16);
      b = parseInt(color.slice(5, 7), 16);
    } catch (e) {}
  } else if (color && color.startsWith('rgba')) {
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
