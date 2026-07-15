// Cloudflare cron trigger → GitHub Actions dispatch (Kiểu A).
// The Worker cron only wakes up and asks GitHub Actions to run morning.yml —
// GitHub's own schedule stays the source of truth/backup; this just gives a
// second, more reliable wake-up call. Never throws — a missing token or a
// failed dispatch must not crash the Worker's scheduled handler.

import type { Env } from './types';
import { fetchWithTimeout } from './http';

export async function dispatchWorkflow(env: Env, runMode: 'morning' | 'evening'): Promise<void> {
  if (!env.GH_DISPATCH_TOKEN) {
    console.error('[dispatch] GH_DISPATCH_TOKEN not set — skipping workflow dispatch');
    return;
  }

  const url = `https://api.github.com/repos/${env.GH_REPO}/actions/workflows/morning.yml/dispatches`;

  try {
    const res = await fetchWithTimeout(url, {
      method: 'POST',
      headers: {
        authorization: `Bearer ${env.GH_DISPATCH_TOKEN}`,
        accept: 'application/vnd.github+json',
        'x-github-api-version': '2022-11-28',
        'user-agent': 'caman-bot-cron',
        'content-type': 'application/json',
      },
      body: JSON.stringify({ ref: 'main', inputs: { run_mode: runMode } }),
    }, 10000);
    console.log(`[dispatch] run_mode=${runMode} status=${res.status}`);
  } catch (e) {
    console.error('[dispatch] failed:', e);
  }
}
