<script lang="ts">
  import type { ModelCatalogResponse, DownloadProgress, ModelCatalogEntry } from '$lib/types';

  let { type, catalog, selectedId, progress, onchange }: {
    type: 'vision' | 'siglip' | 'text_embedder';
    catalog: ModelCatalogResponse;
    selectedId: string;
    progress: DownloadProgress | null;
    onchange: (id: string) => void;
  } = $props();

  let isOpen = $state(false);
  let dropdownElement: HTMLDivElement;
  let focusedIndex = $state(-1);

  function getEntries() {
    return catalog[type];
  }

  function getSelectedEntry() {
    return getEntries().find(e => e.id === selectedId);
  }

  function toggleDropdown() {
    isOpen = !isOpen;
  }

  function handleClickOutside(event: MouseEvent) {
    if (dropdownElement && !dropdownElement.contains(event.target as Node)) {
      isOpen = false;
    }
  }

  function selectOption(id: string) {
    selectedId = id;
    isOpen = false;
    onchange(id);
  }

  function isDownloading() {
    return progress?.active && progress?.model_type === type;
  }

  function getBadge(entry: ModelCatalogEntry) {
    if (entry.cached) return { text: 'Cached', color: '#4ade80' };
    if (isDownloading() && entry.id === selectedId) return { text: 'Downloading', color: '#3b82f6' };
    if (progress?.error && entry.id === selectedId) return { text: 'Error', color: '#ef4444' };
    return { text: 'Not cached', color: '#555' };
  }

  function handleKeyDown(event: KeyboardEvent) {
    const entries = getEntries();

    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      if (isOpen && focusedIndex >= 0 && focusedIndex < entries.length) {
        selectOption(entries[focusedIndex].id);
      } else {
        toggleDropdown();
      }
    } else if (event.key === 'Escape') {
      isOpen = false;
      focusedIndex = -1;
    } else if (isOpen) {
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        focusedIndex = Math.min(focusedIndex + 1, entries.length - 1);
      } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        focusedIndex = Math.max(focusedIndex - 1, 0);
      }
    }
  }

  function handleOptionKeyDown(event: KeyboardEvent, index: number) {
    focusedIndex = index;
    handleKeyDown(event);
  }
</script>

<svelte:body on:click={handleClickOutside} />

<div class="dropdown" bind:this={dropdownElement}>
  <div class="dropdown-trigger" onclick={toggleDropdown} onkeydown={handleKeyDown} tabindex="0">
    {#if getSelectedEntry()}
      <span class="selected-label">{getSelectedEntry()?.label || 'Select model'}</span>
      <span class="selected-size">{getSelectedEntry()?.size_label || ''}</span>
    {:else}
      <span class="selected-label">Select model</span>
    {/if}
    {#if isDownloading()}
      <div class="spinner"></div>
    {/if}
  </div>

  {#if isOpen}
    <div class="dropdown-options">
      {#each getEntries() as entry, index}
        <div
          class="dropdown-option"
          class:focused={index === focusedIndex}
          onclick={() => selectOption(entry.id)}
          onkeydown={(e) => handleOptionKeyDown(e, index)}
          tabindex="0"
        >
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

  .dropdown-option.focused {
    background: #3b82f6;
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
