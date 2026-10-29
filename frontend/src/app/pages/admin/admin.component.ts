import { Component, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';
import { HttpClient } from '@angular/common/http';
import { CampaignService } from '../../services/campaign.service';
import { DonationService } from '../../services/donation.service';
import { AuthService } from '../../services/auth.service';
import { Campaign, AdminDonationItem, AdminDonationsSummary } from '../../models/campaign.model';

@Component({
  selector: 'app-admin',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterModule],
  template: `
    <div class="admin-page container">
      <div class="admin-header">
        <div class="admin-title-row">
          <div>
            <h1>🛡️ Trust & Safety Moderation</h1>
            <p>Admin verification portal. Only platform administrators can review, accept, or reject fundraiser demands.</p>
          </div>
          <div class="admin-user-badge" *ngIf="authService.isAdmin()">
            <span class="admin-avatar">👑</span>
            <div class="admin-user-info">
              <strong>{{ authService.currentUser()?.full_name }}</strong>
              <span class="role-tag">PLATFORM ADMIN</span>
            </div>
            <button class="btn btn-sm btn-outline btn-logout" (click)="authService.logout()">Logout</button>
          </div>
        </div>
      </div>

      <!-- Auth Required Gate: Shown if current user is not ADMIN -->
      <div class="admin-login-card card" *ngIf="!authService.isAdmin()">
        <div class="gate-icon">🔒</div>
        <h2>Administrator Authentication Required</h2>
        <p class="gate-desc">
          Under platform security policy, only verified administrators can view the review queue, accept, or reject campaign demands.
        </p>

        <form (ngSubmit)="loginAsAdmin()" class="admin-login-form">
          <div class="form-group">
            <label>Admin Email</label>
            <input type="email" class="input" [(ngModel)]="loginEmail" name="email" required placeholder="admin@crowdfund-trust.in" />
          </div>
          <div class="form-group">
            <label>Password</label>
            <input type="password" class="input" [(ngModel)]="loginPassword" name="password" required placeholder="••••••••" />
          </div>
          <button type="submit" class="btn btn-primary btn-full" [disabled]="loginLoading()">
            {{ loginLoading() ? 'Authenticating…' : '🔐 Sign In as Administrator' }}
          </button>
          <div class="error-msg" *ngIf="loginError()">{{ loginError() }}</div>
        </form>

        <div class="quick-admin-box">
          <span>⚡ Development / Demo Quick Access:</span>
          <button class="btn btn-sm btn-outline quick-btn" (click)="quickLoginAdmin()">
            Fill & Sign In as Lead Moderator (Vikram Mehta)
          </button>
        </div>
      </div>

      <!-- Admin Portal View (Only shown when authService.isAdmin() is true) -->
      <div *ngIf="authService.isAdmin()">
        <!-- Stats Bar -->
        <div class="stats-bar">
          <div class="stat-item">
            <span class="stat-n">{{ pendingCampaigns.length }}</span>
            <span class="stat-l">Pending Review</span>
          </div>
          <div class="stat-item">
            <span class="stat-n">{{ flaggedCampaigns.length }}</span>
            <span class="stat-l">Flagged by AI</span>
          </div>
          <div class="stat-item">
            <span class="stat-n">{{ allCampaigns().length }}</span>
            <span class="stat-l">Total in Queue</span>
          </div>
          <div class="stat-item donation-stat" (click)="setTab('donations')">
            <span class="stat-n">💰 ₹{{ formatINR(donationSummary()?.total_amount_raised || 0) }}</span>
            <span class="stat-l">{{ donationSummary()?.total_donations_count || 0 }} Donations Ledger</span>
          </div>
          <div class="stat-item audit-stat" (click)="activeTab = 'audit_logs'">
            <span class="stat-n">📜</span>
            <span class="stat-l">View Audit Trail</span>
          </div>
        </div>

        <!-- Filter Tabs -->
        <div class="filter-tabs">
          <button class="tab-btn" *ngFor="let tab of tabs" [class.active]="activeTab === tab.value" (click)="setTab(tab.value)">
            {{ tab.label }}
          </button>
        </div>

        <!-- Audit Logs View -->
        <div class="audit-logs-view card" *ngIf="activeTab === 'audit_logs'">
          <h3>📜 Immutable Admin Audit Logs</h3>
          <p class="section-sub">Every decision to accept or reject a fundraiser is cryptographically verified and permanently logged.</p>
          <div class="loading-state" *ngIf="loadingAuditLogs()">
            <div class="spinner"></div><p>Loading audit trail…</p>
          </div>
          <table class="audit-table" *ngIf="!loadingAuditLogs() && auditLogs().length > 0">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Action</th>
                <th>Campaign ID</th>
                <th>Status Shift</th>
                <th>Reason / Notes</th>
                <th>Admin IP</th>
              </tr>
            </thead>
            <tbody>
              <tr *ngFor="let log of auditLogs()">
                <td>{{ log.created_at | date:'short' }}</td>
                <td><span class="action-tag" [ngClass]="log.action.toLowerCase()">{{ log.action }}</span></td>
                <td>#{{ log.target_id }}</td>
                <td>{{ log.previous_status }} → <strong>{{ log.new_status }}</strong></td>
                <td>{{ log.reason || '-' }}</td>
                <td><code>{{ log.ip_address || '127.0.0.1' }}</code></td>
              </tr>
            </tbody>
          </table>
          <div class="empty-state" *ngIf="!loadingAuditLogs() && auditLogs().length === 0">
            <p>No audit logs recorded yet.</p>
          </div>
        </div>

        <!-- Donations & Payments Ledger View -->
        <div class="donations-view card" *ngIf="activeTab === 'donations'">
          <div class="donations-header-row">
            <div>
              <h3>💰 Complete Platform Donations & Payment Ledger</h3>
              <p class="section-sub">
                Real-time audit log of who paid, how much was paid, payment gateway details, and the exact requested person (beneficiary).
              </p>
            </div>
            <div class="ledger-summary-pills" *ngIf="donationSummary() as sum">
              <div class="summary-pill">
                <span>Total Collected</span>
                <strong>₹{{ sum.total_amount_raised | number:'1.2-2' }}</strong>
              </div>
              <div class="summary-pill highlight">
                <span>Net to Beneficiaries</span>
                <strong>₹{{ sum.total_net_amount | number:'1.2-2' }}</strong>
              </div>
              <div class="summary-pill">
                <span>Gateway Fees</span>
                <strong>₹{{ sum.total_fee_amount | number:'1.2-2' }}</strong>
              </div>
              <div class="summary-pill">
                <span>Average Donation</span>
                <strong>₹{{ sum.average_donation | number:'1.2-2' }}</strong>
              </div>
            </div>
          </div>

          <!-- Search & Filter Controls -->
          <div class="ledger-filter-bar">
            <div class="search-input-wrap">
              <span class="search-icon">🔍</span>
              <input
                type="text"
                class="input ledger-search-input"
                placeholder="Search by Donor Name, Phone, Email, PAN, Tx Ref, or Beneficiary…"
                [(ngModel)]="donationSearch"
                (input)="onSearchDonations()"
              />
            </div>
            <select class="input campaign-select" [(ngModel)]="selectedCampaignFilter" (change)="loadAdminDonations()">
              <option [value]="0">All Campaigns</option>
              <option *ngFor="let camp of allCampaigns()" [value]="camp.id">
                #{{ camp.id }} - {{ camp.title | slice:0:35 }}…
              </option>
            </select>
          </div>

          <div class="loading-state" *ngIf="loadingDonations()">
            <div class="spinner"></div><p>Loading donations ledger…</p>
          </div>

          <div class="table-responsive" *ngIf="!loadingDonations() && adminDonations().length > 0">
            <table class="ledger-table">
              <thead>
                <tr>
                  <th>Date & Tx Ref</th>
                  <th>Requested Person / Beneficiary</th>
                  <th>Donor Details</th>
                  <th>Amount & Net</th>
                  <th>Payment Gateway</th>
                  <th>80G Receipt</th>
                </tr>
              </thead>
              <tbody>
                <tr *ngFor="let d of adminDonations()">
                  <td>
                    <div class="tx-time">{{ d.created_at | date:'medium' }}</div>
                    <code class="tx-ref">{{ d.transaction_ref }}</code>
                  </td>
                  <td>
                    <div class="beneficiary-box">
                      <span class="beneficiary-name">👤 {{ d.beneficiary_name || 'Requested Patient / Cause' }}</span>
                      <a class="campaign-link" [routerLink]="['/campaigns', d.campaign_id]">
                        Campaign #{{ d.campaign_id }}: {{ d.campaign_title }}
                      </a>
                      <span class="hospital-sub" *ngIf="d.hospital_name">🏥 {{ d.hospital_name }}</span>
                    </div>
                  </td>
                  <td>
                    <div class="donor-details-box">
                      <div class="donor-name-row">
                        <strong>{{ d.donor_name }}</strong>
                        <span class="anon-badge" *ngIf="d.is_anonymous" title="Donor chose anonymous for public display; visible to Admin for tax/compliance">
                          🔒 Anonymous to Public
                        </span>
                      </div>
                      <div class="donor-contact" *ngIf="d.donor_email">📧 {{ d.donor_email }}</div>
                      <div class="donor-contact" *ngIf="d.donor_phone">📱 {{ d.donor_phone }}</div>
                      <div class="donor-pan" *ngIf="d.donor_pan">🪪 PAN: <code>{{ d.donor_pan }}</code></div>
                      <div class="donor-msg-sub" *ngIf="d.support_message">💬 "{{ d.support_message }}"</div>
                    </div>
                  </td>
                  <td>
                    <div class="amount-box">
                      <div class="amount-gross">₹{{ d.amount | number:'1.2-2' }}</div>
                      <div class="amount-net">Net: ₹{{ d.net_amount | number:'1.2-2' }}</div>
                      <div class="amount-fee" *ngIf="d.fee_amount > 0">Fee: ₹{{ d.fee_amount | number:'1.2-2' }}</div>
                      <div class="amount-tip" *ngIf="d.tip_amount > 0">+ Tip: ₹{{ d.tip_amount | number:'1.2-2' }}</div>
                    </div>
                  </td>
                  <td>
                    <div class="payment-method-badge">
                      <span class="method-tag">{{ d.payment_method }}</span>
                      <span class="status-pill status-completed">{{ d.payment_status }}</span>
                      <code class="order-id" *ngIf="d.gateway_order_id">{{ d.gateway_order_id }}</code>
                    </div>
                  </td>
                  <td>
                    <div *ngIf="d.tax_exemption_80g_number" class="tax-80g-pill">
                      📄 {{ d.tax_exemption_80g_number }}
                    </div>
                    <span *ngIf="!d.tax_exemption_80g_number" class="text-muted">-</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="empty-state" *ngIf="!loadingDonations() && adminDonations().length === 0">
            <div class="empty-icon">💸</div>
            <h3>No donations found</h3>
            <p>Try adjusting your search query or campaign filter.</p>
          </div>
        </div>

        <!-- Campaign Queue View -->
        <div *ngIf="activeTab !== 'audit_logs' && activeTab !== 'donations'">
          <!-- Loading -->
          <div class="loading-state" *ngIf="loading()">
            <div class="spinner"></div><p>Loading campaigns…</p>
          </div>

          <!-- Empty -->
          <div class="empty-state" *ngIf="!loading() && filteredCampaigns().length === 0">
            <div class="empty-icon">✅</div>
            <h3>No campaigns in this queue</h3>
            <p>All fundraiser requests have been processed.</p>
          </div>

          <!-- Campaign List -->
          <div class="campaign-queue" *ngIf="!loading()">
            <div class="queue-item card" *ngFor="let c of filteredCampaigns()">
              <div class="queue-top">
                <div class="queue-info">
                  <div class="queue-title-row">
                    <h3 class="queue-title">{{ c.title }}</h3>
                    <span class="status-badge" [ngClass]="'status-' + (c.status || '').toLowerCase()">{{ c.status }}</span>
                  </div>
                  <div class="queue-meta">
                    <span>📂 {{ c.category }}</span>
                    <span>📍 {{ c.city }}, {{ c.state }}</span>
                    <span *ngIf="c.hospital_name">🏥 {{ c.hospital_name }}</span>
                    <span>💰 ₹{{ formatINR(c.goal_amount) }}</span>
                  </div>
                  <p class="queue-desc">{{ c.short_description || c.subtitle || c.story }}</p>
                </div>

                <!-- AI Score Dial -->
                <div class="score-dial" [class.dial-green]="((c.ai_trust_score ?? c.authenticity_score) || 0) >= 80" [class.dial-amber]="((c.ai_trust_score ?? c.authenticity_score) || 0) >= 50 && ((c.ai_trust_score ?? c.authenticity_score) || 0) < 80" [class.dial-red]="((c.ai_trust_score ?? c.authenticity_score) || 0) < 50">
                  <span class="dial-num">{{ (c.ai_trust_score ?? c.authenticity_score) !== undefined ? (c.ai_trust_score ?? c.authenticity_score) : '?' }}</span>
                  <span class="dial-lbl">AI Score</span>
                </div>
              </div>

              <!-- AI Details -->
              <div class="ai-details" *ngIf="c.ai_dimension_scores">
                <div class="ai-dim-row" *ngFor="let dim of getDimensions(c)">
                  <span>{{ dim.label }}</span>
                  <div class="dim-bar">
                    <div [style.width.%]="dim.value"
                      [class.green]="dim.value>=70"
                      [class.amber]="dim.value>=40 && dim.value<70"
                      [class.red]="dim.value<40"></div>
                  </div>
                  <span>{{ dim.value | number:'1.0-0' }}</span>
                </div>
              </div>

              <!-- Red Flags -->
              <div class="red-flags" *ngIf="c.ai_red_flags && c.ai_red_flags.length > 0">
                <div class="flag" *ngFor="let f of c.ai_red_flags">⚠️ {{ f }}</div>
              </div>

              <!-- Decision Reason Input -->
              <div class="decision-reason-box">
                <input class="input reason-input" [(ngModel)]="notes[c.id]" placeholder="Enter justification note for this decision (recorded in audit log)…" />
              </div>

              <!-- Action Buttons -->
              <div class="queue-actions">
                <a [routerLink]="['/campaigns', c.id]" class="btn btn-outline btn-sm">👁️ View Details</a>
                <button class="btn btn-sm btn-approve" (click)="decide(c, 'APPROVE')" [disabled]="actionLoading()[c.id]">
                  ✅ Accept Demand (Activate)
                </button>
                <button class="btn btn-sm btn-info" (click)="decide(c, 'REQUEST_MORE_INFO')" [disabled]="actionLoading()[c.id]">
                  📋 Request More Info
                </button>
                <button class="btn btn-sm btn-reject" (click)="decide(c, 'REJECT')" [disabled]="actionLoading()[c.id]">
                  ❌ Reject Demand
                </button>
              </div>

              <!-- Decision Feedback -->
              <div class="decision-msg" *ngIf="decisions()[c.id]">
                {{ decisions()[c.id] }}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .admin-page { padding: var(--space-8) var(--space-4); }
    .admin-header { margin-bottom: var(--space-6); }
    .admin-title-row { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: var(--space-4); }
    .admin-header h1 { font-size: 1.8rem; font-weight: 800; }
    .admin-header p { color: var(--color-text-secondary); margin-top: 4px; }

    .admin-user-badge {
      display: flex; align-items: center; gap: 12px; background: #fff;
      border: 1px solid #e5e7eb; padding: 8px 16px; border-radius: var(--radius-md);
      box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .admin-avatar { font-size: 1.5rem; }
    .admin-user-info { display: flex; flex-direction: column; }
    .role-tag { font-size: 0.65rem; font-weight: 700; color: #7c3aed; letter-spacing: 0.5px; }
    .btn-logout { font-size: 0.75rem; padding: 4px 10px; margin-left: 8px; }

    /* Admin Login Card */
    .admin-login-card {
      max-width: 520px; margin: 40px auto; padding: 36px; text-align: center;
      box-shadow: 0 10px 30px rgba(0,0,0,0.08); border-radius: var(--radius-lg);
    }
    .gate-icon { font-size: 3rem; margin-bottom: 12px; }
    .admin-login-card h2 { font-size: 1.4rem; font-weight: 800; margin-bottom: 8px; }
    .gate-desc { font-size: 0.9rem; color: var(--color-text-secondary); margin-bottom: 24px; line-height: 1.5; }
    .admin-login-form { text-align: left; display: flex; flex-direction: column; gap: 16px; }
    .form-group label { display: block; font-weight: 600; font-size: 0.85rem; margin-bottom: 6px; }
    .btn-full { width: 100%; padding: 12px; font-size: 0.95rem; }
    .error-msg { color: #ef4444; font-size: 0.85rem; text-align: center; margin-top: 8px; }
    .quick-admin-box {
      margin-top: 24px; padding-top: 20px; border-top: 1px dashed #e5e7eb;
      font-size: 0.8rem; color: var(--color-text-secondary); display: flex; flex-direction: column; gap: 8px;
    }
    .quick-btn { font-size: 0.8rem; padding: 8px 12px; }

    /* Stats Bar */
    .stats-bar { display: flex; gap: var(--space-4); margin-bottom: var(--space-5); flex-wrap: wrap; }
    .stat-item {
      background: #fff; border: 1px solid #e5e7eb; border-radius: var(--radius-md);
      padding: var(--space-3) var(--space-5); text-align: center; flex: 1; min-width: 130px;
    }
    .audit-stat { cursor: pointer; transition: all 0.2s; }
    .audit-stat:hover { border-color: var(--color-primary); background: #fff7ed; }
    .stat-n { display: block; font-size: 1.8rem; font-weight: 800; color: var(--color-primary); }
    .stat-l { font-size: 0.8rem; color: var(--color-text-secondary); }

    .filter-tabs { display: flex; gap: var(--space-2); margin-bottom: var(--space-5); flex-wrap: wrap; }
    .tab-btn {
      padding: 8px 18px; border-radius: 20px; border: 1.5px solid #d1d5db;
      background: #fff; font-weight: 600; font-size: 0.85rem; cursor: pointer; transition: all 0.15s;
    }
    .tab-btn:hover, .tab-btn.active { background: var(--color-primary); border-color: var(--color-primary); color: #fff; }

    /* Audit Logs */
    .audit-logs-view { padding: 24px; margin-bottom: 24px; }
    .section-sub { font-size: 0.88rem; color: var(--color-text-secondary); margin-bottom: 16px; }
    .audit-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; text-align: left; }
    .audit-table th { padding: 10px 12px; background: #f9fafb; border-bottom: 2px solid #e5e7eb; }
    .audit-table td { padding: 12px; border-bottom: 1px solid #f3f4f6; }
    .action-tag { padding: 3px 8px; border-radius: 4px; font-weight: 700; font-size: 0.72rem; }
    .action-tag.campaign_active { background: #d1fae5; color: #065f46; }
    .action-tag.campaign_rejected { background: #fee2e2; color: #991b1b; }
    .action-tag.campaign_pending_verification { background: #fef3c7; color: #92400e; }

    .donation-stat { cursor: pointer; transition: all 0.2s; }
    .donation-stat:hover { border-color: var(--color-primary); background: #fff7ed; }

    /* Donations & Ledger */
    .donations-view { padding: 24px; margin-bottom: 24px; }
    .donations-header-row { display: flex; justify-content: space-between; align-items: flex-start; gap: 20px; flex-wrap: wrap; margin-bottom: 20px; }
    .ledger-summary-pills { display: flex; gap: 10px; flex-wrap: wrap; }
    .summary-pill {
      background: #f8fafc; border: 1px solid #e2e8f0; border-radius: var(--radius-md);
      padding: 8px 14px; display: flex; flex-direction: column; font-size: 0.75rem; color: var(--color-text-secondary);
    }
    .summary-pill strong { font-size: 1.05rem; color: var(--color-text-primary); margin-top: 2px; }
    .summary-pill.highlight { background: #f0fdf4; border-color: #bbf7d0; color: #166534; }
    .summary-pill.highlight strong { color: #15803d; }

    .ledger-filter-bar { display: flex; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; }
    .search-input-wrap { position: relative; flex: 1; min-width: 280px; }
    .search-icon { position: absolute; left: 12px; top: 50%; transform: translateY(-50%); font-size: 0.9rem; opacity: 0.6; }
    .ledger-search-input { width: 100%; padding-left: 36px; font-size: 0.88rem; }
    .campaign-select { max-width: 260px; font-size: 0.88rem; }

    .table-responsive { width: 100%; overflow-x: auto; }
    .ledger-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; text-align: left; }
    .ledger-table th { padding: 12px; background: #f8fafc; border-bottom: 2px solid #e2e8f0; font-weight: 700; color: #475569; }
    .ledger-table td { padding: 14px 12px; border-bottom: 1px solid #f1f5f9; vertical-align: top; }
    .ledger-table tr:hover td { background: #fafafa; }

    .tx-time { font-size: 0.78rem; font-weight: 600; color: var(--color-text-secondary); }
    .tx-ref { font-size: 0.75rem; background: #f1f5f9; padding: 2px 6px; border-radius: 4px; display: inline-block; margin-top: 4px; }

    .beneficiary-box { display: flex; flex-direction: column; gap: 3px; max-width: 240px; }
    .beneficiary-name { font-weight: 700; color: #0f172a; font-size: 0.88rem; }
    .campaign-link { font-size: 0.78rem; color: var(--color-primary); text-decoration: none; font-weight: 600; }
    .campaign-link:hover { text-decoration: underline; }
    .hospital-sub { font-size: 0.72rem; color: #64748b; }

    .donor-details-box { display: flex; flex-direction: column; gap: 2px; max-width: 240px; }
    .donor-name-row { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
    .anon-badge { background: #fef3c7; color: #92400e; font-size: 0.68rem; padding: 1px 6px; border-radius: 4px; font-weight: 600; }
    .donor-contact { font-size: 0.75rem; color: #475569; }
    .donor-pan { font-size: 0.75rem; font-weight: 600; color: #0284c7; }
    .donor-msg-sub { font-size: 0.72rem; font-style: italic; color: #64748b; margin-top: 3px; }

    .amount-box { display: flex; flex-direction: column; gap: 2px; }
    .amount-gross { font-size: 1.05rem; font-weight: 800; color: var(--color-primary); }
    .amount-net { font-size: 0.78rem; font-weight: 700; color: #16a34a; }
    .amount-fee, .amount-tip { font-size: 0.72rem; color: #64748b; }

    .payment-method-badge { display: flex; flex-direction: column; gap: 4px; }
    .method-tag { background: #e0f2fe; color: #0369a1; padding: 2px 8px; border-radius: 4px; font-weight: 700; font-size: 0.72rem; width: fit-content; }
    .status-completed { background: #dcfce7; color: #15803d; }
    .order-id { font-size: 0.68rem; color: #64748b; }

    .tax-80g-pill { background: #f3e8ff; color: #6b21a8; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; font-weight: 600; display: inline-block; }

    /* Queue Items */
    .campaign-queue { display: flex; flex-direction: column; gap: var(--space-4); }
    .queue-item { padding: var(--space-5); }
    .queue-top { display: flex; gap: var(--space-4); align-items: flex-start; }
    .queue-info { flex: 1; }
    .queue-title-row { display: flex; align-items: center; gap: var(--space-3); flex-wrap: wrap; margin-bottom: var(--space-2); }
    .queue-title { font-size: 1.1rem; font-weight: 700; margin: 0; }
    .status-badge { padding: 3px 10px; border-radius: 20px; font-size: 0.72rem; font-weight: 600; }
    .status-pending, .status-pending_verification { background: #fef3c7; color: #92400e; }
    .status-flagged { background: #fee2e2; color: #991b1b; }
    .status-active, .status-approved { background: #d1fae5; color: #065f46; }
    .status-rejected { background: #fee2e2; color: #991b1b; }

    .queue-meta { display: flex; gap: var(--space-3); flex-wrap: wrap; font-size: 0.82rem; color: var(--color-text-secondary); margin-bottom: var(--space-2); }
    .queue-desc { font-size: 0.88rem; color: var(--color-text-secondary); margin: 0; line-height: 1.5; }

    .score-dial {
      width: 80px; height: 80px; border-radius: 50%;
      display: flex; flex-direction: column; align-items: center; justify-content: center;
      flex-shrink: 0; border: 4px solid;
    }
    .dial-green { border-color: var(--color-secondary); color: var(--color-secondary); }
    .dial-amber { border-color: #f59e0b; color: #f59e0b; }
    .dial-red   { border-color: #ef4444; color: #ef4444; }
    .dial-num { font-size: 1.4rem; font-weight: 800; line-height: 1; }
    .dial-lbl { font-size: 0.65rem; color: var(--color-text-secondary); }

    .ai-details { margin-top: var(--space-3); padding-top: var(--space-3); border-top: 1px solid #f3f4f6; display: flex; flex-direction: column; gap: 8px; }
    .ai-dim-row { display: grid; grid-template-columns: 130px 1fr 30px; gap: 8px; align-items: center; font-size: 0.8rem; }
    .dim-bar { background: #e5e7eb; border-radius: 4px; height: 6px; overflow: hidden; }
    .dim-bar div { height: 100%; border-radius: 4px; max-width: 100%; }
    .dim-bar .green { background: var(--color-secondary); }
    .dim-bar .amber { background: #f59e0b; }
    .dim-bar .red   { background: #ef4444; }

    .red-flags { display: flex; flex-direction: column; gap: 4px; margin-top: var(--space-3); }
    .flag { background: #fef3c7; color: #92400e; border-radius: var(--radius-sm); padding: 5px 12px; font-size: 0.8rem; }

    .decision-reason-box { margin-top: 14px; }
    .reason-input { font-size: 0.85rem; padding: 8px 12px; }

    .queue-actions { display: flex; gap: var(--space-2); margin-top: var(--space-3); flex-wrap: wrap; align-items: center; }
    .btn-sm { padding: 8px 16px; font-size: 0.85rem; }
    .btn-approve { background: #d1fae5; color: #065f46; border: 1.5px solid #6ee7b7; border-radius: var(--radius-md); cursor: pointer; font-weight: 600; }
    .btn-approve:hover { background: var(--color-secondary); color: #fff; }
    .btn-info { background: #ede9fe; color: #4c1d95; border: 1.5px solid #c4b5fd; border-radius: var(--radius-md); cursor: pointer; font-weight: 600; }
    .btn-reject { background: #fee2e2; color: #991b1b; border: 1.5px solid #fca5a5; border-radius: var(--radius-md); cursor: pointer; font-weight: 600; }
    .btn-reject:hover { background: #ef4444; color: #fff; }

    .decision-msg { font-size: 0.85rem; color: var(--color-secondary); font-weight: 600; margin-top: var(--space-2); }

    .loading-state { text-align: center; padding: 60px 0; }
    .spinner {
      width: 40px; height: 40px; border: 4px solid #f3f4f6;
      border-top-color: var(--color-primary); border-radius: 50%;
      animation: spin 0.8s linear infinite; margin: 0 auto 12px;
    }
    @keyframes spin { to { transform: rotate(360deg); } }
    .empty-state { text-align: center; padding: 60px 0; }
    .empty-icon { font-size: 3rem; margin-bottom: var(--space-3); }
  `]
})
export class AdminComponent implements OnInit {
  private campaignService = inject(CampaignService);
  private donationService = inject(DonationService);
  private http = inject(HttpClient);
  public authService = inject(AuthService);

