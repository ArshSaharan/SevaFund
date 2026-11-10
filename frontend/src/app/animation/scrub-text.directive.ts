import { AfterViewInit, Directive, ElementRef, Input, NgZone, OnDestroy, inject } from '@angular/core';
import { gsap, isBrowser, prefersReducedMotion, SplitText } from './gsap';

/**
 * Scroll-scrubbed "read-along" text: each word brightens from a faint ghost to
 * full ink as the paragraph travels up the viewport. Scrolling back dims it again.
 *
 *   <p class="display-md" appScrubText>When a family faces a bill…</p>
 */
@Directive({
  selector: '[appScrubText]',
  standalone: true,
})
export class ScrubTextDirective implements AfterViewInit, OnDestroy {
  @Input() scrubStart = 'top 82%';
  @Input() scrubEnd = 'bottom 48%';
  @Input() scrubFrom = 0.14;

  private host = inject<ElementRef<HTMLElement>>(ElementRef);
  private zone = inject(NgZone);
  private ctx?: gsap.Context;

  ngAfterViewInit(): void {
    if (!isBrowser || prefersReducedMotion()) return;

    const el = this.host.nativeElement;

    this.zone.runOutsideAngular(() => {
      this.ctx = gsap.context(() => {
        SplitText.create(el, {
          type: 'words',
          autoSplit: true,
          onSplit: (self: SplitText) =>
            gsap.fromTo(
              self.words,
              { opacity: this.scrubFrom },
              {
                opacity: 1,
                ease: 'none',
                stagger: 0.1,
                scrollTrigger: {
                  trigger: el,
                  start: this.scrubStart,
                  end: this.scrubEnd,
                  scrub: 0.6,
                },
              },
            ),
        });
      }, el);
    });
  }

  ngOnDestroy(): void {
    this.ctx?.revert();
  }
}
