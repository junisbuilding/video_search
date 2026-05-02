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
