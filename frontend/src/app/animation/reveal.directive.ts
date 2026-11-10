import { AfterViewInit, Directive, ElementRef, Input, NgZone, OnDestroy, inject } from '@angular/core';
import { gsap, isBrowser, prefersReducedMotion, revealStart } from './gsap';

export type RevealVariant = '' | 'up' | 'fade' | 'scale' | 'left' | 'right' | 'clip';

const FROM: Record<Exclude<RevealVariant, '' | 'clip'>, gsap.TweenVars> = {
  up: { autoAlpha: 0, y: 48 },
  fade: { autoAlpha: 0 },
  scale: { autoAlpha: 0, scale: 0.94, y: 24 },
  left: { autoAlpha: 0, x: -56 },
  right: { autoAlpha: 0, x: 56 },
};

/**
 * Scroll-triggered entrance.
 *
 *   <div appReveal>                       fade + rise when it scrolls into view
 *   <ul appReveal="scale" [revealStagger]="0.08">   animate the children in turn
 *   <img appReveal="clip">                wipe up from the bottom edge
 */
@Directive({
  selector: '[appReveal]',
  standalone: true,
})
export class RevealDirective implements AfterViewInit, OnDestroy {
  @Input('appReveal') variant: RevealVariant = '';
  @Input() revealDelay = 0;
  /** When set, the host's direct children animate in sequence with this stagger. */
  @Input() revealStagger: number | null = null;
  /** Override the trigger point (any ScrollTrigger start value). Defaults to `revealStart()`. */
  @Input() revealStart: string | null = null;

  private host = inject<ElementRef<HTMLElement>>(ElementRef);
  private zone = inject(NgZone);
  private ctx?: gsap.Context;

  ngAfterViewInit(): void {
    if (!isBrowser || prefersReducedMotion()) return;

    const el = this.host.nativeElement;
    const targets = this.revealStagger != null ? Array.from(el.children) : el;
    const scrollTrigger = { trigger: el, start: this.revealStart ?? revealStart(), once: true };

    this.zone.runOutsideAngular(() => {
      this.ctx = gsap.context(() => {
        if (this.variant === 'clip') {
          gsap.fromTo(
            targets,
            { clipPath: 'inset(100% 0% 0% 0%)' },
            {
              clipPath: 'inset(0% 0% 0% 0%)',
              duration: 1.4,
              delay: this.revealDelay,
              stagger: this.revealStagger ?? 0,
              clearProps: 'clipPath',
              scrollTrigger,
            },
          );
          return;
        }

        gsap.from(targets, {
          ...FROM[this.variant || 'up'],
          delay: this.revealDelay,
          stagger: this.revealStagger ?? 0,
          // hand transforms back to CSS so :hover effects keep working
          clearProps: 'transform,opacity,visibility',
          scrollTrigger,
        });
      }, el);
    });
  }

  ngOnDestroy(): void {
    this.ctx?.revert();
  }
}
