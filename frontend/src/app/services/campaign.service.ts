import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { Campaign, CampaignListResponse, VerificationResult } from '../models/campaign.model';

@Injectable({
  providedIn: 'root'
})
export class CampaignService {
  private http = inject(HttpClient);
  private apiUrl = 'http://localhost:8000/api';

  getCampaigns(
    page: number = 1,
    limit: number = 12,
    category?: string,
    search?: string,
    sortBy?: 'trending' | 'newest' | 'most_funded',
    minScore?: number,
  ): Observable<CampaignListResponse> {
    let params = new HttpParams().set('page', page).set('limit', limit);
    if (category && category !== 'ALL') {
      params = params.set('category', category);
    }
    if (search) {
      params = params.set('search', search);
    }
    if (sortBy) {
      params = params.set('sort_by', sortBy);
    }
    if (minScore != null) {
      params = params.set('min_score', minScore);
    }
    return this.http.get<CampaignListResponse>(`${this.apiUrl}/campaigns`, { params });
  }

  getCampaign(id: number): Observable<Campaign> {
    return this.http.get<Campaign>(`${this.apiUrl}/campaigns/${id}`);
  }

  /** @deprecated use getCampaign */
  getCampaignById(id: number): Observable<Campaign> {
    return this.getCampaign(id);
  }

  createCampaign(campaignData: any): Observable<Campaign> {
    return this.http.post<Campaign>(`${this.apiUrl}/campaigns`, campaignData);
  }

  verifyCampaign(id: number): Observable<VerificationResult> {
    return this.http.post<VerificationResult>(`${this.apiUrl}/campaigns/${id}/verify`, {});
  }

  getAdminQueue(): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/admin/flagged`);
  }

  adminDecision(id: number, decision: string, notes?: string): Observable<Campaign> {
    return this.http.post<Campaign>(`${this.apiUrl}/admin/campaigns/${id}/decision`, { decision, notes });
  }

  /** @deprecated use getAdminQueue */
  getFlaggedCampaigns(): Observable<Campaign[]> {
    return this.http.get<Campaign[]>(`${this.apiUrl}/admin/flagged`);
  }

  /** @deprecated use adminDecision */
  submitAdminDecision(id: number, decision: string, notes?: string): Observable<Campaign> {
    return this.adminDecision(id, decision, notes);
  }
}
