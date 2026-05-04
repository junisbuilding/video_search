<script lang="ts">
  import type { ModelCatalogResponse, DownloadProgress } from '$lib/types';

  let { type, catalog, selectedId, progress, onchange }: {
    type: 'vision' | 'siglip' | 'text_embedder';
    catalog: ModelCatalogResponse;
    selectedId: string;
    progress: DownloadProgress | null;
    onchange: (id: string) => void;
  } = $props();

  let isOpen = $state(false);

  function getEntries() {
    return catalog[type];
  }

  function getSelectedEntry() {
    return getEntries().find(e => e.id === selectedId);
  }

  function toggleDropdown() {
    isOpen = !isOpen;
  }

  function selectOption(id: string) {
    selectedId = id;
    isOpen = false;
    onchange(id);
  }

  function isDownloading() {
    return progress?.active && progress?.model_type === type;
  }

  function getBadge(entry: any) {
    if (entry.cached) return { text: 'Cached', color: '#4ade80' };
    if (isDownloading() && entry.id === selectedId) return { text: 'Downloading', color: '#3b82f6' };
    return { text: 'Not cached', color: '#555' };
  }
</script>

<div class="dropdown">
  <div class="dropdown-trigger" onclick={toggleDropdown}>
    {#if getSelectedEntry()}
      <span class="selected-label">{getSelectedEntry().label}</span>
      <span class="selected-size">{getSelectedEntry().size_label}</span>
    {:else}
      <span class="selected-label">Select model</span>
    {/if}
    {#if isDownloading()}
      <div class="spinner"></div>
    {/if}
  </div>

  {#if isOpen}
    <div class="dropdown-options">
      {#each getEntries() as entry}
        <div class="dropdown-option" onclick={() => selectOption(entry.id)}>
          <span class="option-label">{entry.label}</span>
          <span class="option-size">{entry.size_label}</span>
          <span class="option-badge" style="background: {getBadge(entry).color}">
            {getBadge(entry).text}
          </span>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .dropdown {
    position: relative;
  }

  .dropdown-trigger {
    display: flex;
    align-items: center;
    justify-content: space-between;
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 6px;
    padding: 8px 12px;
    font-size: 11px;
    color: #e0e0e0;
    cursor: pointer;
  }

  .dropdown-trigger:hover {
    border-color: #4ade80;
  }

  .selected-label {
    font-weight: 500;
  }

  .selected-size {
    color: #888;
    font-size: 10px;
  }

  .spinner {
    width: 16px;
    height: 16px;
    border: 2px solid #4ade80;
    border-top-color: transparent;
    border-radius: 50%;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .dropdown-options {
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 6px;
    margin-top: 4px;
    max-height: 300px;
    overflow-y: auto;
    z-index: 10;
  }

  .dropdown-option {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 8px 12px;
    cursor: pointer;
    border-bottom: 1px solid #2a2a2a;
  }

  .dropdown-option:last-child {
    border-bottom: none;
  }

  .dropdown-option:hover {
    background: #2a2a2a;
  }

  .option-label {
    font-size: 11px;
    color: #e0e0e0;
  }

  .option-size {
    font-size: 10px;
    color: #888;
  }

  .option-badge {
    font-size: 8px;
    color: white;
    padding: 2px 4px;
    border-radius: 4px;
    white-space: nowrap;
  }
</style>
