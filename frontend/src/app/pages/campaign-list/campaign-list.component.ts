import { Component, ElementRef, NgZone, OnDestroy, OnInit, ViewChild, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterModule } from '@angular/router';
import { Subject, Subscription, debounceTime, distinctUntilChanged } from 'rxjs';
import { CampaignService } from '../../services/campaign.service';
import { SmoothScrollService } from '../../services/smooth-scroll.service';
import { Campaign } from '../../models/campaign.model';
import { CampaignCardComponent } from '../../components/campaign-card/campaign-card.component';
import { NextChapterComponent } from '../../components/next-chapter/next-chapter.component';
import { MOTION, gsap, ScrollTrigger, isBrowser, prefersReducedMotion } from '../../animation';

type SortKey = 'trending' | 'newest' | 'most_funded';

const CATEGORIES: { value: string; label: string }[] = [
  { value: 'ALL', label: 'All causes' },
  { value: 'MEDICAL', label: 'Medical' },
  { value: 'EMERGENCY', label: 'Emergency' },
  { value: 'EDUCATION', label: 'Education' },
  { value: 'COMMUNITY', label: 'Community' },
  { value: 'MEMORIAL', label: 'Memorial' },
  { value: 'ANIMALS', label: 'Animals' },
];

/** Matches the backend's auto-approve threshold. */
const VERIFIED_SCORE = 80;

