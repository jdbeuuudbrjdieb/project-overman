# ══════════════════════════════════════════════════════════════════════════════
# 🌟 PROJECT OVERMAN - ULTIMATE OS EDITION v2.0
# ══════════════════════════════════════════════════════════════════════════════
# قابلیت‌ها: ساعت زنده + آنلاین همیشگی + تایپ مداوم
# منشی AI (با قابلیت خاموش/روشن) + خلبان خودکار + مدیریت گروه پیشرفته
# صندوق امانات + ضد حذف پیام + مترجم درجا + پنل کنترل از راه دور
# ══════════════════════════════════════════════════════════════════════════════

import os
import asyncio
import logging
import time
import re
import json
from datetime import datetime
from zoneinfo import ZoneInfo
import requests
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.functions.account import UpdateProfileRequest, UpdateStatusRequest
from telethon.tl.functions.messages import SetTypingRequest
from telethon.tl.types import SendMessageTypingAction, ChatBannedRights
from telethon.tl.functions.channels import EditBannedRequest
from telethon.errors import FloodWaitError, ChatAdminRequiredError

# ══════════════════════════════════════════════════════════════════════════════
# ۱. تنظیمات اولیه
# ══════════════════════════════════════════════════════════════════════════════
logging.basicConfig(format="%(asctime)s | %(levelname)-8s | %(message)s", level=logging.INFO)
logger = logging.getLogger("OvermanUltimate")

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SESSION_STRING = os.getenv("SESSION_STRING", "")
BASE_NAME = os.getenv("BASE_NAME", "Master")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

if not API_ID or not API_HASH or not SESSION_STRING:
    logger.critical("❌ متغیرهای محیطی یافت نشدند.")
    exit(1)

KABUL_TZ = ZoneInfo("Asia/Kabul")
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# ══════════════════════════════════════════════════════════════════════════════
# ۲. حافظه‌های موقت (State Management)
# ══════════════════════════════════════════════════════════════════════════════
recent_ai_replies = {}   # جلوگیری از اسپم منشی
user_warns = {}          # سیستم اخطار: { (chat_id, user_id): count }
message_cache = {}       # حافظه برای ضد حذف: { (chat_id, msg_id): text }
secretary_enabled = True # وضعیت منشی
ai_history = {}          # حافظه کوتاه‌مدت AI: { user_id: [messages] }

# ══════════════════════════════════════════════════════════════════════════════
# ۳. موتورهای خارجی (AI و Translator)
# ══════════════════════════════════════════════════════════════════════════════
async def ai_reply(user_msg, sender_name, user_id):
    url = "https://text.pollinations.ai/openai"
    
    # مدیریت حافظه کوتاه مدت AI
    if user_id not in ai_history: ai_history[user_id] = []
    ai_history[user_id].append({"role": "user", "content": user_msg})
    if len(ai_history[user_id]) > 4: ai_history[user_id].pop(0)
    
    sys_prompt = (
        f"You are the personal AI secretary of {BASE_NAME}. "
        f"The user '{sender_name}' is talking to you. "
        f"Reply politely in the same language, saying {BASE_NAME} is currently busy. "
        f"Keep it very short (max 2 sentences)."
    )
    
    payload = {
        "model": "openai",
        "messages": [{"role": "system", "content": sys_prompt}] + ai_history[user_id]
    }
    try:
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(None, lambda: requests.post(url, json=payload, timeout=20))
        if res.status_code == 200:
            reply = res.json()["choices"][0]["message"]["content"]
            ai_history[user_id].append({"role": "assistant", "content": reply})
            return reply
    except Exception as e:
        logger.error(f"AI Error: {e}")
    return f"سلام {sender_name} عزیز، {BASE_NAME} الان در دسترس نیست. به زودی پاسخ می‌دهد."

async def translate_text(text):
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=fa&dt=t&q={requests.utils.quote(text)}"
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(None, lambda: requests.get(url, timeout=10))
        if res.status_code == 200:
            return "".join([part[0] for part in res.json()[0]])
    except Exception as e:
        logger.error(f"Translate Error: {e}")
    return "❌ خطا در ترجمه."

