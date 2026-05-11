/**
 * 科学教育 AIGC 评估系统 - 通用工具函数
 */

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
 * 为 Chart.js 创建渐变背景
 * @param {CanvasRenderingContext2D} ctx 
 * @param {string} color 
 * @returns {CanvasGradient}
 */
export function createChartGradient(ctx, color) {
  if (!ctx || !ctx.canvas) return color;
  
  const canvas = ctx.canvas;
  const dpr = window.devicePixelRatio || 1;
  const width = canvas.width / dpr;
  const height = canvas.height / dpr;
  
  const gradient = ctx.createRadialGradient(
    width / 2, height / 2, 0,
    width / 2, height / 2, Math.min(width, height) / 2
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

/**
 * 高亮文本错误
 * @param {string} text
 * @param {Array<{word: string, suggestion: string}>} errors
 * @returns {string}
 */
export function highlightText(text, errors) {
  if (!errors || errors.length === 0) return text;

  let highlighted = text;
  errors.forEach(err => {
    const regex = new RegExp(err.word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g');
    highlighted = highlighted.replace(
      regex,
      `<span class="error-highlight" data-suggestion="建议修改为: ${err.suggestion}">${err.word}</span>`
    );
  });
  return highlighted;
}
