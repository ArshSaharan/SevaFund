import { Component, Input } from '@angular/core';
import { CommonModule, CurrencyPipe } from '@angular/common';
import { RouterModule } from '@angular/router';
import { Campaign } from '../../models/campaign.model';

@Component({
  selector: 'app-campaign-card',
  standalone: true,
  imports: [CommonModule, RouterModule, CurrencyPipe],
  template: `
    <div class="card campaign-card" [routerLink]="['/campaigns', campaign.id]">
      <!-- Cover Image -->
      <div class="card-image">
        <img
          [src]="campaign.cover_image_url || '/assets/default-campaign.jpg'"
          [alt]="campaign.title"
          onerror="this.src='/assets/default-campaign.jpg'"
        />
        <span class="badge badge-primary category-badge">{{ campaign.category }}</span>
        <span
          class="trust-badge"
          [class.trust-verified]="trustScore >= 80"
          [class.trust-review]="trustScore >= 50 && trustScore < 80"
          [class.trust-pending]="trustScore < 50"
          *ngIf="trustScore > 0"
        >
          {{ getTrustIcon() }} {{ getTrustLabel() }}
        </span>
      </div>

      <!-- Card Content -->
      <div class="card-body">
        <h3 class="campaign-title">{{ campaign.title }}</h3>
        <p class="campaign-desc">{{ shortDescription }}</p>

        <!-- Progress Bar -->
        <div class="progress-section">
          <div class="progress-bar-wrap">
            <div class="progress-bar" [style.width.%]="getProgressPercent()"></div>
          </div>
          <div class="progress-stats">
            <span class="raised">₹{{ formatINR(campaign.current_amount) }} raised</span>
            <span class="percent">{{ getProgressPercent() }}%</span>
          </div>
          <div class="goal-line">
            of ₹{{ formatINR(campaign.goal_amount) }} goal
            <span class="donor-count">· {{ campaign.donor_count || 0 }} donors</span>
          </div>
        </div>

        <!-- Hospital Tag -->
        <div class="hospital-tag" *ngIf="campaign.hospital_name">
          🏥 {{ campaign.hospital_name }}
        </div>

        <!-- 80G Badge -->
        <div class="tax-badge" *ngIf="campaign.is_80g_tax_exempt">
          📄 80G Tax Exemption Available
        </div>

        <!-- Donate Button -->
        <button class="btn btn-primary btn-full" (click)="onDonate($event)">
          Donate Now
        </button>
      </div>
    </div>
  `,
  styles: [`
    .campaign-card {
      cursor: pointer;
      transition: transform 0.2s ease, box-shadow 0.2s ease;
      height: 100%;
      display: flex;
      flex-direction: column;
    }
    .campaign-card:hover {
      transform: translateY(-4px);
      box-shadow: 0 12px 40px rgba(0,0,0,0.15);
    }
    .card-image {
      position: relative;
      width: 100%;
      height: 200px;
      overflow: hidden;
      border-radius: var(--radius-lg) var(--radius-lg) 0 0;
    }
    .card-image img {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
    .category-badge {
      position: absolute;
      top: 12px;
      left: 12px;
      text-transform: uppercase;
      font-size: 0.7rem;
      letter-spacing: 0.05em;
    }
    .trust-badge {
      position: absolute;
      top: 12px;
      right: 12px;
      padding: 4px 10px;
      border-radius: 20px;
      font-size: 0.72rem;
      font-weight: 600;
    }
    .trust-verified { background: rgba(0,168,107,0.9); color: #fff; }
    .trust-review   { background: rgba(255,165,0,0.9);  color: #fff; }
    .trust-pending  { background: rgba(150,150,150,0.85); color: #fff; }

    .card-body {
      padding: var(--space-4);
      display: flex;
      flex-direction: column;
      flex: 1;
      gap: var(--space-2);
    }
    .campaign-title {
      font-size: 1.05rem;
      font-weight: 700;
      color: var(--color-text-primary);
      line-height: 1.3;
      margin: 0;
    }
    .campaign-desc {
      font-size: 0.88rem;
      color: var(--color-text-secondary);
      line-height: 1.5;
      margin: 0;
      flex: 1;
    }
    .progress-section { margin-top: var(--space-2); }
    .progress-bar-wrap {
      background: #e5e7eb;
      border-radius: 8px;
      height: 8px;
      overflow: hidden;
    }
    .progress-bar {
      height: 100%;
      background: linear-gradient(90deg, var(--color-primary), #ff8c42);
      border-radius: 8px;
      max-width: 100%;
      transition: width 0.5s ease;
    }
    .progress-stats {
      display: flex;
      justify-content: space-between;
      margin-top: 6px;
    }
    .raised { font-weight: 700; font-size: 0.9rem; color: var(--color-primary); }
    .percent { font-size: 0.85rem; color: var(--color-text-secondary); }
    .goal-line { font-size: 0.78rem; color: var(--color-text-secondary); margin-top: 2px; }
    .donor-count { color: var(--color-text-muted, #9ca3af); }

    .hospital-tag {
      font-size: 0.78rem;
      color: var(--color-secondary);
      font-weight: 500;
    }
    .tax-badge {
      font-size: 0.75rem;
      color: #7c3aed;
      font-weight: 500;
    }
    .btn-full { width: 100%; margin-top: auto; }
  `]
})
export class CampaignCardComponent {
  @Input() campaign!: Campaign;

  get trustScore(): number {
    return this.campaign.ai_trust_score ?? this.campaign.authenticity_score ?? 0;
  }

  get shortDescription(): string {
    const desc = this.campaign.short_description || this.campaign.subtitle || this.campaign.story || '';
    return desc.length > 100 ? desc.slice(0, 100) + '…' : desc;
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

  getTrustIcon(): string {
    const score = this.trustScore;
    if (score >= 80) return '🛡️';
    if (score >= 50) return '⚠️';
    return '❓';
  }

  getTrustLabel(): string {
    const score = this.trustScore;
    if (score >= 80) return 'AI Verified';
    if (score >= 50) return 'Under Review';
    return 'Pending';
  }

  onDonate(event: Event): void {
    event.stopPropagation();
  }
}
