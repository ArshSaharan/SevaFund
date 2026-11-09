import { Injectable, NgZone, inject } from '@angular/core';
import { Router, NavigationEnd } from '@angular/router';
import { filter } from 'rxjs/operators';
import Lenis from 'lenis';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';

@Injectable({
  providedIn: 'root'
})
export class SmoothScrollService {
  private lenis: Lenis | null = null;
  private ngZone = inject(NgZone);
  private router = inject(Router);
  private tickerCallback: ((time: number) => void) | null = null;

  constructor() {
    this.initSmoothScroll();
    this.handleRouteTransitions();
  }

  /**
   * Initialize Lenis smooth scroll and synchronize with GSAP ScrollTrigger
   */
  private initSmoothScroll(): void {
    if (typeof window === 'undefined') return;

    this.ngZone.runOutsideAngular(() => {
      // Register ScrollTrigger plugin with GSAP
      gsap.registerPlugin(ScrollTrigger);

      // Instantiate Lenis with exponential smooth easing
      this.lenis = new Lenis({
        duration: 1.2,
        easing: (t: number) => Math.min(1, 1.001 - Math.pow(2, -10 * t)), // Exponential Ease-Out (Expo feel)
        orientation: 'vertical',
        gestureOrientation: 'vertical',
        smoothWheel: true,
        touchMultiplier: 1.4,
        infinite: false
      });

      // Synchronize ScrollTrigger with Lenis scroll updates
      this.lenis.on('scroll', () => {
        ScrollTrigger.update();
      });

      // Synchronize GSAP ticker with Lenis requestAnimationFrame
      this.tickerCallback = (time: number) => {
        if (this.lenis) {
          this.lenis.raf(time * 1000);
        }
      };

      gsap.ticker.add(this.tickerCallback);

      // Disable GSAP lag smoothing to ensure frame-perfect synchronization
      gsap.ticker.lagSmoothing(0);
    });
  }

  /**
   * Reset scroll position and refresh ScrollTrigger on route navigation
   */
  private handleRouteTransitions(): void {
    this.router.events
      .pipe(filter(event => event instanceof NavigationEnd))
      .subscribe(() => {
        this.scrollTo(0, { immediate: true });
        setTimeout(() => {
          this.refresh();
        }, 100);
      });
  }

  /**
   * Get the active Lenis instance
   */
  getLenis(): Lenis | null {
    return this.lenis;
  }

  /**
   * Get GSAP instance with plugins registered
   */
  getGsap() {
    return gsap;
  }

  /**
   * Get ScrollTrigger instance
   */
  getScrollTrigger() {
    return ScrollTrigger;
  }

  /**
   * Scroll smoothly to a target (element, selector, or position)
   */
  scrollTo(target: string | number | HTMLElement, options?: { offset?: number; immediate?: boolean; duration?: number }): void {
    if (!this.lenis) {
      if (typeof window !== 'undefined') {
        if (typeof target === 'number') {
          window.scrollTo({ top: target, behavior: options?.immediate ? 'auto' : 'smooth' });
        }
      }
      return;
    }

    this.lenis.scrollTo(target, {
      offset: options?.offset ?? 0,
      immediate: options?.immediate ?? false,
      duration: options?.duration
    });
  }

  /**
   * Recalculate ScrollTrigger positions and Lenis scroll bounds
   */
  refresh(): void {
    if (typeof window === 'undefined') return;
    this.ngZone.runOutsideAngular(() => {
      ScrollTrigger.refresh();
      if (this.lenis) {
        this.lenis.resize();
      }
    });
  }

  /**
   * Cleanup resources on service teardown
   */
  destroy(): void {
    if (this.tickerCallback) {
      gsap.ticker.remove(this.tickerCallback);
      this.tickerCallback = null;
    }
    if (this.lenis) {
      this.lenis.destroy();
      this.lenis = null;
    }
  }
}
