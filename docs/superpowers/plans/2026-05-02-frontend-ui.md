# Frontend UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a SvelteKit SPA that gives users a search-first interface for their local video library, compiled to static files served by the existing FastAPI server.

**Architecture:** SvelteKit 2 with `adapter-static` compiles the app to `src/videosearch/static/`. FastAPI gains a `StaticFiles(html=True)` mount that serves those files — `html=True` provides the SPA fallback (any unmatched path returns `index.html`). During development, Vite proxies `/api` and `/ws` to the FastAPI server on port 8083. Three Svelte `writable` stores (`searchResults`, `activeVideo`, `jobs`) cover all runtime state; the `jobs` store is fed by a WebSocket client that auto-reconnects on disconnect.

**Tech Stack:** SvelteKit 2, Svelte 5, TypeScript 5, Vite 6, Vitest 3, `@testing-library/svelte` 5, `@sveltejs/adapter-static` 3, Node.js 22.

---

## File Structure

**Create (frontend project):**
- `frontend/package.json` — scripts, devDependencies
- `frontend/svelte.config.js` — adapter-static, output to `../src/videosearch/static`
- `frontend/vite.config.ts` — SvelteKit plugin, `/api` + `/ws` proxy
- `frontend/vitest.config.ts` — jsdom, globals, setup file
- `frontend/vitest-setup.ts` — `@testing-library/jest-dom/vitest` import
- `frontend/tsconfig.json` — extends `.svelte-kit/tsconfig.json`
- `frontend/src/routes/+layout.ts` — `ssr = false; prerender = false`
- `frontend/src/routes/+layout.svelte` — navbar, global CSS, WS init
- `frontend/src/routes/+page.svelte` — Search page (empty + results states)
- `frontend/src/routes/library/+page.svelte` — Library page
- `frontend/src/routes/jobs/+page.svelte` — Jobs page
- `frontend/src/routes/settings/+page.svelte` — Settings page
- `frontend/src/lib/types.ts` — TypeScript interfaces mirroring API models
- `frontend/src/lib/api.ts` — typed fetch wrappers (one per endpoint)
- `frontend/src/lib/api.test.ts` — Vitest unit tests with mocked fetch
- `frontend/src/lib/stores.ts` — `searchResults`, `activeVideo`, `jobs`, `upsertById`
- `frontend/src/lib/stores.test.ts` — unit tests for `upsertById`
- `frontend/src/lib/ws.ts` — WebSocket client with auto-reconnect
- `frontend/src/lib/ws.test.ts` — unit tests for reconnect logic
- `frontend/src/lib/components/MomentCard.svelte`
- `frontend/src/lib/components/MomentCard.test.ts`
- `frontend/src/lib/components/MomentGrid.svelte`
- `frontend/src/lib/components/MomentGrid.test.ts`
- `frontend/src/lib/components/VideoPlayer.svelte`
- `frontend/src/lib/components/VideoPlayer.test.ts`
- `frontend/src/lib/components/FolderPicker.svelte`
- `frontend/src/lib/components/FolderPicker.test.ts`
- `frontend/src/lib/components/JobItem.svelte`
- `frontend/src/lib/components/JobItem.test.ts`

**Modify:**
- `src/videosearch/api/app.py` — add `StaticFiles` mount after all routers

---

## Tasks

### Task 1: Scaffold SvelteKit project

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/svelte.config.js`
- Create: `frontend/vite.config.ts`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/vitest-setup.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/src/routes/+layout.ts`
- Create: `frontend/src/app.html`

- [ ] **Step 1: Create `frontend/package.json`**

```json
{
  "name": "videosearch-frontend",
  "version": "0.0.1",
  "private": true,
  "scripts": {
    "dev": "vite dev",
    "build": "vite build",
    "preview": "vite preview",
    "check": "svelte-kit sync && svelte-check --tsconfig ./tsconfig.json",
    "test": "vitest run"
  },
  "devDependencies": {
    "@sveltejs/adapter-static": "^3.0.0",
    "@sveltejs/kit": "^2.0.0",
    "@testing-library/jest-dom": "^6.0.0",
    "@testing-library/svelte": "^5.0.0",
    "jsdom": "^25.0.0",
    "svelte": "^5.0.0",
    "svelte-check": "^4.0.0",
    "typescript": "^5.0.0",
    "vite": "^6.0.0",
    "vitest": "^3.0.0"
  }
}
```

- [ ] **Step 2: Create `frontend/svelte.config.js`**

```js
import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

export default {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({
      pages: '../src/videosearch/static',
      assets: '../src/videosearch/static',
      fallback: 'index.html',
      precompress: false,
    }),
  },
};
```

- [ ] **Step 3: Create `frontend/vite.config.ts`**

```typescript
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [sveltekit()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://localhost:8083',
      '/ws': { target: 'ws://localhost:8083', ws: true },
    },
  },
});
```

- [ ] **Step 4: Create `frontend/vitest.config.ts`**

```typescript
import { defineConfig } from 'vitest/config';
import { sveltekit } from '@sveltejs/kit/vite';

export default defineConfig({
  plugins: [sveltekit()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest-setup.ts'],
  },
});
```

- [ ] **Step 5: Create `frontend/vitest-setup.ts`**

```typescript
import '@testing-library/jest-dom/vitest';
```

- [ ] **Step 6: Create `frontend/tsconfig.json`**

```json
{
  "extends": "./.svelte-kit/tsconfig.json",
  "compilerOptions": {
    "allowJs": true,
    "checkJs": true,
    "esModuleInterop": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "skipLibCheck": true,
    "sourceMap": true,
    "strict": true
  }
}
```

- [ ] **Step 7: Create `frontend/src/app.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <link rel="icon" href="%sveltekit.assets%/favicon.png" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    %sveltekit.head%
  </head>
  <body data-sveltekit-preload-data="hover">
    <div style="display: contents">%sveltekit.body%</div>
  </body>
</html>
```

- [ ] **Step 8: Create `frontend/src/routes/+layout.ts`**

```typescript
export const prerender = false;
export const ssr = false;
```

- [ ] **Step 9: Install dependencies**

```bash
cd frontend && npm install
```

Expected: `node_modules/` created, no errors.

- [ ] **Step 10: Run `svelte-kit sync` to generate `.svelte-kit/` (required for tsconfig)**

```bash
cd frontend && npx svelte-kit sync
```

Expected: `.svelte-kit/` directory created.

- [ ] **Step 11: Verify vitest runs (no tests yet, should exit 0 or report "no test files")**

```bash
cd frontend && npm test
```

Expected: exit 0 (or `No test files found` — either is acceptable at this stage).

- [ ] **Step 12: Commit**

```bash
git add frontend/
git commit -m "feat(frontend): scaffold SvelteKit project"
```

---

### Task 2: TypeScript types + API client

**Files:**
- Create: `frontend/src/lib/types.ts`
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/lib/api.test.ts`

- [ ] **Step 1: Create `frontend/src/lib/types.ts`**

These types mirror the FastAPI Pydantic response models exactly.

```typescript
export interface HealthResponse {
  status: string;
  db: boolean;
  models_loaded: boolean;
  gpu_backend: string;
  indexed_count: number;
}

export interface MomentResponse {
  timestamp_sec: number;
  score: number;
  thumb_url: string | null;
  caption: string | null;
  source: 'frame' | 'caption';
}

export interface VideoResultResponse {
  video_id: string;
  path: string;
  duration_sec: number;
  top_score: number;
  moments: MomentResponse[];
}

export interface SearchResponse {
  query: string;
  results: VideoResultResponse[];
}

export interface FolderCounts {
  indexed: number;
  pending: number;
  failed: number;
  missing: number;
}

export interface FolderResponse {
  id: string;
  path: string;
  added_at: number;
  counts: FolderCounts;
}

export interface LibraryResponse {
  folders: FolderResponse[];
  ad_hoc_counts: FolderCounts;
}

export interface RegisterFolderResponse {
  folder: FolderResponse;
  enqueued: number;
}

export interface Job {
  id: string;
  video_id: string | null;
  path: string | null;
  kind: string;
  status: string;
  progress: number;
  error: string | null;
  created_at: number;
  updated_at: number;
}

export interface JobsListResponse {
  jobs: Job[];
}

export interface RetryResponse {
  job_id: string;
}

export interface FsEntry {
  name: string;
  path: string;
  kind: 'dir' | 'video' | 'other';
  size_bytes: number | null;
  mtime: number;
}

export interface FsListResponse {
  path: string;
  parent: string | null;
  entries: FsEntry[];
}

export interface IngestResponse {
  enqueued: string[];
}