  allCampaigns = signal<Campaign[]>([]);
  loading = signal(false);
  actionLoading = signal<Record<number, boolean>>({});
  decisions = signal<Record<number, string>>({});
  notes: Record<number, string> = {};

  loginEmail = 'admin@crowdfund-trust.in';
  loginPassword = 'admin123';
  loginLoading = signal(false);
  loginError = signal('');

  activeTab = 'all';
  tabs = [
    { label: 'All Demands', value: 'all' },
    { label: 'Pending Review', value: 'PENDING_VERIFICATION' },
    { label: 'Flagged by AI', value: 'FLAGGED' },
    { label: 'Accepted (Active)', value: 'ACTIVE' },
    { label: 'Rejected', value: 'REJECTED' },
    { label: '💰 Donations & Ledger', value: 'donations' },
    { label: '📜 Audit Trail', value: 'audit_logs' }
  ];

  auditLogs = signal<any[]>([]);
  loadingAuditLogs = signal(false);

  // Donations Ledger State
  adminDonations = signal<AdminDonationItem[]>([]);
  donationSummary = signal<AdminDonationsSummary | null>(null);
  loadingDonations = signal(false);
  donationSearch = '';
  selectedCampaignFilter = 0;

  get pendingCampaigns() {
    return this.allCampaigns().filter(c => c.status === 'PENDING' || c.status === 'PENDING_VERIFICATION');
  }
  get flaggedCampaigns() {
    return this.allCampaigns().filter(c => c.status === 'FLAGGED');
  }

