import {
  AfterViewChecked,
  AfterViewInit,
  Component,
  ElementRef,
  HostListener,
  NgZone,
  OnDestroy,
  ViewChild,
  inject,
  signal,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { NavigationStart, Router, RouterLink, RouterLinkActive } from '@angular/router';
import { Subscription, filter } from 'rxjs';
import { AuthService } from '../../services/auth.service';
import { ThemeService } from '../../services/theme.service';
import { SmoothScrollService } from '../../services/smooth-scroll.service';
import { gsap, ScrollTrigger, isBrowser } from '../../animation/gsap';

interface NavLink {
  path: string;
  label: string;
  exact?: boolean;
}

const GOOGLE_CLIENT_ID = '716731888527-pjc53ng4c8kbvrptjg1962o07mqge508.apps.googleusercontent.com';

// Google Identity Services is loaded lazily, the first time the Google tab is opened.
let gsiLoader: Promise<void> | undefined;

function loadGoogleIdentity(): Promise<void> {
  if ((window as any).google?.accounts?.id) return Promise.resolve();
  gsiLoader ??= new Promise<void>((resolve, reject) => {
    const script = document.createElement('script');
    script.src = 'https://accounts.google.com/gsi/client';
    script.async = true;
    script.onload = () => resolve();
    script.onerror = () => {
      script.remove();
      gsiLoader = undefined; // allow a retry next time the tab is opened
      reject(new Error('Failed to load Google Identity Services'));
    };
    document.head.appendChild(script);
  });
  return gsiLoader;
}

@Component({
  selector: 'app-navbar',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, RouterLinkActive],
  template: `
    <header class="site-header" #header>
      <div class="container nav-inner">
        <!-- Brand -->
        <a routerLink="/" class="brand" aria-label="SevaFund India — home">
          <span class="brand-mark" aria-hidden="true">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
              <path d="M12 2L3 7V12C3 17.5 6.8 21.7 12 23C17.2 21.7 21 17.5 21 12V7L12 2Z" fill="currentColor" fill-opacity="0.16" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
              <path d="M8.5 12.2L11 14.7L15.5 9.8" stroke="var(--leaf)" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </span>
          <span class="brand-word">SevaFund</span>
          <span class="brand-tag">India</span>
        </a>

        <!-- Desktop navigation -->
        <nav class="nav-links" aria-label="Primary">
          <a
            *ngFor="let link of links"
            [routerLink]="link.path"
            routerLinkActive="active"
            [routerLinkActiveOptions]="{ exact: !!link.exact }"
            class="nav-link"
          >{{ link.label }}</a>
          <a
            *ngIf="authService.isAdmin()"
            routerLink="/admin"
            routerLinkActive="active"
            class="nav-link nav-link-admin"
          >Moderation</a>
        </nav>

        <!-- Actions -->
        <div class="nav-actions">
          <button
            type="button"
            class="icon-btn theme-toggle"
            (click)="toggleTheme($event)"
            [attr.aria-label]="theme.theme() === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'"
            [attr.title]="theme.theme() === 'dark' ? 'Light theme' : 'Dark theme'"
          >
            <svg *ngIf="theme.theme() === 'light'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>
            </svg>
            <svg *ngIf="theme.theme() === 'dark'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <circle cx="12" cy="12" r="4.2"/>
              <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>
            </svg>
          </button>

          <!-- Signed-in user -->
          <div class="user-pill" *ngIf="authService.currentUser() as user">
            <div class="user-avatar" aria-hidden="true">{{ user.full_name ? user.full_name[0] : 'U' }}</div>
            <div class="user-meta">
              <span class="user-name">{{ user.full_name }}</span>
              <span class="user-role">{{ user.role === 'ADMIN' ? 'Administrator' : 'Supporter' }}</span>
            </div>
            <button class="icon-btn logout-btn" type="button" (click)="authService.logout()" aria-label="Log out" title="Log out">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                <polyline points="16 17 21 12 16 7"></polyline>
                <line x1="21" y1="12" x2="9" y2="12"></line>
              </svg>
            </button>
          </div>

          <button class="btn btn-outline btn-sm sign-in" type="button" *ngIf="!authService.currentUser()" (click)="openAuthModal()">
            Sign in
          </button>

          <a routerLink="/create" class="btn btn-primary btn-sm start-btn">
            Start a fundraiser
          </a>

          <button
            type="button"
            class="icon-btn menu-toggle"
            (click)="toggleMenu()"
            [attr.aria-expanded]="menuOpen()"
            aria-controls="mobile-menu"
            [attr.aria-label]="menuOpen() ? 'Close menu' : 'Open menu'"
          >
            <span class="burger" [class.open]="menuOpen()" aria-hidden="true"><span></span><span></span></span>
          </button>
        </div>
      </div>

      <div class="scroll-progress" aria-hidden="true"><span #progressBar></span></div>
    </header>

    <!-- Mobile menu -->
    <div
      id="mobile-menu"
      class="mobile-menu"
      [class.open]="menuOpen()"
      [attr.aria-hidden]="!menuOpen()"
      [attr.inert]="menuOpen() ? null : ''"
      data-lenis-prevent
    >
      <nav class="mobile-nav" aria-label="Mobile">
        <a
          *ngFor="let link of mobileLinks; let i = index"
          [routerLink]="link.path"
          routerLinkActive="active"
          [routerLinkActiveOptions]="{ exact: !!link.exact }"
          class="mobile-link"
          [style.--i]="i"
          (click)="closeMenu()"
        >
          <span class="mobile-index">{{ (i + 1).toString().padStart(2, '0') }}</span>
          <span>{{ link.label }}</span>
        </a>
      </nav>
      <div class="mobile-foot">
        <a routerLink="/create" class="btn btn-primary btn-lg" (click)="closeMenu()">Start a fundraiser</a>
        <button *ngIf="!authService.currentUser()" type="button" class="btn btn-outline btn-lg" (click)="closeMenu(); openAuthModal()">Sign in</button>
      </div>
    </div>

    <!-- Authentication modal -->
    <div class="auth-modal-overlay" *ngIf="showAuthModal()" (click)="closeAuthModal()" data-lenis-prevent>
      <div class="auth-card" role="dialog" aria-modal="true" aria-labelledby="auth-title" (click)="$event.stopPropagation()">
        <button class="modal-close" type="button" (click)="closeAuthModal()" aria-label="Close sign-in">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>

        <div class="auth-card-header">
          <div class="auth-badge-icon" aria-hidden="true">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
            </svg>
          </div>
          <h2 id="auth-title">Welcome to SevaFund</h2>
          <p>Access your tax receipts, donor dashboard, and fundraiser management</p>
        </div>

        <div class="auth-tabs" role="tablist">
          <button type="button" role="tab" class="tab-btn" [class.active]="authMethod === 'OTP'" [attr.aria-selected]="authMethod === 'OTP'" (click)="authMethod = 'OTP'">Mobile OTP</button>
          <button type="button" role="tab" class="tab-btn" [class.active]="authMethod === 'GOOGLE'" [attr.aria-selected]="authMethod === 'GOOGLE'" (click)="authMethod = 'GOOGLE'">Google</button>
          <button type="button" role="tab" class="tab-btn" [class.active]="authMethod === 'EMAIL'" [attr.aria-selected]="authMethod === 'EMAIL'" (click)="authMethod = 'EMAIL'">Email</button>
        </div>

        <!-- Mobile OTP -->
        <div class="auth-body" *ngIf="authMethod === 'OTP'">
          <div *ngIf="!otpSent()">
            <label class="form-label" for="auth-phone">Indian mobile number</label>
            <div class="phone-input-wrap">
              <span class="phone-prefix">+91</span>
              <input
                id="auth-phone"
                type="tel"
                class="input phone-input"
                [(ngModel)]="phoneNumber"
                placeholder="98765 43210"
                maxlength="10"
                autocomplete="tel"
              />
            </div>
            <button
              type="button"
              class="btn btn-primary btn-full mt-4"
              (click)="requestOtp()"
              [disabled]="otpLoading() || !phoneNumber || phoneNumber.length < 10"
            >
              {{ otpLoading() ? 'Sending verification code…' : 'Send 6-digit OTP' }}
            </button>
          </div>

          <div *ngIf="otpSent()" class="otp-stage">
            <div class="otp-notice">
              <span>Code sent to <strong>+91 {{ phoneNumber }}</strong></span>
              <button type="button" class="btn-link" (click)="otpSent.set(false)">Change number</button>
            </div>

            <label class="form-label" for="auth-otp">6-digit verification code</label>
            <input
              id="auth-otp"
              type="text"
              class="input otp-input"
              [(ngModel)]="otpCode"
              placeholder="••••••"
              maxlength="6"
              inputmode="numeric"
              autocomplete="one-time-code"
            />

            <label class="form-label mt-3" for="auth-otp-name">Full name (optional for new accounts)</label>
            <input id="auth-otp-name" type="text" class="input" [(ngModel)]="fullName" placeholder="Your full name" />

            <button
              type="button"
              class="btn btn-primary btn-full mt-4"
              (click)="submitOtp()"
              [disabled]="otpLoading() || !otpCode || otpCode.length < 4"
            >
              {{ otpLoading() ? 'Verifying…' : 'Verify & sign in' }}
            </button>

            <div class="dev-otp-hint" *ngIf="devOtp()">
              <span>Demo OTP:</span> <strong>{{ devOtp() }}</strong>
            </div>
          </div>
        </div>

        <!-- Google -->
        <div class="auth-body" *ngIf="authMethod === 'GOOGLE'">
          <div class="google-auth-container">
            <p class="google-intro">Fast, passwordless sign-in with your Google account.</p>
            <div id="google-signin-btn" class="google-btn-box"></div>
            <div *ngIf="googleLoading()" class="google-loading-msg">Verifying credential with server…</div>
            <div class="google-security-note">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
              </svg>
              Protected by Google OAuth 2.0 Identity Services
            </div>
          </div>
        </div>

        <!-- Email / password -->
        <div class="auth-body" *ngIf="authMethod === 'EMAIL'">
          <label class="form-label" for="auth-email">Email address</label>
          <input id="auth-email" type="email" class="input" [(ngModel)]="email" placeholder="name@example.com" autocomplete="email" />

          <label class="form-label mt-3" for="auth-password">Password</label>
          <input id="auth-password" type="password" class="input" [(ngModel)]="password" placeholder="••••••••" autocomplete="current-password" />

          <ng-container *ngIf="isRegisterMode">
            <label class="form-label mt-3" for="auth-name">Your full name</label>
            <input id="auth-name" type="text" class="input" [(ngModel)]="fullName" placeholder="Enter your full name" />
          </ng-container>

          <button type="button" class="btn btn-primary btn-full mt-4" (click)="submitEmailAuth()" [disabled]="emailLoading()">
            {{ emailLoading() ? 'Processing…' : (isRegisterMode ? 'Create account' : 'Sign in') }}
          </button>

          <div class="auth-toggle-row mt-3">
            <span *ngIf="!isRegisterMode">New to SevaFund? <button type="button" class="btn-link" (click)="isRegisterMode = true">Create an account</button></span>
            <span *ngIf="isRegisterMode">Already registered? <button type="button" class="btn-link" (click)="isRegisterMode = false">Sign in</button></span>
          </div>
        </div>

        <div class="auth-error-banner mt-3" *ngIf="authError()" role="alert">{{ authError() }}</div>
      </div>
    </div>
  `,
  styles: [`
    .site-header {
      position: sticky;
      top: 0;
      z-index: 100;
      border-bottom: 1px solid transparent;
      transition: transform 0.55s var(--ease-expo), background-color 0.3s ease, border-color 0.3s ease;
    }

    .site-header.is-scrolled {
      background: var(--glass-bg);
      backdrop-filter: blur(18px) saturate(160%);
      -webkit-backdrop-filter: blur(18px) saturate(160%);
      border-bottom-color: var(--line);
    }

    .site-header.is-hidden:not(:focus-within) {
      transform: translateY(-101%);
    }

    .nav-inner {
      display: flex;
      align-items: center;
      gap: 24px;
      height: var(--navbar-height);
    }

    /* Brand */
    .brand {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      margin-right: auto;
    }

    .brand-mark {
      width: 38px;
      height: 38px;
      border-radius: 12px;
      display: grid;
      place-items: center;
      color: var(--accent);
      background: var(--primary-light);
      transition: transform 0.5s var(--ease-spring);
    }

    .brand:hover .brand-mark { transform: rotate(-8deg) scale(1.06); }

    .brand-word {
      font-family: var(--font-display);
      font-size: 22px;
      font-weight: 600;
      letter-spacing: -0.03em;
      color: var(--ink);
    }

    .brand-tag {
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.14em;
      text-transform: uppercase;
      color: var(--ink-3);
      border: 1px solid var(--line);
      padding: 2px 7px;
      border-radius: var(--radius-full);
      transform: translateY(1px);
    }

    /* Links */
    .nav-links {
      display: flex;
      align-items: center;
      gap: 4px;
    }

    .nav-link {
      position: relative;
      padding: 8px 12px;
      font-size: 14.5px;
      font-weight: 500;
      color: var(--ink-2);
      transition: color 0.2s ease;
    }

    .nav-link::after {
      content: '';
      position: absolute;
      left: 12px;
      right: 12px;
      bottom: 3px;
      height: 1.5px;
      background: var(--accent);
      transform: scaleX(0);
      transform-origin: right;
      transition: transform 0.45s var(--ease-expo);
    }

    .nav-link:hover { color: var(--ink); }
    .nav-link:hover::after,
    .nav-link.active::after {
      transform: scaleX(1);
      transform-origin: left;
    }
    .nav-link.active { color: var(--ink); }
    .nav-link-admin { color: var(--danger); }

    /* Actions */
    .nav-actions {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .icon-btn {
      width: 38px;
      height: 38px;
      display: grid;
      place-items: center;
      border-radius: 50%;
      border: 1px solid var(--line);
      background: transparent;
      color: var(--ink-2);
      cursor: pointer;
      transition: background-color 0.2s ease, color 0.2s ease, transform 0.4s var(--ease-expo);
    }

    .icon-btn:hover {
      color: var(--ink);
      background: var(--surface);
    }

    .theme-toggle:hover { transform: rotate(-20deg); }

    .menu-toggle { display: none; }

    .burger {
      position: relative;
      width: 16px;
      height: 10px;
    }

    .burger span {
      position: absolute;
      left: 0;
      width: 100%;
      height: 1.5px;
      background: currentColor;
      border-radius: 2px;
      transition: transform 0.45s var(--ease-expo), top 0.45s var(--ease-expo);
    }

    .burger span:first-child { top: 0; }
    .burger span:last-child { top: 8.5px; }
    .burger.open span:first-child { top: 4.25px; transform: rotate(45deg); }
    .burger.open span:last-child { top: 4.25px; transform: rotate(-45deg); }

    /* Scroll progress */
    .scroll-progress {
      position: absolute;
      left: 0;
      right: 0;
      bottom: -1px;
      height: 2px;
      pointer-events: none;
    }

    .scroll-progress span {
      display: block;
      height: 100%;
      background: linear-gradient(90deg, var(--accent), var(--leaf));
      transform: scaleX(0);
      transform-origin: left;
    }

    /* User pill */
    .user-pill {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 3px 4px 3px 4px;
      background: var(--surface);
      border: 1px solid var(--line);
      border-radius: var(--radius-full);
    }

    .user-avatar {
      width: 30px;
      height: 30px;
      border-radius: 50%;
      background: var(--accent);
      color: var(--on-accent);
      font-weight: 700;
      font-size: 13px;
      display: grid;
      place-items: center;
    }

    .user-meta {
      display: flex;
      flex-direction: column;
      line-height: 1.2;
    }

    .user-name {
      font-size: 13px;
      font-weight: 600;
      max-width: 120px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .user-role { font-size: 10.5px; color: var(--ink-3); }

    .logout-btn { width: 30px; height: 30px; border: none; }
    .logout-btn:hover { color: var(--danger); background: var(--danger-light); }

    /* Mobile menu */
    .mobile-menu {
      position: fixed;
      inset: 0;
      z-index: 90;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      padding: calc(var(--navbar-height) + 32px) var(--gutter) 40px;
      background: var(--paper);
      clip-path: inset(0 0 100% 0);
      visibility: hidden;
      transition: clip-path 0.7s var(--ease-expo), visibility 0s linear 0.7s;
      overflow-y: auto;
    }

    .mobile-menu.open {
      clip-path: inset(0 0 0 0);
      visibility: visible;
      transition: clip-path 0.7s var(--ease-expo), visibility 0s;
    }

    .mobile-nav {
      display: flex;
      flex-direction: column;
    }

    .mobile-link {
      display: flex;
      align-items: baseline;
      gap: 16px;
      padding: 14px 0;
      border-bottom: 1px solid var(--line);
      font-family: var(--font-display);
      font-size: clamp(2rem, 8vw, 2.75rem);
      line-height: 1.1;
      letter-spacing: -0.03em;
      color: var(--ink);
      opacity: 0;
      transform: translateY(32px);
      transition: opacity 0.6s var(--ease-expo), transform 0.8s var(--ease-expo), color 0.2s ease;
    }

    .mobile-menu.open .mobile-link {
      opacity: 1;
      transform: none;
      transition-delay: calc(var(--i) * 55ms + 160ms);
    }

    .mobile-link.active { color: var(--accent-ink); }

    .mobile-index {
      font-family: var(--font-mono);
      font-size: 12px;
      color: var(--ink-3);
      letter-spacing: 0;
    }

    .mobile-foot {
      display: flex;
      flex-direction: column;
      gap: 10px;
      margin-top: 32px;
    }

    /* Auth modal */
    .auth-modal-overlay {
      position: fixed;
      inset: 0;
      background: rgba(20, 16, 11, 0.6);
      backdrop-filter: blur(6px);
      -webkit-backdrop-filter: blur(6px);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 1000;
      padding: 20px;
      animation: fadeIn 0.25s ease-out;
    }

    .auth-card {
      width: 100%;
      max-width: 440px;
      max-height: calc(100vh - 40px);
      overflow-y: auto;
      background: var(--surface);
      border-radius: var(--radius-2xl);
      border: 1px solid var(--line);
      box-shadow: var(--shadow-xl);
      padding: 32px 28px;
      position: relative;
      animation: fadeInUp 0.45s var(--ease-expo);
    }

    .modal-close {
      position: absolute;
      top: 16px;
      right: 16px;
      width: 32px;
      height: 32px;
      display: grid;
      place-items: center;
      background: var(--slate-100);
      border: none;
      border-radius: 50%;
      color: var(--ink-3);
      cursor: pointer;
    }

    .modal-close:hover { color: var(--ink); background: var(--slate-200); }

    .auth-card-header { text-align: center; margin-bottom: 22px; }

    .auth-badge-icon {
      width: 46px;
      height: 46px;
      border-radius: 50%;
      background: var(--primary-light);
      color: var(--primary);
      display: inline-grid;
      place-items: center;
      margin-bottom: 12px;
    }

    .auth-card-header h2 { font-size: 26px; }
    .auth-card-header p { font-size: 13.5px; color: var(--ink-3); margin-top: 6px; line-height: 1.5; }

    .auth-tabs {
      display: flex;
      gap: 4px;
      background: var(--slate-100);
      padding: 4px;
      border-radius: var(--radius-full);
      margin-bottom: 22px;
    }

    .tab-btn {
      flex: 1;
      padding: 8px 10px;
      border-radius: var(--radius-full);
      border: none;
      background: transparent;
      font-size: 12.5px;
      font-weight: 600;
      color: var(--ink-3);
      cursor: pointer;
    }

    .tab-btn.active {
      background: var(--surface);
      color: var(--ink);
      box-shadow: var(--shadow-xs);
    }

    .phone-input-wrap { display: flex; align-items: center; gap: 8px; }

    .phone-prefix {
      padding: 11px 14px;
      background: var(--slate-100);
      border: 1.5px solid var(--line);
      border-radius: var(--radius-md);
      font-weight: 700;
      font-size: 14px;
      color: var(--ink-2);
    }

    .phone-input { font-size: 15px; font-weight: 600; letter-spacing: 0.05em; }

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
      color: var(--ink-2);
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
      color: var(--warning);
      text-align: center;
    }

    .google-auth-container { text-align: center; padding: 10px 0; }
    .google-intro { font-size: 13.5px; color: var(--ink-2); margin-bottom: 16px; }
    .google-btn-box { display: flex; justify-content: center; min-height: 48px; }
    .google-loading-msg { font-size: 12.5px; color: var(--ink-3); margin-top: 10px; }

    .google-security-note {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 11.5px;
      color: var(--ink-3);
      margin-top: 16px;
    }

    .auth-toggle-row { text-align: center; font-size: 13px; color: var(--ink-3); }

    .auth-error-banner {
      padding: 10px 14px;
      border-radius: var(--radius-md);
      background: var(--danger-light);
      border: 1px solid var(--danger-border);
      font-size: 12.5px;
      color: var(--danger);
      text-align: center;
    }

    @media (max-width: 1080px) {
      .nav-links { display: none; }
      .menu-toggle { display: grid; }
    }

    @media (max-width: 640px) {
      .start-btn, .sign-in, .user-meta, .brand-tag { display: none; }
      .nav-inner { gap: 12px; }
    }
  `]
})
export class NavbarComponent implements AfterViewInit, AfterViewChecked, OnDestroy {
  public authService = inject(AuthService);
  public theme = inject(ThemeService);
  private smoothScroll = inject(SmoothScrollService);
  private ngZone = inject(NgZone);
  private router = inject(Router);

