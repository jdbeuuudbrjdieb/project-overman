# ══════════════════════════════════════════════════════════════════════════════
# 🌟 PROJECT OVERMAN - Enterprise Userbot Edition v1.0
# ══════════════════════════════════════════════════════════════════════════════
# قابلیت‌ها: ساعت زنده کابل + آنلاین همیشگی + تایپ مداوم
#           + منشی هوشمند AI + خلبان خودکار + مدیریت گروه + صندوق امانات
# ══════════════════════════════════════════════════════════════════════════════

import os
import asyncio
import logging
import time
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
# ۱. تنظیمات لاگ
# ══════════════════════════════════════════════════════════════════════════════
logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("Overman")

# ══════════════════════════════════════════════════════════════════════════════
# ۲. خواندن متغیرها
# ══════════════════════════════════════════════════════════════════════════════
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

# حافظه‌های موقت
recent_ai_replies = {}     # { user_id: timestamp }
auto_pilot_tasks = []      # لیست تسک‌ها

# ══════════════════════════════════════════════════════════════════════════════
# ۳. موتور هوش مصنوعی
# ══════════════════════════════════════════════════════════════════════════════
async def ai_reply(user_msg, sender_name):
    url = "https://text.pollinations.ai/openai"
    sys_prompt = (
        f"You are the AI secretary of {BASE_NAME}. User '{sender_name}' sent a message. "
        f"Reply politely on behalf of {BASE_NAME} in the same language. "
        f"Say {BASE_NAME} is currently busy and will reply soon. Keep it short."
    )
    payload = {
        "model": "openai",
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_msg}
        ]
    }
    try:
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(None, lambda: requests.post(url, json=payload, timeout=20))
        if res.status_code == 200:
            return res.json()["choices"][0]["message"]["content"]
    except Exception as e:
        logger.error(f"AI Error: {e}")
    return f"سلام، {BASE_NAME} الان در دسترس نیست. به زودی پاسخ می‌دهد."

# ══════════════════════════════════════════════════════════════════════════════
# ۴. منشی هوشمند (پاسخ خودکار در چت‌های خصوصی)
# ══════════════════════════════════════════════════════════════════════════════
@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
async def secretary(event):
    sender = await event.get_sender()
    me = await client.get_me()
    if sender.bot or sender.id == me.id:
        return
    
    now = time.time()
    if sender.id in recent_ai_replies and now - recent_ai_replies[sender.id] < 600:
        return
    
    logger.info(f"🤖 منشی پاسخ داد به {sender.first_name}")
    reply = await ai_reply(event.raw_text or "[Media]", sender.first_name)
    try:
        await event.reply(reply)
        recent_ai_replies[sender.id] = now
    except Exception as e:
        logger.error(f"Secretary Error: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# ۵. صندوق امانات (آرشیو پیام‌های خصوصی)
# ══════════════════════════════════════════════════════════════════════════════
@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
async def vault(event):
    sender = await event.get_sender()
    me = await client.get_me()
    if sender.id == me.id:
        return
    
    text = event.raw_text or "[رسانه]"
    ts = datetime.now(KABUL_TZ).strftime("%Y-%m-%d %H:%M")
    msg = f"📩 **صندوق امانات**\n👤 از: {sender.first_name} (`{sender.id}`)\n⏰ {ts}\n\n{text}"
    try:
        await client.send_message("me", msg)
    except Exception as e:
        logger.error(f"Vault Error: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# ۶. مدیریت گروه (دستورات فارسی)
# ══════════════════════════════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True, pattern=r"^(بن|سکوت|آزاد|اخطار|حذف)$"))
async def moderator(event):
    if not event.is_group:
        return
    
    cmd = event.pattern_match.group(1)
    reply = await event.get_reply_message()
    if not reply:
        return await event.edit("❌ روی پیام کاربر ریپلای کنید.")
    
    target = await reply.get_sender()
    
    try:
        if cmd == "بن":
            await client(EditBannedRequest(event.chat_id, target.id, ChatBannedRights(until_date=None, view_messages=True)))
            await event.edit(f"⛔️ {target.first_name} بن شد.")
        elif cmd == "سکوت":
            await client(EditBannedRequest(event.chat_id, target.id, ChatBannedRights(until_date=None, send_messages=True)))
            await event.edit(f"🔇 {target.first_name} سکوت شد.")
        elif cmd == "آزاد":
            await client(EditBannedRequest(event.chat_id, target.id, ChatBannedRights(until_date=None)))
            await event.edit(f"🔊 {target.first_name} آزاد شد.")
        elif cmd == "اخطار":
            await event.edit(f"⚠️ {target.first_name} اخطار گرفت.")
        elif cmd == "حذف":
            await reply.delete()
            await event.delete()
    except ChatAdminRequiredError:
        await event.edit("❌ ربات در این گروه ادمین نیست.")
    except Exception as e:
        logger.error(f"Mod Error: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# ۷. خلبان خودکار (Auto Pilot)
# ══════════════════════════════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True, pattern=r"^#pilot (.+)"))
async def auto_pilot(event):
    me = await client.get_me()
    if event.chat_id != me.id:
        return
    
    task = event.pattern_match.group(1).strip()
    await event.edit(f"✈️ خلبان خودکار فعال شد.")
    
    async def run():
        while True:
            try:
                parts = task.split("|")
                if len(parts) == 3 and parts[0].strip() == "send":
                    await client.send_message(parts[1].strip(), parts[2].strip())
                    logger.info(f"✈️ پیام ارسال شد به {parts[1]}")
                await asyncio.sleep(3600)
            except Exception as e:
                logger.error(f"Pilot Error: {e}")
                await asyncio.sleep(60)
    
    asyncio.create_task(run())

# ══════════════════════════════════════════════════════════════════════════════
# ۸. حلقه ساعت و آنلاین
# ══════════════════════════════════════════════════════════════════════════════
async def clock_loop():
    while True:
        try:
            now = datetime.now(KABUL_TZ)
            name = f"🕒 {now.strftime('%H:%M')} | {BASE_NAME}"
            await client(UpdateProfileRequest(first_name=name[:64]))
            await client(UpdateStatusRequest(offline=False))
        except FloodWaitError as e:
            logger.warning(f"⏳ محدودیت: {e.seconds}s")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            logger.error(f"Clock Error: {e}")
        await asyncio.sleep(30)

# ══════════════════════════════════════════════════════════════════════════════
# ۹. حلقه تایپ مداوم
# ══════════════════════════════════════════════════════════════════════════════
async def typing_loop():
    peer = None
    while True:
        try:
            if peer is None:
                dialogs = await client.get_dialogs(limit=1)
                peer = dialogs[0].entity if dialogs else await client.get_me()
            await client(SetTypingRequest(peer=peer, action=SendMessageTypingAction()))
        except:
            peer = None
        await asyncio.sleep(4)

# ══════════════════════════════════════════════════════════════════════════════
# ۱۰. نقطه ورود
# ══════════════════════════════════════════════════════════════════════════════
async def main():
    logger.info("🚀 اتصال به تلگرام...")
    await client.connect()
    
    if not await client.is_user_authorized():
        logger.error("❌ سشن نامعتبر است.")
        return
    
    me = await client.get_me()
    logger.info(f"✅ متصل شد به: {me.first_name}")
    logger.info("🔥 همه سیستم‌ها فعال شدند.")
    
    asyncio.create_task(clock_loop())
    asyncio.create_task(typing_loop())
    
    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        client.loop.run_until_complete(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("👋 خاموش شد.")
    finally:
        try:
            client.loop.run_until_complete(client.disconnect())
        except:
            pass
