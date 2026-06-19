import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatIconModule } from '@angular/material/icon';
import { ApiService } from '../../core/services/api.service';
import { AuthService } from '../../core/services/auth.service';
import { TailoredCVResponse, DiffEntry } from '../../core/models';

@Component({
  selector: 'app-cv-tailoring',
  standalone: true,
  imports: [
    CommonModule,
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
  loading = true;
  tailoredData?: TailoredCVResponse;
  errorMessage = '';

  // Track approved diff indices
  approvedIndices: Set<number> = new Set<number>();
  approving = false;
  downloadUrl = '';

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
        
        // If it was already approved in DB, pre-approve all
        if (!res.pending_approval) {
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
    if (!this.tailoredData || !this.tailoredData.diff) return false;
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
      next: (res) => {
        this.approving = false;
        this.downloadUrl = this.apiService.getCVDownloadUrl(this.jobId);
        // Trigger file download
        window.open(this.downloadUrl, '_blank');
      },
      error: (err) => {
        this.approving = false;
        this.errorMessage = err.message || 'Failed to approve changes.';
      }
    });
  }

  goBack(): void {
    window.history.back();
  }

  logout(): void {
    this.authService.logout();
  }
}