  filteredCampaigns = signal<Campaign[]>([]);

  ngOnInit() {
    if (this.authService.isAdmin()) {
      this.loadAll();
    }
  }

  loginAsAdmin() {
    this.loginLoading.set(true);
    this.loginError.set('');
    this.authService.login(this.loginEmail, this.loginPassword).subscribe({
      next: () => {
        this.loginLoading.set(false);
        this.loadAll();
      },
      error: (err) => {
        this.loginLoading.set(false);
        this.loginError.set(err?.error?.detail || 'Invalid admin credentials');
      }
    });
  }

  quickLoginAdmin() {
    this.loginEmail = 'admin@crowdfund-trust.in';
    this.loginPassword = 'admin123';
    this.loginAsAdmin();
  }

  setTab(tabValue: string) {
    this.activeTab = tabValue;
    if (tabValue === 'audit_logs') {
      this.loadAuditLogs();
    } else if (tabValue === 'donations') {
      this.loadAdminDonations();
    } else {
      this.updateFilter();
    }
  }

  loadAdminDonations() {
    this.loadingDonations.set(true);
    this.donationService.getAdminDonations({
      campaign_id: this.selectedCampaignFilter > 0 ? this.selectedCampaignFilter : undefined,
      search: this.donationSearch.trim() || undefined
    }).subscribe({
      next: (res) => {
        this.adminDonations.set(res.items || []);
        this.donationSummary.set(res.summary);
        this.loadingDonations.set(false);
      },
      error: () => this.loadingDonations.set(false)
    });
  }

