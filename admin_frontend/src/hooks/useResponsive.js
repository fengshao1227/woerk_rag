import { useState, useEffect } from 'react';

/**
 * 响应式Hook - 使用 window.innerWidth 判断设备类型
 * @returns {{ isMobile: boolean, isTablet: boolean, isDesktop: boolean, windowWidth: number }}
 */
export default function useResponsive() {
  const [windowWidth, setWindowWidth] = useState(
    typeof window !== 'undefined' ? window.innerWidth : 1200
  );

  useEffect(() => {
    const handleResize = () => setWindowWidth(window.innerWidth);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return {
    windowWidth,
    isMobile: windowWidth < 768,      // 手机
    isTablet: windowWidth >= 768 && windowWidth < 1024,  // 平板
    isDesktop: windowWidth >= 1024,   // 桌面
  };
}
