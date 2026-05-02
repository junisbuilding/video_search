import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { get } from 'svelte/store';
import { jobs } from './stores';
import { connectJobsSocket } from './ws';

interface MockWs {
  url: string;
  onmessage: ((e: { data: string }) => void) | null;
  onclose: (() => void) | null;
  onerror: (() => void) | null;
  close: () => void;
}

let mockWs: MockWs;
let WebSocketSpy: ReturnType<typeof vi.fn>;

beforeEach(() => {
  mockWs = { url: '', onmessage: null, onclose: null, onerror: null, close: vi.fn() };
  WebSocketSpy = vi.fn().mockImplementation((url: string) => {
    mockWs.url = url;
    return mockWs;
  });
  vi.stubGlobal('WebSocket', WebSocketSpy);
  vi.stubGlobal('location', { host: 'localhost:5173' });
  vi.useFakeTimers();
  jobs.set([]);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe('connectJobsSocket', () => {
  it('connects to ws://{host}/ws/jobs', () => {
    connectJobsSocket();
    expect(WebSocketSpy).toHaveBeenCalledWith('ws://localhost:5173/ws/jobs');
  });

  it('upserts job into store on message', () => {
    connectJobsSocket();
    const event = { job_id: 'job-1', video_id: null, path: '/v.mp4', kind: 'index', status: 'pending', progress: 0, error: null, created_at: 0, updated_at: 0 };
    mockWs.onmessage?.({ data: JSON.stringify(event) });
    const stored = get(jobs);
    expect(stored).toHaveLength(1);
    expect(stored[0].id).toBe('job-1');
  });

  it('reconnects after 2000ms on close', () => {
    connectJobsSocket();
    expect(WebSocketSpy).toHaveBeenCalledTimes(1);
    mockWs.onclose?.();
    vi.advanceTimersByTime(1999);
    expect(WebSocketSpy).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(1);
    expect(WebSocketSpy).toHaveBeenCalledTimes(2);
  });

  it('calls ws.close() on error', () => {
    connectJobsSocket();
    mockWs.onerror?.();
    expect(mockWs.close).toHaveBeenCalled();
  });
});