  onSearchDonations() {
    this.loadAdminDonations();
  }

  loadAuditLogs() {
    this.loadingAuditLogs.set(true);
    this.http.get<any[]>('http://localhost:8000/api/admin/audit-logs').subscribe({
      next: (res) => {
        this.auditLogs.set(res || []);
        this.loadingAuditLogs.set(false);
      },
      error: () => this.loadingAuditLogs.set(false)
    });
  }

  loadAll() {
    this.loading.set(true);
    this.loadAdminDonations();
    this.campaignService.getAdminQueue().subscribe({
      next: (res) => {
        const list: Campaign[] = Array.isArray(res) ? res : (res.campaigns || res.items || []);
        const sorted = [...list].sort((a: Campaign, b: Campaign) =>
          ((a.ai_trust_score ?? a.authenticity_score ?? 0) - (b.ai_trust_score ?? b.authenticity_score ?? 0))
        );
        this.allCampaigns.set(sorted);
        this.updateFilter();
        this.loading.set(false);
      },
      error: (err) => {
        if (err?.status === 401 || err?.status === 403) {
          this.authService.logout();
        }
        this.loading.set(false);
      }
    });
  }

  updateFilter() {
    if (this.activeTab === 'all') {
      this.filteredCampaigns.set(this.allCampaigns());
    } else if (this.activeTab === 'PENDING_VERIFICATION') {
      this.filteredCampaigns.set(this.allCampaigns().filter(c => c.status === 'PENDING' || c.status === 'PENDING_VERIFICATION'));
    } else {
      this.filteredCampaigns.set(this.allCampaigns().filter(c => c.status === this.activeTab));
    }
  }

