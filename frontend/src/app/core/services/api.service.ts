import { Injectable } from '@angular/core';
import { HttpClient, HttpEvent, HttpHeaders, HttpRequest } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  CVProfile,
  CVUploadResponse,
  SearchFilters,
  SearchStartResponse,
  SearchStatusResponse,
  JobSearchStrategyResponse,
  JobWithFit,
  FitAnalysisResponse,
  TailoredCVResponse,
  ApproveChangesResponse,
  JobResultsResponse,
  ApplicationSubmitResponse,
} from '../models';

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private readonly baseUrl = environment.apiUrl;

  constructor(private http: HttpClient) {}

  // CV Methods
  uploadCV(file: File): Observable<HttpEvent<CVUploadResponse>> {
    const formData = new FormData();
    formData.append('file', file);

    const req = new HttpRequest('POST', `${this.baseUrl}/cv/upload`, formData, {
      reportProgress: true,
      responseType: 'json'
    });

    return this.http.request<CVUploadResponse>(req);
  }

  getProfile(): Observable<CVProfile> {
    return this.http.get<CVProfile>(`${this.baseUrl}/cv/profile`);
  }

  // Search Methods
  startSearch(targetRole: string, filters: SearchFilters): Observable<SearchStartResponse> {
    return this.http.post<SearchStartResponse>(`${this.baseUrl}/search/start`, {
      target_role: targetRole,
      filters
    });
  }

  getSearchStatus(sessionId: string): Observable<SearchStatusResponse> {
    return this.http.get<SearchStatusResponse>(`${this.baseUrl}/search/status/${sessionId}`);
  }

  // Strategy Methods
  getStrategy(sessionId: string): Observable<JobSearchStrategyResponse> {
    return this.http.get<JobSearchStrategyResponse>(`${this.baseUrl}/strategy/${sessionId}`);
  }

  // Jobs Methods
  getJobResults(sessionId: string): Observable<JobResultsResponse> {
    return this.http.get<JobResultsResponse>(`${this.baseUrl}/jobs/results/${sessionId}`);
  }

  getJobs(sessionId: string): Observable<JobWithFit[]> {
    return this.http.get<JobWithFit[]>(`${this.baseUrl}/jobs/${sessionId}`);
  }

  getJobFit(jobId: string): Observable<FitAnalysisResponse> {
    return this.http.get<FitAnalysisResponse>(`${this.baseUrl}/jobs/${jobId}/fit`);
  }

  // Tailoring Methods
  tailorCV(jobId: string): Observable<TailoredCVResponse> {
    return this.http.post<TailoredCVResponse>(`${this.baseUrl}/tailor/${jobId}`, {});
  }

  approveCVChanges(jobId: string, approvedChanges: number[]): Observable<ApproveChangesResponse> {
    return this.http.post<ApproveChangesResponse>(`${this.baseUrl}/tailor/${jobId}/approve`, {
      approved_changes: approvedChanges
    });
  }

  getCVDownloadUrl(jobId: string): string {
    return `${this.baseUrl}/tailor/${jobId}/download`;
  }

  getCVPreview(jobId: string): Observable<TailoredCVResponse> {
    return this.http.get<TailoredCVResponse>(`${this.baseUrl}/tailor/${jobId}/preview`);
  }

  submitApplication(jobId: string): Observable<ApplicationSubmitResponse> {
    return this.http.post<ApplicationSubmitResponse>(`${this.baseUrl}/apply/${jobId}`, {
      confirm_cv: true
    });
  }
}
