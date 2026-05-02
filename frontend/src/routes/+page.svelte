<script lang="ts">
  import { onMount } from 'svelte';
  import { getHealth, search as apiSearch } from '$lib/api';
  import { searchResults, activeVideo } from '$lib/stores';
  import MomentGrid from '$lib/components/MomentGrid.svelte';
  import VideoPlayer from '$lib/components/VideoPlayer.svelte';
  import type { VideoResultResponse } from '$lib/types';

  let query = $state('');
  let indexedCount = $state<number | null>(null);
  let loading = $state(false);
  let searchError = $state<string | null>(null);

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
    searchError = null;
    try {
      const result = await apiSearch(query.trim(), 10);
      searchResults.set(result);
    } catch (e) {
      searchError = e instanceof Error ? e.message : 'Search failed';
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

    {#if searchError}
      <p class="search-error">{searchError}</p>
    {/if}

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

  .search-error {
    font-size: 10px;
    color: #f87171;
  }

  .results-area {
    display: flex;
    gap: 12px;
    padding: 0 20px 16px;
    flex: 1;
    min-height: 0;
  }
</style>
