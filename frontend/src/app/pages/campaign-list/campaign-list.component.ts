import {
  Component,
  OnInit,
  AfterViewInit,
  OnDestroy,
  inject,
  signal,
  ElementRef,
  NgZone
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import gsap from 'gsap';
import { ScrollTrigger } from 'gsap/ScrollTrigger';
import { CampaignService } from '../../services/campaign.service';
import { SmoothScrollService } from '../../services/smooth-scroll.service';
import { Campaign } from '../../models/campaign.model';
import { CampaignCardComponent } from '../../components/campaign-card/campaign-card.component';
import { ExpoGlassesComponent } from '../../components/expo-glasses/expo-glasses.component';

const CATEGORIES = ['ALL', 'MEDICAL', 'EMERGENCY', 'EDUCATION', 'COMMUNITY', 'MEMORIAL', 'ANIMALS'];

@Component({
  selector: 'app-campaign-list',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule, CampaignCardComponent, ExpoGlassesComponent],
  template: `
    <!-- Hero Section -->
    <section class="hero-section" #heroSection>
      <div class="container hero-container">
        <!-- Left: Copy & Actions -->
        <div class="hero-content">
          <div class="hero-badge expo-glass-pill">
            <span class="badge-dot"></span>
            <span>Institutional AI Verification · 0% Platform Fee</span>
          </div>

          <h1 class="hero-title">
            Every Rupee Counts.<br>
            <span class="gradient-text">Every Story Verified.</span>
          </h1>

          <p class="hero-subtitle">
            SevaFund India pairs deep medical AI verification with complete financial transparency.
            Inspect hospital bills, authenticate treatments, and ensure 100% of your donation reaches patients.
          </p>

          <div class="hero-actions">
            <a routerLink="/create" class="btn btn-primary btn-lg start-fundraiser-btn">
              <span>Start a Fundraiser</span>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
                <line x1="5" y1="12" x2="19" y2="12"></line>
                <polyline points="12 5 19 12 12 19"></polyline>
              </svg>
            </a>
            <a href="#campaigns" class="btn btn-outline btn-lg" (click)="onBrowseCampaigns($event)">
              Explore Verified Causes
            </a>
          </div>

          <!-- Hero Metrics Bar -->
          <div class="hero-metrics expo-glass">
            <div class="metric-item">
              <span class="metric-num">₹2.4Cr+</span>
              <span class="metric-lbl">Directly Raised</span>
            </div>
            <div class="metric-divider"></div>
            <div class="metric-item">
              <span class="metric-num">1,200+</span>
              <span class="metric-lbl">Patients Supported</span>
            </div>
            <div class="metric-divider"></div>
            <div class="metric-item">
              <span class="metric-num">98.4%</span>
              <span class="metric-lbl">AI Verification Rate</span>
            </div>
            <div class="metric-divider"></div>
            <div class="metric-item">
              <span class="metric-num">0%</span>
              <span class="metric-lbl">Platform Markup</span>
            </div>
          </div>
        </div>

        <!-- Right: 3D Interactive Expo Glasses -->
        <div class="hero-interactive-col">
          <app-expo-glasses></app-expo-glasses>
        </div>
      </div>
    </section>

    <!-- Trust & Verification Bar -->
    <div class="trust-bar" #trustBar>
      <div class="container trust-bar-inner">
        <div class="trust-item">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
            <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
          </svg>
          <span>End-to-End Escrow & UPI</span>
        </div>
        <div class="trust-item">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
          </svg>
          <span>Real-Time Fraud Detection</span>
        </div>
        <div class="trust-item">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
            <polyline points="14 2 14 8 20 8"></polyline>
          </svg>
          <span>Section 80G Tax Certificates</span>
        </div>
        <div class="trust-item">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
          </svg>
          <span>Direct Hospital Billing NEFT</span>
        </div>
      </div>
    </div>

    <!-- Campaigns Section -->
    <section class="campaigns-section container" id="campaigns" #campaignsSection>
      <div class="section-header">
        <div>
          <h2 class="section-title">Verified Causes Requiring Urgent Support</h2>
          <p class="section-subtitle">Browse transparent fundraisers audited by our automated medical verification network.</p>
        </div>
      </div>

      <!-- Filters & Search Toolbar -->
      <div class="filters-toolbar">
        <div class="search-wrap">
          <svg class="search-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
          </svg>
          <input
            type="text"
            class="input search-input"
            placeholder="Search by cause, hospital, or city…"
            [(ngModel)]="searchQuery"
            (input)="onSearch()"
          />
        </div>

        <div class="category-pills">
          <button
            *ngFor="let cat of categories"
            class="cat-chip"
            [class.active]="selectedCategory === cat"
            (click)="selectCategory(cat)"
          >
            {{ cat }}
          </button>
        </div>

        <div class="sort-wrap">
          <select class="input sort-select" [(ngModel)]="sortBy" (change)="loadCampaigns()">
            <option value="recent">Most Recent</option>
            <option value="trending">Trending Now</option>
            <option value="ending_soon">Ending Soonest</option>
            <option value="most_funded">Most Funded</option>
          </select>
        </div>
      </div>

      <!-- Loading Skeleton Grid -->
      <div class="loading-grid" *ngIf="loading()">
        <div class="skeleton-card" *ngFor="let s of [1,2,3,4,5,6]"></div>
      </div>

      <!-- Empty State -->
      <div class="empty-state card" *ngIf="!loading() && campaigns().length === 0">
        <div class="empty-icon-wrap">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
          </svg>
        </div>
        <h3>No verified campaigns found</h3>
        <p>Try refining your search keyword or selecting a different cause category.</p>
        <button class="btn btn-outline btn-sm mt-3" (click)="selectedCategory = 'ALL'; searchQuery = ''; loadCampaigns()">
          Reset Filters
        </button>
      </div>

      <!-- Campaign Grid -->
      <div class="campaigns-grid" #campaignsGrid *ngIf="!loading() && campaigns().length > 0">
        <app-campaign-card
          *ngFor="let c of campaigns()"
          [campaign]="c"
          class="campaign-grid-item"
        ></app-campaign-card>
      </div>

      <!-- Pagination -->
      <div class="pagination-bar" *ngIf="totalPages > 1">
        <button class="btn btn-outline btn-sm" [disabled]="currentPage === 1" (click)="goToPage(currentPage - 1)">
          Previous
        </button>
        <span class="page-indicator">Page {{ currentPage }} of {{ totalPages }}</span>
        <button class="btn btn-outline btn-sm" [disabled]="currentPage === totalPages" (click)="goToPage(currentPage + 1)">
          Next
        </button>
      </div>
    </section>

    <!-- How SevaFund Works -->
    <section class="how-it-works-section" #howSection>
      <div class="container">
        <div class="how-header">
          <span class="sub-heading">Verification Architecture</span>
          <h2 class="section-title">How Every Rupee Is Accounted For</h2>
          <p class="section-subtitle">
            An automated three-tier verification protocol guarantees that legitimate patients receive financial relief without leakage.
          </p>
        </div>

        <div class="steps-grid">
          <!-- Step 1 -->
          <div class="step-card card">
            <div class="step-number">01</div>
            <div class="step-icon-wrap">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 20h9"></path>
                <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path>
              </svg>
            </div>
            <h3>AI Story Assistant</h3>
            <p>Organizers input medical details and patient records. Our generative AI crafts a compelling narrative with medical accuracy.</p>
          </div>

          <!-- Step 2 -->
          <div class="step-card card">
            <div class="step-number">02</div>
            <div class="step-icon-wrap">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
              </svg>
            </div>
            <h3>Institutional Benchmark Audit</h3>
            <p>Our algorithms compare requested amounts against typical Indian hospital treatment costs to flag inflated or fraudulent figures.</p>
          </div>

          <!-- Step 3 -->
          <div class="step-card card">
            <div class="step-number">03</div>
            <div class="step-icon-wrap">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="2" y="5" width="20" height="14" rx="2"></rect>
                <line x1="2" y1="10" x2="22" y2="10"></line>
              </svg>
            </div>
            <h3>Instant UPI & 0% Fee</h3>
            <p>Donors contribute via UPI, Cards, or Netbanking. 100% of the donation goes toward the cause with instant digital 80G tax receipts.</p>
          </div>

          <!-- Step 4 -->
          <div class="step-card card">
            <div class="step-number">04</div>
            <div class="step-icon-wrap">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"></path>
                <polyline points="9 22 9 12 15 12 15 22"></polyline>
              </svg>
            </div>
            <h3>Direct Hospital Settlement</h3>
            <p>For verified medical procedures, funds are settled directly into the hospital's registered trust account via automated NEFT/RTGS.</p>
          </div>
        </div>
      </div>
    </section>
  `,
  styles: [`
    /* Hero */
    .hero-section {
      position: relative;
      background: radial-gradient(circle at 85% 20%, rgba(255, 107, 0, 0.08) 0%, transparent 55%),
                  radial-gradient(circle at 10% 80%, rgba(0, 168, 107, 0.06) 0%, transparent 45%),
                  linear-gradient(180deg, #FFFFFF 0%, var(--slate-50) 100%);
      padding: 60px 0 50px;
      border-bottom: 1px solid var(--border);
      overflow: hidden;
    }

    .hero-container {
      display: grid;
      grid-template-columns: 1.15fr 0.85fr;
      align-items: center;
      gap: 36px;
    }

    .hero-content {
      text-align: left;
    }

    .hero-badge {
      margin-bottom: 18px;
      gap: 8px;
    }

    .badge-dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background: var(--secondary);
      box-shadow: 0 0 8px var(--secondary);
    }

    .hero-title {
      font-size: clamp(2.3rem, 4.4vw, 3.6rem);
      font-weight: 800;
      color: var(--slate-900);
      line-height: 1.12;
      margin-bottom: 16px;
      letter-spacing: -0.03em;
    }

    .gradient-text {
      background: linear-gradient(135deg, #FF6B00 0%, #00A86B 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }

    .hero-subtitle {
      font-size: 16px;
      color: var(--slate-600);
      line-height: 1.65;
      margin-bottom: 28px;
      max-width: 560px;
    }

    .hero-actions {
      display: flex;
      align-items: center;
      gap: 14px;
      flex-wrap: wrap;
      margin-bottom: 36px;
    }

    .start-fundraiser-btn {
      gap: 10px;
    }

    /* Hero Metrics Bar */
    .hero-metrics {
      display: inline-flex;
      align-items: center;
      gap: 20px;
      padding: 14px 24px;
      border-radius: var(--radius-xl);
    }

    .metric-item {
      display: flex;
      flex-direction: column;
    }

    .metric-num {
      font-family: var(--font-heading);
      font-size: 19px;
      font-weight: 800;
      color: var(--slate-900);
      line-height: 1.1;
      letter-spacing: -0.02em;
    }

    .metric-lbl {
      font-size: 11px;
      font-weight: 600;
      color: var(--slate-500);
      margin-top: 2px;
      text-transform: uppercase;
      letter-spacing: 0.04em;
    }

    .metric-divider {
      width: 1px;
      height: 28px;
      background: var(--slate-200);
    }

    .hero-interactive-col {
      display: flex;
      justify-content: center;
      align-items: center;
      width: 100%;
    }

    /* Trust Bar */
    .trust-bar {
      background: var(--slate-900);
      color: #FFFFFF;
      padding: 14px 0;
      box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06);
    }

    .trust-bar-inner {
      display: flex;
      align-items: center;
      justify-content: space-around;
      flex-wrap: wrap;
      gap: 16px;
    }

    .trust-item {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
      font-weight: 600;
      color: var(--slate-300);
    }

    .trust-item svg {
      color: var(--secondary);
    }

    /* Campaigns Section */
    .campaigns-section {
      padding: 60px var(--space-5);
    }

    .section-header {
      margin-bottom: 24px;
    }

    .section-title {
      font-size: clamp(1.8rem, 3vw, 2.3rem);
      font-weight: 800;
      color: var(--slate-900);
      letter-spacing: -0.02em;
      margin-bottom: 6px;
    }

    .section-subtitle {
      font-size: 15px;
      color: var(--slate-500);
      max-width: 680px;
    }

    /* Filters Toolbar */
    .filters-toolbar {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 30px;
      flex-wrap: wrap;
      background: var(--surface);
      padding: 12px 16px;
      border-radius: var(--radius-xl);
      border: 1px solid var(--border);
      box-shadow: var(--shadow-xs);
    }

    .search-wrap {
      position: relative;
      flex: 1;
      min-width: 240px;
    }

    .search-icon {
      position: absolute;
      left: 12px;
      top: 50%;
      transform: translateY(-50%);
      color: var(--slate-400);
    }

    .search-input {
      padding-left: 36px;
      height: 40px;
      font-size: 13.5px;
    }

    .category-pills {
      display: flex;
      gap: 6px;
      overflow-x: auto;
      padding-bottom: 2px;
    }

    .cat-chip {
      padding: 6px 14px;
      border-radius: var(--radius-full);
      border: 1px solid var(--border);
      background: var(--slate-50);
      color: var(--slate-600);
      font-size: 12.5px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.15s ease;
      white-space: nowrap;
    }

    .cat-chip:hover {
      background: var(--slate-100);
      color: var(--slate-900);
    }

    .cat-chip.active {
      background: var(--primary);
      border-color: var(--primary);
      color: #FFFFFF;
      box-shadow: 0 2px 8px rgba(255, 107, 0, 0.25);
    }

    .sort-wrap {
      min-width: 150px;
    }

    .sort-select {
      height: 40px;
      font-size: 13px;
    }

    /* Grid */
    .campaigns-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 24px;
    }

    /* Skeleton */
    .loading-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 24px;
    }

    .skeleton-card {
      height: 380px;
      border-radius: var(--radius-xl);
      background: linear-gradient(90deg, #F1F5F9 25%, #E2E8F0 50%, #F1F5F9 75%);
      background-size: 200% 100%;
      animation: shimmer 1.5s infinite;
    }

    /* Empty */
    .empty-state {
      text-align: center;
      padding: 60px 24px;
      max-width: 480px;
      margin: 40px auto;
    }

    .empty-icon-wrap {
      width: 56px;
      height: 56px;
      border-radius: 50%;
      background: var(--slate-100);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      color: var(--slate-400);
      margin-bottom: 16px;
    }

    .empty-state h3 {
      font-size: 18px;
      font-weight: 700;
      margin-bottom: 6px;
    }

    .empty-state p {
      font-size: 14px;
      color: var(--slate-500);
      line-height: 1.5;
    }

    /* Pagination */
    .pagination-bar {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 16px;
      margin-top: 48px;
    }

    .page-indicator {
      font-size: 13.5px;
      font-weight: 600;
      color: var(--slate-500);
    }

    /* How It Works */
    .how-it-works-section {
      background: var(--surface);
      border-top: 1px solid var(--border);
      padding: 80px 0 90px;
    }

    .how-header {
      text-align: center;
      max-width: 680px;
      margin: 0 auto 50px;
    }

    .sub-heading {
      font-size: 12px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--primary);
      margin-bottom: 8px;
      display: block;
    }

    .steps-grid {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 24px;
    }

    .step-card {
      padding: 28px 24px;
      position: relative;
      display: flex;
      flex-direction: column;
    }

    .step-number {
      font-family: var(--font-heading);
      font-size: 13px;
      font-weight: 800;
      color: var(--slate-400);
      margin-bottom: 16px;
    }

    .step-icon-wrap {
      width: 44px;
      height: 44px;
      border-radius: var(--radius-lg);
      background: var(--primary-light);
      color: var(--primary);
      display: flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 18px;
    }

    .step-card h3 {
      font-size: 17px;
      font-weight: 700;
      margin-bottom: 10px;
      color: var(--slate-900);
    }

    .step-card p {
      font-size: 13.5px;
      color: var(--slate-500);
      line-height: 1.6;
    }

    @media (max-width: 1024px) {
      .steps-grid {
        grid-template-columns: repeat(2, 1fr);
      }
      .hero-container {
        grid-template-columns: 1fr;
        text-align: center;
      }
      .hero-content {
        text-align: center;
      }
      .hero-subtitle {
        margin-left: auto;
        margin-right: auto;
      }
      .hero-actions {
        justify-content: center;
      }
      .hero-metrics {
        justify-content: center;
      }
    }

    @media (max-width: 640px) {
      .steps-grid {
        grid-template-columns: 1fr;
      }
      .hero-metrics {
        flex-direction: column;
        align-items: stretch;
      }
      .metric-divider {
        display: none;
      }
      .filters-toolbar {
        flex-direction: column;
        align-items: stretch;
      }
    }
  `]
})
export class CampaignListComponent implements OnInit, AfterViewInit, OnDestroy {
  private campaignService = inject(CampaignService);
  private smoothScroll = inject(SmoothScrollService);
  private ngZone = inject(NgZone);

