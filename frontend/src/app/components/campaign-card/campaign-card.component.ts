import { Component, Input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { Campaign } from '../../models/campaign.model';

@Component({
  selector: 'app-campaign-card',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <article class="campaign-card">
      <div class="card-image-wrap">
        <img
          [src]="campaign.cover_image_url || '/assets/default-campaign.jpg'"
          alt=""
          class="card-img"
          loading="lazy"
          onerror="this.src='/assets/default-campaign.jpg'"
        />
        <div class="image-badges">
          <span class="category-pill">{{ campaign.category | titlecase }}</span>
          <span
            class="trust-badge"
            [class.trust-high]="trustScore >= 80"
            [class.trust-med]="trustScore >= 50 && trustScore < 80"
            [class.trust-low]="trustScore < 50"
            *ngIf="trustScore > 0"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" aria-hidden="true">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
            </svg>
            {{ trustScore | number: '1.0-0' }} trust score
          </span>
        </div>
      </div>

      <div class="card-body">
        <h3 class="campaign-title">
          <!-- Stretched link: the whole card is clickable, but only the title is announced -->
          <a [routerLink]="['/campaigns', campaign.id]" class="card-link">{{ campaign.title }}</a>
        </h3>
        <p class="campaign-desc">{{ shortDescription }}</p>

        <p class="hospital-line" *ngIf="campaign.hospital_name">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
          </svg>
          <span>{{ campaign.hospital_name }}</span>
        </p>

        <div class="progress-section">
          <div class="progress-track" role="progressbar" [attr.aria-valuenow]="progress" aria-valuemin="0" aria-valuemax="100" [attr.aria-label]="progress + '% funded'">
            <div class="progress-fill" [style.width.%]="progress"></div>
          </div>
          <div class="funding-metrics">
            <p>
              <span class="raised-amount">₹{{ formatINR(campaign.current_amount) }}</span>
              <span class="raised-label">of ₹{{ formatINR(campaign.goal_amount) }}</span>
            </p>
            <span class="percent-num">{{ progress }}%</span>
          </div>
        </div>

        <div class="card-footer">
          <div class="meta-tags">
            <span *ngIf="campaign.donor_count"><strong>{{ campaign.donor_count }}</strong> donors</span>
            <span class="tax-tag" *ngIf="campaign.is_80g_tax_exempt">80G</span>
          </div>
          <span class="donate-cta" aria-hidden="true">
            Donate
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <line x1="5" y1="12" x2="19" y2="12"></line>
              <polyline points="12 5 19 12 12 19"></polyline>
            </svg>
          </span>
        </div>
      </div>
    </article>
  `,
  styles: [`
    :host { display: block; height: 100%; }

    .campaign-card {
      position: relative;
      display: flex;
      flex-direction: column;
      height: 100%;
      overflow: hidden;
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: var(--radius-xl);
      transition: transform 0.5s var(--ease-expo), box-shadow 0.5s var(--ease-expo), border-color 0.3s ease;
    }

    .campaign-card:hover,
    .campaign-card:focus-within {
      transform: translateY(-6px);
      box-shadow: var(--shadow-card-hover);
      border-color: var(--slate-300);
    }

    .card-image-wrap {
      position: relative;
      aspect-ratio: 16 / 10;
      overflow: hidden;
      background: var(--slate-100);
    }

    .card-img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      transition: transform 0.9s var(--ease-expo);
    }

    .campaign-card:hover .card-img { transform: scale(1.06); }

    .image-badges {
      position: absolute;
      inset: 12px 12px auto;
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
    }

    .category-pill,
    .trust-badge {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      padding: 5px 10px;
      border-radius: var(--radius-full);
      font-size: 11.5px;
      font-weight: 600;
      backdrop-filter: blur(10px);
      -webkit-backdrop-filter: blur(10px);
    }

    .category-pill { background: rgba(20, 16, 11, 0.62); color: #FBF7F0; }
    .trust-badge { color: #FFFFFF; box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15); }
    .trust-badge.trust-high { background: rgba(14, 122, 85, 0.92); }
    .trust-badge.trust-med { background: rgba(180, 83, 9, 0.92); }
    .trust-badge.trust-low { background: rgba(90, 79, 68, 0.88); }

    .card-body {
      display: flex;
      flex-direction: column;
      flex: 1;
      padding: 20px 22px 18px;
    }

    .campaign-title {
      margin-bottom: 8px;
      font-family: var(--font-display);
      font-size: 20px;
      font-weight: 500;
      line-height: 1.2;
      letter-spacing: -0.015em;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }

    .card-link { color: var(--ink); }
    .card-link::after { content: ''; position: absolute; inset: 0; z-index: 1; }
    .card-link:focus-visible { outline: none; }
    .campaign-card:has(.card-link:focus-visible) { outline: 2px solid var(--accent); outline-offset: 3px; }

    .campaign-desc {
      flex: 1;
      margin-bottom: 12px;
      font-size: 14px;
      line-height: 1.55;
      color: var(--ink-3);
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }

    .hospital-line {
      display: flex;
      align-items: center;
      gap: 6px;
      margin-bottom: 14px;
      font-size: 12.5px;
      font-weight: 600;
      color: var(--leaf);
    }

    .hospital-line span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

    .progress-section { margin-top: auto; padding-top: 6px; }

    .progress-track {
      height: 6px;
      margin-bottom: 10px;
      overflow: hidden;
      border-radius: var(--radius-full);
      background: var(--slate-100);
    }

    .progress-fill {
      height: 100%;
      max-width: 100%;
      border-radius: inherit;
      background: linear-gradient(90deg, var(--accent), color-mix(in srgb, var(--accent) 55%, var(--leaf)));
      transition: width 0.8s var(--ease-expo);
    }

    .funding-metrics {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 8px;
    }

    .raised-amount {
      font-family: var(--font-display);
      font-size: 20px;
      font-weight: 500;
      color: var(--ink);
      letter-spacing: -0.02em;
      margin-right: 6px;
    }

    .raised-label { font-size: 12.5px; color: var(--ink-3); }
    .percent-num { font-size: 13px; font-weight: 700; color: var(--primary); }

    .card-footer {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
      margin-top: 14px;
      padding-top: 14px;
      border-top: 1px solid var(--line-2);
    }

    .meta-tags {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 12.5px;
      color: var(--ink-3);
    }

    .meta-tags strong { color: var(--ink); }

    .tax-tag {
      padding: 2px 8px;
      border-radius: var(--radius-full);
      background: var(--violet-soft);
      color: var(--violet);
      font-size: 11px;
      font-weight: 700;
    }

    .donate-cta {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 7px 14px;
      border-radius: var(--radius-full);
      background: var(--accent);
      color: var(--on-accent);
      font-size: 13px;
      font-weight: 600;
      transition: gap 0.35s var(--ease-expo);
    }

    .campaign-card:hover .donate-cta { gap: 10px; }
  `]
})
export class CampaignCardComponent {
  @Input({ required: true }) campaign!: Campaign;

  get trustScore(): number {
    return this.campaign.ai_trust_score ?? this.campaign.authenticity_score ?? 0;
  }

  get shortDescription(): string {
    const desc = this.campaign.short_description || this.campaign.subtitle || this.campaign.story || '';
    return desc.length > 110 ? desc.slice(0, 110) + '…' : desc;
  }

  get progress(): number {
    if (!this.campaign.goal_amount) return 0;
    return Math.min(100, Math.round((this.campaign.current_amount / this.campaign.goal_amount) * 100));
  }

  formatINR(amount: number): string {
    if (!amount) return '0';
    if (amount >= 10_000_000) return (amount / 10_000_000).toFixed(1) + 'Cr';
    if (amount >= 100_000) return (amount / 100_000).toFixed(1) + 'L';
    if (amount >= 1000) return (amount / 1000).toFixed(1) + 'K';
    return amount.toString();
  }
}
