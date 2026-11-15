import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { StoryEnhanceResponse, VerificationResult, BenchmarkComparison } from '../models/campaign.model';

@Injectable({
  providedIn: 'root'
})
export class AiService {
  private http = inject(HttpClient);
  private apiUrl = 'http://localhost:8000/api/ai';

  /**
   * Calls the backend AI story enhancement endpoint.
   * Accepts the full campaign draft so the backend can produce
   * a rich, India-specific story.
   */
  enhanceStory(data: {
    title?: string;
    category: string;
    goal_amount: number;
    city?: string;
    state?: string;
    hospital_name?: string;
    story?: string;
    // legacy alias kept for compatibility
    rough_notes?: string;
    beneficiary_name?: string;
    target_audience?: string;
  }): Observable<StoryEnhanceResponse> {
    // Normalise: backend expects rough_notes; forward story content there
    const payload = {
      ...data,
      rough_notes: data.rough_notes || data.story || '',
    };
    return this.http.post<StoryEnhanceResponse>(`${this.apiUrl}/enhance-story`, payload);
  }

  preCheckVerification(data: {
    title: string;
    category: string;
    story: string;
    goal_amount: number;
    hospital_name?: string;
    beneficiary_name?: string;
    beneficiary_type?: string;
    city?: string;
    state?: string;
    documents?: any[];
  }): Observable<VerificationResult> {
    return this.http.post<VerificationResult>(`${this.apiUrl}/verify-request`, data);
  }

  uploadProofDocument(file: File, docType = 'OTHER'): Observable<{
    doc_type: string;
    title: string;
    file_url: string;
    verified: boolean;
  }> {
    const form = new FormData();
    form.append('file', file);
    form.append('doc_type', docType);
    form.append('title', file.name);
    return this.http.post<any>('http://localhost:8000/api/documents/upload', form);
  }

  checkCostBenchmark(category: string, description: string, requestedAmount: number): Observable<BenchmarkComparison> {
    return this.http.post<BenchmarkComparison>(`${this.apiUrl}/benchmark-cost`, {
      category,
      description,
      requested_amount: requestedAmount
    });
  }
}
