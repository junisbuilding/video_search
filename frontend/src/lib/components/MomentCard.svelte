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
