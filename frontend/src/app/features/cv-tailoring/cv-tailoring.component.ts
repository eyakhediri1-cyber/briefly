import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatIconModule } from '@angular/material/icon';
import { ApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { TailoredCVResponse, ApplicationSubmitResponse } from '../../core/models';

@Component({
  selector: 'app-cv-tailoring',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterLink,
    MatCardModule,
    MatButtonModule,
    MatCheckboxModule,
    MatProgressSpinnerModule,
    MatIconModule
  ],
  templateUrl: './cv-tailoring.component.html',
  styleUrls: ['./cv-tailoring.component.css']
})
export class CVTailoringComponent implements OnInit {
  jobId = '';
  mode: 'preview' | 'apply' = 'preview';
  loading = true;
  tailoredData?: TailoredCVResponse;
  errorMessage = '';
  applyMessage = '';
  applicationResult?: ApplicationSubmitResponse;

  approvedIndices: Set<number> = new Set<number>();
  approving = false;
  applying = false;
  downloadUrl = '';
  showFullCv = false;
  cvConfirmed = false;
  window = window;

  constructor(
    private route: ActivatedRoute,
    private apiService: ApiService,
    private authService: AuthService,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.route.params.subscribe(params => {
      this.jobId = params['jobId'];
      this.fetchTailoringData();
    });
    this.route.queryParams.subscribe(q => {
      this.mode = q['mode'] === 'apply' ? 'apply' : 'preview';
      this.showFullCv = true;
    });
  }

  fetchTailoringData(): void {
    this.loading = true;
    this.errorMessage = '';
    this.approvedIndices.clear();
    this.downloadUrl = '';

    this.apiService.tailorCV(this.jobId).subscribe({
      next: (res) => {
        this.tailoredData = res;
        this.loading = false;
        
        // If there are no diffs, auto-approve everything
        if (!res.diff || res.diff.length === 0) {
          res.diff.forEach((_, index) => this.approvedIndices.add(index));
          // Auto-set download URL if no diffs
          this.downloadUrl = this.apiService.getCVDownloadUrl(this.jobId);
        } 
        // If it was already approved in DB, pre-approve all
        else if (!res.pending_approval) {
          res.diff.forEach((_, index) => this.approvedIndices.add(index));
          this.downloadUrl = this.apiService.getCVDownloadUrl(this.jobId);
        }
      },
      error: (err) => {
        this.loading = false;
        this.errorMessage = err.message || 'Failed to start CV tailoring agent.';
      }
    });
  }

  toggleApproval(index: number, checked: boolean): void {
    if (checked) {
      this.approvedIndices.add(index);
    } else {
      this.approvedIndices.delete(index);
    }
  }

  isAllApproved(): boolean {
    if (!this.tailoredData) return false;
    if (!this.tailoredData.diff || this.tailoredData.diff.length === 0) return true;
    return this.approvedIndices.size === this.tailoredData.diff.length;
  }

  getChangeTypeClass(changeType: string): string {
    switch (changeType) {
      case 'KEYWORD_ADDED': return 'bg-success';
      case 'REPHRASED': return 'bg-info';
      case 'STRENGTHENED': return 'bg-primary';
      case 'REORDERED': return 'bg-warning text-dark';
      default: return 'bg-secondary';
    }
  }

  approveAll(): void {
    if (!this.tailoredData || !this.tailoredData.diff) return;
    this.tailoredData.diff.forEach((_, index) => this.approvedIndices.add(index));
  }

  submitApprovalAndDownload(): void {
    if (!this.isAllApproved()) return;

    this.approving = true;
    const approvedList = Array.from(this.approvedIndices);

    this.apiService.approveCVChanges(this.jobId, approvedList).subscribe({
      next: () => {
        this.approving = false;
        if (this.tailoredData) {
          this.tailoredData.pending_approval = false;
        }
        this.downloadUrl = this.apiService.getCVDownloadUrl(this.jobId);
        if (this.mode !== 'apply') {
          window.open(this.downloadUrl, '_blank');
        }
      },
      error: (err) => {
        this.approving = false;
        this.errorMessage = err.error?.detail || err.message || 'Failed to approve changes.';
      }
    });
  }

  canApply(): boolean {
    return (
      this.mode === 'apply' &&
      this.cvConfirmed &&
      !this.tailoredData?.pending_approval &&
      !this.applicationResult
    );
  }

  submitApplication(): void {
    if (!this.canApply()) return;

    this.applying = true;
    this.applyMessage = '';

    this.apiService.submitApplication(this.jobId).subscribe({
      next: (res) => {
        this.applying = false;
        this.applicationResult = res;
        this.applyMessage = res.message;
      },
      error: (err) => {
        this.applying = false;
        this.errorMessage = err.error?.detail || err.message || 'Failed to submit application.';
      }
    });
  }

  get adaptedSectionKeys(): string[] {
    if (!this.tailoredData?.adapted_sections) return [];
    return Object.keys(this.tailoredData.adapted_sections);
  }

  goBack(): void {
    const from = this.route.snapshot.queryParams['from'];
    if (from) {
      this.router.navigate(['/results', from]);
    } else {
      window.history.back();
    }
  }

  logout(): void {
    this.authService.logout();
  }
}