# ══════════════════════════════════════════════════════════════════════════════
# ۴. منشی هوشمند (AI Secretary)
# ══════════════════════════════════════════════════════════════════════════════
@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
async def secretary(event):
    global secretary_enabled
    if not secretary_enabled: return
    
    sender = await event.get_sender()
    me = await client.get_me()
    if sender.bot or sender.id == me.id: return
    
    now = time.time()
    if sender.id in recent_ai_replies and now - recent_ai_replies[sender.id] < 300: return # ۵ دقیقه کول‌داون
    
    logger.info(f"🤖 منشی پاسخ داد به {sender.first_name}")
    reply = await ai_reply(event.raw_text or "[Media]", sender.first_name, sender.id)
    try:
        await event.reply(reply)
        recent_ai_replies[sender.id] = now
    except Exception as e:
        logger.error(f"Secretary Error: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# ۵. سیستم ضد حذف (Anti-Delete Black Box)
# ══════════════════════════════════════════════════════════════════════════════
@client.on(events.NewMessage(incoming=True))
async def cache_messages(event):
    # ذخیره پیام‌ها در حافظه برای جلوگیری از حذف
    if event.raw_text:
        message_cache[(event.chat_id, event.message.id)] = (event.sender_id, event.raw_text)
        # جلوگیری از پر شدن حافظه (فقط ۲۰۰۰ پیام آخر)
        if len(message_cache) > 2000: message_cache.pop(next(iter(message_cache)))

@client.on(events.MessageDeleted)
async def anti_delete(event):
    for msg_id in event.deleted_ids:
        key = (event.chat_id, msg_id)
        if key in message_cache:
            sender_id, text = message_cache.pop(key)
            try:
                # ارسال به Saved Messages
                await client.send_message("me", f"🚨 **پیام حذف‌شده**\n👤 فرستنده: `{sender_id}`\n📝 متن: {text}")
            except: pass

# ══════════════════════════════════════════════════════════════════════════════
# ۶. مدیریت گروه (Moderator & Warn System)
# ══════════════════════════════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True, pattern=r"^(بن|سکوت|آزاد|اخطار|حذف|پاکسازی)$"))
async def moderator(event):
    if not event.is_group: return
    
    cmd = event.pattern_match.group(1)
    
    if cmd == "پاکسازی":
        count = 0
        async for msg in client.iter_messages(event.chat_id, limit=50):
            if msg.id == event.id: break
            try: await msg.delete(); count += 1
            except: pass
        return await event.edit(f"🧹 {count} پیام پاک شد.")
    
    reply = await event.get_reply_message()
    if not reply: return await event.edit("❌ روی پیام کاربر ریپلای کنید.")
    
    target = await reply.get_sender()
    chat_id = event.chat_id
    target_id = target.id
    
    try:
        if cmd == "بن":
            await client(EditBannedRequest(chat_id, target_id, ChatBannedRights(until_date=None, view_messages=True)))
            await event.edit(f"⛔️ {target.first_name} بن شد.")
        elif cmd == "سکوت":
            await client(EditBannedRequest(chat_id, target_id, ChatBannedRights(until_date=None, send_messages=True)))
            await event.edit(f"🔇 {target.first_name} سکوت شد.")
        elif cmd == "آزاد":
            await client(EditBannedRequest(chat_id, target_id, ChatBannedRights(until_date=None)))
            await event.edit(f"🔊 {target.first_name} آزاد شد.")
        elif cmd == "حذف":
            await reply.delete()
            await event.delete()
        elif cmd == "اخطار":
            key = (chat_id, target_id)
            user_warns[key] = user_warns.get(key, 0) + 1
            warns = user_warns[key]
            if warns >= 3:
                await client(EditBannedRequest(chat_id, target_id, ChatBannedRights(until_date=None, view_messages=True)))
                await event.edit(f"⛔️ {target.first_name} با ۳ اخطار بن شد.")
                del user_warns[key]
            else:
                await event.edit(f"⚠️ {target.first_name} اخطار گرفت. ({warns}/3)")
    except ChatAdminRequiredError:
        await event.edit("❌ ربات در این گروه ادمین نیست.")

# ══════════════════════════════════════════════════════════════════════════════
# ۷. پنل کنترل از راه دور (Remote Panel) + مترجم
# ══════════════════════════════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True))
async def remote_control(event):
    text = event.raw_text.strip()
    
    # ۱. مترجم
    if text == "#ترجمه" and event.is_reply:
        reply = await event.get_reply_message()
        if reply.raw_text:
            await event.edit("⏳ در حال ترجمه...")
            translated = await translate_text(reply.raw_text)
            await event.edit(f"🌐 **ترجمه:**\n{translated}")
        return

    # ۲. پنل کنترل (فقط در Saved Messages)
    me = await client.get_me()
    if event.chat_id != me.id: return
    
    if text == "#status":
        status = (
            f"👑 **وضعیت ربات**\n"
            f"🟢 آنلاین: بله\n"
            f"⌨️ تایپ: بله\n"
            f"🤖 منشی: {'روشن' if secretary_enabled else 'خاموش'}\n"
            f"👥 پیام‌های کش‌شده: {len(message_cache)}\n"
            f"⚠️ اخطارهای فعال: {len(user_warns)}"
        )
        await event.edit(status)
    elif text == "#secretary off":
        globals()['secretary_enabled'] = False
        await event.edit("🔴 منشی خاموش شد.")
    elif text == "#secretary on":
        globals()['secretary_enabled'] = True
        await event.edit("🟢 منشی روشن شد.")
    elif text.startswith("#pilot send|"):
        try:
            parts = text.replace("#pilot ", "").split("|")
            if len(parts) == 3:
                target, msg = parts[1].strip(), parts[2].strip()
                await event.edit(f"✈️ خلبان فعال شد: ارسال به {target}")
                
                async def pilot_task():
                    while True:
                        try: await client.send_message(target, msg)
                        except Exception as e: logger.error(f"Pilot: {e}")
                        await asyncio.sleep(3600)
                asyncio.create_task(pilot_task())
        except Exception: await event.edit("❌ فرمت اشتباه است.")

# ══════════════════════════════════════════════════════════════════════════════
# ۸. حلقه‌های پس‌زمینه (ساعت، آنلاین، تایپ)
# ══════════════════════════════════════════════════════════════════════════════
async def clock_loop():
    while True:
        try:
            now = datetime.now(KABUL_TZ)
            name = f"🕒 {now.strftime('%H:%M')} | {BASE_NAME}"
            await client(UpdateProfileRequest(first_name=name[:64]))
            await client(UpdateStatusRequest(offline=False))
        except FloodWaitError as e: await asyncio.sleep(e.seconds)
        except Exception as e: logger.error(f"Clock: {e}")
        await asyncio.sleep(30)

async def typing_loop():
    peer = None
    while True:
        try:
            if peer is None:
                dialogs = await client.get_dialogs(limit=1)
                peer = dialogs[0].entity if dialogs else await client.get_me()
            await client(SetTypingRequest(peer=peer, action=SendMessageTypingAction()))
        except: peer = None
        await asyncio.sleep(4)

# ══════════════════════════════════════════════════════════════════════════════
# ۹. نقطه ورود
# ══════════════════════════════════════════════════════════════════════════════
async def main():
    logger.info("🚀 اتصال به تلگرام...")
    await client.connect()
    if not await client.is_user_authorized():
        logger.error("❌ سشن نامعتبر است.")
        return
    me = await client.get_me()
    logger.info(f"✅ متصل شد به: {me.first_name}")
    logger.info("🔥 Ultimate OS v2.0 فعال شد.")
    
    asyncio.create_task(clock_loop())
    asyncio.create_task(typing_loop())
    await client.run_until_disconnected()

if __name__ == "__main__":
    try: client.loop.run_until_complete(main())
    except (KeyboardInterrupt, SystemExit): logger.info("👋 خاموش شد.")
    finally:
        try: client.loop.run_until_complete(client.disconnect())
        except: pass
