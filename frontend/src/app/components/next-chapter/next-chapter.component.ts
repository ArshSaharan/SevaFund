import { Component, Input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { SplitTextDirective } from '../../animation';

/** "Turn the page" link that ends each story page and leads into the next. */
@Component({
  selector: 'app-next-chapter',
  standalone: true,
  imports: [RouterLink, SplitTextDirective],
  template: `
    <section class="next" aria-label="Next chapter">
      <a [routerLink]="link" class="next-link">
        <span class="container next-inner">
          <span class="next-meta">
            <span class="eyebrow">Next chapter · {{ number }}</span>
            <span class="next-desc">{{ description }}</span>
          </span>
          <span class="next-title display-lg" appSplit>{{ title }}</span>
          <span class="next-arrow" aria-hidden="true">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6">
              <line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline>
            </svg>
          </span>
        </span>
      </a>
    </section>
  `,
  styles: [`
    .next { border-top: 1px solid var(--line); }

    .next-link {
      display: block;
      position: relative;
      overflow: hidden;
      isolation: isolate;
    }

    .next-link::before {
      content: '';
      position: absolute;
      inset: 0;
      z-index: -1;
      background: var(--primary-light);
      transform: scaleY(0);
      transform-origin: bottom;
      transition: transform 0.7s var(--ease-expo);
    }

    .next-link:hover::before { transform: scaleY(1); }

    .next-inner {
      display: grid;
      grid-template-columns: 1fr auto;
      grid-template-areas: 'meta arrow' 'title arrow';
      align-items: end;
      gap: 16px 32px;
      padding-block: clamp(56px, 8vw, 104px);
    }

    .next-meta {
      grid-area: meta;
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px 24px;
    }

    .next-desc { color: var(--ink-3); font-size: 15px; }

    .next-title { grid-area: title; display: block; }

    .next-arrow {
      grid-area: arrow;
      width: clamp(64px, 8vw, 104px);
      aspect-ratio: 1;
      border-radius: 50%;
      border: 1px solid var(--line);
      display: grid;
      place-items: center;
      color: var(--ink);
      transition: background-color 0.4s ease, color 0.4s ease, transform 0.6s var(--ease-expo), border-color 0.4s ease;
    }

    .next-link:hover .next-arrow {
      background: var(--accent);
      border-color: var(--accent);
      color: var(--on-accent);
      transform: rotate(-45deg);
    }
  `]
})
export class NextChapterComponent {
  @Input({ required: true }) link!: string;
  @Input({ required: true }) title!: string;
  @Input() description = '';
  @Input() number = '';
}
