import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormBuilder, FormGroup, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { interval, Subscription, switchMap, takeWhile } from 'rxjs';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { ApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { SearchStatusResponse } from '../../core/models';

interface PipelineStep {
  key: string;
  label: string;
  status: 'pending' | 'active' | 'done';
}

@Component({
  selector: 'app-search',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatCheckboxModule,
    MatButtonModule,
    MatProgressBarModule
  ],
  templateUrl: './search.component.html',
  styleUrls: ['./search.component.css']
})
export class SearchComponent implements OnInit, OnDestroy {
  searchForm: FormGroup;
  searching = false;
  progressPercent = 0;
  progressStep = '';
  searchError = '';
  noResultsMessage = '';
  sessionId = '';
  jobsFound: number | null = null;
  jobsAnalyzed: number | null = null;
  currentAgent = '';

  pipelineSteps: PipelineStep[] = [
    { key: 'PENDING', label: 'Initializing pipeline...', status: 'pending' },
    { key: 'AGENT_2_RUNNING', label: 'Searching job boards...', status: 'pending' },
    { key: 'AGENT_3_RUNNING', label: 'Analyzing job requirements...', status: 'pending' },
    { key: 'AGENT_4_RUNNING', label: 'Computing fit scores...', status: 'pending' },
    { key: 'AGENT_5_RUNNING', label: 'Building your strategy...', status: 'pending' },
  ];

  private pollSubscription?: Subscription;

  constructor(
    private fb: FormBuilder,
    private apiService: ApiService,
    private authService: AuthService,
    private router: Router
  ) {
    this.searchForm = this.fb.group({
      target_role: ['', Validators.required],
      location: [''],
      contract_type: ['internship'],
      remote: [false]
    });
  }

  ngOnInit(): void {}

  onSubmit(): void {
    if (this.searchForm.invalid) return;

    this.searching = true;
    this.progressPercent = 0;
    this.progressStep = 'Initializing job search...';
    this.searchError = '';
    this.noResultsMessage = '';
    this.jobsFound = null;
    this.jobsAnalyzed = null;
    this.currentAgent = '';
    this.resetPipelineSteps();

    const filters = {
      location: this.searchForm.value.location || undefined,
      contract_type: this.searchForm.value.contract_type || undefined,
      remote: this.searchForm.value.remote || undefined,
      max_results: 80
    };

    this.apiService.startSearch(this.searchForm.value.target_role, filters).subscribe({
      next: (res) => {
        console.log('[Brieflyy] Search started:', res);
        this.sessionId = String(res.session_id);
        this.startPollingStatus();
      },
      error: (err) => {
        console.error('[Brieflyy] Search start error:', err);
        this.searching = false;
        this.searchError = err.error?.detail || err.message || 'Failed to start job search. Please try again.';
      }
    });
  }

  startPollingStatus(): void {
    this.pollSubscription = interval(1500)
      .pipe(
        switchMap(() => this.apiService.getSearchStatus(this.sessionId)),
        takeWhile(status => status.status !== 'COMPLETED' && status.status !== 'FAILED', true)
      )
      .subscribe({
        next: (status) => {
          console.log('[Brieflyy] Pipeline status:', status);
          this.updateFromStatus(status);

          if (status.status === 'COMPLETED') {
            this.progressPercent = 100;
            this.markAllStepsDone();

            if (status.jobs_found === 0) {
              this.searching = false;
              this.noResultsMessage = 'No matches found. Try different keywords or locations.';
              this.progressStep = this.noResultsMessage;
              return;
            }

            this.progressStep = status.current_step || 'Strategy plan generated!';
            setTimeout(() => {
              this.router.navigate([`/strategy/${this.sessionId}`]);
            }, 1000);
          } else if (status.status === 'FAILED') {
            this.searching = false;
            this.searchError = status.current_step || 'Agent pipeline failed. Please try again.';
          }
        },
        error: (err) => {
          console.error('[Brieflyy] Status poll error:', err);
          this.searching = false;
          this.searchError = 'Error polling search status. Please check your network.';
        }
      });
  }

  private updateFromStatus(status: SearchStatusResponse): void {
    this.progressPercent = status.progress_percent;
    this.progressStep = status.current_step || this.statusToMessage(status.status);
    this.currentAgent = status.current_agent || '';
    if (status.jobs_found != null) this.jobsFound = status.jobs_found;
    if (status.jobs_analyzed != null) this.jobsAnalyzed = status.jobs_analyzed;
    this.updatePipelineSteps(status.status);
  }

  private statusToMessage(status: string): string {
    const messages: Record<string, string> = {
      PENDING: 'Starting agent pipeline...',
      AGENT_2_RUNNING: 'Searching job boards...',
      AGENT_3_RUNNING: 'Analyzing job requirements...',
      AGENT_4_RUNNING: 'Computing your fit scores...',
      AGENT_5_RUNNING: 'Building your personalized strategy...',
      COMPLETED: 'Done!',
      FAILED: 'Pipeline failed',
    };
    return messages[status] || 'Processing...';
  }

  private resetPipelineSteps(): void {
    this.pipelineSteps = this.pipelineSteps.map(s => ({ ...s, status: 'pending' as const }));
  }

  private updatePipelineSteps(currentStatus: string): void {
    const order = ['PENDING', 'AGENT_2_RUNNING', 'AGENT_3_RUNNING', 'AGENT_4_RUNNING', 'AGENT_5_RUNNING'];
    const currentIdx = order.indexOf(currentStatus);

    this.pipelineSteps = this.pipelineSteps.map((step, idx) => {
      if (currentStatus === 'COMPLETED') {
        return { ...step, status: 'done' as const };
      }
      if (idx < currentIdx) {
        return { ...step, status: 'done' as const };
      }
      if (idx === currentIdx) {
        return { ...step, status: 'active' as const };
      }
      return { ...step, status: 'pending' as const };
    });
  }

  private markAllStepsDone(): void {
    this.pipelineSteps = this.pipelineSteps.map(s => ({ ...s, status: 'done' as const }));
  }

  logout(): void {
    this.authService.logout();
  }

  ngOnDestroy(): void {
    this.pollSubscription?.unsubscribe();
  }
}
