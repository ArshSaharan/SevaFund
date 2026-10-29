import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { CampaignService } from '../../services/campaign.service';
import { Campaign } from '../../models/campaign.model';
import { CampaignCardComponent } from '../../components/campaign-card/campaign-card.component';

const CATEGORIES = ['ALL', 'MEDICAL', 'EMERGENCY', 'EDUCATION', 'COMMUNITY', 'MEMORIAL', 'ANIMALS'];

@Component({
  selector: 'app-campaign-list',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule, CampaignCardComponent],
  template: `
    <!-- Hero -->
    <section class="hero">
      <div class="hero-content container">
        <div class="hero-badge">🇮🇳 India's AI-Powered Crowdfunding</div>
        <h1 class="hero-title">Every Rupee Counts.<br>Every Story Matters.</h1>
        <p class="hero-subtitle">
          SevaFund India uses AI to verify every campaign so your donation reaches genuine causes.
          UPI • Netbanking • 0% platform fee • 80G Tax Exemption
        </p>
        <div class="hero-actions">
          <a routerLink="/create" class="btn btn-primary btn-lg">🚀 Start a Fundraiser</a>
          <a href="#campaigns" class="btn btn-outline btn-lg">Browse Campaigns</a>
        </div>
        <div class="hero-stats">
          <div class="stat"><span class="stat-num">₹2.4Cr+</span><span class="stat-lbl">Raised</span></div>
          <div class="stat"><span class="stat-num">1,200+</span><span class="stat-lbl">Campaigns</span></div>
          <div class="stat"><span class="stat-num">98%</span><span class="stat-lbl">AI Verified</span></div>
          <div class="stat"><span class="stat-num">0%</span><span class="stat-lbl">Platform Fee</span></div>
        </div>
      </div>
    </section>

    <!-- Trust Bar -->
    <div class="trust-bar">
      <div class="container trust-bar-inner">
        <span>🔒 Secure Payments</span>
        <span>🛡️ AI Fraud Detection</span>
        <span>📄 Section 80G Tax Benefits</span>
        <span>🏥 Direct Hospital Transfer</span>
        <span>💳 UPI • Netbanking • RuPay</span>
      </div>
    </div>

    <!-- Campaign Section -->
    <section class="campaigns-section container" id="campaigns">
      <!-- Search + Filters -->
      <div class="filters-bar">
        <div class="search-wrap">
          <span class="search-icon">🔍</span>
          <input
            type="text"
            class="input search-input"
            placeholder="Search campaigns..."
            [(ngModel)]="searchQuery"
            (input)="onSearch()"
          />
        </div>
        <div class="category-chips">
          <button
            *ngFor="let cat of categories"
            class="chip"
            [class.active]="selectedCategory === cat"
            (click)="selectCategory(cat)"
          >{{ cat }}</button>
        </div>
        <select class="input sort-select" [(ngModel)]="sortBy" (change)="loadCampaigns()">
          <option value="recent">Most Recent</option>
          <option value="trending">Trending</option>
          <option value="ending_soon">Ending Soon</option>
          <option value="most_funded">Most Funded</option>
        </select>
      </div>

      <!-- Loading -->
      <div class="loading-grid" *ngIf="loading()">
        <div class="skeleton-card" *ngFor="let s of [1,2,3,4,5,6]"></div>
      </div>

      <!-- Empty -->
      <div class="empty-state" *ngIf="!loading() && campaigns().length === 0">
        <div class="empty-icon">🔍</div>
        <h3>No campaigns found</h3>
        <p>Try a different search or category</p>
      </div>

      <!-- Grid -->
      <div class="campaigns-grid" *ngIf="!loading() && campaigns().length > 0">
        <app-campaign-card
          *ngFor="let c of campaigns()"
          [campaign]="c"
        ></app-campaign-card>
      </div>

      <!-- Pagination -->
      <div class="pagination" *ngIf="totalPages > 1">
        <button class="btn btn-outline" [disabled]="currentPage === 1" (click)="goToPage(currentPage - 1)">← Prev</button>
        <span class="page-info">Page {{ currentPage }} of {{ totalPages }}</span>
        <button class="btn btn-outline" [disabled]="currentPage === totalPages" (click)="goToPage(currentPage + 1)">Next →</button>
      </div>
    </section>

    <!-- How It Works -->
    <section class="how-section">
      <div class="container">
        <h2 class="section-title">How SevaFund Works</h2>
        <div class="steps-grid">
          <div class="step">
            <div class="step-icon">✍️</div>
            <h3>Share Your Story</h3>
            <p>Our AI Story Assistant helps you write a compelling fundraiser in minutes</p>
          </div>
          <div class="step">
            <div class="step-icon">🤖</div>
            <h3>AI Verification</h3>
            <p>Advanced AI cross-checks hospital records, costs, and documents for authenticity</p>
          </div>
          <div class="step">
            <div class="step-icon">💸</div>
            <h3>Collect Donations</h3>
            <p>Accept UPI, Netbanking, and cards. 0% platform fee — 100% goes to the cause</p>
          </div>
          <div class="step">
            <div class="step-icon">🏥</div>
            <h3>Direct to Hospital</h3>
            <p>Funds transferred directly to hospital accounts via NEFT/IMPS for medical campaigns</p>
          </div>
        </div>
      </div>
    </section>
  `,
  styles: [`
    /* Hero */
    .hero {
      background: linear-gradient(135deg, #fff7ed 0%, #fef3c7 50%, #ecfdf5 100%);
      padding: 80px 0 60px;
      border-bottom: 1px solid #f3f4f6;
    }
    .hero-content { text-align: center; max-width: 800px; margin: 0 auto; }
    .hero-badge {
      display: inline-block;
      background: var(--color-primary);
      color: #fff;
      padding: 6px 18px;
      border-radius: 20px;
      font-size: 0.85rem;
      font-weight: 600;
      margin-bottom: var(--space-4);
    }
    .hero-title {
      font-size: clamp(2rem, 5vw, 3.2rem);
      font-weight: 800;
      color: var(--color-text-primary);
      line-height: 1.15;
      margin-bottom: var(--space-4);
    }
    .hero-subtitle {
      font-size: 1.1rem;
      color: var(--color-text-secondary);
      margin-bottom: var(--space-6);
      line-height: 1.7;
    }
    .hero-actions { display: flex; gap: var(--space-3); justify-content: center; flex-wrap: wrap; margin-bottom: var(--space-8); }
    .btn-lg { padding: 14px 32px; font-size: 1rem; }
    .btn-outline {
      border: 2px solid var(--color-primary);
      color: var(--color-primary);
      background: transparent;
      border-radius: var(--radius-md);
      padding: 12px 28px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
    }
    .btn-outline:hover { background: var(--color-primary); color: #fff; }
    .hero-stats {
      display: flex;
      gap: var(--space-8);
      justify-content: center;
      flex-wrap: wrap;
    }
    .stat { display: flex; flex-direction: column; align-items: center; }
    .stat-num { font-size: 1.6rem; font-weight: 800; color: var(--color-primary); }
    .stat-lbl { font-size: 0.8rem; color: var(--color-text-secondary); margin-top: 2px; }

    /* Trust Bar */
    .trust-bar {
      background: var(--color-secondary);
      color: #fff;
      padding: 12px 0;
    }
    .trust-bar-inner {
      display: flex;
      gap: var(--space-6);
      justify-content: center;
      flex-wrap: wrap;
      font-size: 0.85rem;
      font-weight: 500;
    }

    /* Campaigns Section */
    .campaigns-section { padding: var(--space-10) var(--space-4); }
    .filters-bar {
      display: flex;
      gap: var(--space-4);
      align-items: center;
      flex-wrap: wrap;
      margin-bottom: var(--space-6);
    }
    .search-wrap {
      position: relative;
      flex: 1;
      min-width: 220px;
    }
    .search-icon {
      position: absolute;
      left: 12px;
      top: 50%;
      transform: translateY(-50%);
    }
    .search-input { padding-left: 38px; }
    .category-chips { display: flex; gap: var(--space-2); flex-wrap: wrap; }
    .chip {
      padding: 6px 14px;
      border-radius: 20px;
      border: 1.5px solid #d1d5db;
      background: #fff;
      font-size: 0.8rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.15s;
      color: var(--color-text-secondary);
    }
    .chip:hover, .chip.active {
      background: var(--color-primary);
      border-color: var(--color-primary);
      color: #fff;
    }
    .sort-select {
      min-width: 160px;
      padding: 10px 12px;
    }
    .campaigns-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: var(--space-6);
    }
    /* Skeleton */
    .loading-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: var(--space-6); }
    .skeleton-card {
      height: 380px;
      border-radius: var(--radius-lg);
      background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
      background-size: 200% 100%;
      animation: shimmer 1.5s infinite;
    }
    @keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }
    /* Empty */
    .empty-state { text-align: center; padding: 60px 0; color: var(--color-text-secondary); }
    .empty-icon { font-size: 3rem; margin-bottom: var(--space-4); }
    /* Pagination */
    .pagination { display: flex; align-items: center; gap: var(--space-4); justify-content: center; margin-top: var(--space-8); }
    .page-info { color: var(--color-text-secondary); font-size: 0.9rem; }

    /* How It Works */
    .how-section {
      background: #f9fafb;
      padding: var(--space-10) var(--space-4);
      border-top: 1px solid #e5e7eb;
    }
    .section-title { text-align: center; font-size: 1.8rem; font-weight: 800; margin-bottom: var(--space-8); }
    .steps-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: var(--space-6);
    }
    .step {
      text-align: center;
      padding: var(--space-6);
      background: #fff;
      border-radius: var(--radius-lg);
      box-shadow: 0 2px 12px rgba(0,0,0,0.06);
    }
    .step-icon { font-size: 2.5rem; margin-bottom: var(--space-3); }
    .step h3 { font-size: 1.1rem; font-weight: 700; margin-bottom: var(--space-2); }
    .step p { font-size: 0.88rem; color: var(--color-text-secondary); line-height: 1.6; margin: 0; }
  `]
})
export class CampaignListComponent implements OnInit {
  private campaignService = inject(CampaignService);

  campaigns = signal<Campaign[]>([]);
  loading = signal(true);

  categories = CATEGORIES;
  selectedCategory = 'ALL';
  searchQuery = '';
  sortBy = 'recent';
  currentPage = 1;
  totalPages = 1;
  pageSize = 9;

  ngOnInit() { this.loadCampaigns(); }

  loadCampaigns() {
    this.loading.set(true);
    const category = this.selectedCategory === 'ALL' ? undefined : this.selectedCategory;
    this.campaignService.getCampaigns(this.currentPage, this.pageSize, category, this.searchQuery || undefined)
      .subscribe({
        next: (res) => {
          this.campaigns.set(res.campaigns || res.items || []);
          this.totalPages = Math.ceil((res.total || 0) / this.pageSize) || 1;
          this.loading.set(false);
        },
        error: () => {
          this.loading.set(false);
        }
      });
  }

  selectCategory(cat: string) {
    this.selectedCategory = cat;
    this.currentPage = 1;
    this.loadCampaigns();
  }

  onSearch() {
    this.currentPage = 1;
    this.loadCampaigns();
  }

  goToPage(page: number) {
    this.currentPage = page;
    this.loadCampaigns();
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }
}