  decide(campaign: Campaign, decision: string) {
    this.actionLoading.update(v => ({ ...v, [campaign.id]: true }));
    const noteText = this.notes[campaign.id] || `Admin decision: ${decision}`;

    this.campaignService.adminDecision(campaign.id, decision, noteText).subscribe({
      next: () => {
        const actionLabel = decision === 'APPROVE' ? 'ACCEPTED (ACTIVE)' : decision;
        this.decisions.update(v => ({
          ...v,
          [campaign.id]: `✅ Demand ${actionLabel} by Admin`
        }));
        this.actionLoading.update(v => ({ ...v, [campaign.id]: false }));
        setTimeout(() => this.loadAll(), 1200);
      },
      error: (err) => {
        this.actionLoading.update(v => ({ ...v, [campaign.id]: false }));
        alert(err?.error?.detail || 'Failed to submit decision.');
      }
    });
  }

  getDimensions(c: Campaign): { label: string; value: number }[] {
    const ds = c.ai_dimension_scores;
    if (!ds) return [];
    return [
      { label: 'Specificity',   value: ds.specificity_score   || 0 },
      { label: 'Benchmark Fit', value: ds.benchmark_score     || 0 },
      { label: 'Documentation', value: ds.documentation_score || 0 },
      { label: 'Urgency',       value: ds.urgency_score       || 0 },
    ];
  }

  formatINR(amount: number): string {
    if (!amount) return '0';
    if (amount >= 10_000_000) return (amount / 10_000_000).toFixed(1) + 'Cr';
    if (amount >= 100_000)    return (amount / 100_000).toFixed(1) + 'L';
    if (amount >= 1000)       return (amount / 1000).toFixed(1) + 'K';
    return amount.toString();
  }
}