export interface SettingsPatch {
  frame_fps?: number | null;
  scene_detection?: boolean | null;
  port?: number | null;
  siglip_model?: string | null;
  text_embedder?: string | null;
  vlm_model?: string | null;
  vlm_mmproj?: string | null;
  vlm_n_gpu_layers?: number | null;
}
```

- [ ] **Step 2: Write failing tests in `frontend/src/lib/api.test.ts`**

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  search, getHealth, getLibrary, addFolder, deleteFolder,
  rescanFolder, getJobs, retryJob, revealVideo, listFs,
  getSettings, patchSettings,
} from './api';

function mockFetch(body: unknown, status = 200) {
  return vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    statusText: status === 200 ? 'OK' : 'Error',
    json: () => Promise.resolve(body),
    text: () => Promise.resolve(JSON.stringify(body)),
  });
}

beforeEach(() => {
  vi.unstubAllGlobals();
});

describe('search', () => {
  it('POSTs to /api/search and returns SearchResponse', async () => {
    const response = { query: 'dogs', results: [] };
    vi.stubGlobal('fetch', mockFetch(response));
    const result = await search('dogs', 5);
    expect(result).toEqual(response);
    expect(fetch).toHaveBeenCalledWith('/api/search', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ query: 'dogs', k: 5 }),
    }));
  });
});

describe('getHealth', () => {
  it('GETs /api/health', async () => {
    const response = { status: 'ok', db: true, models_loaded: true, gpu_backend: 'cpu', indexed_count: 12 };
    vi.stubGlobal('fetch', mockFetch(response));
    const result = await getHealth();
    expect(result).toEqual(response);
    expect(fetch).toHaveBeenCalledWith('/api/health', undefined);
  });
});

describe('getLibrary', () => {
  it('GETs /api/library', async () => {
    const response = { folders: [], ad_hoc_counts: { indexed: 0, pending: 0, failed: 0, missing: 0 } };
    vi.stubGlobal('fetch', mockFetch(response));
    const result = await getLibrary();
    expect(result).toEqual(response);
  });
});

describe('addFolder', () => {
  it('POSTs path to /api/library/folders', async () => {
    const response = { folder: { id: '1', path: '/home/user/videos', added_at: 0, counts: { indexed: 0, pending: 1, failed: 0, missing: 0 } }, enqueued: 1 };
    vi.stubGlobal('fetch', mockFetch(response));
    await addFolder('/home/user/videos');
    expect(fetch).toHaveBeenCalledWith('/api/library/folders', expect.objectContaining({
      method: 'POST',
      body: JSON.stringify({ path: '/home/user/videos' }),
    }));
  });
});

describe('deleteFolder', () => {
  it('DELETEs /api/library/folders/{id}', async () => {
    vi.stubGlobal('fetch', mockFetch({}));
    await deleteFolder('folder-1');
    expect(fetch).toHaveBeenCalledWith('/api/library/folders/folder-1', expect.objectContaining({ method: 'DELETE' }));
  });
});

describe('rescanFolder', () => {
  it('POSTs to /api/library/folders/{id}/rescan', async () => {
    vi.stubGlobal('fetch', mockFetch({ enqueued: 3 }));
    const result = await rescanFolder('folder-1');
    expect(result).toEqual({ enqueued: 3 });
  });
});

describe('getJobs', () => {
  it('GETs /api/jobs', async () => {
    vi.stubGlobal('fetch', mockFetch({ jobs: [] }));
    const result = await getJobs();
    expect(result).toEqual({ jobs: [] });
  });
});

describe('retryJob', () => {
  it('POSTs to /api/jobs/{id}/retry', async () => {
    vi.stubGlobal('fetch', mockFetch({ job_id: 'new-job' }));
    const result = await retryJob('job-1');
    expect(result).toEqual({ job_id: 'new-job' });
    expect(fetch).toHaveBeenCalledWith('/api/jobs/job-1/retry', expect.objectContaining({ method: 'POST' }));
  });
});

describe('revealVideo', () => {
  it('POSTs to /api/videos/{id}/reveal', async () => {
    vi.stubGlobal('fetch', mockFetch({ ok: true }));
    await revealVideo('vid-1');
    expect(fetch).toHaveBeenCalledWith('/api/videos/vid-1/reveal', expect.objectContaining({ method: 'POST' }));
  });
});

describe('listFs', () => {
  it('GETs /api/fs/list with no path', async () => {
    vi.stubGlobal('fetch', mockFetch({ path: '/home/user', parent: null, entries: [] }));
    await listFs();
    expect(fetch).toHaveBeenCalledWith('/api/fs/list', undefined);
  });

  it('encodes path in query string', async () => {
    vi.stubGlobal('fetch', mockFetch({ path: '/home/user/my videos', parent: '/home/user', entries: [] }));
    await listFs('/home/user/my videos');
    expect(fetch).toHaveBeenCalledWith('/api/fs/list?path=%2Fhome%2Fuser%2Fmy%20videos', undefined);
  });
});

describe('getSettings', () => {
  it('GETs /api/settings', async () => {
    vi.stubGlobal('fetch', mockFetch({ frame_fps: 1.0 }));
    const result = await getSettings();
    expect(result).toEqual({ frame_fps: 1.0 });
  });
});

describe('patchSettings', () => {
  it('PATCHes /api/settings with provided fields', async () => {
    vi.stubGlobal('fetch', mockFetch({ frame_fps: 2.0 }));
    await patchSettings({ frame_fps: 2.0 });
    expect(fetch).toHaveBeenCalledWith('/api/settings', expect.objectContaining({
      method: 'PATCH',
      body: JSON.stringify({ frame_fps: 2.0 }),
    }));
  });
});

describe('error handling', () => {
  it('throws on non-ok response', async () => {
    vi.stubGlobal('fetch', mockFetch({ detail: 'not found' }, 404));
    await expect(getHealth()).rejects.toThrow();
  });
});
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
cd frontend && npm test -- --reporter=verbose 2>&1 | head -30
```

Expected: Tests fail with `Cannot find module './api'` or similar.

- [ ] **Step 4: Implement `frontend/src/lib/api.ts`**

```typescript
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
```

- [ ] **Step 5: Run tests and confirm they pass**

```bash
cd frontend && npm test -- --reporter=verbose 2>&1 | tail -20
```

Expected: All tests PASS, no failures.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/
git commit -m "feat(frontend): add TypeScript types and API client"
```

---

### Task 3: Stores and WebSocket client

**Files:**
- Create: `frontend/src/lib/stores.ts`
- Create: `frontend/src/lib/stores.test.ts`
- Create: `frontend/src/lib/ws.ts`
- Create: `frontend/src/lib/ws.test.ts`

- [ ] **Step 1: Write failing tests in `frontend/src/lib/stores.test.ts`**

```typescript
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
```

- [ ] **Step 2: Write failing tests in `frontend/src/lib/ws.test.ts`**

```typescript
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

  it('closes and reconnects on error', () => {
    connectJobsSocket();
    mockWs.onerror?.();
    expect(mockWs.close).toHaveBeenCalled();
  });
});
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
cd frontend && npm test -- --reporter=verbose 2>&1 | grep -E "FAIL|PASS|Cannot find"
```

Expected: Fail with `Cannot find module './stores'` and `./ws`.

- [ ] **Step 4: Implement `frontend/src/lib/stores.ts`**

```typescript
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
```

- [ ] **Step 5: Implement `frontend/src/lib/ws.ts`**

The WebSocket server sends `job_id` (not `id`) as the job identifier. This file remaps it to `id` before upserting.

```typescript
import { jobs, upsertById } from './stores';
import type { Job } from './types';

type WsEvent = Omit<Job, 'id'> & { job_id: string };

export function connectJobsSocket(): void {
  const ws = new WebSocket(`ws://${location.host}/ws/jobs`);

  ws.onmessage = (e: MessageEvent) => {
    const raw = JSON.parse(e.data as string) as WsEvent;
    const job: Job = { ...raw, id: raw.job_id };
    jobs.update(list => upsertById(list, job));
  };

  ws.onclose = () => {
    setTimeout(connectJobsSocket, 2000);
  };

  ws.onerror = () => {
    ws.close();
  };
}
```

- [ ] **Step 6: Run tests and confirm they pass**

```bash
cd frontend && npm test -- --reporter=verbose 2>&1 | tail -20
```

Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/stores.ts frontend/src/lib/stores.test.ts frontend/src/lib/ws.ts frontend/src/lib/ws.test.ts
git commit -m "feat(frontend): add stores and WebSocket client"
```

---

### Task 4: Layout — navbar and global styles

**Files:**
- Create: `frontend/src/routes/+layout.svelte`
- Create: `frontend/src/lib/components/Layout.test.ts` (tests `+layout.svelte` logic indirectly via stores)

The navbar shows the app logo and four nav links. The active link (matching the current pathname) is underlined in green. `connectJobsSocket` is called once on mount.

- [ ] **Step 1: Create `frontend/src/routes/+layout.svelte`**

