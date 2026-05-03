<!-- frontend/src/routes/settings/+page.svelte -->
<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { getModelCatalog, getSettings, patchSettings, startModelDownload, getDownloadProgress } from '$lib/api';
  import type { ModelCatalogEntry, ModelCatalogResponse, DownloadProgress } from '$lib/types';

  let catalog = $state<ModelCatalogResponse | null>(null);
  let currentSettings = $state<Record<string, unknown>>({});
  let originalSettings = $state<Record<string, unknown>>({});
  let progress = $state<DownloadProgress | null>(null);
  let saving = $state(false);
  let saved = $state(false);
  let pollInterval: ReturnType<typeof setInterval> | null = null;

  // Client-side maps mirroring catalog.py — resolve catalog IDs to raw settings strings
  const VLM_SPECS: Record<string, { vlm_model: string; vlm_mmproj: string }> = {
    'moondream2': {
      vlm_model: 'moondream/moondream2-gguf::moondream2-text-model-f16.gguf',
      vlm_mmproj: 'moondream/moondream2-gguf::moondream2-mmproj-f16.gguf',
    },
    'llava-1.5-7b': {
      vlm_model: 'mys/ggml_llava-v1.5-7b::ggml-model-q4_k.gguf',
      vlm_mmproj: 'mys/ggml_llava-v1.5-7b::mmproj-model-f16.gguf',
    },
    'llava-1.5-13b': {
      vlm_model: 'mys/ggml_llava-v1.5-13b::ggml-model-q4_k.gguf',
      vlm_mmproj: 'mys/ggml_llava-v1.5-13b::mmproj-model-f16.gguf',
    },
  };

  const SIGLIP_REPOS: Record<string, string> = {
    'siglip2-base': 'google/siglip2-base-patch16-256',
    'siglip2-large': 'google/siglip2-large-patch16-256',
    'siglip-so400m': 'google/siglip-so400m-patch14-384',
  };

  const BGE_REPOS: Record<string, string> = {
    'bge-small-en': 'BAAI/bge-small-en-v1.5',
    'bge-base-en': 'BAAI/bge-base-en-v1.5',
    'bge-large-en': 'BAAI/bge-large-en-v1.5',
    'bge-m3': 'BAAI/bge-m3',
  };

  onMount(async () => {
    const [cat, settings] = await Promise.all([getModelCatalog(), getSettings()]);
    catalog = cat;
    currentSettings = { ...settings };
    originalSettings = { ...settings };
    startPolling();
  });

  onDestroy(stopPolling);

  function startPolling() {
    pollInterval = setInterval(async () => {
      progress = await getDownloadProgress();
      if (!progress.active) {
        catalog = await getModelCatalog();
      }
    }, 1500);
  }

  function stopPolling() {
    if (pollInterval !== null) { clearInterval(pollInterval); pollInterval = null; }
  }

  async function handleModelChange(type: string, newId: string) {
    if (!catalog) return;
    const entries = catalog[type as 'vision' | 'siglip' | 'text_embedder'];
    const entry = entries.find((e: ModelCatalogEntry) => e.id === newId);
    if (!entry) return;

    let patch: Record<string, string> = {};
    if (type === 'vision') {
      const specs = VLM_SPECS[newId];
      if (specs) patch = { vlm_model: specs.vlm_model, vlm_mmproj: specs.vlm_mmproj };
    } else if (type === 'siglip') {
      patch = { siglip_model: SIGLIP_REPOS[newId] ?? newId };
    } else if (type === 'text_embedder') {
      patch = { text_embedder: BGE_REPOS[newId] ?? newId };
    }

    await patchSettings(patch as Record<string, unknown>);
    currentSettings = { ...currentSettings, ...patch };
    originalSettings = { ...currentSettings };

    if (!entry.cached) {
      await startModelDownload(type, newId);
    }
    catalog = await getModelCatalog();
  }

  function advancedTouched(): Record<string, unknown> {
    const patch: Record<string, unknown> = {};
    for (const key of ['frame_fps', 'scene_detection', 'port', 'vlm_n_gpu_layers']) {
      if (currentSettings[key] !== originalSettings[key]) {
        patch[key] = currentSettings[key];
      }
    }
    return patch;
  }

  async function doSave() {
    if (saving) return;
    saving = true;
    try {
      const patch = advancedTouched();
      if ('frame_fps' in patch) patch.frame_fps = Number(patch.frame_fps);
      if ('port' in patch) patch.port = Number(patch.port);
      if ('vlm_n_gpu_layers' in patch) patch.vlm_n_gpu_layers = Number(patch.vlm_n_gpu_layers);
      await patchSettings(patch);
      originalSettings = { ...currentSettings };
      saved = true;
      setTimeout(() => (saved = false), 2000);
    } finally {
      saving = false;
    }
  }

  async function handleSave(e: SubmitEvent) {
    e.preventDefault();
    await doSave();
  }

  function selectedId(type: string): string {
    if (!catalog) return '';
    const am = catalog.active_models[type as keyof typeof catalog.active_models];
    return am || catalog[type as 'vision' | 'siglip' | 'text_embedder'].find((e: ModelCatalogEntry) => e.default)?.id || '';
  }

  function activeCachedForType(type: string): boolean {
    if (!catalog) return false;
    const id = selectedId(type);
    return catalog[type as 'vision' | 'siglip' | 'text_embedder'].find((e: ModelCatalogEntry) => e.id === id)?.cached ?? false;
  }

  function isDownloadingType(type: string): boolean {
    return (progress?.active ?? false) && progress?.model_type === type;
  }

  function downloadPct(): number {
    if (!progress?.total_bytes) return 0;
    return Math.round((progress.downloaded_bytes / progress.total_bytes) * 100);
  }

  function formatBytes(n: number): string {
    if (n > 1e9) return (n / 1e9).toFixed(1) + ' GB';
    if (n > 1e6) return (n / 1e6).toFixed(0) + ' MB';
    return n + ' B';
  }
