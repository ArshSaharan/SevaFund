import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { SpotlightDirective } from '../../animation';

/**
 * "Your cause could be next" — fills the last slot of a short grid with an invitation to start a fundraiser,
 * instead of leaving a hole.  Give the host the grid's item class so it joins the grid's entrance animation.
 */
@Component({
  selector: 'app-invite-card',
  standalone: true,
  imports: [RouterLink, SpotlightDirective],
  template: `
    <a routerLink="/create" class="invite-card" appSpotlight>
      <span class="invite-plus" aria-hidden="true">
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round">
          <line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line>
        </svg>
      </span>
      <span class="invite-kicker">Room for one more</span>
      <span class="invite-title">Your cause could be <em>next.</em></span>
      <span class="invite-text">Start a fundraiser with a hospital estimate or a supplier quote. Every request is
        checked before it can raise a rupee.</span>
      <span class="invite-cta">
        Start a verified fundraiser
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true">
          <line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline>
        </svg>
      </span>
    </a>
  `,
  styles: [`
    :host { display: block; min-height: 420px; }

    .invite-card {
      position: relative;
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      gap: 14px;
      box-sizing: border-box;
      height: 100%;
      padding: 34px 30px;
      border: 1.5px dashed var(--slate-300);
      border-radius: var(--radius-xl);
      background-color: color-mix(in srgb, var(--surface) 55%, transparent);
      color: var(--ink);
      text-decoration: none;
      transition: transform 0.5s var(--ease-expo), border-color 0.3s ease, box-shadow 0.5s var(--ease-expo),
                  background-color 0.3s ease;
    }

    .invite-card:hover,
    .invite-card:focus-visible {
      transform: translateY(-6px);
      border-color: var(--accent);
      border-style: solid;
      background-color: var(--surface);
      box-shadow: var(--shadow-card-hover);
    }

    .invite-plus {
      display: grid;
      place-items: center;
      width: 52px;
      height: 52px;
      border-radius: 50%;
      background: var(--primary-light);
      color: var(--primary);
      transition: transform 0.6s var(--ease-spring), background-color 0.3s ease, color 0.3s ease;
    }

    .invite-card:hover .invite-plus {
      transform: rotate(90deg) scale(1.08);
      background: var(--accent);
      color: var(--on-accent);
    }

    .invite-kicker {
      margin-top: auto;
      font-size: 11.5px;
      font-weight: 600;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: var(--accent-ink);
    }

    .invite-title {
      font-family: var(--font-display);
      font-size: clamp(26px, 2.4vw, 32px);
      line-height: 1.08;
      letter-spacing: -0.02em;
    }

    .invite-title em { color: var(--accent-ink); }

    .invite-text { font-size: 14.5px; line-height: 1.6; color: var(--ink-3); max-width: 34ch; }

    .invite-cta {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      margin-top: 6px;
      font-size: 14px;
      font-weight: 600;
      color: var(--ink);
      border-bottom: 1.5px solid var(--accent);
      padding-bottom: 2px;
      transition: gap 0.35s var(--ease-expo);
    }

    .invite-card:hover .invite-cta { gap: 12px; }

    @media (max-width: 640px) { :host { min-height: 0; } }
  `],
})
export class InviteCardComponent {}
