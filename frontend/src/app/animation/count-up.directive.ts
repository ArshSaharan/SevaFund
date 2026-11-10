import { AfterViewInit, Directive, ElementRef, Input, NgZone, OnDestroy, inject } from '@angular/core';
import { gsap, isBrowser, prefersReducedMotion, revealStart } from './gsap';

/**
 * Counts a number up from zero the first time it scrolls into view.
 * Put the final, formatted value in the template so it is correct without JS.
 *
 *   <span [appCountUp]="1200" countSuffix="+">1,200+</span>
 */
@Directive({
  selector: '[appCountUp]',
  standalone: true,
})
export class CountUpDirective implements AfterViewInit, OnDestroy {
  @Input({ alias: 'appCountUp', required: true }) value = 0;
  @Input() countDecimals = 0;
  @Input() countPrefix = '';
  @Input() countSuffix = '';
  @Input() countDuration = 2.2;

  private host = inject<ElementRef<HTMLElement>>(ElementRef);
  private zone = inject(NgZone);
  private ctx?: gsap.Context;

  ngAfterViewInit(): void {
    const el = this.host.nativeElement;
    el.textContent = this.format(this.value);
    if (!isBrowser || prefersReducedMotion()) return;

    const counter = { v: 0 };
    el.textContent = this.format(0);

    this.zone.runOutsideAngular(() => {
      this.ctx = gsap.context(() => {
        gsap.to(counter, {
          v: this.value,
          duration: this.countDuration,
          ease: 'power3.out',
          onUpdate: () => {
            el.textContent = this.format(counter.v);
          },
          scrollTrigger: { trigger: el, start: revealStart(0.92), once: true },
        });
      }, el);
    });
  }

  private format(n: number): string {
    const body = this.countDecimals > 0
      ? n.toFixed(this.countDecimals)
      : Math.round(n).toLocaleString('en-IN');
    return `${this.countPrefix}${body}${this.countSuffix}`;
  }

  ngOnDestroy(): void {
    this.ctx?.revert();
  }
}
