// Whitelist gate — private bot, only allowed chat IDs

export function isAllowed(chatId: number | string, allowedCsv: string): boolean {
  const set = new Set(allowedCsv.split(',').map(s => s.trim()).filter(Boolean));
  return set.has(String(chatId));
}
