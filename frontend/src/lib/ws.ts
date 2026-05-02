import { jobs, upsertById } from './stores';
import type { Job } from './types';

type WsEvent = Omit<Job, 'id'> & { job_id: string };

export function connectJobsSocket(): () => void {
  let stopped = false;
  let timeoutId: ReturnType<typeof setTimeout> | undefined;

  function connect(): void {
    if (stopped) return;
    const ws = new WebSocket(`ws://${location.host}/ws/jobs`);

    ws.onmessage = (e: MessageEvent) => {
      const { job_id, ...rest } = JSON.parse(e.data as string) as WsEvent;
      const job: Job = { ...rest, id: job_id };
      jobs.update(list => upsertById(list, job));
    };

    ws.onclose = () => {
      if (!stopped) {
        timeoutId = setTimeout(connect, 2000);
      }
    };

    ws.onerror = () => {
      ws.close();
    };
  }

  connect();

  return () => {
    stopped = true;
    clearTimeout(timeoutId);
  };
}