</script>

<div class="page">
  <h1 class="page-title">Settings</h1>

  {#if catalog}
    <!-- Vision model -->
    <section class="model-section">
      <div class="model-label">Vision model</div>
      <p class="model-desc">Describes what's happening in each frame of your videos — the smarter the model, the better your search results.</p>
      <div class="select-row">
        <select
          class="model-select"
          value={selectedId('vision')}
          onchange={(e) => handleModelChange('vision', (e.target as HTMLSelectElement).value)}
        >
          {#each catalog.vision as entry}
            <option value={entry.id}>{entry.label} · {entry.size_label}</option>
          {/each}
        </select>
        {#if !isDownloadingType('vision')}
          {#if activeCachedForType('vision')}
            <span class="cached-badge">● Cached</span>
          {:else}
            <span class="uncached-badge">○ Not cached</span>
          {/if}
        {/if}
      </div>
      {#if isDownloadingType('vision')}
        <div class="progress-box">
          <div class="progress-header">
            <span>Downloading…</span>
            <span class="progress-pct">{formatBytes(progress!.downloaded_bytes)} / {formatBytes(progress!.total_bytes)}</span>
          </div>
          <div class="progress-track"><div class="progress-fill" style="width:{downloadPct()}%"></div></div>
        </div>
      {/if}
    </section>

    <!-- Image understanding -->
    <section class="model-section">
      <div class="model-label">Image understanding</div>
      <p class="model-desc">Recognises objects, scenes, and people in video frames so you can search visually.</p>
      <div class="select-row">
        <select
          class="model-select"
          value={selectedId('siglip')}
          onchange={(e) => handleModelChange('siglip', (e.target as HTMLSelectElement).value)}
        >
          {#each catalog.siglip as entry}
            <option value={entry.id}>{entry.label} · {entry.size_label}</option>
          {/each}
        </select>
        {#if !isDownloadingType('siglip')}
          {#if activeCachedForType('siglip')}
            <span class="cached-badge">● Cached</span>
          {:else}
            <span class="uncached-badge">○ Not cached</span>
          {/if}
        {/if}
      </div>
      {#if isDownloadingType('siglip')}
        <div class="progress-box">
          <div class="progress-header">
            <span>Downloading…</span>
            <span class="progress-pct">{formatBytes(progress!.downloaded_bytes)} / {formatBytes(progress!.total_bytes)}</span>
          </div>
          <div class="progress-track"><div class="progress-fill" style="width:{downloadPct()}%"></div></div>
        </div>
      {/if}
    </section>

    <!-- Search model -->
    <section class="model-section">
      <div class="model-label">Search model</div>
      <p class="model-desc">Understands your search phrases and matches them to moments in your videos.</p>
      <div class="select-row">
        <select
          class="model-select"
          value={selectedId('text_embedder')}
          onchange={(e) => handleModelChange('text_embedder', (e.target as HTMLSelectElement).value)}
        >
          {#each catalog.text_embedder as entry}
            <option value={entry.id}>{entry.label} · {entry.size_label}</option>
          {/each}
        </select>
        {#if !isDownloadingType('text_embedder')}
          {#if activeCachedForType('text_embedder')}
            <span class="cached-badge">● Cached</span>
          {:else}
            <span class="uncached-badge">○ Not cached</span>
          {/if}
        {/if}
      </div>
      {#if isDownloadingType('text_embedder')}
        <div class="progress-box">
          <div class="progress-header">
            <span>Downloading…</span>
            <span class="progress-pct">{formatBytes(progress!.downloaded_bytes)} / {formatBytes(progress!.total_bytes)}</span>
          </div>
          <div class="progress-track"><div class="progress-fill" style="width:{downloadPct()}%"></div></div>
        </div>
      {/if}
    </section>
  {:else}
    <p class="loading">Loading…</p>
  {/if}

  <!-- Advanced options -->
  <form onsubmit={handleSave}>
    <details class="advanced" role="group">
      <summary class="advanced-summary">Advanced options</summary>

      <div class="advanced-fields">
        <div class="field">
          <label class="field-label" for="frame_fps">Frames per second</label>
          <input
            id="frame_fps"
            class="input"
            type="number"
            step="0.5"
            min="0.1"
            value={currentSettings.frame_fps}
            oninput={(e) => { currentSettings = { ...currentSettings, frame_fps: (e.target as HTMLInputElement).value }; }}
          />
        </div>

        <div class="field">
          <label class="field-label checkbox-label" for="scene_detection">
            <input
              id="scene_detection"
              type="checkbox"
              checked={currentSettings.scene_detection as boolean}
              onchange={(e) => { currentSettings = { ...currentSettings, scene_detection: (e.target as HTMLInputElement).checked }; }}
            />
            Scene detection
          </label>
        </div>

        <div class="field">
          <label class="field-label" for="port">
            Port
            <span class="restart-hint">⚠ requires restart</span>
          </label>
          <input
            id="port"
            class="input"
            type="number"
            value={currentSettings.port}
            oninput={(e) => { currentSettings = { ...currentSettings, port: (e.target as HTMLInputElement).value }; }}
          />
        </div>

        <div class="field">
          <label class="field-label" for="vlm_n_gpu_layers">
            GPU layers
            <span class="field-hint">(-1 = all)</span>
          </label>
          <input
            id="vlm_n_gpu_layers"
            class="input"
            type="number"
            value={currentSettings.vlm_n_gpu_layers}
            oninput={(e) => { currentSettings = { ...currentSettings, vlm_n_gpu_layers: (e.target as HTMLInputElement).value }; }}
          />
        </div>

        <div class="form-footer">
          {#if saved}<span class="saved-msg">Saved.</span>{/if}
          <button class="btn-save" type="button" onclick={doSave} disabled={saving}>
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </details>
  </form>
</div>

<style>
  .page {
    padding: 24px 20px;
    max-width: 560px;
    display: flex;
    flex-direction: column;
    gap: 0;
  }
  .page-title {
    font-size: 16px;
    color: #e0e0e0;
    font-weight: 600;
    margin-bottom: 24px;
  }
  .model-section { margin-bottom: 22px; }
  .model-label {
    font-size: 12px;
    font-weight: 600;
    color: #e0e0e0;
    margin-bottom: 3px;
  }
  .model-desc {
    font-size: 10px;
    color: #555;
    line-height: 1.5;
    margin-bottom: 8px;
  }
  .select-row { display: flex; align-items: center; gap: 10px; }
  .model-select {
    flex: 1;
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 11px;
    color: #e0e0e0;
    font-family: inherit;
    outline: none;
    cursor: pointer;
  }
  .model-select:focus { border-color: #4ade80; }
  .cached-badge { font-size: 10px; color: #4ade80; white-space: nowrap; }
  .uncached-badge { font-size: 10px; color: #555; white-space: nowrap; }
  .progress-box {
    background: #0f1a10;
    border: 1px solid #4ade8033;
    border-radius: 6px;
    padding: 8px 12px;
    margin-top: 6px;
  }
  .progress-header {
    display: flex;
    justify-content: space-between;
    font-size: 9px;
    color: #888;
    margin-bottom: 5px;
  }
  .progress-pct { color: #4ade80; }
  .progress-track {
    background: #1a2a1a;
    border-radius: 2px;
    height: 3px;
    overflow: hidden;
  }
  .progress-fill {
    background: #4ade80;
    height: 3px;
    border-radius: 2px;
    transition: width 0.4s ease;
  }
  .loading { font-size: 11px; color: #555; }
  .advanced {
    border-top: 1px solid #1e1e1e;
    padding-top: 14px;
    margin-top: 4px;
  }
  .advanced-summary {
    font-size: 10px;
    color: #555;
    cursor: pointer;
    list-style: none;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .advanced-summary::-webkit-details-marker { display: none; }
  .advanced-summary::before { content: '▶'; font-size: 8px; }
  details[open] .advanced-summary::before { content: '▼'; }
  .advanced-fields {
    display: flex;
    flex-direction: column;
    gap: 14px;
    padding-top: 14px;
  }
  .field { display: flex; flex-direction: column; gap: 5px; }
  .field-label {
    font-size: 11px;
    color: #888;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .checkbox-label { flex-direction: row; cursor: pointer; }
  .restart-hint { font-size: 9px; color: #f59e0b; }
  .field-hint { font-size: 9px; color: #555; }
  .input {
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 6px;
    padding: 7px 10px;
    font-size: 12px;
    color: #e0e0e0;
    font-family: inherit;
    outline: none;
    width: 120px;
  }
  .input:focus { border-color: #4ade80; }
  .form-footer {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 12px;
    padding-top: 4px;
  }
  .saved-msg { font-size: 11px; color: #4ade80; }
  .btn-save {
    background: #4ade80;
    border: none;
    color: #000;
    font-size: 11px;
    font-weight: 700;
    padding: 7px 18px;
    border-radius: 6px;
  }
  .btn-save:disabled { opacity: 0.5; }
</style>
