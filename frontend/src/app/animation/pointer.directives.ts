import { AfterViewInit, Directive, ElementRef, Input, NgZone, OnDestroy, inject } from '@angular/core';
import { gsap, isBrowser, prefersReducedMotion } from './gsap';

/** Pointer effects only make sense with a precise, hovering pointer (not touch). */
function finePointer(): boolean {
  return isBrowser && window.matchMedia('(hover: hover) and (pointer: fine)').matches;
}

/**
 * A soft light that follows the cursor across a surface.
 *
 *   <article appSpotlight>            uses the saffron glow
 *   <div appSpotlight="leaf">         uses the green "verified" glow
 *
 * Sets --spot-x / --spot-y on the host and the `has-spotlight` class; styles.css draws the light.
 */
@Directive({ selector: '[appSpotlight]', standalone: true })
export class SpotlightDirective implements AfterViewInit, OnDestroy {
  @Input('appSpotlight') tone: '' | 'accent' | 'leaf' | 'violet' = '';

  private host = inject<ElementRef<HTMLElement>>(ElementRef);
  private zone = inject(NgZone);
  private frame = 0;
  private cleanup?: () => void;

  ngAfterViewInit(): void {
    if (!finePointer() || prefersReducedMotion()) return;
    const el = this.host.nativeElement;
    el.classList.add('has-spotlight');
    if (this.tone && this.tone !== 'accent') el.classList.add(`spotlight-${this.tone}`);

    this.zone.runOutsideAngular(() => {
      const move = (e: PointerEvent) => {
        cancelAnimationFrame(this.frame);
        this.frame = requestAnimationFrame(() => {
          const r = el.getBoundingClientRect();
          el.style.setProperty('--spot-x', `${e.clientX - r.left}px`);
          el.style.setProperty('--spot-y', `${e.clientY - r.top}px`);
        });
      };
      const enter = () => el.classList.add('spotlight-on');
      const leave = () => el.classList.remove('spotlight-on');
      el.addEventListener('pointermove', move, { passive: true });
      el.addEventListener('pointerenter', enter);
      el.addEventListener('pointerleave', leave);
      this.cleanup = () => {
        el.removeEventListener('pointermove', move);
        el.removeEventListener('pointerenter', enter);
        el.removeEventListener('pointerleave', leave);
      };
    });
  }

  ngOnDestroy(): void {
    cancelAnimationFrame(this.frame);
    this.cleanup?.();
  }
}

/**
 * A gentle 3D tilt toward the cursor, with a moving glare.  Uses GSAP's rotationX / rotationY so it composes with
 * any other GSAP animation on the same element (entrances, scroll scrubs).
 *
 *   <div appTilt [tiltMax]="8">
 */
@Directive({ selector: '[appTilt]', standalone: true })
export class TiltDirective implements AfterViewInit, OnDestroy {
  /** Maximum rotation in degrees. */
  @Input() tiltMax = 7;

  private host = inject<ElementRef<HTMLElement>>(ElementRef);
  private zone = inject(NgZone);
  private cleanup?: () => void;

  ngAfterViewInit(): void {
    if (!finePointer() || prefersReducedMotion()) return;
    const el = this.host.nativeElement;
    el.classList.add('has-tilt');

    this.zone.runOutsideAngular(() => {
      gsap.set(el, { transformPerspective: 900 });
      const rotX = gsap.quickTo(el, 'rotationX', { duration: 0.7, ease: 'power3.out' });
      const rotY = gsap.quickTo(el, 'rotationY', { duration: 0.7, ease: 'power3.out' });

      const move = (e: PointerEvent) => {
        const r = el.getBoundingClientRect();
        const px = (e.clientX - r.left) / r.width;     // 0 … 1
        const py = (e.clientY - r.top) / r.height;
        rotY((px - 0.5) * 2 * this.tiltMax);
        rotX(-(py - 0.5) * 2 * this.tiltMax);
        el.style.setProperty('--glare-x', `${px * 100}%`);
        el.style.setProperty('--glare-y', `${py * 100}%`);
      };
      const enter = () => el.classList.add('tilt-on');
      const leave = () => {
        el.classList.remove('tilt-on');
        rotX(0);
        rotY(0);
      };
      el.addEventListener('pointermove', move, { passive: true });
      el.addEventListener('pointerenter', enter);
      el.addEventListener('pointerleave', leave);
      this.cleanup = () => {
        el.removeEventListener('pointermove', move);
        el.removeEventListener('pointerenter', enter);
        el.removeEventListener('pointerleave', leave);
      };
    });
  }

  ngOnDestroy(): void {
    this.cleanup?.();
  }
}

/**
 * Pulls an element a little toward the cursor while it hovers nearby, then springs back.
 * Drives the CSS `translate` property (via --mag-x / --mag-y), so it never fights :hover transforms.
 *
 *   <a class="btn btn-primary" appMagnetic>
 */
@Directive({ selector: '[appMagnetic]', standalone: true })
export class MagneticDirective implements AfterViewInit, OnDestroy {
  /** Fraction of the cursor's offset from the centre that the element follows. */
  @Input() magneticStrength = 0.28;

  private host = inject<ElementRef<HTMLElement>>(ElementRef);
  private zone = inject(NgZone);
  private cleanup?: () => void;

  ngAfterViewInit(): void {
    if (!finePointer() || prefersReducedMotion()) return;
    const el = this.host.nativeElement;
    el.classList.add('is-magnetic');

    this.zone.runOutsideAngular(() => {
      const state = { x: 0, y: 0 };
      const apply = () => {
        el.style.setProperty('--mag-x', `${state.x.toFixed(2)}px`);
        el.style.setProperty('--mag-y', `${state.y.toFixed(2)}px`);
      };
      const toX = gsap.quickTo(state, 'x', { duration: 0.6, ease: 'power3.out', onUpdate: apply });
      const toY = gsap.quickTo(state, 'y', { duration: 0.6, ease: 'power3.out', onUpdate: apply });

      const move = (e: PointerEvent) => {
        const r = el.getBoundingClientRect();
        toX((e.clientX - (r.left + r.width / 2)) * this.magneticStrength);
        toY((e.clientY - (r.top + r.height / 2)) * this.magneticStrength);
      };
      const leave = () => {
        toX(0);
        toY(0);
      };
      el.addEventListener('pointermove', move, { passive: true });
      el.addEventListener('pointerleave', leave);
      this.cleanup = () => {
        el.removeEventListener('pointermove', move);
        el.removeEventListener('pointerleave', leave);
        gsap.killTweensOf(state);
      };
    });
  }

  ngOnDestroy(): void {
    this.cleanup?.();
  }
}