  @ViewChild('header') headerRef!: ElementRef<HTMLElement>;
  @ViewChild('progressBar') progressRef!: ElementRef<HTMLElement>;

  readonly links: NavLink[] = [
    { path: '/campaigns', label: 'Explore causes' },
    { path: '/how-it-works', label: 'How it works' },
    { path: '/trust', label: 'Trust & safety' },
    { path: '/about', label: 'About' },
  ];

  readonly mobileLinks: NavLink[] = [{ path: '/', label: 'Home', exact: true }, ...this.links];

  menuOpen = signal(false);
  showAuthModal = signal(false);
  authMethod: 'OTP' | 'GOOGLE' | 'EMAIL' = 'OTP';

  // OTP state
  phoneNumber = '';
  otpCode = '';
  fullName = '';
  otpSent = signal(false);
  otpLoading = signal(false);
  devOtp = signal('');

  // Google state
  googleLoading = signal(false);
  private googleBtnRendered = false;
  private googleInitialized = false;

  // Email state
  email = '';
  password = '';
  isRegisterMode = false;
  emailLoading = signal(false);

  authError = signal('');

  private ctx?: gsap.Context;
  private navSub?: Subscription;

  ngAfterViewInit(): void {
    this.navSub = this.router.events
      .pipe(filter((e) => e instanceof NavigationStart))
      .subscribe(() => this.closeMenu());

    if (!isBrowser) return;
    const header = this.headerRef.nativeElement;

    this.ngZone.runOutsideAngular(() => {
      this.ctx = gsap.context(() => {
        // Hide on scroll down, reveal on scroll up; glass background once scrolled.
        ScrollTrigger.create({
          start: 0,
          end: 'max',
          onUpdate: (self) => {
            const y = self.scroll();
            header.classList.toggle('is-scrolled', y > 8);
            header.classList.toggle('is-hidden', self.direction === 1 && y > 280 && !this.menuOpen());
          },
        });

        // Reading-progress bar under the header.
        gsap.to(this.progressRef.nativeElement, {
          scaleX: 1,
          ease: 'none',
          scrollTrigger: { start: 0, end: 'max', scrub: 0.3 },
        });
      });
    });
  }

