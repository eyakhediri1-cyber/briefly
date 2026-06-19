import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatIconModule } from '@angular/material/icon';
import { ApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { FitAnalysisResponse } from '../../core/models';

@Component({
  selector: 'app-job-detail',
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    MatCardModule,
    MatButtonModule,
    MatProgressSpinnerModule,
    MatIconModule
  ],
  templateUrl: './job-detail.component.html',
  styleUrls: ['./job-detail.component.css']
})
export class JobDetailComponent implements OnInit {
  jobId = '';
  loading = true;
  fitData?: FitAnalysisResponse;
  errorMessage = '';

  constructor(
    private route: ActivatedRoute,
    private apiService: ApiService,
    private authService: AuthService,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.route.params.subscribe(params => {
      this.jobId = params['jobId'];
      this.fetchFitAnalysis();
    });
  }

  fetchFitAnalysis(): void {
    this.loading = true;
    this.errorMessage = '';

    this.apiService.getJobFit(this.jobId).subscribe({
      next: (res) => {
        this.fitData = res;
        this.loading = false;
      },
      error: (err) => {
        this.loading = false;
        this.errorMessage = err.message || 'Failed to retrieve detailed fit analysis.';
      }
    });
  }

  getFitColor(pct: number): string {
    if (pct >= 80) return '#10b981';
    if (pct >= 60) return '#f59e0b';
    if (pct >= 40) return '#f97316';
    return '#ef4444';
  }

  getMatchBadgeClass(assessment: string): string {
    switch (assessment) {
      case 'EXACT_MATCH': return 'bg-success';
      case 'TRANSFERABLE': return 'bg-info';
      case 'PARTIAL': return 'bg-warning text-dark';
      case 'GAP': return 'bg-danger';
      default: return 'bg-secondary';
    }
  }

  getMatchRowClass(assessment: string): string {
    switch (assessment) {
      case 'EXACT_MATCH': return 'row-exact';
      case 'TRANSFERABLE': return 'row-transferable';
      case 'PARTIAL': return 'row-partial';
      case 'GAP': return 'row-gap';
      default: return '';
    }
  }

  goBack(): void {
    window.history.back();
  }

  logout(): void {
    this.authService.logout();
  }
}
