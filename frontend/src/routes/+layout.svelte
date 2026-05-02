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
