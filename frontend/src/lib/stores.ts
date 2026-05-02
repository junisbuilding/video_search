import { writable } from 'svelte/store';
import type { Job, SearchResponse } from './types';

export const searchResults = writable<SearchResponse | null>(null);
export const activeVideo = writable<{ videoId: string; frameIdx: number | null; timestamp: number } | null>(null);
export const jobs = writable<Job[]>([]);

export function upsertById(list: Job[], event: Job): Job[] {
  const idx = list.findIndex(j => j.id === event.id);
  if (idx === -1) {
    return [event, ...list];
  }
  const updated = [...list];
  updated[idx] = { ...updated[idx], ...event };
  return updated;
}
