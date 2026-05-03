import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  search, getHealth, getLibrary, addFolder, deleteFolder,
  rescanFolder, getJobs, retryJob, revealVideo, listFs,
  getSettings, patchSettings,
  getModelCatalog, startModelDownload, getDownloadProgress,
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

describe('models API', () => {
  it('getModelCatalog fetches /api/models/catalog', async () => {
    const mockCatalog = {
      first_run: false,
      active_models: { vision: 'moondream2', siglip: 'siglip2-base', text_embedder: 'bge-small-en' },
      vision: [{ id: 'moondream2', label: 'moondream2', size_label: '~2 GB', cached: true, default: true }],
      siglip: [],
      text_embedder: [],
    };
    vi.stubGlobal('fetch', mockFetch(mockCatalog));
    const result = await getModelCatalog();
    expect(fetch).toHaveBeenCalledWith('/api/models/catalog', undefined);
    expect(result.first_run).toBe(false);
    expect(result.vision[0].id).toBe('moondream2');
  });

  it('startModelDownload POSTs to /api/models/download', async () => {
    vi.stubGlobal('fetch', mockFetch({ queued: true }));
    await startModelDownload('siglip', 'siglip2-base');
    expect(fetch).toHaveBeenCalledWith(
      '/api/models/download',
      expect.objectContaining({ method: 'POST' })
    );
  });

  it('getDownloadProgress fetches /api/models/download/progress', async () => {
    const mockProgress = {
      active: true, model_type: 'vision', model_id: 'moondream2',
      downloaded_bytes: 500, total_bytes: 2000, error: null, complete: false,
    };
    vi.stubGlobal('fetch', mockFetch(mockProgress));
    const result = await getDownloadProgress();
    expect(result.active).toBe(true);
    expect(result.downloaded_bytes).toBe(500);
  });
});
