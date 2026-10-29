import { Injectable, inject, signal, computed } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';

export interface User {
  id: number;
  email?: string;
  phone_number?: string;
  full_name: string;
  avatar_url?: string;
  role: 'USER' | 'ADMIN' | 'TRUST_REVIEWER';
  is_identity_verified: boolean;
  is_email_verified?: boolean;
  is_phone_verified?: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface OTPSendResponse {
  phone_number: string;
  message: string;
  expires_in_seconds: number;
  dev_otp?: string;
}

@Injectable({
  providedIn: 'root'
})
export class AuthService {
  private http = inject(HttpClient);
  private apiUrl = 'http://localhost:8000/api/auth';

  currentUser = signal<User | null>(null);
  token = signal<string | null>(localStorage.getItem('sevafund_token'));
  isAuthenticated = computed(() => !!this.currentUser());
  isAdmin = computed(() => this.currentUser()?.role === 'ADMIN');

  constructor() {
    const savedUser = localStorage.getItem('sevafund_user');
    if (savedUser) {
      try {
        this.currentUser.set(JSON.parse(savedUser));
      } catch (e) {
        localStorage.removeItem('sevafund_user');
      }
    }
    // Verify token validity on boot
    if (this.token()) {
      this.fetchProfile().subscribe({
        error: () => this.logout()
      });
    }
  }

  login(email: string, password: string): Observable<TokenResponse> {
    return this.http.post<TokenResponse>(`${this.apiUrl}/login`, { email, password }).pipe(
      tap(res => this.handleAuthSuccess(res))
    );
  }

  register(data: { email: string; password: string; full_name: string; phone_number?: string }): Observable<TokenResponse> {
    return this.http.post<TokenResponse>(`${this.apiUrl}/register`, data).pipe(
      tap(res => this.handleAuthSuccess(res))
    );
  }

  loginWithGoogle(idToken: string): Observable<TokenResponse> {
    return this.http.post<TokenResponse>(`${this.apiUrl}/google`, { id_token: idToken }).pipe(
      tap(res => this.handleAuthSuccess(res))
    );
  }

  sendMobileOtp(phoneNumber: string): Observable<OTPSendResponse> {
    return this.http.post<OTPSendResponse>(`${this.apiUrl}/otp/send`, { phone_number: phoneNumber });
  }

  verifyMobileOtp(phoneNumber: string, otp: string, fullName?: string): Observable<TokenResponse> {
    return this.http.post<TokenResponse>(`${this.apiUrl}/otp/verify`, {
      phone_number: phoneNumber,
      otp,
      full_name: fullName
    }).pipe(
      tap(res => this.handleAuthSuccess(res))
    );
  }

  fetchProfile(): Observable<User> {
    return this.http.get<User>(`${this.apiUrl}/me`).pipe(
      tap(user => {
        this.currentUser.set(user);
        localStorage.setItem('sevafund_user', JSON.stringify(user));
      })
    );
  }

  logout() {
    this.currentUser.set(null);
    this.token.set(null);
    localStorage.removeItem('sevafund_token');
    localStorage.removeItem('sevafund_user');
  }

  private handleAuthSuccess(res: TokenResponse) {
    this.token.set(res.access_token);
    this.currentUser.set(res.user);
    localStorage.setItem('sevafund_token', res.access_token);
    localStorage.setItem('sevafund_user', JSON.stringify(res.user));
  }
}
