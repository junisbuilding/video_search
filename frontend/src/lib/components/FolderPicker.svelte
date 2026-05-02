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
