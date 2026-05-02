import { describe, it, expect } from 'vitest';
import { get } from 'svelte/store';
import { searchResults, activeVideo, jobs, upsertById } from './stores';
import type { Job } from './types';

const makeJob = (overrides: Partial<Job> = {}): Job => ({
  id: 'job-1', video_id: null, path: '/video.mp4', kind: 'index',
  status: 'pending', progress: 0, error: null, created_at: 0, updated_at: 0,
  ...overrides,
});

describe('initial store values', () => {
  it('searchResults starts null', () => {
    expect(get(searchResults)).toBeNull();
  });

  it('activeVideo starts null', () => {
    expect(get(activeVideo)).toBeNull();
  });

  it('jobs starts empty', () => {
    expect(get(jobs)).toEqual([]);
  });
});

describe('upsertById', () => {
  it('prepends a new job when id not found', () => {
    const job = makeJob({ id: 'job-1' });
    const result = upsertById([], job);
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe('job-1');
  });

  it('updates existing job in place when id matches', () => {
    const existing = makeJob({ id: 'job-1', status: 'pending' });
    const update = makeJob({ id: 'job-1', status: 'done', progress: 1 });
    const result = upsertById([existing], update);
    expect(result).toHaveLength(1);
    expect(result[0].status).toBe('done');
    expect(result[0].progress).toBe(1);
  });

  it('preserves fields not in the update', () => {
    const existing = makeJob({ id: 'job-1', path: '/video.mp4' });
    const update = { id: 'job-1', status: 'done' } as Job;
    const result = upsertById([existing], update);
    expect(result[0].path).toBe('/video.mp4');
  });

  it('new job is prepended, not appended', () => {
    const existing = makeJob({ id: 'job-1' });
    const newJob = makeJob({ id: 'job-2' });
    const result = upsertById([existing], newJob);
    expect(result[0].id).toBe('job-2');
    expect(result[1].id).toBe('job-1');
  });
});
