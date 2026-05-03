<!-- frontend/src/lib/components/SetupModal.svelte -->
<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { goto } from '$app/navigation';
  import { getModelCatalog, startModelDownload, getDownloadProgress, getSettings, patchSettings } from '$lib/api';
  import type { ModelCatalogEntry, DownloadProgress } from '$lib/types';

  let visible = $state(true);
  let step = $state<'token' | 'downloading'>('token');
  let tokenInput = $state('');
  let visionEntries = $state<ModelCatalogEntry[]>([]);
  let siglipEntries = $state<ModelCatalogEntry[]>([]);
  let textEntries = $state<ModelCatalogEntry[]>([]);
  let progresses = $state<DownloadProgress[]>([]);
  let pollInterval: ReturnType<typeof setInterval> | null = null;

  type ModelSection = { type: string; label: string; entry: ModelCatalogEntry | undefined };

  let sections = $derived.by<ModelSection[]>(() => [
    { type: 'vision',        label: 'Vision model',        entry: visionEntries.find(e => e.default) },
    { type: 'siglip',       label: 'Image understanding',  entry: siglipEntries.find(e => e.default) },
    { type: 'text_embedder', label: 'Search model',        entry: textEntries.find(e => e.default) },
  ]);

  function sectionProgress(section: ModelSection): DownloadProgress | undefined {
    return progresses.find(p => p.model_type === section.type);
  }

  function sectionStatus(section: ModelSection): 'cached' | 'downloading' | 'error' | 'queued' {
    if (section.entry?.cached) return 'cached';
    const p = sectionProgress(section);
    if (p?.error) return 'error';
    if (p?.active) return 'downloading';
    return 'queued';
  }

  function pct(section: ModelSection): number {
    const p = sectionProgress(section);
    if (!p || !p.total_bytes) return 0;
    return Math.round((p.downloaded_bytes / p.total_bytes) * 100);
  }

  async function refreshCatalog() {
    const catalog = await getModelCatalog();
    visionEntries = catalog.vision;
    siglipEntries = catalog.siglip;
    textEntries = catalog.text_embedder;
    if (!catalog.first_run) {
      localStorage.setItem('setup_seen', '1');
      stopPolling();
      visible = false;
    }
  }

  function startPolling() {
    pollInterval = setInterval(async () => {
      progresses = await getDownloadProgress();
      await refreshCatalog();
      if (progresses.length > 0 && progresses.every(p => !p.active)) stopPolling();
    }, 1000);
  }

  function stopPolling() {
    if (pollInterval !== null) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
  }

  async function beginDownloads() {
    step = 'downloading';
    for (const [type, entries] of [
      ['vision', visionEntries] as const,
      ['siglip', siglipEntries] as const,
      ['text_embedder', textEntries] as const,
    ]) {
      const def = entries.find(e => e.default);
      if (def && !def.cached) {
        await startModelDownload(type, def.id);
      }
    }
    startPolling();
  }

  async function handleContinue() {
    if (tokenInput.trim()) {
      await patchSettings({ hf_token: tokenInput.trim() });
    }
    await beginDownloads();
  }

  async function handleSkip() {
    await beginDownloads();
  }

  async function retryDownload(section: ModelSection) {
    if (section.entry) {
      await startModelDownload(section.type, section.entry.id);
      if (!pollInterval) startPolling();
    }
  }

  onMount(async () => {
    const [catalog, settings] = await Promise.all([getModelCatalog(), getSettings()]);
    visionEntries = catalog.vision;
    siglipEntries = catalog.siglip;
    textEntries = catalog.text_embedder;

    if (settings.hf_token !== null) {
      await beginDownloads();
    }
  });

  onDestroy(stopPolling);

  function customise() {
    goto('/settings');
  }
</script>

