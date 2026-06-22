import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { JobCardComponent } from '../../components/job-card/job-card.component';
import { ApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { JobResultsResponse, JobWithTailoredPreview } from '../../core/models';

@Component({
  selector: 'app-job-results',
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    MatCardModule,
    MatButtonModule,
    MatProgressSpinnerModule,
    JobCardComponent,
  ],
  templateUrl: './job-results.component.html',
  styleUrls: ['./job-results.component.css']
})
export class JobResultsComponent implements OnInit {
  sessionId = '';
  loading = true;
  results?: JobResultsResponse;
  errorMessage = '';

  constructor(
    private route: ActivatedRoute,
    private apiService: ApiService,
    private authService: AuthService,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.route.params.subscribe(params => {
      this.sessionId = params['sessionId'];
      this.fetchResults();
    });
  }

  fetchResults(): void {
    this.loading = true;
    this.errorMessage = '';
    this.apiService.getJobResults(this.sessionId).subscribe({
      next: async (res) => {
        console.log('JobResults API response', res);
        // Normalize response shape (support older shape with `results` or `jobs`)
        const anyRes: any = res as any;
        const jobsArr = Array.isArray(anyRes.jobs)
          ? anyRes.jobs
          : Array.isArray(anyRes.results)
          ? anyRes.results
          : [];

        const normalized = {
          session_id: anyRes.session_id || this.sessionId,
          jobs: jobsArr,
          total_jobs_found: anyRes.total_jobs_found ?? anyRes.jobs_found ?? jobsArr.length,
          total_tailored: anyRes.total_tailored ?? anyRes.cvs_ready ?? 0,
        } as JobResultsResponse;

        this.results = normalized;
        // Add artificial 2 second delay to show agents working
        await new Promise(resolve => setTimeout(resolve, 2000));
        this.loading = false;
      },
      error: (err) => {
        this.loading = false;
        this.errorMessage = err.error?.detail || err.message || 'Failed to load job results.';
      }
    });
  }

  getFitColor(pct: number): string {
    if (pct >= 80) return '#10b981';
    if (pct >= 60) return '#f59e0b';
    return '#94a3b8';
  }

  formatContractType(type: string): string {
    if (!type) return 'Not specified';
    const map: Record<string, string> = {
      internship: 'Internship',
      fulltime: 'Full-time',
      parttime: 'Part-time',
    };
    return map[type.toLowerCase()] || type;
  }

  viewTailoredCv(job: JobWithTailoredPreview): void {
    this.router.navigate(['/tailor', job.job_id], { queryParams: { mode: 'preview', from: this.sessionId } });
  }

  applyToJob(job: JobWithTailoredPreview): void {
    this.router.navigate(['/tailor', job.job_id], { queryParams: { mode: 'apply', from: this.sessionId } });
  }

  isApplied(job: JobWithTailoredPreview): boolean {
    return !!job.application_status;
  }

  logout(): void {
    this.authService.logout();
  }
}
