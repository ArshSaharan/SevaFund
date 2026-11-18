import { gsap, isBrowser, prefersReducedMotion } from './gsap';

const COLORS = ['#F26B1D', '#FFB547', '#0E7A55', '#34C08F', '#C2410C', '#FBDCC6'];

/**
 * A short, celebratory burst of paper confetti from an element (for example a completed donation).
 * Pure DOM + GSAP, removed when finished; does nothing for users who prefer reduced motion.
 */
export function celebrate(origin: HTMLElement | null, pieces = 46): void {
  if (!isBrowser || !origin || prefersReducedMotion()) return;
  const rect = origin.getBoundingClientRect();
  const layer = document.createElement('div');
  layer.setAttribute('aria-hidden', 'true');
  Object.assign(layer.style, { position: 'fixed', inset: '0', pointerEvents: 'none', zIndex: '1200', overflow: 'hidden' });
  document.body.appendChild(layer);

  const cx = rect.left + rect.width / 2;
  const cy = rect.top + Math.min(rect.height / 2, 120);
  const tl = gsap.timeline({ onComplete: () => layer.remove() });

  for (let i = 0; i < pieces; i++) {
    const bit = document.createElement('span');
    const w = gsap.utils.random(6, 11);
    const round = Math.random() < 0.3;
    Object.assign(bit.style, {
      position: 'absolute',
      left: `${cx}px`,
      top: `${cy}px`,
      width: `${w}px`,
      height: `${round ? w : w * 0.45}px`,
      borderRadius: round ? '50%' : '2px',
      background: COLORS[i % COLORS.length],
      willChange: 'transform, opacity',
    });
    layer.appendChild(bit);

    const angle = gsap.utils.random(-Math.PI * 0.95, -Math.PI * 0.05);   // upward fan
    const speed = gsap.utils.random(160, 360);
    const dx = Math.cos(angle) * speed;
    const dy = Math.sin(angle) * speed;
    tl.fromTo(
      bit,
      { x: 0, y: 0, rotation: 0, scale: 0.4, opacity: 1 },
      {
        keyframes: [
          { x: dx * 0.7, y: dy * 0.7, scale: 1, rotation: gsap.utils.random(-260, 260), duration: 0.55, ease: 'power3.out' },
          { x: dx, y: dy + gsap.utils.random(220, 380), rotation: gsap.utils.random(-540, 540), opacity: 0, duration: 1.3, ease: 'power1.in' },
        ],
      },
      gsap.utils.random(0, 0.08),
    );
  }
}
