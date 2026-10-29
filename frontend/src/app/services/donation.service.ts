import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { DonationReceipt, CreateGatewayOrderResponse, AdminDonationsResponse } from '../models/campaign.model';

@Injectable({
  providedIn: 'root'
})
export class DonationService {
  private http = inject(HttpClient);
  private apiUrl = 'http://localhost:8000/api';

  createGatewayOrder(campaignId: number, amount: number): Observable<CreateGatewayOrderResponse> {
    return this.http.post<CreateGatewayOrderResponse>(`${this.apiUrl}/donations/create-order`, {
      campaign_id: campaignId,
      amount
    });
  }

  donate(campaignId: number, donationData: {
    amount: number;
    payment_method?: string;
    upi_id?: string;
    donor_name?: string;
    donor_email?: string;
    donor_phone?: string;
    donor_pan?: string;
    message?: string;
    support_message?: string;
    tip_amount?: number;
    is_anonymous?: boolean;
    gateway_order_id?: string;
    gateway_payment_id?: string;
    gateway_signature?: string;
  }): Observable<DonationReceipt> {
    return this.http.post<DonationReceipt>(`${this.apiUrl}/campaigns/${campaignId}/donate`, donationData);
  }

  getCampaignDonations(campaignId: number): Observable<any> {
    return this.http.get<any>(`${this.apiUrl}/campaigns/${campaignId}/donations`);
  }

  getAdminDonations(params?: { campaign_id?: number; search?: string; page?: number; limit?: number }): Observable<AdminDonationsResponse> {
    let httpParams = new HttpParams();
    if (params?.campaign_id) httpParams = httpParams.set('campaign_id', params.campaign_id.toString());
    if (params?.search) httpParams = httpParams.set('search', params.search);
    if (params?.page) httpParams = httpParams.set('page', params.page.toString());
    if (params?.limit) httpParams = httpParams.set('limit', params.limit.toString());

    return this.http.get<AdminDonationsResponse>(`${this.apiUrl}/admin/donations`, { params: httpParams });
  }
}