```svelte
<script lang="ts">
  import type { Snippet } from 'svelte';
  import { page } from '$app/state';
  import { onMount } from 'svelte';
  import { connectJobsSocket } from '$lib/ws';

  let { children }: { children: Snippet } = $props();

  onMount(() => {
    connectJobsSocket();
  });

  const navItems = [
    { label: 'Search', href: '/' },
    { label: 'Library', href: '/library' },
    { label: 'Jobs', href: '/jobs' },
    { label: 'Settings', href: '/settings' },
  ];
</script>

<div class="app">
  <nav class="navbar">
    <div class="logo">
      <div class="logo-square" aria-hidden="true"></div>
      <span class="logo-text">VIDEOSEARCH</span>
    </div>
    <div class="nav-links">
      {#each navItems as item}
        <a
          href={item.href}
          class="nav-link"
          class:active={page.url.pathname === item.href}
        >{item.label}</a>
      {/each}
    </div>
  </nav>

  <main class="main-content">
    {@render children()}
  </main>
</div>

<style>
  :global(*) {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
  }

  :global(body) {
    background: #0d0d0d;
    color: #e0e0e0;
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 14px;
    min-height: 100vh;
  }

  :global(button) {
    cursor: pointer;
    font-family: inherit;
    font-size: inherit;
  }

  .app {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
  }

  .navbar {
    background: #111;
    border-bottom: 1px solid #1e1e1e;
    padding: 10px 20px;
    display: flex;
    align-items: center;
    gap: 20px;
    flex-shrink: 0;
  }

  .logo {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .logo-square {
    width: 20px;
    height: 20px;
    background: #4ade80;
    border-radius: 4px;
  }

  .logo-text {
    font-family: ui-monospace, 'Cascadia Code', 'Source Code Pro', monospace;
    font-size: 11px;
    color: #4ade80;
    font-weight: 700;
    letter-spacing: 0.08em;
  }

  .nav-links {
    margin-left: auto;
    display: flex;
    gap: 20px;
    align-items: center;
  }

  .nav-link {
    font-size: 11px;
    color: #555;
    text-decoration: none;
    padding-bottom: 2px;
  }

  .nav-link.active {
    color: #4ade80;
    border-bottom: 1px solid #4ade80;
  }

  .nav-link:not(.active):hover {
    color: #888;
  }

  .main-content {
    flex: 1;
    display: flex;
    flex-direction: column;
  }
</style>
```

- [ ] **Step 2: Verify the dev server can parse the layout (syntax check)**

```bash
cd frontend && npx svelte-check --tsconfig ./tsconfig.json 2>&1 | tail -10
```

Expected: 0 errors (warnings about unused CSS are fine). If `.svelte-kit/tsconfig.json` doesn't exist yet, run `npx svelte-kit sync` first.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/routes/+layout.svelte
git commit -m "feat(frontend): add navbar layout with global styles"
```

---

### Task 5: MomentCard and MomentGrid components

**Files:**
- Create: `frontend/src/lib/components/MomentCard.svelte`
- Create: `frontend/src/lib/components/MomentCard.test.ts`
- Create: `frontend/src/lib/components/MomentGrid.svelte`
- Create: `frontend/src/lib/components/MomentGrid.test.ts`

Each `MomentCard` shows a frame thumbnail (or placeholder), a green timestamp, a caption, and a filename. Clicking it calls `onselect`. The selected card gets a green border. `MomentGrid` renders a scrollable column of cards and forwards the select event.

- [ ] **Step 1: Write failing tests in `frontend/src/lib/components/MomentCard.test.ts`**

```typescript
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import MomentCard from './MomentCard.svelte';
import type { MomentResponse } from '$lib/types';

const moment: MomentResponse = {
  timestamp_sec: 42.5,
  score: 0.9,
  thumb_url: null,
  caption: 'A dog runs on the beach',
  source: 'caption',
};

describe('MomentCard', () => {
  it('renders the caption', () => {
    render(MomentCard, { moment });
    expect(screen.getByText('A dog runs on the beach')).toBeInTheDocument();
  });

  it('renders the timestamp formatted as m:ss', () => {
    render(MomentCard, { moment });
    expect(screen.getByText('0:42')).toBeInTheDocument();
  });

  it('calls onselect with the moment when clicked', async () => {
    const onselect = vi.fn();
    render(MomentCard, { moment, onselect });
    await fireEvent.click(screen.getByRole('article'));
    expect(onselect).toHaveBeenCalledWith(moment);
  });

  it('applies selected class when selected=true', () => {
    render(MomentCard, { moment, selected: true });
    expect(screen.getByRole('article')).toHaveClass('selected');
  });

  it('renders thumbnail image when thumb_url is set', () => {
    const momentWithThumb = { ...moment, thumb_url: '/api/videos/v1/thumbs/10' };
    render(MomentCard, { moment: momentWithThumb });
    expect(screen.getByRole('img')).toHaveAttribute('src', '/api/videos/v1/thumbs/10');
  });
});
```

- [ ] **Step 2: Write failing tests in `frontend/src/lib/components/MomentGrid.test.ts`**

```typescript
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import MomentGrid from './MomentGrid.svelte';
import type { MomentResponse, VideoResultResponse } from '$lib/types';

const makeMoment = (caption: string, timestamp_sec: number): MomentResponse => ({
  timestamp_sec, score: 0.8, thumb_url: null, caption, source: 'caption',
});

const results: VideoResultResponse[] = [
  { video_id: 'v1', path: '/a.mp4', duration_sec: 60, top_score: 0.9, moments: [makeMoment('Dog on beach', 10)] },
  { video_id: 'v2', path: '/b.mp4', duration_sec: 120, top_score: 0.7, moments: [makeMoment('Cat napping', 30)] },
];

describe('MomentGrid', () => {
  it('renders all moments across results', () => {
    render(MomentGrid, { results, activeVideoId: null, activeMomentTimestamp: null });
    expect(screen.getByText('Dog on beach')).toBeInTheDocument();
    expect(screen.getByText('Cat napping')).toBeInTheDocument();
  });

  it('calls onselect when a card is clicked', async () => {
    const onselect = vi.fn();
    render(MomentGrid, { results, activeVideoId: null, activeMomentTimestamp: null, onselect });
    await fireEvent.click(screen.getByText('Dog on beach').closest('article')!);
    expect(onselect).toHaveBeenCalledWith({ videoId: 'v1', frameIdx: null, timestamp: 10 });
  });
});
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
cd frontend && npm test -- --reporter=verbose 2>&1 | grep -E "MomentCard|MomentGrid|FAIL"
```

Expected: Fail with `Cannot find module`.

- [ ] **Step 4: Implement `frontend/src/lib/components/MomentCard.svelte`**

```svelte
<script lang="ts">
  import type { MomentResponse } from '$lib/types';

  let {
    moment,
    filename = '',
    selected = false,
    onselect,
  }: {
    moment: MomentResponse;
    filename?: string;
    selected?: boolean;
    onselect?: (moment: MomentResponse) => void;
  } = $props();

  function formatTime(sec: number): string {
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  }
</script>

<article
  class="card"
  class:selected
  role="article"
  tabindex="0"
  onclick={() => onselect?.(moment)}
  onkeydown={(e) => e.key === 'Enter' && onselect?.(moment)}
