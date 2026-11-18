import { AfterViewInit, Directive, ElementRef, Input, NgZone, OnChanges, OnDestroy, SimpleChanges, inject } from '@angular/core';
import { gsap, isBrowser, prefersReducedMotion, revealStart } from './gsap';

/**
 * Counts a number up from zero the first time it scrolls into view, and glides to any new value afterwards
 * (for example a fundraiser total that grows after a donation).
 * Put the final, formatted value in the template so it is correct without JS.
 *
 *   <span [appCountUp]="1200" countSuffix="+">1,200+</span>
 */
@Directive({
  selector: '[appCountUp]',
  standalone: true,
})
export class CountUpDirective implements AfterViewInit, OnChanges, OnDestroy {
  @Input({ alias: 'appCountUp', required: true }) value = 0;
  @Input() countDecimals = 0;
  @Input() countPrefix = '';
  @Input() countSuffix = '';
  @Input() countDuration = 2.2;

  private host = inject<ElementRef<HTMLElement>>(ElementRef);
  private zone = inject(NgZone);
  private ctx?: gsap.Context;
  private counter = { v: 0 };
  private ready = false;

  ngAfterViewInit(): void {
    const el = this.host.nativeElement;
    el.textContent = this.format(this.value);
    this.counter.v = this.value;
    this.ready = true;
    if (!isBrowser || prefersReducedMotion()) return;

    this.counter.v = 0;
    el.textContent = this.format(0);

    this.zone.runOutsideAngular(() => {
      this.ctx = gsap.context(() => {
        gsap.to(this.counter, {
          v: this.value,
          duration: this.countDuration,
          ease: 'power3.out',
          onUpdate: () => {
            el.textContent = this.format(this.counter.v);
          },
          scrollTrigger: { trigger: el, start: revealStart(0.92), once: true },
        });
      }, el);
    });
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (!this.ready || !isBrowser) return;
    if (!changes['value'] && !changes['countSuffix'] && !changes['countPrefix'] && !changes['countDecimals']) return;
    const el = this.host.nativeElement;
    if (prefersReducedMotion() || !changes['value']) {
      gsap.killTweensOf(this.counter);
      this.counter.v = this.value;
      el.textContent = this.format(this.value);
      return;
    }
    this.zone.runOutsideAngular(() => {
      gsap.to(this.counter, {
        v: this.value,
        duration: 1.2,
        ease: 'power3.out',
        overwrite: true,
        onUpdate: () => {
          el.textContent = this.format(this.counter.v);
        },
      });
    });
  }

  private format(n: number): string {
    const body = this.countDecimals > 0
      ? n.toFixed(this.countDecimals)
      : Math.round(n).toLocaleString('en-IN');
    return `${this.countPrefix}${body}${this.countSuffix}`;
  }

  ngOnDestroy(): void {
    gsap.killTweensOf(this.counter);
    this.ctx?.revert();
  }
}