  campaigns = signal<Campaign[]>([]);
  loading = signal(true);

  categories = CATEGORIES;
  selectedCategory = 'ALL';
  searchQuery = '';
  sortBy = 'recent';
  currentPage = 1;
  totalPages = 1;
  pageSize = 9;

  private scrollTriggers: ScrollTrigger[] = [];

  ngOnInit() {
    this.loadCampaigns();
  }

  ngAfterViewInit(): void {
    if (typeof window === 'undefined') return;

    this.ngZone.runOutsideAngular(() => {
      // Hero elements entrance stagger
      gsap.from('.hero-badge, .hero-title, .hero-subtitle, .hero-actions, .hero-metrics', {
        y: 30,
        opacity: 0,
        duration: 1.1,
        stagger: 0.1,
        ease: 'expo.out'
      });

      // Trust bar trigger
      const trustTrigger = ScrollTrigger.create({
        trigger: '.trust-bar',
        start: 'top 92%',
        onEnter: () => {
          gsap.from('.trust-item', {
            y: 16,
            opacity: 0,
            duration: 0.8,
            stagger: 0.08,
            ease: 'expo.out'
          });
        },
        once: true
      });
      this.scrollTriggers.push(trustTrigger);

      // How it works steps reveal
      const stepsTrigger = ScrollTrigger.create({
        trigger: '.how-it-works-section',
        start: 'top 85%',
        onEnter: () => {
          gsap.from('.step-card', {
            y: 35,
            opacity: 0,
            duration: 0.9,
            stagger: 0.12,
            ease: 'expo.out'
          });
        },
        once: true
      });
      this.scrollTriggers.push(stepsTrigger);
    });
  }

