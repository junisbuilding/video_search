export interface HealthResponse {
  status: string;
  db: boolean;
  models_loaded: boolean;
  gpu_backend: string;
  indexed_count: number;
}

export interface MomentResponse {
  timestamp_sec: number;
  score: number;
  thumb_url: string | null;
  caption: string | null;
  source: 'frame' | 'caption';
}

export interface VideoResultResponse {
  video_id: string;
  path: string;
  duration_sec: number;
  top_score: number;
  moments: MomentResponse[];
}

export interface SearchResponse {
  query: string;
  results: VideoResultResponse[];
}

export interface FolderCounts {
  indexed: number;
  pending: number;
  failed: number;
  missing: number;
}

export interface FolderResponse {
  id: string;
  path: string;
  added_at: number;
  counts: FolderCounts;
}

export interface LibraryResponse {
  folders: FolderResponse[];
  ad_hoc_counts: FolderCounts;
}

export interface RegisterFolderResponse {
  folder: FolderResponse;
  enqueued: number;
}

export interface Job {
  id: string;
  video_id: string | null;
  path: string | null;
  kind: string;
  status: string;
  progress: number;
  error: string | null;
  created_at: number;
  updated_at: number;
}

export interface JobsListResponse {
  jobs: Job[];
}

export interface RetryResponse {
  job_id: string;
}

export interface FsEntry {
  name: string;
  path: string;
  kind: 'dir' | 'video' | 'other';
  size_bytes: number | null;
  mtime: number;
}

export interface FsListResponse {
  path: string;
  parent: string | null;
  entries: FsEntry[];
}

export interface IngestResponse {
  enqueued: string[];
}

export interface SettingsResponse {
  hf_token: string | null;
}

export interface SettingsPatch {
  frame_fps?: number | null;
  scene_detection?: boolean | null;
  port?: number | null;
  siglip_model?: string | null;
  text_embedder?: string | null;
  vlm_model?: string | null;
  vlm_mmproj?: string | null;
  vlm_n_gpu_layers?: number | null;
  hf_token?: string | null;
}

export interface ModelCatalogEntry {
  id: string;
  label: string;
  size_label: string;
  cached: boolean;
  default: boolean;
}

export interface ModelCatalogResponse {
  first_run: boolean;
  active_models: { vision: string; siglip: string; text_embedder: string };
  vision: ModelCatalogEntry[];
  siglip: ModelCatalogEntry[];
  text_embedder: ModelCatalogEntry[];
}

export interface DownloadProgress {
  active: boolean;
  model_type: string;
  model_id: string;
  downloaded_bytes: number;
  total_bytes: number;
  error: string | null;
  complete: boolean;
}
