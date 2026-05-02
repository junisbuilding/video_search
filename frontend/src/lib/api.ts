import type {
  FsListResponse, HealthResponse, IngestResponse, JobsListResponse,
  LibraryResponse, RegisterFolderResponse, RetryResponse,
  SearchResponse, SettingsPatch,
} from './types';

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(body || `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export async function search(query: string, k = 10): Promise<SearchResponse> {
  return apiFetch('/api/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, k }),
  });
}

export async function getHealth(): Promise<HealthResponse> {
  return apiFetch('/api/health');
}

export async function getLibrary(): Promise<LibraryResponse> {
  return apiFetch('/api/library');
}

export async function addFolder(path: string): Promise<RegisterFolderResponse> {
  return apiFetch('/api/library/folders', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  });
}

export async function deleteFolder(id: string): Promise<void> {
  await apiFetch('/api/library/folders/' + id, { method: 'DELETE' });
}

export async function rescanFolder(id: string): Promise<{ enqueued: number }> {
  return apiFetch(`/api/library/folders/${id}/rescan`, { method: 'POST' });
}

export async function ingest(path: string, recursive?: boolean): Promise<IngestResponse> {
  return apiFetch('/api/ingest', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path, recursive }),
  });
}

export async function getJobs(): Promise<JobsListResponse> {
  return apiFetch('/api/jobs');
}

export async function retryJob(id: string): Promise<RetryResponse> {
  return apiFetch(`/api/jobs/${id}/retry`, { method: 'POST' });
}

export async function revealVideo(id: string): Promise<void> {
  await apiFetch(`/api/videos/${id}/reveal`, { method: 'POST' });
}

export async function listFs(path?: string): Promise<FsListResponse> {
  const url = '/api/fs/list' + (path ? `?path=${encodeURIComponent(path)}` : '');
  return apiFetch(url);
}

export async function getSettings(): Promise<Record<string, unknown>> {
  return apiFetch('/api/settings');
}

export async function patchSettings(patch: Partial<SettingsPatch>): Promise<Record<string, unknown>> {
  return apiFetch('/api/settings', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  });
}
