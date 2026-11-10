import { AfterViewInit, Directive, ElementRef, Input, NgZone, OnDestroy, inject } from '@angular/core';
import { gsap, isBrowser, prefersReducedMotion } from './gsap';

/**
 * Scrubbed vertical parallax. `speed` is the fraction of scroll distance the
 * element lags by: 0.2 drifts gently, negative values move against the scroll.
 *
 *   <div [appParallax]="0.25">…</div>
 */
@Directive({
  selector: '[appParallax]',
  standalone: true,
})
export class ParallaxDirective implements AfterViewInit, OnDestroy {
  @Input('appParallax') speed = 0.2;

  private host = inject<ElementRef<HTMLElement>>(ElementRef);
  private zone = inject(NgZone);
  private ctx?: gsap.Context;

  ngAfterViewInit(): void {
    if (!isBrowser || prefersReducedMotion() || !this.speed) return;

    const el = this.host.nativeElement;
    const travel = () => this.speed * (window.innerHeight + el.offsetHeight) * 0.5;

    this.zone.runOutsideAngular(() => {
      this.ctx = gsap.context(() => {
        gsap.fromTo(
          el,
          { y: () => -travel() },
          {
            y: () => travel(),
            ease: 'none',
            scrollTrigger: {
              trigger: el,
              start: 'top bottom',
              end: 'bottom top',
              scrub: true,
              invalidateOnRefresh: true,
            },
          },
        );
      }, el);
    });
  }

  ngOnDestroy(): void {
    this.ctx?.revert();
  }
}