>
  <div class="thumb">
    {#if moment.thumb_url}
      <img src={moment.thumb_url} alt="frame thumbnail" />
    {:else}
      <div class="thumb-placeholder" aria-hidden="true">▶</div>
    {/if}
    <span class="timestamp">{formatTime(moment.timestamp_sec)}</span>
  </div>
  <div class="info">
    <p class="caption">{moment.caption ?? ''}</p>
    {#if filename}
      <p class="filename">{filename}</p>
    {/if}
  </div>
</article>

<style>
  .card {
    background: #1a1a1a;
    border: 1px solid #1e1e1e;
    border-radius: 8px;
    overflow: hidden;
    cursor: pointer;
    flex-shrink: 0;
    transition: border-color 0.1s;
  }

  .card:hover {
    border-color: #2a2a2a;
  }

  .card.selected {
    border-color: #4ade80;
  }

  .thumb {
    height: 72px;
    background: #222;
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
  }

  .thumb img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .thumb-placeholder {
    color: #333;
    font-size: 16px;
  }

  .timestamp {
    position: absolute;
    bottom: 4px;
    left: 4px;
    background: rgba(0, 0, 0, 0.7);
    color: #4ade80;
    font-size: 9px;
    padding: 1px 4px;
    border-radius: 3px;
    font-family: ui-monospace, monospace;
  }

  .info {
    padding: 6px 8px;
  }

  .caption {
    font-size: 9px;
    color: #e0e0e0;
    line-height: 1.3;
    margin-bottom: 3px;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .filename {
    font-size: 8px;
    color: #555;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
```

- [ ] **Step 5: Implement `frontend/src/lib/components/MomentGrid.svelte`**

```svelte
<script lang="ts">
  import type { VideoResultResponse, MomentResponse } from '$lib/types';
  import MomentCard from './MomentCard.svelte';

  let {
    results,
    activeVideoId,
    activeMomentTimestamp,
    onselect,
  }: {
    results: VideoResultResponse[];
    activeVideoId: string | null;
    activeMomentTimestamp: number | null;
    onselect?: (selection: { videoId: string; frameIdx: number | null; timestamp: number }) => void;
  } = $props();

  function handleSelect(videoId: string, moment: MomentResponse) {
    onselect?.({
      videoId,
      frameIdx: null,
      timestamp: moment.timestamp_sec,
    });
  }

  function isSelected(videoId: string, moment: MomentResponse): boolean {
    return activeVideoId === videoId && activeMomentTimestamp === moment.timestamp_sec;
  }

  function filename(path: string): string {
    return path.split('/').pop() ?? path;
  }
</script>

<div class="grid">
  {#each results as result}
    {#each result.moments as moment}
      <MomentCard
        {moment}
        filename={filename(result.path)}
        selected={isSelected(result.video_id, moment)}
        onselect={() => handleSelect(result.video_id, moment)}
      />
    {/each}
  {/each}
</div>

<style>
  .grid {
    display: flex;
    flex-direction: column;
    gap: 8px;
    overflow-y: auto;
    width: 240px;
    flex-shrink: 0;
  }
</style>
```

- [ ] **Step 6: Run tests and confirm they pass**

```bash
cd frontend && npm test -- --reporter=verbose 2>&1 | tail -20
```

Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/components/MomentCard.svelte frontend/src/lib/components/MomentCard.test.ts frontend/src/lib/components/MomentGrid.svelte frontend/src/lib/components/MomentGrid.test.ts
git commit -m "feat(frontend): add MomentCard and MomentGrid components"
```

---

### Task 6: VideoPlayer component

**Files:**
- Create: `frontend/src/lib/components/VideoPlayer.svelte`
- Create: `frontend/src/lib/components/VideoPlayer.test.ts`

The player subscribes to `activeVideo`. When it changes, it swaps the `src` (if the `video_id` changed) and seeks to `timestamp`. Below the player: filename, caption, and a Reveal button.

- [ ] **Step 1: Write failing test in `frontend/src/lib/components/VideoPlayer.test.ts`**

```typescript
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import { tick } from 'svelte';
import VideoPlayer from './VideoPlayer.svelte';
import { activeVideo } from '$lib/stores';
import * as api from '$lib/api';

vi.mock('$lib/api');

beforeEach(() => {
  activeVideo.set(null);
  vi.mocked(api.revealVideo).mockResolvedValue(undefined);
});

describe('VideoPlayer', () => {
  it('renders nothing when activeVideo is null', () => {
    render(VideoPlayer, { caption: null, path: null });
    expect(screen.queryByRole('region')).not.toBeInTheDocument();
  });

  it('seeks to timestamp when activeVideo changes', async () => {
    const seekSpy = vi.spyOn(HTMLMediaElement.prototype, 'currentTime', 'set');
    render(VideoPlayer, { caption: null, path: '/video.mp4' });

    activeVideo.set({ videoId: 'v1', frameIdx: null, timestamp: 42.5 });
    await tick();

    expect(seekSpy).toHaveBeenCalledWith(42.5);
  });

  it('shows Reveal button and calls revealVideo on click', async () => {
    render(VideoPlayer, { caption: 'A dog', path: '/video.mp4' });
    activeVideo.set({ videoId: 'v1', frameIdx: null, timestamp: 10 });
    await tick();

    const btn = await screen.findByText(/reveal/i);
    await fireEvent.click(btn);
    expect(api.revealVideo).toHaveBeenCalledWith('v1');
  });

  it('shows caption below player', async () => {
    render(VideoPlayer, { caption: 'A dog on the beach', path: '/video.mp4' });
    activeVideo.set({ videoId: 'v1', frameIdx: null, timestamp: 10 });
    await tick();
    expect(screen.getByText('A dog on the beach')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd frontend && npm test -- VideoPlayer.test --reporter=verbose 2>&1 | tail -15
```

Expected: FAIL with `Cannot find module './VideoPlayer.svelte'`.

- [ ] **Step 3: Implement `frontend/src/lib/components/VideoPlayer.svelte`**

```svelte
<script lang="ts">
  import { activeVideo } from '$lib/stores';
  import { revealVideo } from '$lib/api';

  let { caption, path }: { caption: string | null; path: string | null } = $props();

  let videoEl: HTMLVideoElement | undefined = $state();
  let currentVideoId: string | null = $state(null);

  $effect(() => {
    const av = $activeVideo;
    if (!av || !videoEl) return;

    if (av.videoId !== currentVideoId) {
      currentVideoId = av.videoId;
      videoEl.src = `/api/videos/${av.videoId}/stream`;
      videoEl.load();
    }
    videoEl.currentTime = av.timestamp;
    videoEl.play().catch(() => {});
  });

  async function handleReveal() {
    if ($activeVideo) {
      await revealVideo($activeVideo.videoId);
    }
  }
</script>

{#if $activeVideo}
  <div class="player" role="region" aria-label="video player">
    <div class="video-area">
      <video
        bind:this={videoEl}
        controls
        class="video-el"
      >
        <track kind="captions" />
      </video>
    </div>
    <div class="player-footer">
      <div class="player-meta">
        {#if path}
          <p class="player-filename">{path.split('/').pop()}</p>
        {/if}
        {#if caption}
          <p class="player-caption">{caption}</p>
        {/if}
      </div>
      <button class="reveal-btn" onclick={handleReveal}>📂 Reveal</button>
    </div>
  </div>
{/if}

<style>
  .player {
    flex: 1;
    background: #111;
    border-radius: 10px;
    border: 1px solid #1e1e1e;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .video-area {
    flex: 1;
    background: #0a0a0a;
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 160px;
  }

  .video-el {
    width: 100%;
    height: 100%;
    max-height: 480px;
    object-fit: contain;
  }

  .player-footer {
    padding: 10px 14px;
    border-top: 1px solid #1e1e1e;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 12px;
  }

  .player-meta {
    min-width: 0;
    flex: 1;
  }

  .player-filename {
    font-size: 11px;
    color: #e0e0e0;
    font-weight: 600;
    margin-bottom: 3px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .player-caption {
    font-size: 10px;
    color: #555;
    line-height: 1.4;
  }

  .reveal-btn {
    background: none;
    border: 1px solid #2a2a2a;
    color: #555;
    font-size: 9px;
    padding: 4px 8px;
    border-radius: 4px;
    white-space: nowrap;
    flex-shrink: 0;
  }

  .reveal-btn:hover {
    border-color: #4ade80;
    color: #4ade80;
  }
</style>
```

- [ ] **Step 4: Run tests and confirm they pass**

```bash
cd frontend && npm test -- VideoPlayer.test --reporter=verbose 2>&1 | tail -15
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/components/VideoPlayer.svelte frontend/src/lib/components/VideoPlayer.test.ts
git commit -m "feat(frontend): add VideoPlayer component"
```

---

### Task 7: Search page

**Files:**
- Create: `frontend/src/routes/+page.svelte`
- Create: `frontend/src/routes/page.test.ts`

**Empty state:** search bar centred vertically, moment count from `GET /api/health` below.
**Results state:** search bar at top-left area, left column (240 px) of `MomentGrid`, right column `VideoPlayer`.

- [ ] **Step 1: Write failing tests in `frontend/src/routes/page.test.ts`**

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import Page from './+page.svelte';
import * as api from '$lib/api';
import { searchResults, activeVideo } from '$lib/stores';

vi.mock('$lib/api');
vi.mock('$app/state', () => ({
  page: { url: { pathname: '/' } },
}));

beforeEach(() => {
  searchResults.set(null);
  activeVideo.set(null);
  vi.mocked(api.getHealth).mockResolvedValue({
    status: 'ok', db: true, models_loaded: true, gpu_backend: 'cpu', indexed_count: 247,
  });
  vi.mocked(api.search).mockResolvedValue({ query: 'dogs', results: [] });
});

describe('Search page — empty state', () => {
  it('shows the indexed moment count', async () => {
    render(Page);
    await screen.findByText(/247/);
  });

  it('shows the search input', () => {
    render(Page);
    expect(screen.getByRole('searchbox')).toBeInTheDocument();
  });
});

describe('Search page — after search', () => {
  it('calls api.search on form submit', async () => {
    render(Page);
    const input = screen.getByRole('searchbox');
    await fireEvent.input(input, { target: { value: 'dogs' } });
    await fireEvent.submit(input.closest('form')!);
    await waitFor(() => expect(api.search).toHaveBeenCalledWith('dogs', 10));
  });

  it('shows result count after search', async () => {
    vi.mocked(api.search).mockResolvedValue({
      query: 'dogs',
      results: [
        {
          video_id: 'v1', path: '/a.mp4', duration_sec: 60, top_score: 0.9,
          moments: [{ timestamp_sec: 10, score: 0.9, thumb_url: null, caption: 'Dog running', source: 'caption' as const }],
        },
      ],
    });
    render(Page);
    const input = screen.getByRole('searchbox');
    await fireEvent.input(input, { target: { value: 'dogs' } });
    await fireEvent.submit(input.closest('form')!);
    await screen.findByText(/1 moment/);
  });
});
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd frontend && npm test -- page.test --reporter=verbose 2>&1 | tail -15
```

Expected: FAIL with `Cannot find module './+page.svelte'`.

- [ ] **Step 3: Implement `frontend/src/routes/+page.svelte`**

```svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import { getHealth, search as apiSearch } from '$lib/api';
  import { searchResults, activeVideo } from '$lib/stores';
  import MomentGrid from '$lib/components/MomentGrid.svelte';
  import VideoPlayer from '$lib/components/VideoPlayer.svelte';
  import type { MomentResponse, VideoResultResponse } from '$lib/types';

  let query = $state('');
  let indexedCount = $state<number | null>(null);
  let loading = $state(false);

  onMount(async () => {
    try {
      const health = await getHealth();
      indexedCount = health.indexed_count;
    } catch {
      // health unavailable; count stays null
    }
  });

  async function handleSearch(e: SubmitEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    loading = true;
    try {
      const result = await apiSearch(query.trim(), 10);
      searchResults.set(result);
    } finally {
      loading = false;
    }
  }

  function totalMoments(results: VideoResultResponse[]): number {
    return results.reduce((sum, r) => sum + r.moments.length, 0);
  }

  function handleSelect(selection: { videoId: string; frameIdx: number | null; timestamp: number }) {
    activeVideo.set(selection);
  }

  let activeCaption = $derived.by(() => {
    const av = $activeVideo;
    if (!av || !$searchResults) return null;
    for (const vr of $searchResults.results) {
      if (vr.video_id === av.videoId) {
        const m = vr.moments.find(m => m.timestamp_sec === av.timestamp);
        return m?.caption ?? null;
      }
    }
    return null;
  });

  let activePath = $derived.by(() => {
    const av = $activeVideo;
    if (!av || !$searchResults) return null;
    return $searchResults.results.find(r => r.video_id === av.videoId)?.path ?? null;
  });
</script>

<div class="page" class:has-results={$searchResults !== null}>
  <div class="search-area">
    <form class="search-form" onsubmit={handleSearch}>
      <div class="search-bar">
        <span class="search-icon" aria-hidden="true">🔍</span>
        <input
          class="search-input"
          role="searchbox"
          type="text"
          placeholder="Search your videos…"
          bind:value={query}
          aria-label="search"
        />
        <button class="search-btn" type="submit" disabled={loading}>
          {loading ? '…' : 'Search'}
        </button>
      </div>
    </form>

    {#if $searchResults !== null}
      <p class="result-count">
        {totalMoments($searchResults.results)} moment{totalMoments($searchResults.results) === 1 ? '' : 's'} found
      </p>
    {:else if indexedCount !== null}
      <p class="indexed-count">{indexedCount} moments indexed</p>
    {/if}
  </div>

  {#if $searchResults !== null}
    <div class="results-area">
      <MomentGrid
        results={$searchResults.results}
        activeVideoId={$activeVideo?.videoId ?? null}
        activeMomentTimestamp={$activeVideo?.timestamp ?? null}
        onselect={handleSelect}
      />
      <VideoPlayer
        caption={activeCaption}
        path={activePath}
      />
    </div>
  {/if}
</div>

<style>
  .page {
    display: flex;
    flex-direction: column;
    flex: 1;
  }

  .page:not(.has-results) .search-area {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 20px;
    gap: 12px;
  }

  .page.has-results .search-area {
    padding: 16px 20px 12px;
  }

  .search-form {
    width: 100%;
    max-width: 500px;
  }

  .search-bar {
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 10px;
    padding: 10px 16px;
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .search-icon {
    font-size: 14px;
    color: #555;
  }

  .search-input {
    flex: 1;
    background: none;
    border: none;
    outline: none;
    font-size: 12px;
    color: #e0e0e0;
  }

  .search-input::placeholder {
    color: #333;
  }

  .search-btn {
    background: #4ade80;
    color: #000;
    font-size: 10px;
    font-weight: 700;
    padding: 4px 10px;
    border: none;
    border-radius: 5px;
  }

  .search-btn:disabled {
    opacity: 0.5;
  }

  .result-count,
  .indexed-count {
    font-size: 10px;
    color: #333;
  }

  .results-area {
    display: flex;
    gap: 12px;
    padding: 0 20px 16px;
    flex: 1;
    min-height: 0;
  }
</style>
```

- [ ] **Step 4: Run tests and confirm they pass**

```bash
cd frontend && npm test -- page.test --reporter=verbose 2>&1 | tail -20
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/routes/+page.svelte frontend/src/routes/page.test.ts
git commit -m "feat(frontend): add Search page with empty and results states"
```

---

### Task 8: FolderPicker component

**Files:**
- Create: `frontend/src/lib/components/FolderPicker.svelte`
- Create: `frontend/src/lib/components/FolderPicker.test.ts`

A modal dialog that calls `GET /api/fs/list` on open and on each directory navigation step. Shows directories and video files. "Add this folder" calls `onconfirm` with the current path. "Cancel" calls `oncancel`.

- [ ] **Step 1: Write failing tests in `frontend/src/lib/components/FolderPicker.test.ts`**

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import FolderPicker from './FolderPicker.svelte';
import * as api from '$lib/api';

vi.mock('$lib/api');

const homeFs = {
  path: '/home/user',
  parent: null,
  entries: [
    { name: 'videos', path: '/home/user/videos', kind: 'dir' as const, size_bytes: null, mtime: 0 },
    { name: 'movie.mp4', path: '/home/user/movie.mp4', kind: 'video' as const, size_bytes: 1024, mtime: 0 },
    { name: 'readme.txt', path: '/home/user/readme.txt', kind: 'other' as const, size_bytes: 100, mtime: 0 },
  ],
};

beforeEach(() => {
  vi.mocked(api.listFs).mockResolvedValue(homeFs);
});

describe('FolderPicker', () => {
  it('shows current path on load', async () => {
    render(FolderPicker, { onconfirm: vi.fn(), oncancel: vi.fn() });
    await screen.findByText('/home/user');
  });

  it('lists directories and video files', async () => {
    render(FolderPicker, { onconfirm: vi.fn(), oncancel: vi.fn() });
    await screen.findByText('videos');
    expect(screen.getByText('movie.mp4')).toBeInTheDocument();
    expect(screen.queryByText('readme.txt')).not.toBeInTheDocument();
  });

  it('navigates into a directory on click', async () => {
    const subFs = { path: '/home/user/videos', parent: '/home/user', entries: [] };
    vi.mocked(api.listFs).mockResolvedValueOnce(homeFs).mockResolvedValueOnce(subFs);
    render(FolderPicker, { onconfirm: vi.fn(), oncancel: vi.fn() });
    await screen.findByText('videos');
    await fireEvent.click(screen.getByText('videos'));
    await screen.findByText('/home/user/videos');
  });

  it('navigates to parent on ".." click', async () => {
    const subFs = { path: '/home/user/videos', parent: '/home/user', entries: [] };
    vi.mocked(api.listFs).mockResolvedValueOnce(subFs);
    render(FolderPicker, { onconfirm: vi.fn(), oncancel: vi.fn() });
    await screen.findByText('/home/user/videos');
    vi.mocked(api.listFs).mockResolvedValueOnce(homeFs);
    await fireEvent.click(screen.getByText('..'));
    await screen.findByText('/home/user');
  });

  it('calls onconfirm with current path on "Add this folder"', async () => {
    const onconfirm = vi.fn();
    render(FolderPicker, { onconfirm, oncancel: vi.fn() });
    await screen.findByText('/home/user');
    await fireEvent.click(screen.getByText('Add this folder'));
    expect(onconfirm).toHaveBeenCalledWith('/home/user');
  });

  it('calls oncancel on "Cancel"', async () => {
    const oncancel = vi.fn();
    render(FolderPicker, { onconfirm: vi.fn(), oncancel });
    await screen.findByText('/home/user');
    await fireEvent.click(screen.getByText('Cancel'));
    expect(oncancel).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd frontend && npm test -- FolderPicker.test --reporter=verbose 2>&1 | tail -10
```

Expected: FAIL with `Cannot find module './FolderPicker.svelte'`.

- [ ] **Step 3: Implement `frontend/src/lib/components/FolderPicker.svelte`**

```svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import { listFs } from '$lib/api';
  import type { FsEntry } from '$lib/types';

  let {
    onconfirm,
    oncancel,
  }: {
    onconfirm: (path: string) => void;
    oncancel: () => void;
  } = $props();

  let currentPath = $state<string | null>(null);
  let parentPath = $state<string | null>(null);
  let entries = $state<FsEntry[]>([]);
  let loading = $state(true);

  async function navigate(path?: string) {
    loading = true;
    try {
      const result = await listFs(path);
      currentPath = result.path;
      parentPath = result.parent;
      entries = result.entries.filter(e => e.kind === 'dir' || e.kind === 'video');
    } finally {
      loading = false;
    }
  }

  onMount(() => navigate());
</script>

<div class="overlay" role="dialog" aria-modal="true" aria-label="folder picker">
  <div class="modal">
    <div class="modal-header">
      <h2 class="modal-title">Add Folder</h2>
      <p class="current-path">{currentPath ?? '…'}</p>
    </div>

    <div class="entry-list">
      {#if loading}
        <p class="loading">Loading…</p>
      {:else}
        {#if parentPath !== null}
          <button class="entry entry-dir" onclick={() => navigate(parentPath ?? undefined)}>
            <span class="entry-icon">📁</span>
            <span class="entry-name">..</span>
          </button>
        {/if}
        {#each entries as entry}
          {#if entry.kind === 'dir'}
            <button class="entry entry-dir" onclick={() => navigate(entry.path)}>
              <span class="entry-icon">📁</span>
              <span class="entry-name">{entry.name}</span>
            </button>
          {:else}
            <div class="entry entry-video">
              <span class="entry-icon">🎬</span>
              <span class="entry-name">{entry.name}</span>
            </div>
          {/if}
        {/each}
        {#if entries.length === 0 && parentPath !== null}
          <p class="empty">Empty directory</p>
        {/if}
      {/if}
    </div>

    <div class="modal-footer">
      <button class="btn-cancel" onclick={oncancel}>Cancel</button>
      <button class="btn-confirm" onclick={() => currentPath && onconfirm(currentPath)}>
        Add this folder
      </button>
    </div>
  </div>
</div>

<style>
  .overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
  }

  .modal {
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 12px;
    width: 480px;
    max-width: 90vw;
    max-height: 80vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .modal-header {
    padding: 16px 20px 12px;
    border-bottom: 1px solid #222;
  }

  .modal-title {
    font-size: 13px;
    color: #e0e0e0;
    font-weight: 600;
    margin-bottom: 4px;
  }

  .current-path {
    font-size: 10px;
    color: #4ade80;
    font-family: ui-monospace, monospace;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .entry-list {
    flex: 1;
    overflow-y: auto;
    padding: 8px 0;
  }

  .entry {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 20px;
    font-size: 12px;
    width: 100%;
    text-align: left;
    background: none;
    border: none;
    color: #e0e0e0;
  }

  .entry-dir {
    cursor: pointer;
  }

  .entry-dir:hover {
    background: #222;
  }

  .entry-video {
    color: #555;
    cursor: default;
  }

  .entry-icon {
    font-size: 14px;
    flex-shrink: 0;
  }

  .entry-name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .loading,
  .empty {
    padding: 20px;
    text-align: center;
    font-size: 11px;
    color: #555;
  }

  .modal-footer {
    padding: 12px 20px;
    border-top: 1px solid #222;
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }

  .btn-cancel {
    background: none;
    border: 1px solid #2a2a2a;
    color: #555;
    font-size: 11px;
    padding: 6px 14px;
    border-radius: 6px;
  }

  .btn-cancel:hover {
    border-color: #555;
    color: #888;
  }

  .btn-confirm {
    background: #4ade80;
    border: none;
    color: #000;
    font-size: 11px;
    font-weight: 700;
    padding: 6px 14px;
    border-radius: 6px;
  }

  .btn-confirm:hover {
    background: #6ae896;
  }
</style>
```

- [ ] **Step 4: Run tests and confirm they pass**

```bash
cd frontend && npm test -- FolderPicker.test --reporter=verbose 2>&1 | tail -15
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/components/FolderPicker.svelte frontend/src/lib/components/FolderPicker.test.ts
git commit -m "feat(frontend): add FolderPicker modal component"
```

---

### Task 9: Library page

**Files:**
- Create: `frontend/src/routes/library/+page.svelte`
- Create: `frontend/src/routes/library/page.test.ts`

Lists registered library folders with counts. "Add Folder" opens `FolderPicker`. "Rescan" calls the rescan endpoint. "Remove" with confirmation calls the delete endpoint.

- [ ] **Step 1: Write failing tests in `frontend/src/routes/library/page.test.ts`**

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import Page from './+page.svelte';
import * as api from '$lib/api';

vi.mock('$lib/api');
vi.mock('$app/state', () => ({ page: { url: { pathname: '/library' } } }));

const folder = {
  id: 'f1',
  path: '/home/user/videos',
  added_at: 0,
  counts: { indexed: 5, pending: 0, failed: 0, missing: 1 },
};

beforeEach(() => {
  vi.mocked(api.getLibrary).mockResolvedValue({ folders: [folder], ad_hoc_counts: { indexed: 0, pending: 0, failed: 0, missing: 0 } });
  vi.mocked(api.rescanFolder).mockResolvedValue({ enqueued: 2 });
  vi.mocked(api.deleteFolder).mockResolvedValue(undefined);
  vi.mocked(api.addFolder).mockResolvedValue({ folder, enqueued: 1 });
});

describe('Library page', () => {
  it('lists folder paths', async () => {
    render(Page);
    await screen.findByText('/home/user/videos');
  });

  it('shows indexed and missing counts', async () => {
    render(Page);
    await screen.findByText(/5 indexed/);
    await screen.findByText(/1 missing/);
  });

  it('calls rescanFolder on Rescan click', async () => {
    render(Page);
    await screen.findByText('Rescan');
    await fireEvent.click(screen.getByText('Rescan'));
    await waitFor(() => expect(api.rescanFolder).toHaveBeenCalledWith('f1'));
  });

  it('calls deleteFolder after Remove confirmation', async () => {
    vi.stubGlobal('confirm', () => true);
    render(Page);
    await screen.findByText('Remove');
    await fireEvent.click(screen.getByText('Remove'));
    await waitFor(() => expect(api.deleteFolder).toHaveBeenCalledWith('f1'));
    vi.unstubAllGlobals();
  });

  it('shows Add Folder button', async () => {
    render(Page);
    await screen.findByText('Add Folder');
  });
});
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd frontend && npm test -- library/page.test --reporter=verbose 2>&1 | tail -10
```

Expected: FAIL.

- [ ] **Step 3: Implement `frontend/src/routes/library/+page.svelte`**

```svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import { getLibrary, deleteFolder as apiDelete, rescanFolder as apiRescan, addFolder } from '$lib/api';
  import FolderPicker from '$lib/components/FolderPicker.svelte';
  import type { FolderResponse } from '$lib/types';

  let folders = $state<FolderResponse[]>([]);
  let showPicker = $state(false);

  onMount(async () => {
    const lib = await getLibrary();
    folders = lib.folders;
  });

  async function handleRescan(id: string) {
    await apiRescan(id);
  }

  async function handleRemove(id: string, path: string) {
    if (!confirm(`Remove folder "${path}" from library?`)) return;
    await apiDelete(id);
    folders = folders.filter(f => f.id !== id);
  }

  async function handleAdd(path: string) {
    showPicker = false;
    const res = await addFolder(path);
    folders = [...folders, res.folder];
  }
</script>

<div class="page">
  <div class="page-header">
    <h1 class="page-title">Library</h1>
    <button class="btn-primary" onclick={() => (showPicker = true)}>Add Folder</button>
  </div>

  {#if folders.length === 0}
    <p class="empty">No folders added yet.</p>
  {:else}
    <ul class="folder-list">
      {#each folders as folder (folder.id)}
        <li class="folder-row">
          <div class="folder-info">
            <p class="folder-path">{folder.path}</p>
            <p class="folder-counts">
              {folder.counts.indexed} indexed ·
              {folder.counts.pending} pending ·
              {folder.counts.failed} failed ·
              {folder.counts.missing} missing
            </p>
          </div>
          <div class="folder-actions">
            <button class="btn-secondary" onclick={() => handleRescan(folder.id)}>Rescan</button>
            <button class="btn-danger" onclick={() => handleRemove(folder.id, folder.path)}>Remove</button>
          </div>
        </li>
      {/each}
    </ul>
  {/if}
</div>

{#if showPicker}
  <FolderPicker onconfirm={handleAdd} oncancel={() => (showPicker = false)} />
{/if}

<style>
  .page {
    padding: 24px 20px;
    flex: 1;
  }

  .page-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
  }

  .page-title {
    font-size: 16px;
    color: #e0e0e0;
    font-weight: 600;
  }

  .empty {
    font-size: 12px;
    color: #555;
    text-align: center;
    margin-top: 40px;
  }

  .folder-list {
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .folder-row {
    background: #1a1a1a;
    border: 1px solid #1e1e1e;
    border-radius: 8px;
    padding: 12px 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
  }

  .folder-info {
    min-width: 0;
  }

  .folder-path {
    font-size: 12px;
    color: #e0e0e0;
    font-family: ui-monospace, monospace;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    margin-bottom: 4px;
  }

  .folder-counts {
    font-size: 10px;
    color: #555;
  }

  .folder-actions {
    display: flex;
    gap: 6px;
    flex-shrink: 0;
  }

  .btn-primary {
    background: #4ade80;
    border: none;
    color: #000;
    font-size: 11px;
    font-weight: 700;
    padding: 6px 14px;
    border-radius: 6px;
  }

  .btn-secondary {
    background: none;
    border: 1px solid #2a2a2a;
    color: #888;
    font-size: 10px;
    padding: 4px 10px;
    border-radius: 5px;
  }

  .btn-secondary:hover {
    border-color: #4ade80;
    color: #4ade80;
  }

  .btn-danger {
    background: none;
    border: 1px solid #2a2a2a;
    color: #888;
    font-size: 10px;
    padding: 4px 10px;
    border-radius: 5px;
  }

  .btn-danger:hover {
    border-color: #f87171;
    color: #f87171;
  }
</style>
```

- [ ] **Step 4: Run tests and confirm they pass**

```bash
cd frontend && npm test -- library/page.test --reporter=verbose 2>&1 | tail -15
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/routes/library/
git commit -m "feat(frontend): add Library page with folder management"
```

---

### Task 10: JobItem component and Jobs page

**Files:**
- Create: `frontend/src/lib/components/JobItem.svelte`
- Create: `frontend/src/lib/components/JobItem.test.ts`
- Create: `frontend/src/routes/jobs/+page.svelte`
- Create: `frontend/src/routes/jobs/page.test.ts`

`JobItem` shows filename, status badge, progress bar (in-progress), error (failed), retry button (failed). The Jobs page reads the `jobs` store (populated by WebSocket) and shows jobs in reverse-chronological order.

- [ ] **Step 1: Write failing tests in `frontend/src/lib/components/JobItem.test.ts`**

```typescript
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/svelte';
import JobItem from './JobItem.svelte';
import * as api from '$lib/api';
import type { Job } from '$lib/types';

vi.mock('$lib/api');

const makeJob = (overrides: Partial<Job> = {}): Job => ({
  id: 'job-1', video_id: null, path: '/home/user/video.mp4', kind: 'index',
  status: 'pending', progress: 0, error: null, created_at: 0, updated_at: 0,
  ...overrides,
});

describe('JobItem', () => {
  it('shows the filename from path', () => {
    render(JobItem, { job: makeJob() });
    expect(screen.getByText('video.mp4')).toBeInTheDocument();
  });

  it('shows status badge', () => {
    render(JobItem, { job: makeJob({ status: 'done' }) });
    expect(screen.getByText('done')).toBeInTheDocument();
  });

  it('shows progress bar when in_progress', () => {
    const { container } = render(JobItem, { job: makeJob({ status: 'in_progress', progress: 0.5 }) });
    const bar = container.querySelector('.progress-fill');
    expect(bar).toBeInTheDocument();
    expect((bar as HTMLElement).style.width).toBe('50%');
  });

  it('shows error message when failed', () => {
    render(JobItem, { job: makeJob({ status: 'failed', error: 'model error' }) });
    expect(screen.getByText('model error')).toBeInTheDocument();
  });

  it('shows Retry button when failed', () => {
    render(JobItem, { job: makeJob({ status: 'failed' }) });
    expect(screen.getByText('Retry')).toBeInTheDocument();
  });

  it('calls retryJob on Retry click', async () => {
    vi.mocked(api.retryJob).mockResolvedValue({ job_id: 'new-job' });
    render(JobItem, { job: makeJob({ status: 'failed' }) });
    await fireEvent.click(screen.getByText('Retry'));
    expect(api.retryJob).toHaveBeenCalledWith('job-1');
  });

  it('does not show Retry button for non-failed jobs', () => {
    render(JobItem, { job: makeJob({ status: 'done' }) });
    expect(screen.queryByText('Retry')).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Write failing tests in `frontend/src/routes/jobs/page.test.ts`**

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/svelte';
import Page from './+page.svelte';
import { jobs } from '$lib/stores';
import type { Job } from '$lib/types';

vi.mock('$lib/api');
vi.mock('$app/state', () => ({ page: { url: { pathname: '/jobs' } } }));

const makeJob = (overrides: Partial<Job> = {}): Job => ({
  id: 'job-1', video_id: null, path: '/video.mp4', kind: 'index',
  status: 'pending', progress: 0, error: null, created_at: 0, updated_at: 0,
  ...overrides,
});

beforeEach(() => {
  jobs.set([]);
});

describe('Jobs page', () => {
  it('shows empty state when no jobs', () => {
    render(Page);
    expect(screen.getByText(/no jobs/i)).toBeInTheDocument();
  });

  it('renders a job from the store', () => {
    jobs.set([makeJob({ path: '/home/user/movie.mp4', status: 'done' })]);
    render(Page);
    expect(screen.getByText('movie.mp4')).toBeInTheDocument();
    expect(screen.getByText('done')).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
cd frontend && npm test -- "JobItem|jobs/page" --reporter=verbose 2>&1 | tail -10
```

Expected: FAIL.

- [ ] **Step 4: Implement `frontend/src/lib/components/JobItem.svelte`**

```svelte
<script lang="ts">
  import { retryJob } from '$lib/api';
  import type { Job } from '$lib/types';

  let { job }: { job: Job } = $props();

  function filename(path: string | null): string {
    if (!path) return '(unknown)';
    return path.split('/').pop() ?? path;
  }

  function statusColor(status: string): string {
    if (status === 'done') return '#4ade80';
    if (status === 'failed') return '#f87171';
    if (status === 'in_progress') return '#60a5fa';
    return '#555';
  }

  async function handleRetry() {
    await retryJob(job.id);
  }
</script>

<li class="job-item">
  <div class="job-main">
    <div class="job-left">
      <span class="job-filename">{filename(job.path)}</span>
      <span class="job-badge" style="color: {statusColor(job.status)}">{job.status}</span>
    </div>
    {#if job.status === 'failed'}
      <button class="retry-btn" onclick={handleRetry}>Retry</button>
    {/if}
  </div>

  {#if job.status === 'in_progress'}
    <div class="progress-bar">
      <div class="progress-fill" style="width: {Math.round(job.progress * 100)}%"></div>
    </div>
  {/if}

  {#if job.error}
    <p class="error-msg">{job.error}</p>
  {/if}
</li>

<style>
  .job-item {
    background: #1a1a1a;
    border: 1px solid #1e1e1e;
    border-radius: 8px;
    padding: 10px 14px;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .job-main {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
  }

  .job-left {
    display: flex;
    align-items: center;
    gap: 10px;
    min-width: 0;
  }

  .job-filename {
    font-size: 11px;
    color: #e0e0e0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .job-badge {
    font-size: 9px;
    font-weight: 600;
    flex-shrink: 0;
  }

  .retry-btn {
    background: none;
    border: 1px solid #f87171;
    color: #f87171;
    font-size: 9px;
    padding: 3px 8px;
    border-radius: 4px;
    flex-shrink: 0;
  }

  .retry-btn:hover {
    background: #f8717122;
  }

  .progress-bar {
    height: 2px;
    background: #2a2a2a;
    border-radius: 1px;
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    background: #4ade80;
    border-radius: 1px;
    transition: width 0.3s;
  }

  .error-msg {
    font-size: 9px;
    color: #f87171;
  }
</style>
```

- [ ] **Step 5: Implement `frontend/src/routes/jobs/+page.svelte`**

```svelte
<script lang="ts">
  import { jobs } from '$lib/stores';
  import JobItem from '$lib/components/JobItem.svelte';
</script>

<div class="page">
  <div class="page-header">
    <h1 class="page-title">Jobs</h1>
  </div>

  {#if $jobs.length === 0}
    <p class="empty">No jobs yet.</p>
  {:else}
    <ul class="job-list">
      {#each $jobs as job (job.id)}
        <JobItem {job} />
      {/each}
    </ul>
  {/if}
</div>

<style>
  .page {
    padding: 24px 20px;
    flex: 1;
  }

  .page-header {
    margin-bottom: 20px;
  }

  .page-title {
    font-size: 16px;
    color: #e0e0e0;
    font-weight: 600;
  }

  .empty {
    font-size: 12px;
    color: #555;
    text-align: center;
    margin-top: 40px;
  }

  .job-list {
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
</style>
```

- [ ] **Step 6: Run tests and confirm they pass**

```bash
cd frontend && npm test -- --reporter=verbose 2>&1 | tail -20
```

Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/components/JobItem.svelte frontend/src/lib/components/JobItem.test.ts frontend/src/routes/jobs/
git commit -m "feat(frontend): add JobItem component and Jobs page"
```

---

### Task 11: Settings page

**Files:**
- Create: `frontend/src/routes/settings/+page.svelte`
- Create: `frontend/src/routes/settings/page.test.ts`

Loads current settings from `GET /api/settings` on mount. Tracks which fields the user has changed. Submits only touched fields via `PATCH /api/settings`. Fields that require a restart are annotated with "⚠ requires restart".

- [ ] **Step 1: Write failing tests in `frontend/src/routes/settings/page.test.ts`**

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/svelte';
import Page from './+page.svelte';
import * as api from '$lib/api';

vi.mock('$lib/api');
vi.mock('$app/state', () => ({ page: { url: { pathname: '/settings' } } }));

beforeEach(() => {
  vi.mocked(api.getSettings).mockResolvedValue({
    frame_fps: 1.0,
    scene_detection: true,
    port: 8083,
    siglip_model: 'google/siglip2-base-patch16-256',
    text_embedder: 'BAAI/bge-small-en-v1.5',
    vlm_model: null,
    vlm_mmproj: null,
    vlm_n_gpu_layers: -1,
  });
  vi.mocked(api.patchSettings).mockResolvedValue({ frame_fps: 2.0 });
});

describe('Settings page', () => {
  it('loads and shows current frame_fps', async () => {
    render(Page);
    const input = await screen.findByLabelText(/frames per second/i);
    expect((input as HTMLInputElement).value).toBe('1');
  });

  it('submits only changed fields', async () => {
    render(Page);
    const input = await screen.findByLabelText(/frames per second/i);
    await fireEvent.input(input, { target: { value: '2' } });
    await fireEvent.submit(screen.getByRole('form'));
    await waitFor(() => expect(api.patchSettings).toHaveBeenCalledWith({ frame_fps: 2 }));
  });

  it('does not submit unchanged fields', async () => {
    render(Page);
    await screen.findByLabelText(/frames per second/i);
    await fireEvent.submit(screen.getByRole('form'));
    await waitFor(() => expect(api.patchSettings).toHaveBeenCalledWith({}));
  });

  it('shows requires-restart hint for port field', async () => {
    render(Page);
    await screen.findByLabelText(/port/i);
    expect(screen.getAllByText(/requires restart/i).length).toBeGreaterThan(0);
  });
});
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd frontend && npm test -- settings/page.test --reporter=verbose 2>&1 | tail -10
```

Expected: FAIL.

- [ ] **Step 3: Implement `frontend/src/routes/settings/+page.svelte`**

```svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import { getSettings, patchSettings } from '$lib/api';

  type FieldValue = string | number | boolean | null;
  type Settings = Record<string, FieldValue>;

  let original = $state<Settings>({});
  let current = $state<Settings>({});
  let saving = $state(false);
  let saved = $state(false);

  onMount(async () => {
    const s = await getSettings();
    original = { ...s } as Settings;
    current = { ...s } as Settings;
  });

  function touched(): Partial<Settings> {
    const patch: Partial<Settings> = {};
    for (const key of Object.keys(current)) {
      if (current[key] !== original[key]) {
        patch[key] = current[key];
      }
    }
    return patch;
  }

  async function handleSubmit(e: SubmitEvent) {
    e.preventDefault();
    saving = true;
    try {
      await patchSettings(touched() as Record<string, unknown>);
      original = { ...current };
      saved = true;
      setTimeout(() => (saved = false), 2000);
    } finally {
      saving = false;
    }
  }

  const restartFields = new Set(['port', 'siglip_model', 'text_embedder', 'vlm_model', 'vlm_mmproj']);
</script>

<div class="page">
  <div class="page-header">
    <h1 class="page-title">Settings</h1>
  </div>

  <form class="settings-form" onsubmit={handleSubmit} role="form">
    <div class="field">
      <label class="label" for="frame_fps">Frames per second</label>
      <input
        id="frame_fps"
        class="input"
        type="number"
        step="0.5"
        min="0.1"
        bind:value={current.frame_fps}
      />
    </div>

    <div class="field">
      <label class="label" for="scene_detection">
        <input
          id="scene_detection"
          type="checkbox"
          bind:checked={current.scene_detection as boolean}
        />
        Scene detection
      </label>
    </div>

    <div class="field">
      <label class="label" for="port">
        Port
        <span class="restart-hint">⚠ requires restart</span>
      </label>
      <input id="port" class="input" type="number" bind:value={current.port} />
    </div>

    <div class="field">
      <label class="label" for="siglip_model">
        SigLIP model
        <span class="restart-hint">⚠ requires restart</span>
      </label>
      <input id="siglip_model" class="input" type="text" bind:value={current.siglip_model as string} />
    </div>

    <div class="field">
      <label class="label" for="text_embedder">
        Text embedder
        <span class="restart-hint">⚠ requires restart</span>
      </label>
      <input id="text_embedder" class="input" type="text" bind:value={current.text_embedder as string} />
    </div>

    <div class="field">
      <label class="label" for="vlm_model">
        VLM model path
        <span class="restart-hint">⚠ requires restart</span>
      </label>
      <input id="vlm_model" class="input" type="text" bind:value={current.vlm_model as string} placeholder="GGUF path or HF repo" />
    </div>

    <div class="field">
      <label class="label" for="vlm_mmproj">
        VLM mmproj path
        <span class="restart-hint">⚠ requires restart</span>
      </label>
      <input id="vlm_mmproj" class="input" type="text" bind:value={current.vlm_mmproj as string} placeholder="mmproj path" />
    </div>

    <div class="field">
      <label class="label" for="vlm_n_gpu_layers">GPU layers (-1 = all)</label>
      <input id="vlm_n_gpu_layers" class="input" type="number" bind:value={current.vlm_n_gpu_layers} />
    </div>

    <div class="form-footer">
      {#if saved}
        <span class="saved-msg">Saved.</span>
      {/if}
      <button class="btn-save" type="submit" disabled={saving}>
        {saving ? 'Saving…' : 'Save'}
      </button>
    </div>
  </form>
</div>

<style>
  .page {
    padding: 24px 20px;
    flex: 1;
    max-width: 560px;
  }

  .page-header {
    margin-bottom: 24px;
  }

  .page-title {
    font-size: 16px;
    color: #e0e0e0;
    font-weight: 600;
  }

  .settings-form {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 5px;
  }

  .label {
    font-size: 11px;
    color: #888;
    display: flex;
    align-items: center;
    gap: 6px;
  }

  .restart-hint {
    font-size: 9px;
    color: #f59e0b;
  }

  .input {
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 6px;
    padding: 7px 10px;
    font-size: 12px;
    color: #e0e0e0;
    font-family: inherit;
    outline: none;
    width: 100%;
  }

  .input:focus {
    border-color: #4ade80;
  }

  .form-footer {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 12px;
    padding-top: 8px;
  }

  .saved-msg {
    font-size: 11px;
    color: #4ade80;
  }

  .btn-save {
    background: #4ade80;
    border: none;
    color: #000;
    font-size: 11px;
    font-weight: 700;
    padding: 7px 18px;
    border-radius: 6px;
  }

  .btn-save:disabled {
    opacity: 0.5;
  }
</style>
```

- [ ] **Step 4: Run tests and confirm they pass**

```bash
cd frontend && npm test -- settings/page.test --reporter=verbose 2>&1 | tail -15
```

Expected: All tests PASS.

- [ ] **Step 5: Run all tests to check nothing is broken**

```bash
cd frontend && npm test -- --reporter=verbose 2>&1 | tail -30
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/routes/settings/
git commit -m "feat(frontend): add Settings page"
```

---

### Task 12: FastAPI static mount and build integration

**Files:**
- Modify: `src/videosearch/api/app.py` (add `StaticFiles` mount)

This task adds the `StaticFiles` mount to FastAPI and runs the SvelteKit build to produce `src/videosearch/static/`.

**Context on `app.py`:** The file already has all routers and the WebSocket router registered. The static mount must come **after** all `app.include_router(...)` calls — FastAPI matches routes in registration order, so `/api/*` routes must be registered first.

- [ ] **Step 1: Read `src/videosearch/api/app.py` to find where to add the mount**

The mount goes after the last `app.include_router(...)` call, which is currently `app.include_router(make_ws_router(...))`. The block to add:

```python
from fastapi.staticfiles import StaticFiles
from pathlib import Path

_STATIC = Path(__file__).parent.parent / "static"

if _STATIC.exists():
    app.mount("/", StaticFiles(directory=_STATIC, html=True), name="static")
```

`html=True` makes `StaticFiles` return `index.html` for any path not found as a real file — this is the SPA fallback. FastAPI routes registered above take priority, so `/api/*` is unaffected.

- [ ] **Step 2: Add the static mount to `src/videosearch/api/app.py`**

After the line `app.include_router(make_ws_router(deps.get_broadcaster, deps.get_jobs_queue))`, add:

```python
    from pathlib import Path

    from fastapi.staticfiles import StaticFiles

    _STATIC = Path(__file__).parent.parent / "static"
    if _STATIC.exists():
        app.mount("/", StaticFiles(directory=_STATIC, html=True), name="static")

    return app
```

The full final block in `create_app` looks like:

```python
    app.include_router(health.router, prefix="/api")
    app.include_router(search.router, prefix="/api")
    app.include_router(library.router, prefix="/api")
    app.include_router(ingest.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    app.include_router(videos.router, prefix="/api")
    app.include_router(fs.router, prefix="/api")
    app.include_router(settings_router.router, prefix="/api")
    app.include_router(make_ws_router(deps.get_broadcaster, deps.get_jobs_queue))

    from pathlib import Path
    from fastapi.staticfiles import StaticFiles

    _STATIC = Path(__file__).parent.parent / "static"
    if _STATIC.exists():
        app.mount("/", StaticFiles(directory=_STATIC, html=True), name="static")

    return app
```

- [ ] **Step 3: Run the Python test suite to confirm nothing is broken**

```bash
uv run pytest tests/ -q 2>&1 | tail -10
```

Expected: All tests pass (the `if _STATIC.exists()` guard means the mount is skipped when static/ doesn't exist yet).

- [ ] **Step 4: Build the SvelteKit app**

```bash
cd frontend && npm run build 2>&1 | tail -20
```

Expected: Build succeeds and `../src/videosearch/static/` is created containing `index.html`.

- [ ] **Step 5: Verify the static output exists**

```bash
ls src/videosearch/static/ | head -10
```

Expected: `index.html` and asset directories are present.

- [ ] **Step 6: Commit everything**

```bash
git add src/videosearch/api/app.py src/videosearch/static/
git commit -m "feat: add FastAPI static mount and initial frontend build"
```

---

## Validation

After all tasks are complete, verify the full integration:

1. Run `uv run pytest tests/ -q` — all Python tests pass.
2. Run `cd frontend && npm test` — all frontend tests pass.
3. Run `uv run videosearch serve` (requires model env vars) — navigate to `http://localhost:8083/` in a browser and confirm the search UI loads. Without real model weights, the health endpoint will return `degraded` but the UI should still render.
