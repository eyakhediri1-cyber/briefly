import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatChipsModule } from '@angular/material/chips';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatIconModule } from '@angular/material/icon';
import { ApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { JobSearchStrategyResponse, JobWithFit } from '../../core/models';

@Component({
  selector: 'app-strategy',
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    MatCardModule,
    MatButtonModule,
    MatChipsModule,
    MatCheckboxModule,
    MatProgressSpinnerModule,
    MatIconModule
  ],
  templateUrl: './strategy.component.html',
  styleUrls: ['./strategy.component.css']
})
export class StrategyComponent implements OnInit {
  sessionId = '';
  loading = true;
  strategy?: JobSearchStrategyResponse;
  errorMessage = '';

  get totalJobsFound(): number {
    if (!this.strategy) return 0;
    if (this.strategy.total_jobs_found != null) return this.strategy.total_jobs_found;
    return (
      this.strategy.quick_wins.length +
      this.strategy.stretch_goals.length +
      this.strategy.develop_first.length
    );
  }

  get totalJobsCategorized(): number {
    if (!this.strategy) return 0;
    return (
      this.strategy.quick_wins.length +
      this.strategy.stretch_goals.length +
      this.strategy.develop_first.length
    );
  }

  get hasNoJobMatches(): boolean {
    return !!this.strategy && this.totalJobsCategorized === 0;
  }

  constructor(
    private route: ActivatedRoute,
    private apiService: ApiService,
    private authService: AuthService,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.route.params.subscribe(params => {
      this.sessionId = params['sessionId'];
      this.fetchStrategy();
    });
  }

  fetchStrategy(): void {
    this.loading = true;
    this.errorMessage = '';

    this.apiService.getStrategy(this.sessionId).subscribe({
      next: (res) => {
        console.log('[Brieflyy] Strategy response:', res);
        this.strategy = res;
        this.loading = false;
      },
      error: (err) => {
        this.loading = false;
        this.errorMessage = err.message || 'Failed to fetch strategy dashboard.';
      }
    });
  }

  getFitColor(pct: number): string {
    if (pct >= 80) return '#10b981'; // emerald
    if (pct >= 60) return '#f59e0b'; // amber
    if (pct >= 40) return '#f97316'; // orange
    return '#ef4444'; // red
  }

  getFitBg(pct: number): string {
    if (pct >= 80) return 'rgba(16, 185, 129, 0.1)';
    if (pct >= 60) return 'rgba(245, 158, 11, 0.1)';
    if (pct >= 40) return 'rgba(249, 115, 22, 0.1)';
    return 'rgba(239, 68, 68, 0.1)';
  }

  logout(): void {
    this.authService.logout();
  }
}
