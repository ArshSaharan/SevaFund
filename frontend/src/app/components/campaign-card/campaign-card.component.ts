import { Component, Input } from '@angular/core';
import { CommonModule, CurrencyPipe } from '@angular/common';
import { RouterModule } from '@angular/router';
import { Campaign } from '../../models/campaign.model';

@Component({
  selector: 'app-campaign-card',
  standalone: true,
  imports: [CommonModule, RouterModule, CurrencyPipe],
  template: `
    <article class="campaign-card card" [routerLink]="['/campaigns', campaign.id]">
      <!-- Cover Image Wrap -->
      <div class="card-image-wrap">
        <img
          [src]="campaign.cover_image_url || '/assets/default-campaign.jpg'"
          [alt]="campaign.title"
          class="card-img"
          loading="lazy"
          onerror="this.src='/assets/default-campaign.jpg'"
        />
        <div class="image-gradient-overlay"></div>

        <!-- Badges on Image -->
        <div class="image-top-badges">
          <span class="category-pill">{{ campaign.category }}</span>

          <span
            class="trust-score-badge"
            [class.trust-high]="trustScore >= 80"
            [class.trust-med]="trustScore >= 50 && trustScore < 80"
            [class.trust-low]="trustScore < 50"
            *ngIf="trustScore > 0"
          >
            <svg class="trust-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
            </svg>
            <span>{{ trustScore }}% AI Trust</span>
          </span>
        </div>
      </div>

      <!-- Card Body Content -->
      <div class="card-body">
        <!-- Title & Description -->
        <h3 class="campaign-title" [title]="campaign.title">{{ campaign.title }}</h3>
        <p class="campaign-desc">{{ shortDescription }}</p>

        <!-- Hospital / Location Tag if available -->
        <div class="hospital-line" *ngIf="campaign.hospital_name">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
          </svg>
          <span class="hospital-name">{{ campaign.hospital_name }}</span>
        </div>

        <!-- Progress Metrics -->
        <div class="progress-section">
          <div class="progress-bar-track">
            <div class="progress-bar-fill" [style.width.%]="getProgressPercent()"></div>
          </div>

          <div class="funding-metrics">
            <div class="raised-col">
              <span class="raised-amount">₹{{ formatINR(campaign.current_amount) }}</span>
              <span class="raised-label">raised of ₹{{ formatINR(campaign.goal_amount) }}</span>
            </div>
            <div class="percentage-col">
              <span class="percent-num">{{ getProgressPercent() }}%</span>
            </div>
          </div>
        </div>

        <!-- Card Footer Meta & Action -->
        <div class="card-footer-meta">
          <div class="meta-tags">
            <span class="donor-badge" *ngIf="campaign.donor_count">
              <strong>{{ campaign.donor_count }}</strong> donors
            </span>
            <span class="tax-tag" *ngIf="campaign.is_80g_tax_exempt">
              80G Tax Saver
            </span>
          </div>

          <button class="btn btn-primary btn-sm donate-cta" (click)="onDonate($event)">
            Donate
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <line x1="5" y1="12" x2="19" y2="12"></line>
              <polyline points="12 5 19 12 12 19"></polyline>
            </svg>
          </button>
        </div>
      </div>
    </article>
  `,
  styles: [`
    .campaign-card {
      display: flex;
      flex-direction: column;
      height: 100%;
      cursor: pointer;
      position: relative;
      border-radius: var(--radius-xl);
      border: 1px solid var(--border);
      background: var(--surface);
      overflow: hidden;
      transition: transform 0.35s var(--ease-expo), box-shadow 0.35s var(--ease-expo), border-color 0.25s ease;
    }

    .campaign-card:hover {
      transform: translateY(-5px);
      box-shadow: 0 16px 36px -8px rgba(15, 23, 42, 0.12), 0 0 0 1px rgba(255, 107, 0, 0.25);
      border-color: rgba(255, 107, 0, 0.3);
    }

    /* Cover Image */
    .card-image-wrap {
      position: relative;
      width: 100%;
      height: 200px;
      overflow: hidden;
      background: var(--slate-100);
    }

    .card-img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      transition: transform 0.6s var(--ease-expo);
    }

    .campaign-card:hover .card-img {
      transform: scale(1.04);
    }

    .image-gradient-overlay {
      position: absolute;
      inset: 0;
      background: linear-gradient(180deg, rgba(0,0,0,0.3) 0%, transparent 40%, rgba(0,0,0,0.15) 100%);
      pointer-events: none;
    }

    .image-top-badges {
      position: absolute;
      top: 12px;
      left: 12px;
      right: 12px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      z-index: 2;
    }

    .category-pill {
      background: rgba(15, 23, 42, 0.75);
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
      color: #FFFFFF;
      font-size: 11px;
      font-weight: 700;
      padding: 4px 10px;
      border-radius: var(--radius-full);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    .trust-score-badge {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 4px 10px;
      border-radius: var(--radius-full);
      font-size: 11px;
      font-weight: 700;
      backdrop-filter: blur(8px);
      -webkit-backdrop-filter: blur(8px);
      box-shadow: 0 2px 6px rgba(0,0,0,0.15);
    }

    .trust-score-badge.trust-high {
      background: rgba(16, 185, 129, 0.9);
      color: #FFFFFF;
    }

    .trust-score-badge.trust-med {
      background: rgba(245, 158, 11, 0.9);
      color: #FFFFFF;
    }

    .trust-score-badge.trust-low {
      background: rgba(100, 116, 139, 0.85);
      color: #FFFFFF;
    }

    .trust-icon {
      flex-shrink: 0;
    }

    /* Body */
    .card-body {
      padding: 18px 20px 16px;
      display: flex;
      flex-direction: column;
      flex: 1;
    }

    .campaign-title {
      font-size: 16px;
      font-weight: 700;
      color: var(--slate-900);
      line-height: 1.35;
      margin-bottom: 6px;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }

    .campaign-desc {
      font-size: 13.5px;
      color: var(--slate-500);
      line-height: 1.5;
      margin-bottom: 12px;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
      flex: 1;
    }

    .hospital-line {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      color: var(--secondary);
      font-weight: 600;
      margin-bottom: 14px;
    }

    .hospital-name {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      max-width: 250px;
    }

    /* Progress */
    .progress-section {
      margin-top: auto;
      padding-top: 10px;
    }

    .progress-bar-track {
      width: 100%;
      height: 6px;
      background: var(--slate-200);
      border-radius: var(--radius-full);
      overflow: hidden;
      margin-bottom: 8px;
    }

    .progress-bar-fill {
      height: 100%;
      background: linear-gradient(90deg, #FF6B00 0%, #FFA048 100%);
      border-radius: var(--radius-full);
      transition: width 0.8s var(--ease-expo);
      max-width: 100%;
    }

    .funding-metrics {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
    }

    .raised-col {
      display: flex;
      flex-direction: column;
    }

    .raised-amount {
      font-family: var(--font-heading);
      font-size: 16px;
      font-weight: 800;
      color: var(--slate-900);
      letter-spacing: -0.01em;
    }

    .raised-label {
      font-size: 11.5px;
      color: var(--slate-400);
    }

    .percentage-col {
      text-align: right;
    }

    .percent-num {
      font-family: var(--font-heading);
      font-size: 14px;
      font-weight: 700;
      color: var(--primary);
    }

    /* Footer Meta */
    .card-footer-meta {
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-top: 1px solid var(--border-light);
      margin-top: 14px;
      padding-top: 12px;
      gap: 8px;
    }

    .meta-tags {
      display: flex;
      align-items: center;
      gap: 6px;
      flex-wrap: wrap;
    }

    .donor-badge {
      font-size: 11.5px;
      color: var(--slate-500);
    }

    .tax-tag {
      font-size: 10.5px;
      font-weight: 700;
      color: #7C3AED;
      background: #F3E8FF;
      padding: 2px 6px;
      border-radius: var(--radius-sm);
    }

    .donate-cta {
      padding: 6px 14px;
      font-size: 12.5px;
      border-radius: var(--radius-md);
    }
  `]
})
export class CampaignCardComponent {
  @Input() campaign!: Campaign;

  get trustScore(): number {
    return this.campaign.ai_trust_score ?? this.campaign.authenticity_score ?? 0;
  }

  get shortDescription(): string {
    const desc = this.campaign.short_description || this.campaign.subtitle || this.campaign.story || '';
    return desc.length > 95 ? desc.slice(0, 95) + '…' : desc;
  }

  getProgressPercent(): number {
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

  onDonate(event: Event): void {
    event.stopPropagation();
  }
}
