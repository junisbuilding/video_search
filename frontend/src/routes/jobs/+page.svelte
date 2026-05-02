<script lang="ts">
  import { jobs } from '$lib/stores';
  import JobItem from '$lib/components/JobItem.svelte';
</script>

<div class="page">
  <div class="page-header">
    <h1 class="page-title">Jobs</h1>
  </div>

  {#if $jobs.length === 0}
    <p class="empty">No jobs yet.</p>
  {:else}
    <ul class="job-list">
      {#each $jobs as job (job.id)}
        <JobItem {job} />
      {/each}
    </ul>
  {/if}
</div>

<style>
  .page {
    padding: 24px 20px;
    flex: 1;
  }

  .page-header {
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

  .job-list {
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
</style>
