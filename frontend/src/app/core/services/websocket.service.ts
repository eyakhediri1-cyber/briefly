import { Injectable } from '@angular/core';
import { Subject, Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class WebsocketService {
  private socketSubject = new Subject<any>();

  constructor() {}

  connect(url: string): Observable<any> {
    console.log(`Websocket: Connecting to ${url}`);
    // Mock WebSocket connection
    setTimeout(() => {
      this.socketSubject.next({ event: 'connected', msg: 'Mock connection established' });
    }, 1000);

    return this.socketSubject.asObservable();
  }

  send(msg: any): void {
    console.log('Websocket sending:', msg);
  }

  disconnect(): void {
    console.log('Websocket disconnected');
  }
}
