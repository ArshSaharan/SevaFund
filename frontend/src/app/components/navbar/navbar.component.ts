import { Component, inject, signal, AfterViewChecked, NgZone } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-navbar',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, RouterLinkActive],
  template: `
    <header class="navbar">
      <div class="container nav-content">
        <!-- Brand -->
        <a routerLink="/" class="brand">
          <div class="brand-mark">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M12 2L3 7V12C3 17.5 6.8 21.7 12 23C17.2 21.7 21 17.5 21 12V7L12 2Z" fill="#FF6B00" fill-opacity="0.15" stroke="#FF6B00" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              <path d="M9 12L11 14L15 10" stroke="#00A86B" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </div>
          <div class="brand-text">
            <span class="brand-title">SevaFund<span class="brand-highlight">India</span></span>
            <span class="brand-subtitle">AI-Verified Crowdfunding</span>
          </div>
        </a>

        <!-- Desktop Navigation -->
        <nav class="nav-links">
          <a routerLink="/" routerLinkActive="active" [routerLinkActiveOptions]="{exact: true}" class="nav-item">
            Explore Causes
          </a>
          <a routerLink="/create" routerLinkActive="active" class="nav-item nav-item-ai">
            <span class="sparkle-icon">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2L14.4 8.6L21 11L14.4 13.4L12 20L9.6 13.4L3 11L9.6 8.6L12 2Z"/>
              </svg>
            </span>
            AI Story Creator
          </a>
          <a routerLink="/admin" routerLinkActive="active" class="nav-item nav-item-admin" *ngIf="authService.isAdmin()">
            <span class="shield-dot"></span>
            Moderation Portal
            <span class="admin-badge">Admin</span>
          </a>
        </nav>

        <!-- Right Side Actions -->
        <div class="nav-actions">
          <!-- Logged In User Pill -->
          <div class="user-pill" *ngIf="authService.currentUser() as user">
            <div class="user-avatar">{{ user.full_name ? user.full_name[0] : 'U' }}</div>
            <div class="user-meta">
              <span class="user-name">{{ user.full_name }}</span>
              <span class="user-role" *ngIf="user.role === 'ADMIN'">Administrator</span>
              <span class="user-role" *ngIf="user.role !== 'ADMIN'">Supporter</span>
            </div>
            <button class="btn btn-ghost btn-sm logout-btn" (click)="authService.logout()" title="Log out">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                <polyline points="16 17 21 12 16 7"></polyline>
                <line x1="21" y1="12" x2="9" y2="12"></line>
              </svg>
            </button>
          </div>

          <!-- Log In Button (Guest) -->
          <button class="btn btn-outline btn-sm auth-trigger" *ngIf="!authService.currentUser()" (click)="openAuthModal()">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
              <circle cx="12" cy="7" r="4"></circle>
            </svg>
            Sign In
          </button>

          <!-- Primary CTA Button -->
          <a routerLink="/create" class="btn btn-primary btn-sm start-btn">
            <span>Start a Fundraiser</span>
            <span class="btn-micro-badge">0% Fee</span>
          </a>
        </div>
      </div>
    </header>

    <!-- Authentication Modal Overlay -->
    <div class="auth-modal-overlay" *ngIf="showAuthModal()" (click)="closeAuthModal($event)">
      <div class="auth-card" (click)="$event.stopPropagation()">
        <!-- Close Button -->
        <button class="modal-close" (click)="showAuthModal.set(false)" aria-label="Close modal">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>

        <!-- Header -->
        <div class="auth-card-header">
          <div class="auth-badge-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#FF6B00" stroke-width="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
            </svg>
          </div>
          <h2>Welcome to SevaFund</h2>
          <p>Access your tax receipts, donor dashboard, and fundraiser management</p>
        </div>

        <!-- Auth Tabs -->
        <div class="auth-tabs">
          <button class="tab-btn" [class.active]="authMethod === 'OTP'" (click)="authMethod = 'OTP'">
            Mobile OTP
          </button>
          <button class="tab-btn" [class.active]="authMethod === 'GOOGLE'" (click)="authMethod = 'GOOGLE'">
            Google Auth
          </button>
          <button class="tab-btn" [class.active]="authMethod === 'EMAIL'" (click)="authMethod = 'EMAIL'">
            Email / Password
          </button>
        </div>

        <!-- Tab 1: Mobile OTP -->
        <div class="auth-body" *ngIf="authMethod === 'OTP'">
          <div *ngIf="!otpSent()">
            <label class="form-label">Indian Mobile Number</label>
            <div class="phone-input-wrap">
              <span class="phone-prefix">+91</span>
              <input
                type="tel"
                class="input phone-input"
                [(ngModel)]="phoneNumber"
                placeholder="98765 43210"
                maxlength="10"
                autocomplete="tel"
              />
            </div>
            <button
              class="btn btn-primary btn-full mt-4"
              (click)="requestOtp()"
              [disabled]="otpLoading() || !phoneNumber || phoneNumber.length < 10"
            >
              {{ otpLoading() ? 'Sending verification code…' : 'Send 6-Digit OTP' }}
            </button>
          </div>

          <div *ngIf="otpSent()" class="otp-stage">
            <div class="otp-notice">
              <span>Code sent to <strong>+91 {{ phoneNumber }}</strong></span>
              <button class="btn-link" (click)="otpSent.set(false)">Change number</button>
            </div>

            <label class="form-label">Enter 6-Digit Verification Code</label>
            <input
              type="text"
              class="input otp-input"
              [(ngModel)]="otpCode"
              placeholder="••••••"
              maxlength="6"
              inputmode="numeric"
            />

            <label class="form-label mt-3">Full Name (optional for new accounts)</label>
            <input
              type="text"
              class="input"
              [(ngModel)]="fullName"
              placeholder="Your full name"
            />

            <button
              class="btn btn-primary btn-full mt-4"
              (click)="submitOtp()"
              [disabled]="otpLoading() || !otpCode || otpCode.length < 4"
            >
              {{ otpLoading() ? 'Verifying…' : 'Verify & Sign In' }}
            </button>

            <div class="dev-otp-hint" *ngIf="devOtp()">
              <span>Demo OTP:</span> <strong>{{ devOtp() }}</strong>
            </div>
          </div>
        </div>

        <!-- Tab 2: Google Sign-In -->
        <div class="auth-body" *ngIf="authMethod === 'GOOGLE'">
          <div class="google-auth-container">
            <p class="google-intro">
              Fast, passwordless sign-in with your authenticated Google account.
            </p>
            <div id="google-signin-btn" class="google-btn-box"></div>
            <div *ngIf="googleLoading()" class="google-loading-msg">
              Verifying credential with server…
            </div>
            <div class="google-security-note">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
              </svg>
              Protected by Google OAuth 2.0 Identity Services
            </div>
          </div>
        </div>

        <!-- Tab 3: Email / Password -->
        <div class="auth-body" *ngIf="authMethod === 'EMAIL'">
          <div class="form-group">
            <label class="form-label">Email Address</label>
            <input type="email" class="input" [(ngModel)]="email" placeholder="name@example.com" autocomplete="email" />
          </div>

          <div class="form-group mt-3">
            <label class="form-label">Password</label>
            <input type="password" class="input" [(ngModel)]="password" placeholder="••••••••" autocomplete="current-password" />
          </div>

          <div class="form-group mt-3" *ngIf="isRegisterMode">
            <label class="form-label">Your Full Name</label>
            <input type="text" class="input" [(ngModel)]="fullName" placeholder="Enter your full name" />
          </div>

          <button class="btn btn-primary btn-full mt-4" (click)="submitEmailAuth()" [disabled]="emailLoading()">
            {{ emailLoading() ? 'Processing…' : (isRegisterMode ? 'Create Account' : 'Sign In') }}
          </button>

          <div class="auth-toggle-row mt-3">
            <span *ngIf="!isRegisterMode">New to SevaFund? <button class="btn-link" (click)="isRegisterMode = true">Create an account</button></span>
            <span *ngIf="isRegisterMode">Already registered? <button class="btn-link" (click)="isRegisterMode = false">Sign in</button></span>
          </div>
        </div>

        <!-- Error Feedback -->
        <div class="auth-error-banner mt-3" *ngIf="authError()">
          {{ authError() }}
        </div>
      </div>
    </div>
  `,
  styles: [`
    .navbar {
      position: sticky;
      top: 0;
      z-index: 100;
      background: rgba(255, 255, 255, 0.85);
      backdrop-filter: blur(16px) saturate(180%);
      -webkit-backdrop-filter: blur(16px) saturate(180%);
      border-bottom: 1px solid var(--border);
      transition: background 0.3s ease, border-color 0.3s ease;
    }

    .nav-content {
      display: flex;
      align-items: center;
      justify-content: space-between;
      height: 68px;
    }

    /* Brand Logo */
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      text-decoration: none;
    }

    .brand-mark {
      width: 40px;
      height: 40px;
      border-radius: var(--radius-md);
      background: var(--primary-light);
      border: 1px solid rgba(255, 107, 0, 0.2);
      display: flex;
      align-items: center;
      justify-content: center;
      transition: transform 0.2s var(--ease-spring);
    }

    .brand:hover .brand-mark {
      transform: scale(1.05);
    }

    .brand-text {
      display: flex;
      flex-direction: column;
    }

    .brand-title {
      font-family: var(--font-heading);
      font-size: 19px;
      font-weight: 800;
      color: var(--slate-900);
      letter-spacing: -0.02em;
      line-height: 1.15;
    }

    .brand-highlight {
      color: var(--primary);
    }

    .brand-subtitle {
      font-size: 10.5px;
      font-weight: 600;
      color: var(--secondary);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }

    /* Nav Links */
    .nav-links {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .nav-item {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 8px 14px;
      border-radius: var(--radius-md);
      font-size: 14px;
      font-weight: 600;
      color: var(--slate-600);
      transition: all 0.15s ease;
      text-decoration: none;
    }

    .nav-item:hover {
      color: var(--slate-900);
      background: var(--slate-100);
    }

    .nav-item.active {
      color: var(--primary);
      background: var(--primary-light);
    }

    .nav-item-ai {
      color: #6366F1;
    }

    .nav-item-ai:hover {
      color: #4F46E5;
      background: #EEF2FF;
    }

    .sparkle-icon {
      display: inline-flex;
      color: #818CF8;
    }

    .nav-item-admin {
      color: #DC2626;
    }

    .shield-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: #DC2626;
    }

    .admin-badge {
      font-size: 10px;
      font-weight: 700;
      background: #FEE2E2;
      color: #991B1B;
      padding: 2px 6px;
      border-radius: var(--radius-full);
      text-transform: uppercase;
      letter-spacing: 0.03em;
    }

    /* Actions */
    .nav-actions {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .auth-trigger {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 13.5px;
    }

    .start-btn {
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }

    .btn-micro-badge {
      font-size: 10px;
      font-weight: 700;
      background: rgba(255, 255, 255, 0.25);
      padding: 1px 6px;
      border-radius: var(--radius-full);
      letter-spacing: 0.02em;
    }

    /* User Pill */
    .user-pill {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 4px 8px 4px 6px;
      background: var(--slate-100);
      border: 1px solid var(--border);
      border-radius: var(--radius-full);
    }

    .user-avatar {
      width: 30px;
      height: 30px;
      border-radius: 50%;
      background: var(--primary);
      color: #FFFFFF;
      font-weight: 700;
      font-size: 13px;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .user-meta {
      display: flex;
      flex-direction: column;
      line-height: 1.2;
    }

    .user-name {
      font-size: 13px;
      font-weight: 600;
      color: var(--slate-900);
      max-width: 120px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .user-role {
      font-size: 10.5px;
      color: var(--slate-500);
    }

    .logout-btn {
      padding: 4px;
      color: var(--slate-400);
      border-radius: 50%;
    }

    .logout-btn:hover {
      color: var(--danger);
      background: var(--danger-light);
    }

    /* Auth Modal */
    .auth-modal-overlay {
      position: fixed;
      inset: 0;
      background: rgba(15, 23, 42, 0.55);
      backdrop-filter: blur(6px);
      -webkit-backdrop-filter: blur(6px);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 1000;
      padding: 20px;
      animation: fadeIn 0.2s ease-out;
    }

    .auth-card {
      width: 100%;
      max-width: 440px;
      background: var(--surface);
      border-radius: var(--radius-xl);
      border: 1px solid var(--border);
      box-shadow: var(--shadow-xl);
      padding: 32px 28px;
      position: relative;
    }

    .modal-close {
      position: absolute;
      top: 18px;
      right: 18px;
      width: 32px;
      height: 32px;
      display: flex;
      align-items: center;
      justify-content: center;
      background: var(--slate-100);
      border: none;
      border-radius: 50%;
      color: var(--slate-500);
      cursor: pointer;
      transition: all 0.15s ease;
    }

    .modal-close:hover {
      background: var(--slate-200);
      color: var(--slate-900);
    }

    .auth-card-header {
      text-align: center;
      margin-bottom: 22px;
    }

    .auth-badge-icon {
      width: 44px;
      height: 44px;
      border-radius: 50%;
      background: var(--primary-light);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      margin-bottom: 12px;
    }

    .auth-card-header h2 {
      font-size: 20px;
      font-weight: 800;
      color: var(--slate-900);
      letter-spacing: -0.01em;
    }

    .auth-card-header p {
      font-size: 13.5px;
      color: var(--slate-500);
      margin-top: 4px;
      line-height: 1.5;
    }

    /* Tabs */
    .auth-tabs {
      display: flex;
      gap: 4px;
      background: var(--slate-100);
      padding: 4px;
      border-radius: var(--radius-lg);
      margin-bottom: 22px;
    }

    .tab-btn {
      flex: 1;
      padding: 8px 10px;
      border-radius: var(--radius-md);
      border: none;
      background: transparent;
      font-size: 12.5px;
      font-weight: 600;
      color: var(--slate-600);
      cursor: pointer;
      transition: all 0.15s ease;
    }

    .tab-btn.active {
      background: #FFFFFF;
      color: var(--slate-900);
      box-shadow: var(--shadow-xs);
    }

    /* Phone Input Wrap */
    .phone-input-wrap {
      display: flex;
      align-items: center;
      gap: 8px;
    }

    .phone-prefix {
      display: inline-flex;
      align-items: center;
      padding: 10px 14px;
      background: var(--slate-100);
      border: 1.5px solid var(--border);
      border-radius: var(--radius-md);
      font-weight: 700;
      font-size: 14px;
      color: var(--slate-700);
    }

    .phone-input {
      font-size: 15px;
      font-weight: 600;
      letter-spacing: 0.05em;
    }

    .otp-input {
      font-size: 22px;
      font-weight: 800;
      letter-spacing: 0.3em;
      text-align: center;
      font-family: var(--font-mono);
    }

    .otp-notice {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 12.5px;
      color: var(--slate-600);
      margin-bottom: 14px;
    }

    .btn-link {
      background: none;
      border: none;
      color: var(--primary);
      font-weight: 600;
      cursor: pointer;
      text-decoration: underline;
      font-size: inherit;
    }

    .dev-otp-hint {
      margin-top: 14px;
      padding: 8px 12px;
      border-radius: var(--radius-md);
      background: var(--warning-light);
      border: 1px solid var(--warning-border);
      font-size: 12px;
      color: #92400E;
      text-align: center;
    }

    /* Google Container */
    .google-auth-container {
      text-align: center;
      padding: 10px 0;
    }

    .google-intro {
      font-size: 13.5px;
      color: var(--slate-600);
      margin-bottom: 16px;
      line-height: 1.5;
    }

    .google-btn-box {
      display: flex;
      justify-content: center;
      min-height: 48px;
    }

    .google-loading-msg {
      font-size: 12.5px;
      color: var(--slate-500);
      margin-top: 10px;
    }

    .google-security-note {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 11.5px;
      color: var(--slate-400);
      margin-top: 16px;
    }

    .auth-toggle-row {
      text-align: center;
      font-size: 13px;
      color: var(--slate-500);
    }

    .auth-error-banner {
      padding: 10px 14px;
      border-radius: var(--radius-md);
      background: var(--danger-light);
      border: 1px solid var(--danger-border);
      font-size: 12.5px;
      color: var(--danger);
      text-align: center;
    }

    @media (max-width: 768px) {
      .nav-links {
        display: none;
      }
      .brand-subtitle {
        display: none;
      }
      .user-meta {
        display: none;
      }
    }
  `]
})
export class NavbarComponent implements AfterViewChecked {
  public authService = inject(AuthService);
  private ngZone = inject(NgZone);