{#if visible}
  <div class="overlay" role="dialog" aria-modal="true" aria-label="First time setup">
    <div class="modal">
      <div class="modal-head">
        <div class="logo-dot" aria-hidden="true"></div>
        <h2 class="modal-title">Welcome to Videosearch</h2>
      </div>

      {#if step === 'token'}
        <p class="modal-sub">A Hugging Face token speeds up AI model downloads.</p>
        <div class="token-section">
          <input
            type="password"
            class="token-input"
            placeholder="hf_..."
            bind:value={tokenInput}
          />
          <p class="token-hint">Free at huggingface.co · optional but recommended</p>
        </div>
        <div class="token-actions">
          <button class="skip-btn" type="button" onclick={handleSkip}>Skip</button>
          <button class="continue-btn" type="button" onclick={handleContinue}>Continue</button>
        </div>
      {:else}
        <p class="modal-sub">Downloading AI models — this only happens once.</p>
        <div class="model-rows">
          {#each sections as section}
            {@const status = sectionStatus(section)}
            <div class="model-row">
              <div class="row-header">
                <span class="row-label">{section.label}</span>
                <span class="row-meta">{section.entry?.label} · {section.entry?.size_label}</span>
                {#if status === 'cached'}
                  <span class="row-status cached">✓</span>
                {:else if status === 'downloading'}
                  <span class="row-status downloading">{pct(section)}%</span>
                {:else if status === 'error'}
                  <span class="row-status error">failed</span>
                  <button class="retry-btn" type="button" onclick={() => retryDownload(section)}>Retry</button>
                {:else}
                  <span class="row-status queued">queued</span>
                {/if}
              </div>
              <div class="bar-track">
                {#if status === 'downloading'}
                  <div class="bar-fill" style="width: {pct(section)}%"></div>
                {:else if status === 'cached'}
                  <div class="bar-fill full"></div>
                {:else}
                  <div class="bar-empty"></div>
                {/if}
              </div>
            </div>
          {/each}
        </div>
        <div class="modal-footer">
          <span class="footer-hint">You can change models any time in Settings</span>
          <button class="customise-btn" onclick={customise}>Customise ↗</button>
        </div>
      {/if}
    </div>
  </div>
{/if}

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
    padding: 24px;
    width: 380px;
    max-width: 90vw;
  }
  .modal-head {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 4px;
  }
  .logo-dot {
    width: 14px;
    height: 14px;
    background: #4ade80;
    border-radius: 3px;
    flex-shrink: 0;
  }
  .modal-title {
    font-size: 14px;
    font-weight: 700;
    color: #e0e0e0;
  }
  .modal-sub {
    font-size: 10px;
    color: #555;
    margin-bottom: 16px;
    padding-left: 24px;
  }
  .token-section {
    margin-bottom: 16px;
  }
  .token-input {
    width: 100%;
    background: #111;
    border: 1px solid #333;
    border-radius: 6px;
    color: #e0e0e0;
    font-size: 11px;
    padding: 8px 10px;
    box-sizing: border-box;
    margin-bottom: 6px;
  }
  .token-input::placeholder { color: #444; }
  .token-hint {
    font-size: 9px;
    color: #444;
    margin: 0;
  }
  .token-actions {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
    margin-bottom: 4px;
  }
  .skip-btn {
    background: none;
    border: 1px solid #333;
    border-radius: 4px;
    font-size: 10px;
    color: #666;
    cursor: pointer;
    padding: 4px 10px;
  }
  .continue-btn {
    background: #4ade80;
    border: none;
    border-radius: 4px;
    font-size: 10px;
    color: #000;
    font-weight: 600;
    cursor: pointer;
    padding: 4px 12px;
  }
  .model-rows {
    display: flex;
    flex-direction: column;
    gap: 14px;
    margin-bottom: 20px;
  }
  .row-header {
    display: flex;
    align-items: baseline;
    gap: 6px;
    margin-bottom: 5px;
  }
  .row-label {
    font-size: 10px;
    font-weight: 600;
    color: #e0e0e0;
  }
  .row-meta {
    font-size: 9px;
    color: #555;
    flex: 1;
  }
  .row-status { font-size: 9px; }
  .row-status.cached { color: #4ade80; }
  .row-status.downloading { color: #4ade80; }
  .row-status.queued { color: #555; }
  .row-status.error { color: #f87171; }
  .retry-btn {
    background: none;
    border: 1px solid #444;
    border-radius: 3px;
    font-size: 9px;
    color: #f87171;
    cursor: pointer;
    padding: 2px 6px;
  }
  .bar-track {
    background: #2a2a2a;
    border-radius: 2px;
    height: 3px;
    overflow: hidden;
  }
  .bar-fill {
    background: #4ade80;
    height: 3px;
    border-radius: 2px;
    transition: width 0.4s ease;
  }
  .bar-fill.full { width: 100%; }
  .bar-empty { height: 3px; }
  .modal-footer {
    border-top: 1px solid #2a2a2a;
    padding-top: 12px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .footer-hint {
    font-size: 9px;
    color: #444;
  }
  .customise-btn {
    background: none;
    border: none;
    font-size: 9px;
    color: #4ade80;
    cursor: pointer;
    padding: 0;
  }
</style>
