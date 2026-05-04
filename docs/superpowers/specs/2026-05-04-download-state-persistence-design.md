# Download State Persistence Design

## Problem

Download progress state is currently stored only in memory (`ModelDownloader` instance variables). When the server restarts (dev reload, production restart), all progress is lost. The API returns `downloaded: 0, total: 0` even though downloads may still be running in the background.

## Requirements

- **Persistence scope**: Download state must survive both server and client restarts
- **Resume behavior**: Auto-resume interrupted downloads when server restarts
- **History tracking**: Track only active downloads (cleanup when complete)
- **Implementation priority**: Balanced approach - robust without over-engineering

## Solution

Add SQLite database persistence for download state, using the existing database infrastructure.

## Database Schema

### New `downloads` Table

| Field | Type | Description |
|-------|------|-------------|
| `id` | string (PK) | Format: `{model_type}:{model_id}` |
| `model_type` | string | vision, siglip, text_embedder |
| `model_id` | string | From catalog |
| `downloaded_bytes` | integer | Bytes downloaded so far |
| `total_bytes` | integer | Total file size |
| `status` | string | queued, downloading, complete, error |
| `error_message` | string | null | Error details if failed |
| `updated_at` | float | Timestamp of last update |
| `created_at` | float | Timestamp when download started |

### Indexes

- Primary key on `id`
- Index on `status` for querying active downloads

### Lifecycle

1. Created when download starts
2. Updated during progress (downloaded_bytes, total_bytes, updated_at)
3. Marked complete/error when finished
4. Auto-deleted when complete (cleanup on startup)

## Architecture

### Components

#### 1. DownloadStateRepo (new class)

**Location**: `src/videosearch/storage/downloads.py`

**Responsibilities**:
- CRUD operations for download records
- Thread-safe database operations
- Cleanup of completed records

**Methods**:
- `create(model_type, model_id, total_bytes)` - Create new download record
- `update_progress(id, downloaded_bytes, total_bytes)` - Update progress
- `mark_complete(id)` - Mark download as complete
- `mark_error(id, error_message)` - Mark download as failed
- `get_active()` - Get all active downloads (status != complete/error)
- `cleanup_completed()` - Delete completed/error records older than 1 hour

#### 2. ModelDownloader (modified)

**Location**: `src/videosearch/models/downloader.py`

**Changes**:
- Accept `DownloadStateRepo` in constructor
- On startup: call `get_active()` to restore in-memory state
- During download: call `update_progress()` periodically (via tqdm callback)
- On completion/error: call `mark_complete()` / `mark_error()`
- On startup: call `cleanup_completed()` to remove old records

#### 3. Lifespan (modified)

**Location**: `src/videosearch/api/app.py`

**Changes**:
- Create `DownloadStateRepo` after `Database`
- Pass repo to `ModelDownloader`

### Data Flow

```
Download starts → DownloadStateRepo.create()
Progress updates → DownloadStateRepo.update_progress() (thread-safe)
Download completes → DownloadStateRepo.mark_complete()
Server restarts → DownloadStateRepo.get_active() → restore in-memory state
```

## Error Handling

### Database Errors

- **Progress update failure**: Log warning but continue (don't block download)
- **Completion/error write failure**: Retry 3 times with exponential backoff, then log error
- **Startup read failure**: Log error and start with empty state (degraded mode)

### Thread Safety

- `DownloadStateRepo.update_progress()` must be thread-safe (downloads run in executor threads)
- Use SQLite's built-in thread-safety with proper connection handling
- Each thread gets its own connection from the database pool

### Edge Cases

**Orphaned records**: If server crashes during download, record stays in "downloading" state.
- On startup: Check if file exists and is complete → mark complete
- Otherwise: Restart download (HF Hub will resume from where it left off)

**Concurrent downloads**: Multiple downloads can update simultaneously.
- Use row-level locking or optimistic concurrency
- SQLite handles this with proper transaction isolation

**Zero-byte files**: Handle case where total_bytes is 0 initially.
- HF Hub may not know size immediately
- Allow updates with total_bytes = 0, update when known

### Cleanup Strategy

On startup: Delete records with status "complete" or "error" older than 1 hour.
- Keeps table small
- Allows brief inspection of recent failures
- Prevents accumulation of stale records

## Testing

### Unit Tests

- `DownloadStateRepo` CRUD operations
- Thread-safety of concurrent updates
- Error handling (database failures, corrupted data)

### Integration Tests

- Download progress persists across server restart
- Orphaned records are cleaned up on startup
- Multiple concurrent downloads update correctly

### Test Scenarios

1. Start download, verify record created
2. Update progress, verify record updated
3. Simulate server crash, restart, verify state restored
4. Complete download, verify record marked complete
5. Fail download, verify record marked error
6. Multiple concurrent downloads, verify no data loss

## Implementation Notes

- Use existing `Database` class (LanceDB wrapper) for SQLite connection
- Leverage existing database infrastructure in `src/videosearch/storage/db.py`
- Follow existing patterns in other storage classes (videos, jobs, etc.)
- Minimal changes to existing `ModelDownloader` logic
- No changes to API endpoints or frontend required