  showAuthModal = signal(false);
  authMethod: 'OTP' | 'GOOGLE' | 'EMAIL' = 'OTP';

  // OTP State
  phoneNumber = '';
  otpCode = '';
  fullName = '';
  otpSent = signal(false);
  otpLoading = signal(false);
  devOtp = signal('');

  // Google State
  googleLoading = signal(false);
  private googleBtnRendered = false;

  // Email State
  email = '';
  password = '';
  isRegisterMode = false;
  emailLoading = signal(false);

  authError = signal('');

  ngAfterViewChecked() {
    if (this.authMethod === 'GOOGLE' && this.showAuthModal() && !this.googleBtnRendered) {
      const container = document.getElementById('google-signin-btn');
      const goog = (window as any).google;
      if (container && goog?.accounts?.id) {
        const clientId = '716731888527-pjc53ng4c8kbvrptjg1962o07mqge508.apps.googleusercontent.com';
        goog.accounts.id.initialize({
          client_id: clientId,
          callback: (response: any) => {
            this.ngZone.run(() => {
              this.handleGoogleCredential(response);
            });
          },
          auto_select: false,
        });
        goog.accounts.id.renderButton(container, {
          theme: 'outline',
          size: 'large',
          width: 360,
          text: 'signin_with',
          shape: 'rectangular',
          logo_alignment: 'left',
        });
        this.googleBtnRendered = true;
      }
    }
    if (this.authMethod !== 'GOOGLE' || !this.showAuthModal()) {
      this.googleBtnRendered = false;
    }
  }

