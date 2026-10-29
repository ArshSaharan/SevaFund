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
          <div class="brand-logo">
            <span class="flag-circle">🇮🇳</span>
            <div class="brand-text">
              <span class="brand-title">SevaFund<span class="highlight">India</span></span>
              <span class="brand-subtitle">AI-Verified Crowdfunding</span>
            </div>
          </div>
        </a>

        <!-- Nav Links -->
        <nav class="nav-links">
          <a routerLink="/" routerLinkActive="active" [routerLinkActiveOptions]="{exact: true}">Browse Causes</a>
          <a routerLink="/create" routerLinkActive="active" class="link-ai">
            <span class="ai-sparkle">✨</span> AI Story Creator
          </a>
          <a routerLink="/admin" routerLinkActive="active" class="link-admin" *ngIf="authService.isAdmin()">
            🛡️ Admin Queue <span class="admin-pill">Admin</span>
          </a>
        </nav>

        <!-- Right Actions -->
        <div class="nav-actions">
          <!-- User Authenticated -->
          <div class="user-profile-menu" *ngIf="authService.currentUser() as user">
            <span class="user-avatar">{{ user.full_name[0] || 'U' }}</span>
            <div class="user-details">
              <span class="user-name">{{ user.full_name }}</span>
              <span class="user-tag" *ngIf="user.role === 'ADMIN'">👑 Admin</span>
              <span class="user-tag" *ngIf="user.phone_number">📱 {{ user.phone_number }}</span>
            </div>
            <button class="btn btn-sm btn-outline btn-logout" (click)="authService.logout()">Logout</button>
          </div>

          <!-- Login / Sign Up CTA -->
          <button class="btn btn-outline btn-auth" *ngIf="!authService.currentUser()" (click)="openAuthModal()">
            🔐 Sign In / Register
          </button>

          <!-- Start Fundraiser Button -->
          <a routerLink="/create" class="btn btn-primary btn-start">
            <span>+ Start a Fundraiser</span>
            <span class="zero-fee">0% Fee</span>
          </a>
        </div>
      </div>
    </header>

    <!-- Modern Multi-Method Auth Modal (Google, Mobile OTP, Email) -->
    <div class="auth-modal-overlay" *ngIf="showAuthModal()" (click)="closeAuthModal($event)">
      <div class="auth-modal card" (click)="$event.stopPropagation()">
        <button class="modal-close" (click)="showAuthModal.set(false)">✕</button>

        <div class="auth-modal-header">
          <span class="flag-icon">🇮🇳</span>
          <h2>Welcome to SevaFund India</h2>
          <p>Sign in to start fundraisers, manage donations, and view tax receipts</p>
        </div>

        <!-- Auth Tabs -->
        <div class="auth-tabs">
          <button class="tab-btn" [class.active]="authMethod === 'OTP'" (click)="authMethod = 'OTP'">
            📱 Mobile OTP
          </button>
          <button class="tab-btn" [class.active]="authMethod === 'GOOGLE'" (click)="authMethod = 'GOOGLE'">
            🌐 Google Auth
          </button>
          <button class="tab-btn" [class.active]="authMethod === 'EMAIL'" (click)="authMethod = 'EMAIL'">
            ✉️ Email / Password
          </button>
        </div>

        <!-- Tab 1: Mobile OTP -->
        <div class="auth-body" *ngIf="authMethod === 'OTP'">
          <!-- Step 1: Phone Input -->
          <div *ngIf="!otpSent()">
            <label class="form-label">Enter Indian Mobile Number</label>
            <div class="phone-input-wrap">
              <span class="phone-prefix">+91</span>
              <input type="tel" class="input phone-input" [(ngModel)]="phoneNumber" placeholder="98765 43210" maxlength="10" />
            </div>
            <button class="btn btn-primary btn-full mt-3" (click)="requestOtp()" [disabled]="otpLoading() || !phoneNumber">
              {{ otpLoading() ? 'Sending OTP…' : '📲 Send 6-Digit OTP' }}
            </button>
          </div>

          <!-- Step 2: OTP Verification -->
          <div *ngIf="otpSent()">
            <div class="otp-notice">
              <span>OTP sent to <strong>+91 {{ phoneNumber }}</strong></span>
              <button class="btn-link" (click)="otpSent.set(false)">Change number</button>
            </div>
            <label class="form-label">Enter 6-Digit Verification Code</label>
            <input type="text" class="input otp-input" [(ngModel)]="otpCode" placeholder="••••••" maxlength="6" />
            <input type="text" class="input mt-2" [(ngModel)]="fullName" placeholder="Your Name (Optional)" />
            <button class="btn btn-primary btn-full mt-3" (click)="submitOtp()" [disabled]="otpLoading() || !otpCode">
              {{ otpLoading() ? 'Verifying…' : '✓ Verify & Sign In' }}
            </button>
            <div class="dev-otp-hint" *ngIf="devOtp()">
              💡 Testing OTP code: <strong>{{ devOtp() }}</strong>
            </div>
          </div>
        </div>

        <!-- Tab 2: Google Sign-In -->
        <div class="auth-body" *ngIf="authMethod === 'GOOGLE'">
          <div class="google-box">
            <p>Sign in securely using your verified Google account. We never share your data.</p>
            <!-- Google renders its official button here -->
            <div id="google-signin-btn" class="google-btn-container"></div>
            <div *ngIf="googleLoading()" class="google-loading-msg">
              ⏳ Verifying with Google…
            </div>
            <div class="google-badge-note">
              🔒 Verified by Google OAuth 2.0 Identity Services
            </div>
          </div>
        </div>

        <!-- Tab 3: Email / Password -->
        <div class="auth-body" *ngIf="authMethod === 'EMAIL'">
          <div class="form-group">
            <label class="form-label">Email Address</label>
            <input type="email" class="input" [(ngModel)]="email" placeholder="name@example.com" />
          </div>
          <div class="form-group mt-2">
            <label class="form-label">Password</label>
            <input type="password" class="input" [(ngModel)]="password" placeholder="••••••••" />
          </div>
          <div class="form-group mt-2" *ngIf="isRegisterMode">
            <label class="form-label">Full Name</label>
            <input type="text" class="input" [(ngModel)]="fullName" placeholder="Your Full Name" />
          </div>
          <button class="btn btn-primary btn-full mt-3" (click)="submitEmailAuth()" [disabled]="emailLoading()">
            {{ emailLoading() ? 'Processing…' : (isRegisterMode ? 'Create Account' : 'Sign In') }}
          </button>
          <div class="auth-toggle-line mt-2">
            <span *ngIf="!isRegisterMode">Don't have an account? <button class="btn-link" (click)="isRegisterMode = true">Register</button></span>
            <span *ngIf="isRegisterMode">Already have an account? <button class="btn-link" (click)="isRegisterMode = false">Sign In</button></span>
          </div>
        </div>

        <!-- Error Feedback -->
        <div class="error-msg mt-3" *ngIf="authError()">
          {{ authError() }}
        </div>
      </div>
    </div>
  `,
  styles: [`
    .navbar {
      background: white;
      border-bottom: 1px solid var(--gray-200);
      position: sticky;
      top: 0;
      z-index: 100;
      box-shadow: 0 1px 3px rgba(0,0,0,0.02);
    }
    .nav-content {
      display: flex;
      align-items: center;
      justify-content: space-between;
      height: 72px;
    }
    .brand { display: flex; align-items: center; text-decoration: none; }
    .brand-logo { display: flex; align-items: center; gap: 12px; }
    .flag-circle { font-size: 26px; line-height: 1; }
    .brand-title {
      font-family: 'Plus Jakarta Sans', sans-serif;
      font-size: 20px;
      font-weight: 800;
      color: var(--navy);
      letter-spacing: -0.5px;
      display: block;
    }
    .brand-title .highlight { color: var(--primary); }
    .brand-subtitle {
      font-size: 11px;
      font-weight: 600;
      color: var(--secondary);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      display: block;
    }
    .nav-links { display: flex; align-items: center; gap: 24px; }
    .nav-links a { font-size: 15px; font-weight: 500; color: var(--gray-600); transition: color 0.2s; }
    .nav-links a:hover, .nav-links a.active { color: var(--primary); }
    .link-ai { color: #6366F1 !important; font-weight: 600 !important; }
    .link-admin { color: #DC2626 !important; font-weight: 600 !important; display: flex; align-items: center; gap: 6px; }
    .admin-pill { background: #fee2e2; color: #991b1b; padding: 2px 6px; border-radius: 12px; font-size: 10px; font-weight: 700; }

    .nav-actions { display: flex; align-items: center; gap: 14px; }
    .btn-auth { font-size: 0.85rem; padding: 8px 14px; font-weight: 600; }
    .btn-start { flex-direction: column; padding: 8px 18px; line-height: 1.1; }
    .zero-fee { font-size: 10px; opacity: 0.9; font-weight: 400; }

    .user-profile-menu { display: flex; align-items: center; gap: 10px; }
    .user-avatar {
      width: 36px; height: 36px; border-radius: 50%; background: var(--primary);
      color: #fff; font-weight: 700; display: flex; align-items: center; justify-content: center;
    }
    .user-details { display: flex; flex-direction: column; font-size: 0.8rem; }
    .user-name { font-weight: 700; color: var(--navy); }
    .user-tag { font-size: 0.7rem; color: var(--gray-500); }
    .btn-logout { font-size: 0.72rem; padding: 4px 8px; }

    /* Auth Modal */
    .auth-modal-overlay {
      position: fixed; top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(15, 23, 42, 0.65);
      backdrop-filter: blur(4px);
      display: flex; align-items: center; justify-content: center;
      z-index: 1000; padding: 20px;
    }
    .auth-modal {
      width: 100%; max-width: 440px; background: #fff; border-radius: var(--radius-lg);
      padding: 32px 28px; position: relative; box-shadow: 0 20px 40px rgba(0,0,0,0.2);
    }
    .modal-close {
      position: absolute; top: 16px; right: 16px; background: transparent; border: none;
      font-size: 1.2rem; cursor: pointer; color: var(--gray-400);
    }
    .modal-close:hover { color: var(--navy); }
    .auth-modal-header { text-align: center; margin-bottom: 20px; }
    .auth-modal-header h2 { font-size: 1.3rem; font-weight: 800; margin-top: 6px; }
    .auth-modal-header p { font-size: 0.85rem; color: var(--gray-500); margin-top: 4px; }
    .flag-icon { font-size: 2rem; }

    .auth-tabs { display: flex; gap: 6px; background: #f1f5f9; padding: 4px; border-radius: var(--radius-md); margin-bottom: 20px; }
    .auth-tabs .tab-btn {
      flex: 1; padding: 8px 10px; border-radius: var(--radius-sm); border: none;
      background: transparent; font-size: 0.78rem; font-weight: 600; cursor: pointer; color: var(--gray-600);
      transition: all 0.15s;
    }
    .auth-tabs .tab-btn.active { background: #fff; color: var(--navy); box-shadow: 0 2px 4px rgba(0,0,0,0.06); }

    .phone-input-wrap { display: flex; align-items: center; gap: 8px; }
    .phone-prefix {
      background: #f1f5f9; padding: 10px 14px; border-radius: var(--radius-md);
      font-weight: 700; color: var(--gray-700); font-size: 0.95rem; border: 1.5px solid #d1d5db;
    }
    .phone-input { flex: 1; font-size: 1.1rem; letter-spacing: 1px; font-weight: 600; }
    .otp-input { font-size: 1.5rem; letter-spacing: 8px; text-align: center; font-weight: 700; }
    .otp-notice { display: flex; justify-content: space-between; font-size: 0.82rem; margin-bottom: 12px; }
    .btn-link { background: none; border: none; color: var(--primary); font-weight: 600; cursor: pointer; text-decoration: underline; font-size: inherit; }
    .dev-otp-hint { margin-top: 10px; background: #fef3c7; color: #92400e; padding: 8px 12px; border-radius: var(--radius-sm); font-size: 0.8rem; text-align: center; }

    .google-btn-container {
      display: flex; justify-content: center; padding: 16px 0;
      min-height: 50px;
    }
    .google-loading-msg {
      text-align: center; font-size: 0.85rem; color: var(--gray-600);
      padding: 8px; margin-top: 8px;
    }
    .btn-google {
      display: flex; align-items: center; justify-content: center; gap: 12px;
      background: #fff; border: 1.5px solid #dadce0; color: #3c4043; font-weight: 600;
      padding: 12px; border-radius: var(--radius-md); cursor: pointer; transition: background 0.15s;
    }
    .btn-google:hover { background: #f8fafd; border-color: #c2c7d0; }
    .google-badge-note { text-align: center; font-size: 0.75rem; color: var(--gray-500); margin-top: 14px; }

    .form-label { display: block; font-size: 0.82rem; font-weight: 600; margin-bottom: 6px; color: var(--gray-700); }
    .auth-toggle-line { text-align: center; font-size: 0.82rem; color: var(--gray-500); }
    .error-msg { color: #ef4444; font-size: 0.82rem; text-align: center; }
    .btn-full { width: 100%; padding: 12px; }
    .mt-2 { margin-top: 8px; }
    .mt-3 { margin-top: 14px; }
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
    // Render the Google Sign-In button when the GOOGLE tab is active
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
          width: 380,
          text: 'signin_with',
          shape: 'rectangular',
          logo_alignment: 'left',
        });
        this.googleBtnRendered = true;
      }
    }
    // Reset render flag when Google tab is not active
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
