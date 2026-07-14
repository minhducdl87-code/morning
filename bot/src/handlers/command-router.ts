// Slash command dispatch table — loads digest at most once per command (M3)
import type { Env, DigestData } from '../types';
import { sendLongMessage, sendPhoto, sendPhotoBlob, esc } from '../telegram';
import { loadDigest } from '../digest';
import {
  cmdStart, cmdHelp, cmdDigest, cmdTopic, cmdWeek, cmdMonth,
  cmdDeep, cmdImg, cmdClear,
} from '../commands';

const DIGEST_COMMANDS = new Set(['/digest', '/topic', '/week', '/month', '/deep']);

export async function routeCommand(
  trimmedText: string, chatId: number, userId: number, env: Env, token: string,
): Promise<void> {
  const [rawCmd, ...rest] = trimmedText.split(/\s+/);
  const cmd = rawCmd.split('@')[0].toLowerCase();
  const arg = rest.join(' ');

  // Load digest once for the whole group of commands that need it, instead
  // of once per switch case.
  const data: DigestData | null = DIGEST_COMMANDS.has(cmd) ? await loadDigest(env.SITE_BASE_URL) : null;

  let reply: string | null = null;
  let photo: { imageUrl?: string; imageBytes?: Uint8Array; error?: string } | null = null;

  switch (cmd) {
    case '/start': reply = cmdStart(env); break;
    case '/help':  reply = cmdHelp(env); break;
    case '/clear': reply = await cmdClear(env, userId); break;
    case '/digest': reply = cmdDigest(data as DigestData); break;
    case '/topic':  reply = cmdTopic(data as DigestData, arg); break;
    case '/week':   reply = cmdWeek(data as DigestData); break;
    case '/month':  reply = cmdMonth(data as DigestData); break;
    case '/deep':   reply = await cmdDeep(env, data as DigestData, arg); break;
    case '/img':    photo = await cmdImg(env, arg); break;
    default:
      reply = `❓ Không nhận diện lệnh <code>${esc(cmd)}</code>. Gõ /help để xem menu.`;
  }

  if (photo?.imageBytes) {
    await sendPhotoBlob(token, chatId, photo.imageBytes, `🎨 <i>${esc(arg)}</i>`);
  } else if (photo?.imageUrl) {
    await sendPhoto(token, chatId, photo.imageUrl, `🎨 <i>${esc(arg)}</i>`);
  } else if (photo?.error) {
    await sendLongMessage(token, chatId, photo.error);
  } else if (reply) {
    await sendLongMessage(token, chatId, reply);
  }
}