@Component({
  selector: 'app-campaign-list',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule, CampaignCardComponent, NextChapterComponent, ...MOTION],
  template: `
    <!-- Page header -->
    <section class="explore-hero">
      <div class="container">
        <p class="eyebrow" appReveal>Explore causes</p>
        <h1 class="display-lg explore-title" appSplit="words" [splitOnLoad]="true" [splitDelay]="0.1">
          Causes that are <em>live&nbsp;now.</em>
        </h1>
        <p class="lede" appReveal [revealDelay]="0.3">
          Every fundraiser carries an AI trust score built from cost benchmarks, specificity,
          red-flag screening and documents. Look for it before you give.
        </p>
      </div>
    </section>

    <section class="container explore-body" #results id="campaigns" aria-label="Fundraisers">
      <!-- Toolbar -->
      <div class="toolbar" appReveal [revealDelay]="0.4">
        <div class="search-wrap">
          <svg class="search-icon" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <circle cx="11" cy="11" r="8"></circle>
            <line x1="21" y1="21" x2="16.65" y2="16.65"></line>
          </svg>
          <label class="sr-only" for="campaign-search">Search fundraisers</label>
          <input
            id="campaign-search"
            type="search"
            class="input search-input"
            placeholder="Search by cause, patient, hospital or city…"
            [ngModel]="searchQuery"
            (ngModelChange)="onSearch($event)"
          />
        </div>

        <div class="toolbar-right">
          <label class="verified-toggle">
            <input type="checkbox" [(ngModel)]="verifiedOnly" (ngModelChange)="reload()" />
            <span class="switch" aria-hidden="true"></span>
            Verified only (80+)
          </label>
          <label class="sr-only" for="campaign-sort">Sort fundraisers</label>
          <select id="campaign-sort" class="input sort-select" [(ngModel)]="sortBy" (ngModelChange)="reload()">
            <option value="trending">Trending</option>
            <option value="newest">Newest</option>
            <option value="most_funded">Most funded</option>
          </select>
        </div>
      </div>

      <div class="category-row" role="group" aria-label="Filter by category">
        <button
          *ngFor="let cat of categories"
          type="button"
          class="chip"
          [class.active]="selectedCategory === cat.value"
          [attr.aria-pressed]="selectedCategory === cat.value"
          (click)="selectCategory(cat.value)"
        >{{ cat.label }}</button>
      </div>

      <p class="result-count" aria-live="polite">
        <ng-container *ngIf="!loading()">
          {{ total }} {{ total === 1 ? 'fundraiser' : 'fundraisers' }}
          <span *ngIf="selectedCategory !== 'ALL'">in {{ categoryLabel(selectedCategory) }}</span>
          <span *ngIf="searchQuery">matching “{{ searchQuery }}”</span>
        </ng-container>
      </p>

      <!-- Loading -->
      <div class="grid" *ngIf="loading()" aria-busy="true">
        <div class="skeleton skeleton-card" *ngFor="let s of [1, 2, 3, 4, 5, 6]"></div>
      </div>

      <!-- Empty -->
      <div class="empty-state" *ngIf="!loading() && campaigns().length === 0">
        <p class="display-sm">Nothing here <em>yet.</em></p>
        <p>Try a different search or category{{ verifiedOnly ? ', or include fundraisers still under review' : '' }}.</p>
        <button class="btn btn-outline btn-sm" type="button" (click)="resetFilters()">Reset filters</button>
      </div>

      <!-- Grid -->
      <div class="grid" #grid *ngIf="!loading() && campaigns().length > 0">
        <app-campaign-card *ngFor="let c of campaigns(); trackBy: trackById" [campaign]="c" class="grid-item"></app-campaign-card>
      </div>

      <!-- Pagination -->
      <nav class="pagination" *ngIf="totalPages > 1" aria-label="Pagination">
        <button class="btn btn-outline btn-sm" type="button" [disabled]="currentPage === 1" (click)="goToPage(currentPage - 1)">Previous</button>
        <span class="page-indicator">Page {{ currentPage }} of {{ totalPages }}</span>
        <button class="btn btn-outline btn-sm" type="button" [disabled]="currentPage === totalPages" (click)="goToPage(currentPage + 1)">Next</button>
      </nav>
    </section>

    <app-next-chapter
      link="/how-it-works"
      number="02"
      title="How verification works"
      description="What happens before a fundraiser can ask you for a rupee."
    ></app-next-chapter>
  `,
  styles: [`
    :host { display: block; }

    .explore-hero {
      padding: clamp(56px, 9vw, 120px) 0 clamp(32px, 4vw, 48px);
    }

    .explore-title { margin: 18px 0 22px; max-width: 12ch; }

    .explore-body { padding-bottom: var(--section-y); }

    .toolbar {
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 12px;
      padding: 10px;
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: var(--radius-full);
      box-shadow: var(--shadow-sm);
    }

    .search-wrap { position: relative; flex: 1; min-width: 240px; }

    .search-icon {
      position: absolute;
      left: 16px;
      top: 50%;
      transform: translateY(-50%);
      color: var(--ink-3);
    }

    .search-input {
      height: 46px;
      padding-left: 44px;
      border: none;
      border-radius: var(--radius-full);
      background: transparent;
      font-size: 15px;
    }

    .search-input:focus { box-shadow: none; }
    .search-wrap:focus-within { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: var(--radius-full); }

    .toolbar-right { display: flex; align-items: center; gap: 12px; }

    .sort-select {
      height: 46px;
      min-width: 160px;
      border-radius: var(--radius-full);
      background-color: var(--paper);
    }

    .verified-toggle {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      padding: 0 8px;
      font-size: 13.5px;
      font-weight: 600;
      color: var(--ink-2);
      cursor: pointer;
      white-space: nowrap;
    }

    .verified-toggle input { position: absolute; opacity: 0; pointer-events: none; }

    .switch {
      position: relative;
      width: 36px;
      height: 20px;
      border-radius: var(--radius-full);
      background: var(--slate-200);
      transition: background-color 0.3s ease;
    }

    .switch::after {
      content: '';
      position: absolute;
      top: 3px;
      left: 3px;
      width: 14px;
      height: 14px;
      border-radius: 50%;
      background: var(--surface);
      box-shadow: var(--shadow-sm);
      transition: transform 0.4s var(--ease-expo);
    }

    .verified-toggle input:checked + .switch { background: var(--leaf); }
    .verified-toggle input:checked + .switch::after { transform: translateX(16px); }
    .verified-toggle input:focus-visible + .switch { outline: 2px solid var(--accent); outline-offset: 2px; }

    .category-row {
      display: flex;
      gap: 8px;
      margin: 20px 0 12px;
      overflow-x: auto;
      padding-bottom: 4px;
      scrollbar-width: none;
    }

    .result-count {
      min-height: 24px;
      margin-bottom: 24px;
      font-size: 14px;
      color: var(--ink-3);
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
      gap: 24px;
    }

    .skeleton-card { height: 440px; border-radius: var(--radius-xl); }

    .empty-state {
      display: grid;
      justify-items: center;
      gap: 12px;
      padding: 80px 24px;
      text-align: center;
      color: var(--ink-2);
      border: 1px dashed var(--line);
      border-radius: var(--radius-2xl);
    }

    .pagination {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 16px;
      margin-top: 56px;
    }

    .page-indicator { font-size: 14px; font-weight: 600; color: var(--ink-3); }

    @media (max-width: 760px) {
      .toolbar { border-radius: var(--radius-xl); }
      .toolbar-right { width: 100%; justify-content: space-between; }
    }
  `]
})
export class CampaignListComponent implements OnInit, OnDestroy {
  @ViewChild('results', { static: true }) resultsRef!: ElementRef<HTMLElement>;

