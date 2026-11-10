import { AfterViewInit, Directive, ElementRef, Input, NgZone, OnDestroy, inject } from '@angular/core';
import { gsap, isBrowser, prefersReducedMotion, revealStart, SplitText } from './gsap';

export type SplitMode = '' | 'lines' | 'words' | 'chars';

/**
 * Masked headline reveal: text rises line-by-line (or word / char) out of a clip mask.
 * Re-splits automatically on resize and once web fonts load (SplitText autoSplit).
 *
 *   <h2 appSplit>…</h2>                          reveal when scrolled into view
 *   <h1 appSplit="words" [splitOnLoad]="true">   play immediately (heroes)
 */
@Directive({
  selector: '[appSplit]',
  standalone: true,
})
export class SplitTextDirective implements AfterViewInit, OnDestroy {
  @Input('appSplit') mode: SplitMode = '';
  @Input() splitDelay = 0;
  /** Play on first paint instead of waiting for the element to scroll into view. */
  @Input() splitOnLoad = false;

  private host = inject<ElementRef<HTMLElement>>(ElementRef);
  private zone = inject(NgZone);
  private ctx?: gsap.Context;

  ngAfterViewInit(): void {
    if (!isBrowser || prefersReducedMotion()) return;

    const el = this.host.nativeElement;
    const mode = this.mode || 'lines';

    this.zone.runOutsideAngular(() => {
      this.ctx = gsap.context(() => {
        SplitText.create(el, {
          type: mode === 'chars' ? 'lines,words,chars' : mode === 'words' ? 'lines,words' : 'lines',
          mask: 'lines',
          linesClass: 'split-line',
          autoSplit: true,
          onSplit: (self: SplitText) => {
            const targets = mode === 'chars' ? self.chars : mode === 'words' ? self.words : self.lines;
            return gsap.from(targets, {
              yPercent: 115,
              rotate: mode === 'lines' ? 0 : 4,
              duration: 1.25,
              stagger: mode === 'chars' ? 0.018 : mode === 'words' ? 0.05 : 0.11,
              delay: this.splitDelay,
              scrollTrigger: this.splitOnLoad
                ? undefined
                : { trigger: el, start: revealStart(), once: true },
            });
          },
        });
      }, el);
    });
  }

  ngOnDestroy(): void {
    this.ctx?.revert();
  }
}
