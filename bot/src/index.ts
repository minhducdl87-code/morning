// Caman — Cloudflare Worker entry.
// Only: webhook shell (health check, secret verify, JSON parse) + dispatch to router.

import type { Env } from './types';
import type { TgUpdate } from './telegram-types';
import { assertEnv } from './env-guard';
import { handleUpdate } from './router';

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    try {
      assertEnv(env);
    } catch (e) {
      console.error('[env]', e instanceof Error ? e.message : e);
      return new Response('server misconfigured', { status: 500 });
    }

    const url = new URL(request.url);

    // Health check
    if (request.method === 'GET' && url.pathname === '/') {
      return new Response(`caman-bot up. hooked to https://t.me/${env.BOT_USERNAME}`, { status: 200 });
    }

    if (url.pathname !== '/webhook' || request.method !== 'POST') {
      return new Response('Not found', { status: 404 });
    }

    // Verify Telegram webhook secret
    const gotSecret = request.headers.get('X-Telegram-Bot-Api-Secret-Token');
    if (env.TELEGRAM_WEBHOOK_SECRET && gotSecret !== env.TELEGRAM_WEBHOOK_SECRET) {
      return new Response('forbidden', { status: 403 });
    }

    let update: TgUpdate;
    try { update = await request.json() as TgUpdate; }
    catch { return new Response('bad json', { status: 400 }); }

    // Fire and forget — return 200 fast so Telegram doesn't retry
    ctx.waitUntil(handleUpdate(update, env).catch(e => console.error('[handle]', e)));
    return new Response('ok', { status: 200 });
  },
};
