import { Component, Input, Output, EventEmitter } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';

@Component({
  selector: 'app-job-card',
  standalone: true,
  imports: [CommonModule, MatButtonModule],
  templateUrl: './job-card.component.html',
  styleUrls: ['./job-card.component.scss']
})
export class JobCardComponent {
  @Input() job: any;
  @Output() select = new EventEmitter<any>();
  @Output() apply = new EventEmitter<any>();
  @Output() skip = new EventEmitter<any>();

  getScoreColor(score: number): string {
    if (score >= 80) return '#10B981';
    if (score >= 60) return '#F59E0B';
    return '#EF4444';
  }

  getScoreLabel(score: number): string {
    if (score >= 80) return 'Excellent match';
    if (score >= 60) return 'Good fit';
    return 'Review carefully';
  }
}