  ngAfterViewChecked(): void {
    if (this.authMethod !== 'GOOGLE' || !this.showAuthModal()) {
      this.googleBtnRendered = false;
      return;
    }
    if (this.googleBtnRendered) return;

    // Mark as handled up front so repeated change-detection passes don't re-trigger the load.
    this.googleBtnRendered = true;
    loadGoogleIdentity()
      .then(() => this.renderGoogleButton())
      .catch(() =>
        this.ngZone.run(() =>
          this.authError.set('Could not load Google Sign-In. Check your connection or ad blocker, then reopen this tab.'),
        ),
      );
  }

  private renderGoogleButton(): void {
    const goog = (window as any).google;
    const container = document.getElementById('google-signin-btn');
    // The modal may have closed (or the tab changed) while the script was loading,
    // or an earlier load already drew the button here.
    if (!goog?.accounts?.id || !container || container.childElementCount > 0) return;

    if (!this.googleInitialized) {
      goog.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: (response: any) => {
          this.ngZone.run(() => this.handleGoogleCredential(response));
        },
        auto_select: false,
      });
      this.googleInitialized = true;
    }
    goog.accounts.id.renderButton(container, {
      theme: this.theme.theme() === 'dark' ? 'filled_black' : 'outline',
      size: 'large',
      width: 360,
      text: 'signin_with',
      shape: 'pill',
      logo_alignment: 'left',
    });
  }

  toggleTheme(event: MouseEvent): void {
    const rect = (event.currentTarget as HTMLElement).getBoundingClientRect();
    this.theme.toggle({ x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 });
  }

  toggleMenu(): void {
    this.menuOpen() ? this.closeMenu() : this.openMenu();
  }

  openMenu(): void {
    this.menuOpen.set(true);
    this.headerRef?.nativeElement.classList.remove('is-hidden');
    this.smoothScroll.lock();
  }

  closeMenu(): void {
    if (!this.menuOpen()) return;
    this.menuOpen.set(false);
    this.smoothScroll.unlock();
  }

  @HostListener('document:keydown.escape')
  onEscape(): void {
    this.closeMenu();
    if (this.showAuthModal()) this.closeAuthModal();
  }

  openAuthModal(): void {
    this.authError.set('');
    this.showAuthModal.set(true);
    this.smoothScroll.lock();
  }

  closeAuthModal(): void {
    this.showAuthModal.set(false);
    this.smoothScroll.unlock();
  }

  requestOtp(): void {
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

  submitOtp(): void {
    this.otpLoading.set(true);
    this.authError.set('');
    this.authService.verifyMobileOtp(this.phoneNumber, this.otpCode, this.fullName || undefined).subscribe({
      next: () => {
        this.otpLoading.set(false);
        this.closeAuthModal();
      },
      error: (err) => {
        this.otpLoading.set(false);
        this.authError.set(err?.error?.detail || 'Invalid OTP code.');
      }
    });
  }

  private handleGoogleCredential(response: any): void {
    this.googleLoading.set(true);
    this.authError.set('');
    if (response?.credential) {
      this.authService.loginWithGoogle(response.credential).subscribe({
        next: () => {
          this.googleLoading.set(false);
          this.closeAuthModal();
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

  submitEmailAuth(): void {
    this.emailLoading.set(true);
    this.authError.set('');
    const done = {
      next: () => {
        this.emailLoading.set(false);
        this.closeAuthModal();
      },
    };
    if (this.isRegisterMode) {
      this.authService.register({
        email: this.email,
        password: this.password,
        full_name: this.fullName || 'Supporter'
      }).subscribe({
        ...done,
        error: (err) => {
          this.emailLoading.set(false);
          this.authError.set(err?.error?.detail || 'Registration failed.');
        }
      });
    } else {
      this.authService.login(this.email, this.password).subscribe({
        ...done,
        error: (err) => {
          this.emailLoading.set(false);
          this.authError.set(err?.error?.detail || 'Invalid email or password.');
        }
      });
    }
  }

  ngOnDestroy(): void {
    this.navSub?.unsubscribe();
    this.ctx?.revert();
  }
}
