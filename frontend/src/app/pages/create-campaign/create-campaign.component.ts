import { Component, OnInit, OnDestroy, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule, ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { RouterModule, Router } from '@angular/router';
import { CampaignService } from '../../services/campaign.service';
import { AiService } from '../../services/ai.service';
import { Subject } from 'rxjs';
import { debounceTime, takeUntil } from 'rxjs/operators';

const CATEGORIES = ['MEDICAL', 'EMERGENCY', 'EDUCATION', 'COMMUNITY', 'MEMORIAL', 'ANIMALS'];

@Component({
  selector: 'app-create-campaign',
  standalone: true,
  imports: [CommonModule, FormsModule, ReactiveFormsModule, RouterModule],
  template: `
    <div class="create-page container">
      <div class="create-header">
        <h1>🚀 Start a Fundraiser</h1>
        <p>Our AI assistant helps you write a compelling story and verifies your campaign before publishing</p>
      </div>

      <!-- Step Indicator -->
      <div class="steps-indicator">
        <div class="step-dot" *ngFor="let s of steps; let i = index" [class.active]="currentStep === i" [class.done]="currentStep > i">
          <span>{{ currentStep > i ? '✓' : (i + 1) }}</span>
          <label>{{ s }}</label>
        </div>
      </div>

      <form (ngSubmit)="submitCampaign()">

        <!-- Step 0: Basics -->
        <div class="step-panel" *ngIf="currentStep === 0">
          <h2>📋 Basic Information</h2>

          <div class="form-group">
            <label>Campaign Title *</label>
            <input class="input" type="text" [(ngModel)]="form.title" name="title"
              placeholder="e.g., Help Priya Beat Leukemia at Tata Memorial Hospital" required />
          </div>

          <div class="form-group">
            <label>Category *</label>
            <select class="input" [(ngModel)]="form.category" name="category">
              <option *ngFor="let c of categories" [value]="c">{{ c }}</option>
            </select>
          </div>

          <div class="form-row">
            <div class="form-group">
              <label>City</label>
              <input class="input" type="text" [(ngModel)]="form.city" name="city" placeholder="Mumbai" />
            </div>
            <div class="form-group">
              <label>State</label>
              <input class="input" type="text" [(ngModel)]="form.state" name="state" placeholder="Maharashtra" />
            </div>
          </div>

          <div class="form-group">
            <label>Goal Amount (₹) *</label>
            <input class="input" type="number" [(ngModel)]="form.goal_amount" name="goal_amount"
              placeholder="e.g., 500000" min="1000" required />
            <small>{{ formatINR(form.goal_amount) }}</small>
          </div>

          <div class="form-group">
            <label>Campaign Deadline</label>
            <input class="input" type="date" [(ngModel)]="form.deadline" name="deadline" />
          </div>

          <div class="form-group">
            <label>Short Description (max 200 chars) *</label>
            <textarea class="input" rows="2" [(ngModel)]="form.short_description" name="short_description"
              placeholder="Brief one-liner about your campaign" maxlength="200" required></textarea>
            <small>{{ form.short_description.length }}/200</small>
          </div>
        </div>

        <!-- Step 1: Story + AI Assistant -->
        <div class="step-panel" *ngIf="currentStep === 1">
          <h2>✍️ Your Story</h2>
          <p class="step-desc">Write a detailed story. The more specific, the higher your AI Trust Score.</p>

          <!-- Hospital Fields -->
          <div class="form-group" *ngIf="form.category === 'MEDICAL'">
            <label>Hospital Name</label>
            <input class="input" type="text" [(ngModel)]="form.hospital_name" name="hospital_name"
              placeholder="e.g., Tata Memorial Centre, AIIMS Delhi, Apollo Hospital" />
          </div>
          <div class="form-group" *ngIf="form.category === 'MEDICAL'">
            <label>Patient UHID / Hospital ID</label>
            <input class="input" type="text" [(ngModel)]="form.hospital_patient_uhid" name="hospital_patient_uhid"
              placeholder="Patient unique ID from hospital" />
          </div>
          <div class="toggle-group" *ngIf="form.category === 'MEDICAL'">
            <label class="toggle-label">
              <input type="checkbox" [(ngModel)]="form.is_80g_tax_exempt" name="is_80g" />
              <span>This NGO/trust has 80G Tax Exemption status</span>
            </label>
            <label class="toggle-label">
              <input type="checkbox" [(ngModel)]="form.direct_hospital_transfer" name="direct_hospital" />
              <span>Enable Direct Hospital Transfer (funds go directly to hospital NEFT)</span>
            </label>
          </div>

          <!-- Story Textarea -->
          <div class="form-group story-group">
            <label>Full Story *</label>
            <textarea
              class="input story-input"
              rows="10"
              [(ngModel)]="form.story"
              name="story"
              (ngModelChange)="onStoryChange($event)"
              placeholder="Tell your story in detail. Include hospital name, diagnosis, treatment plan, how funds will be used..."
              required
            ></textarea>
          </div>

          <!-- AI Story Assistant -->
          <div class="ai-assistant-box">
            <div class="ai-header">
              <span>🤖 AI Story Assistant</span>
              <small>Click to generate a compelling story based on your details</small>
            </div>
            <div class="ai-inputs">
              <input class="input" type="text" [(ngModel)]="aiHints.condition" name="ai_condition"
                placeholder="Medical condition / cause (e.g., Acute Lymphoblastic Leukemia)" />
              <input class="input" type="text" [(ngModel)]="aiHints.treatment" name="ai_treatment"
                placeholder="Treatment needed (e.g., 6 cycles of chemotherapy + BMT)" />
              <input class="input" type="text" [(ngModel)]="aiHints.patient" name="ai_patient"
                placeholder="Who needs help (e.g., 8-year-old girl from Pune)" />
            </div>
            <button type="button" class="btn btn-secondary ai-btn" (click)="enhanceStory()" [disabled]="enhancing()">
              {{ enhancing() ? '✨ Generating…' : '✨ Generate AI Story' }}
            </button>
            <div class="ai-error" *ngIf="enhanceError()">{{ enhanceError() }}</div>
          </div>
        </div>

        <!-- Step 2: Documents -->
        <div class="step-panel" *ngIf="currentStep === 2">
          <h2>📎 Supporting Documents</h2>
          <p class="step-desc">Upload documents to increase your AI Trust Score. Medical reports, bills, and ID proofs are recommended.</p>

          <div class="doc-note">
            <div class="doc-tip">
              <span class="doc-icon">🏥</span>
              <div>
                <strong>Medical Campaigns</strong>
                <p>Hospital admission slip, doctor's prescription, estimate letter, discharge summary</p>
              </div>
            </div>
            <div class="doc-tip">
              <span class="doc-icon">🪪</span>
              <div>
                <strong>Identity Proof</strong>
                <p>Aadhaar card, PAN card of organizer or patient</p>
              </div>
            </div>
            <div class="doc-tip">
              <span class="doc-icon">📸</span>
              <div>
                <strong>Cover Photo</strong>
                <p>A clear, recent photo increases donor trust significantly</p>
              </div>
            </div>
          </div>

          <div class="form-group">
            <label>Cover Image URL (optional)</label>
            <input class="input" type="url" [(ngModel)]="form.cover_image_url" name="cover_image_url"
              placeholder="https://..." />
            <small>Paste an image URL or upload to an image hosting service</small>
          </div>

          <div class="form-group">
            <label>Organizer's Name *</label>
            <input class="input" type="text" [(ngModel)]="form.organizer_name" name="organizer_name"
              placeholder="Your full name" required />
          </div>
          <div class="form-group">
            <label>Organizer's Phone</label>
            <input class="input" type="tel" [(ngModel)]="form.organizer_phone" name="organizer_phone"
              placeholder="+91 XXXXXXXXXX" />
          </div>
        </div>

        <!-- Step 3: Review + Live AI Score -->
        <div class="step-panel" *ngIf="currentStep === 3">
          <h2>🔍 Review & AI Verification</h2>
          <p class="step-desc">We're running AI verification on your campaign. A score ≥ 80 gets auto-approved.</p>

          <!-- Summary -->
          <div class="review-summary card">
            <div class="review-row"><span>Title</span><strong>{{ form.title }}</strong></div>
            <div class="review-row"><span>Category</span><strong>{{ form.category }}</strong></div>
            <div class="review-row"><span>Goal</span><strong>₹{{ formatINR(form.goal_amount) }}</strong></div>
            <div class="review-row" *ngIf="form.hospital_name"><span>Hospital</span><strong>{{ form.hospital_name }}</strong></div>
            <div class="review-row" *ngIf="form.is_80g_tax_exempt"><span>80G</span><strong>✅ Eligible</strong></div>
          </div>

          <!-- Live AI Score -->
          <div class="ai-score-panel" *ngIf="!verifying() && liveScore()">
            <div class="score-header">
              <span class="score-label">AI Trust Score</span>
              <span class="score-number" [class.green]="(liveScore()?.overall_score||0)>=80" [class.amber]="(liveScore()?.overall_score||0)>=50 && (liveScore()?.overall_score||0)<80" [class.red]="(liveScore()?.overall_score||0)<50">
                {{ liveScore()?.overall_score | number:'1.0-0' }}/100
              </span>
            </div>
            <div class="score-verdict">{{ liveScore()?.decision }}</div>
            <div class="score-explanation">{{ liveScore()?.explanation }}</div>

            <div class="dimension-bars" *ngIf="liveScore()?.dimension_scores">
              <div class="dim-row" *ngFor="let dim of getDimensions()">
                <span>{{ dim.label }}</span>
                <div class="dim-bar"><div [style.width.%]="dim.value" [class.bar-green]="dim.value>=70" [class.bar-amber]="dim.value>=40 && dim.value<70" [class.bar-red]="dim.value<40"></div></div>
                <span>{{ dim.value | number:'1.0-0' }}</span>
              </div>
            </div>

            <!-- Red Flags -->
            <div class="flags-section" *ngIf="liveScore()?.red_flags && liveScore()!.red_flags!.length > 0">
              <div class="flag-item" *ngFor="let f of liveScore()!.red_flags">⚠️ {{ f }}</div>
            </div>

            <!-- Suggestions -->
            <div class="suggestions" *ngIf="liveScore()?.suggestions && liveScore()!.suggestions!.length > 0">
              <strong>💡 Improve your score:</strong>
              <ul>
                <li *ngFor="let s of liveScore()!.suggestions">{{ s }}</li>
              </ul>
            </div>
          </div>

          <div class="verifying-state" *ngIf="verifying()">
            <div class="spinner"></div>
            <p>AI is analyzing your campaign…</p>
          </div>

          <button type="button" class="btn btn-outline" (click)="runVerification()" [disabled]="verifying()">
            🔄 Re-run AI Verification
          </button>
        </div>

        <!-- Navigation Buttons -->
        <div class="step-nav">
          <button type="button" class="btn btn-outline" *ngIf="currentStep > 0" (click)="prevStep()">← Back</button>
          <button type="button" class="btn btn-primary" *ngIf="currentStep < 3" (click)="nextStep()">Next →</button>
          <button type="submit" class="btn btn-primary" *ngIf="currentStep === 3" [disabled]="submitting()">
            {{ submitting() ? 'Submitting…' : '🚀 Submit Campaign' }}
          </button>
        </div>

        <div class="submit-error" *ngIf="submitError()">{{ submitError() }}</div>
      </form>
    </div>
  `,
  styles: [`
    .create-page { max-width: 780px; padding: var(--space-8) var(--space-4); }
    .create-header { margin-bottom: var(--space-6); }
    .create-header h1 { font-size: 2rem; font-weight: 800; }
    .create-header p { color: var(--color-text-secondary); }

    /* Steps */
    .steps-indicator { display: flex; gap: 0; margin-bottom: var(--space-8); counter-reset: step; }
    .step-dot {
      display: flex; flex-direction: column; align-items: center; flex: 1; position: relative;
      font-size: 0.78rem; color: var(--color-text-secondary);
    }
    .step-dot::before {
      content: ''; position: absolute; top: 18px; right: -50%; width: 100%; height: 2px;
      background: #e5e7eb; z-index: 0;
    }
    .step-dot:last-child::before { display: none; }
    .step-dot span {
      width: 36px; height: 36px; border-radius: 50%; background: #e5e7eb;
      display: flex; align-items: center; justify-content: center;
      font-weight: 700; z-index: 1; margin-bottom: 6px; font-size: 0.85rem;
    }
    .step-dot.active span { background: var(--color-primary); color: #fff; }
    .step-dot.done span { background: var(--color-secondary); color: #fff; }
    .step-dot label { text-align: center; }

    /* Panel */
    .step-panel { background: #fff; border: 1px solid #e5e7eb; border-radius: var(--radius-lg); padding: var(--space-6); margin-bottom: var(--space-4); }
    .step-panel h2 { font-size: 1.3rem; font-weight: 700; margin-bottom: var(--space-2); }
    .step-desc { color: var(--color-text-secondary); margin-bottom: var(--space-4); }

    .form-group { margin-bottom: var(--space-4); }
    .form-group label { display: block; font-weight: 600; font-size: 0.9rem; margin-bottom: 6px; }
    .form-group small { color: var(--color-text-secondary); font-size: 0.78rem; }
    .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-3); }

    .story-input { font-size: 0.95rem; line-height: 1.7; }
    .story-group { margin-top: var(--space-4); }

    .toggle-group { display: flex; flex-direction: column; gap: var(--space-2); margin-bottom: var(--space-4); }
    .toggle-label { display: flex; align-items: center; gap: 10px; font-size: 0.9rem; cursor: pointer; }
    .toggle-label input { accent-color: var(--color-primary); width: 16px; height: 16px; }

    /* AI Assistant */
    .ai-assistant-box {
      background: linear-gradient(135deg, #fdf2f8, #fef9f0);
      border: 1.5px solid #fbcfe8;
      border-radius: var(--radius-lg);
      padding: var(--space-4);
      margin-top: var(--space-4);
    }
    .ai-header { margin-bottom: var(--space-3); }
    .ai-header span { font-weight: 700; font-size: 1rem; }
    .ai-header small { display: block; color: var(--color-text-secondary); font-size: 0.82rem; }
    .ai-inputs { display: flex; flex-direction: column; gap: var(--space-2); margin-bottom: var(--space-3); }
    .ai-btn { background: #7c3aed; border-color: #7c3aed; }
    .ai-btn:hover { background: #6d28d9; }
    .ai-error { color: #ef4444; font-size: 0.82rem; margin-top: var(--space-2); }

    /* Docs */
    .doc-note { display: flex; flex-direction: column; gap: var(--space-3); margin-bottom: var(--space-6); }
    .doc-tip { display: flex; gap: var(--space-3); align-items: flex-start; background: #f9fafb; border-radius: var(--radius-md); padding: var(--space-3); }
    .doc-icon { font-size: 1.8rem; flex-shrink: 0; }
    .doc-tip strong { display: block; font-size: 0.9rem; margin-bottom: 2px; }
    .doc-tip p { font-size: 0.8rem; color: var(--color-text-secondary); margin: 0; }

    /* Review */
    .review-summary { padding: var(--space-4); margin-bottom: var(--space-4); }
    .review-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #f3f4f6; font-size: 0.9rem; }
    .review-row:last-child { border-bottom: none; }

    /* AI Score Panel */
    .ai-score-panel { background: #f9fafb; border: 1px solid #e5e7eb; border-radius: var(--radius-lg); padding: var(--space-5); margin-bottom: var(--space-4); }
    .score-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-2); }
    .score-label { font-weight: 600; font-size: 1rem; }
    .score-number { font-size: 2rem; font-weight: 800; }
    .score-number.green { color: var(--color-secondary); }
    .score-number.amber { color: #f59e0b; }
    .score-number.red   { color: #ef4444; }
    .score-verdict { font-weight: 700; margin-bottom: 4px; }
    .score-explanation { font-size: 0.88rem; color: var(--color-text-secondary); margin-bottom: var(--space-4); }

    .dimension-bars { display: flex; flex-direction: column; gap: 10px; margin-bottom: var(--space-3); }
    .dim-row { display: grid; grid-template-columns: 130px 1fr 30px; gap: 8px; align-items: center; font-size: 0.82rem; }
    .dim-bar { background: #e5e7eb; border-radius: 4px; height: 8px; overflow: hidden; }
    .dim-bar div { height: 100%; border-radius: 4px; max-width: 100%; }
    .bar-green { background: var(--color-secondary); }
    .bar-amber { background: #f59e0b; }
    .bar-red   { background: #ef4444; }

    .flags-section { margin-bottom: var(--space-3); }
    .flag-item { color: #92400e; background: #fef3c7; border-radius: var(--radius-sm); padding: 6px 12px; font-size: 0.82rem; margin-bottom: 4px; }
    .suggestions ul { margin: var(--space-2) 0 0 var(--space-4); font-size: 0.85rem; color: var(--color-text-secondary); }
    .suggestions li { margin-bottom: 4px; }

    .verifying-state { text-align: center; padding: var(--space-6) 0; }
    .spinner {
      width: 40px; height: 40px;
      border: 4px solid #f3f4f6;
      border-top-color: var(--color-primary);
      border-radius: 50%;
      animation: spin 0.8s linear infinite;
      margin: 0 auto 12px;
    }
    @keyframes spin { to { transform: rotate(360deg); } }

    /* Nav */
    .step-nav { display: flex; gap: var(--space-3); justify-content: flex-end; margin-top: var(--space-4); }
    .submit-error { color: #ef4444; font-size: 0.85rem; text-align: center; margin-top: var(--space-2); }
  `]
})
export class CreateCampaignComponent implements OnInit, OnDestroy {
  private campaignService = inject(CampaignService);
  private aiService = inject(AiService);
  private router = inject(Router);
  private destroy$ = new Subject<void>();
  private storyChange$ = new Subject<string>();

  steps = ['Basics', 'Story', 'Documents', 'Review'];
  currentStep = 0;
  categories = CATEGORIES;

  form = {
    title: '', category: 'MEDICAL', city: '', state: '',
    goal_amount: 500000, deadline: '', short_description: '', story: '',
    hospital_name: '', hospital_patient_uhid: '',
    is_80g_tax_exempt: false, direct_hospital_transfer: false,
    cover_image_url: '', organizer_name: '', organizer_phone: '',
  };
  aiHints = { condition: '', treatment: '', patient: '' };

  enhancing = signal(false);
  enhanceError = signal('');
  verifying = signal(false);
  liveScore = signal<any>(null);
  submitting = signal(false);
  submitError = signal('');

  ngOnInit() {
    this.storyChange$.pipe(
      debounceTime(1500),
      takeUntil(this.destroy$)
    ).subscribe(() => {
      if (this.currentStep === 3) this.runVerification();
    });
  }

  ngOnDestroy() { this.destroy$.next(); this.destroy$.complete(); }

  onStoryChange(val: string) { this.form.story = val; }

  enhanceStory() {
    this.enhancing.set(true);
    this.enhanceError.set('');
    this.aiService.enhanceStory({
      title: this.form.title,
      category: this.form.category,
      goal_amount: this.form.goal_amount,
      city: this.form.city,
      state: this.form.state,
      hospital_name: this.form.hospital_name,
      story: this.aiHints.condition + ' ' + this.aiHints.treatment + ' ' + this.aiHints.patient,
    }).subscribe({
      next: (res) => {
        this.form.story = res.enhanced_story;
        this.enhancing.set(false);
      },
      error: (err) => {
        this.enhanceError.set(err?.error?.detail || 'AI unavailable. Please write your story manually.');
        this.enhancing.set(false);
      }
    });
  }

  runVerification() {
    this.verifying.set(true);
    this.aiService.preCheckVerification({
      title: this.form.title,
      category: this.form.category,
      goal_amount: this.form.goal_amount,
      story: this.form.story,
      hospital_name: this.form.hospital_name,
    }).subscribe({
      next: (res) => { this.liveScore.set(res); this.verifying.set(false); },
      error: () => this.verifying.set(false)
    });
  }

  getDimensions(): { label: string; value: number }[] {
    const ds = this.liveScore()?.dimension_scores;
    if (!ds) return [];
    return [
      { label: 'Specificity',    value: ds.specificity_score    || 0 },
      { label: 'Benchmark Fit',  value: ds.benchmark_score      || 0 },
      { label: 'Documentation',  value: ds.documentation_score  || 0 },
      { label: 'Urgency',        value: ds.urgency_score        || 0 },
    ];
  }

  nextStep() {
    if (this.currentStep < 3) {
      this.currentStep++;
      if (this.currentStep === 3) this.runVerification();
    }
  }
  prevStep() { if (this.currentStep > 0) this.currentStep--; }

  submitCampaign() {
    this.submitting.set(true);
    this.submitError.set('');
    this.campaignService.createCampaign({
      title: this.form.title,
      category: this.form.category,
      short_description: this.form.short_description,
      story: this.form.story,
      goal_amount: this.form.goal_amount,
      deadline: this.form.deadline || undefined,
      city: this.form.city || undefined,
      state: this.form.state || undefined,
      cover_image_url: this.form.cover_image_url || undefined,
      organizer_name: this.form.organizer_name || undefined,
      organizer_phone: this.form.organizer_phone || undefined,
      hospital_name: this.form.hospital_name || undefined,
      hospital_patient_uhid: this.form.hospital_patient_uhid || undefined,
      is_80g_tax_exempt: this.form.is_80g_tax_exempt,
      direct_hospital_transfer: this.form.direct_hospital_transfer,
    }).subscribe({
      next: (c) => { this.submitting.set(false); this.router.navigate(['/campaigns', c.id]); },
      error: (err) => {
        this.submitError.set(err?.error?.detail || 'Submission failed. Please try again.');
        this.submitting.set(false);
      }
    });
  }

  formatINR(amount: number): string {
    if (!amount) return '';
    if (amount >= 10_000_000) return '₹' + (amount / 10_000_000).toFixed(1) + ' Crore';
    if (amount >= 100_000)    return '₹' + (amount / 100_000).toFixed(1) + ' Lakh';
    if (amount >= 1000)       return '₹' + (amount / 1000).toFixed(1) + 'K';
    return '₹' + amount;
  }
}
