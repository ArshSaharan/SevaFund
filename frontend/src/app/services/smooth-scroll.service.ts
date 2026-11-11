import { Injectable, NgZone, inject } from '@angular/core';
import { Router, NavigationEnd } from '@angular/router';
import { filter } from 'rxjs/operators';
import Lenis from 'lenis';
import { gsap, ScrollTrigger, isBrowser, prefersReducedMotion } from '../animation/gsap';

/**
 * Owns page scrolling: Lenis inertia scrolling driven by the GSAP ticker so
 * ScrollTrigger and Lenis stay frame-locked. Falls back to native scrolling
 * when the user prefers reduced motion.
 */
@Injectable({
  providedIn: 'root'
})
export class SmoothScrollService {
  private lenis: Lenis | null = null;
  private ngZone = inject(NgZone);
  private router = inject(Router);
  private tickerCallback: ((time: number) => void) | null = null;
  private lastPath = '';

  constructor() {
    if (!isBrowser) return;
    this.initSmoothScroll();
    this.handleRouteTransitions();

    // Web fonts change line wrapping and therefore every trigger position.
    document.fonts?.ready.then(() => this.refresh());
  }

  private initSmoothScroll(): void {
    if (prefersReducedMotion()) return;

    this.ngZone.runOutsideAngular(() => {
      this.lenis = new Lenis({
        duration: 1.15,
        easing: (t: number) => Math.min(1, 1.001 - Math.pow(2, -10 * t)), // expo out
        orientation: 'vertical',
        gestureOrientation: 'vertical',
        smoothWheel: true,
        touchMultiplier: 1.4,
      });

      this.lenis.on('scroll', ScrollTrigger.update);

      this.tickerCallback = (time: number) => this.lenis?.raf(time * 1000);
      gsap.ticker.add(this.tickerCallback);
      gsap.ticker.lagSmoothing(0);
    });
  }

  /**
   * Jump to the top when the *path* changes (not for query-param-only updates
   * such as filters), then re-measure triggers once the new page has rendered.
   */
  private handleRouteTransitions(): void {
    this.router.events
      .pipe(filter((event): event is NavigationEnd => event instanceof NavigationEnd))
      .subscribe((event) => {
        const path = event.urlAfterRedirects.split(/[?#]/)[0];
        if (path !== this.lastPath) {
          this.scrollTo(0, { immediate: true });
          this.lastPath = path;
        }
        setTimeout(() => this.refresh(), 120);
      });
  }

  getLenis(): Lenis | null {
    return this.lenis;
  }

  scrollTo(target: string | number | HTMLElement, options?: { offset?: number; immediate?: boolean; duration?: number }): void {
    if (!isBrowser) return;

    if (!this.lenis) {
      if (typeof target === 'number') {
        window.scrollTo({ top: target, behavior: 'auto' });
      } else {
        const el = typeof target === 'string' ? document.querySelector(target) : target;
        el?.scrollIntoView({ block: 'start' });
      }
      return;
    }

    this.lenis.scrollTo(target, {
      offset: options?.offset ?? 0,
      immediate: options?.immediate ?? false,
      duration: options?.duration,
    });
  }

  /** Pause scrolling (e.g. while a modal or the mobile menu is open). */
  lock(): void {
    this.lenis?.stop();
    if (!this.lenis && isBrowser) document.documentElement.style.overflow = 'hidden';
  }

  unlock(): void {
    this.lenis?.start();
    if (!this.lenis && isBrowser) document.documentElement.style.overflow = '';
  }

  /** Recalculate ScrollTrigger positions and Lenis bounds after layout changes. */
  refresh(): void {
    if (!isBrowser) return;
    this.ngZone.runOutsideAngular(() => {
      this.lenis?.resize();
      ScrollTrigger.refresh();
    });
  }

  destroy(): void {
    if (this.tickerCallback) {
      gsap.ticker.remove(this.tickerCallback);
      this.tickerCallback = null;
    }
    this.lenis?.destroy();
    this.lenis = null;
  }
}
