import { gsap } from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { SplitText } from 'gsap/SplitText';

/**
 * Single place where GSAP plugins are registered. Import gsap / ScrollTrigger /
 * SplitText from here (not from 'gsap' directly) so registration always happens.
 */
gsap.registerPlugin(ScrollTrigger, SplitText);

gsap.defaults({ ease: 'expo.out', duration: 1.1 });

export { gsap, ScrollTrigger, SplitText };

export const isBrowser = typeof window !== 'undefined';

export function prefersReducedMotion(): boolean {
  return isBrowser && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/**
 * ScrollTrigger `start` for one-shot entrance animations. Fires when the
 * trigger's top crosses `fraction` of the viewport height, with two guards:
 *  - never later than the last reachable scroll position, so content at the
 *    very bottom of a page still plays;
 *  - free to go negative for content already on screen at load, so it plays
 *    immediately. (`clamp()` would pin that to exactly 0, and a trigger is not
 *    active at progress 0 — it would wait for the first scroll.)
 */
export function revealStart(fraction = 0.88): (self: ScrollTrigger) => number {
  return (self) => {
    const el = self.trigger as Element;
    const top = el.getBoundingClientRect().top + window.scrollY;
    return Math.min(top - window.innerHeight * fraction, ScrollTrigger.maxScroll(window) - 1);
  };
}