  loadCampaigns() {
    this.loading.set(true);
    const category = this.selectedCategory === 'ALL' ? undefined : this.selectedCategory;
    this.campaignService.getCampaigns(this.currentPage, this.pageSize, category, this.searchQuery || undefined)
      .subscribe({
        next: (res) => {
          this.campaigns.set(res.campaigns || res.items || []);
          this.totalPages = Math.ceil((res.total || 0) / this.pageSize) || 1;
          this.loading.set(false);

          setTimeout(() => {
            this.animateCards();
            this.smoothScroll.refresh();
          }, 60);
        },
        error: () => {
          this.loading.set(false);
        }
      });
  }

  private animateCards(): void {
    if (typeof window === 'undefined') return;
    this.ngZone.runOutsideAngular(() => {
      gsap.from('.campaign-grid-item', {
        y: 25,
        opacity: 0,
        duration: 0.75,
        stagger: 0.06,
        ease: 'expo.out'
      });
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

  onBrowseCampaigns(event: Event): void {
    event.preventDefault();
    this.smoothScroll.scrollTo('#campaigns', { offset: -60, duration: 1.2 });
  }

  goToPage(page: number) {
    this.currentPage = page;
    this.loadCampaigns();
    this.smoothScroll.scrollTo(0, { duration: 1.1 });
  }

  ngOnDestroy(): void {
    this.scrollTriggers.forEach(st => st.kill());
    this.scrollTriggers = [];
  }
}