  private campaignService = inject(CampaignService);
  private smoothScroll = inject(SmoothScrollService);
  private route = inject(ActivatedRoute);
  private zone = inject(NgZone);

  campaigns = signal<Campaign[]>([]);
  loading = signal(true);

  readonly categories = CATEGORIES;
  selectedCategory = 'ALL';
  searchQuery = '';
  sortBy: SortKey = 'trending';
  verifiedOnly = false;
  currentPage = 1;
  totalPages = 1;
  total = 0;
  readonly pageSize = 9;

  private search$ = new Subject<string>();
  private subs = new Subscription();
  private request?: Subscription;
  private ctx?: gsap.Context;

  ngOnInit(): void {
    // Footer & other pages deep-link here with ?category=…
    this.subs.add(
      this.route.queryParamMap.subscribe((params) => {
        const category = (params.get('category') || 'ALL').toUpperCase();
        this.selectedCategory = CATEGORIES.some((c) => c.value === category) ? category : 'ALL';
        this.currentPage = 1;
        this.loadCampaigns();
      }),
    );

    this.subs.add(
      this.search$.pipe(debounceTime(300), distinctUntilChanged()).subscribe(() => this.reload()),
    );
  }

  loadCampaigns(): void {
    this.loading.set(true);
    this.request?.unsubscribe();

    const category = this.selectedCategory === 'ALL' ? undefined : this.selectedCategory;
    this.request = this.campaignService
      .getCampaigns(
        this.currentPage,
        this.pageSize,
        category,
        this.searchQuery.trim() || undefined,
        this.sortBy,
        this.verifiedOnly ? VERIFIED_SCORE : undefined,
      )
      .subscribe({
        next: (res) => {
          this.campaigns.set(res.campaigns || res.items || []);
          this.total = res.total || 0;
          this.totalPages = Math.ceil(this.total / this.pageSize) || 1;
          this.loading.set(false);
          this.zone.runOutsideAngular(() => setTimeout(() => this.animateCards(), 0));
        },
        error: () => {
          this.campaigns.set([]);
          this.total = 0;
          this.loading.set(false);
          this.smoothScroll.refresh();
        },
      });
  }

  /** Cards rise in batches as they scroll into view. */
  private animateCards(): void {
    if (!isBrowser) return;
    this.ctx?.revert();

    if (!prefersReducedMotion()) {
      this.ctx = gsap.context(() => {
        const cards = this.resultsRef.nativeElement.querySelectorAll('.grid-item');
        gsap.set(cards, { autoAlpha: 0, y: 56 });
        ScrollTrigger.batch(cards, {
          start: 'top 92%',
          once: true,
          onEnter: (batch) =>
            gsap.to(batch, {
              autoAlpha: 1,
              y: 0,
              stagger: 0.08,
              duration: 1,
              clearProps: 'transform,opacity,visibility',
            }),
        });
      }, this.resultsRef.nativeElement);
    }
    this.smoothScroll.refresh();
  }

  reload(): void {
    this.currentPage = 1;
    this.loadCampaigns();
  }

  onSearch(value: string): void {
    this.searchQuery = value;
    this.search$.next(value.trim());
  }

  selectCategory(cat: string): void {
    if (this.selectedCategory === cat) return;
    this.selectedCategory = cat;
    this.reload();
  }

  resetFilters(): void {
    this.selectedCategory = 'ALL';
    this.searchQuery = '';
    this.verifiedOnly = false;
    this.reload();
  }

  categoryLabel(value: string): string {
    return CATEGORIES.find((c) => c.value === value)?.label ?? value;
  }

  goToPage(page: number): void {
    this.currentPage = page;
    this.loadCampaigns();
    this.smoothScroll.scrollTo(this.resultsRef.nativeElement, { offset: -100, duration: 1.1 });
  }

  trackById(_: number, c: Campaign): number {
    return c.id;
  }

  ngOnDestroy(): void {
    this.subs.unsubscribe();
    this.request?.unsubscribe();
    this.ctx?.revert();
  }
}
