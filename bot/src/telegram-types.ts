// Telegram Bot API update/message shapes actually consumed by this bot.
// Only the fields we read — not a full Telegram API type dump (YAGNI).

export interface TgUser {
  id: number;
  is_bot?: boolean;
  first_name?: string;
  username?: string;
}

export interface TgChat {
  id: number;
  type: string;
}

export interface TgVoice {
  file_id: string;
  file_unique_id: string;
  duration: number;
  mime_type?: string;
  file_size?: number;
}

export interface TgPhotoSize {
  file_id: string;
  file_unique_id: string;
  width: number;
  height: number;
  file_size?: number;
}

export interface TgMessage {
  message_id: number;
  from?: TgUser;
  chat: TgChat;
  date: number;
  text?: string;
  caption?: string;
  voice?: TgVoice;
  photo?: TgPhotoSize[];
}

export interface TgUpdate {
  update_id: number;
  message?: TgMessage;
  edited_message?: TgMessage;
}

// Pulls the effective message out of an update (message or edited_message).
export function getUpdateMessage(update: TgUpdate): TgMessage | null {
  return update.message || update.edited_message || null;
}