  openAuthModal() {
    this.authError.set('');
    this.showAuthModal.set(true);
  }

  closeAuthModal(event: MouseEvent) {
    this.showAuthModal.set(false);
  }

  requestOtp() {
    this.otpLoading.set(true);
    this.authError.set('');
    this.authService.sendMobileOtp(this.phoneNumber).subscribe({
      next: (res) => {
        this.otpSent.set(true);
        this.otpLoading.set(false);
        if (res.dev_otp) this.devOtp.set(res.dev_otp);
      },
      error: (err) => {
        this.otpLoading.set(false);
        this.authError.set(err?.error?.detail || 'Failed to send OTP.');
      }
    });
  }

  submitOtp() {
    this.otpLoading.set(true);
    this.authError.set('');
    this.authService.verifyMobileOtp(this.phoneNumber, this.otpCode, this.fullName || undefined).subscribe({
      next: () => {
        this.otpLoading.set(false);
        this.showAuthModal.set(false);
      },
      error: (err) => {
        this.otpLoading.set(false);
        this.authError.set(err?.error?.detail || 'Invalid OTP code.');
      }
    });
  }

  private handleGoogleCredential(response: any) {
    this.googleLoading.set(true);
    this.authError.set('');
    if (response?.credential) {
      this.authService.loginWithGoogle(response.credential).subscribe({
        next: () => {
          this.googleLoading.set(false);
          this.showAuthModal.set(false);
        },
        error: (err: any) => {
          this.googleLoading.set(false);
          this.authError.set(err?.error?.detail || 'Google sign-in failed on server.');
        }
      });
    } else {
      this.googleLoading.set(false);
      this.authError.set('No credential received from Google. Please try again.');
    }
  }

  submitEmailAuth() {
    this.emailLoading.set(true);
    this.authError.set('');
    if (this.isRegisterMode) {
      this.authService.register({
        email: this.email,
        password: this.password,
        full_name: this.fullName || 'Supporter'
      }).subscribe({
        next: () => {
          this.emailLoading.set(false);
          this.showAuthModal.set(false);
        },
        error: (err) => {
          this.emailLoading.set(false);
          this.authError.set(err?.error?.detail || 'Registration failed.');
        }
      });
    } else {
      this.authService.login(this.email, this.password).subscribe({
        next: () => {
          this.emailLoading.set(false);
          this.showAuthModal.set(false);
        },
        error: (err) => {
          this.emailLoading.set(false);
          this.authError.set(err?.error?.detail || 'Invalid email or password.');
        }
      });
    }
  }
}
