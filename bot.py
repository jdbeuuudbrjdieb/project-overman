# ══════════════════════════════════════════════════════════════════════════════
# 🌟 PROJECT OVERMAN - OMNI-COMMUNICATION EDITION v4.0
# ══════════════════════════════════════════════════════════════════════════════
# قابلیت‌ها: ساعت کابل + آنلاین + تایپ + منشی دری هوشمند + حالت غیبت
# تنظیم متن منشی + زمان‌بند + ری‌اکشن + پنل کنترل از راه دور
# ══════════════════════════════════════════════════════════════════════════════

import os
import sys
import asyncio
import logging
import time
import re
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.functions.account import UpdateProfileRequest, UpdateStatusRequest
from telethon.tl.functions.messages import SetTypingRequest, SendReactionRequest
from telethon.tl.types import SendMessageTypingAction, ChatBannedRights, ReactionEmoji
from telethon.tl.functions.channels import EditBannedRequest
from telethon.errors import FloodWaitError, ChatAdminRequiredError, RPCError

# ══════════════════════════════════════════════════════════════════════════════
# ۱. تنظیمات اولیه
# ══════════════════════════════════════════════════════════════════════════════
logging.basicConfig(format="%(asctime)s | %(levelname)-8s | %(message)s", level=logging.INFO)
logger = logging.getLogger("OvermanOmni")

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SESSION_STRING = os.getenv("SESSION_STRING", "")
BASE_NAME = os.getenv("BASE_NAME", "Master")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

if not API_ID or not API_HASH or not SESSION_STRING:
    sys.exit("❌ متغیرهای محیطی یافت نشدند.")

KABUL_TZ = ZoneInfo("Asia/Kabul")
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# ══════════════════════════════════════════════════════════════════════════════
# ۲. حافظه‌ها و تنظیمات منشی
# ══════════════════════════════════════════════════════════════════════════════
recent_ai_replies = {}
user_warns = {}
message_cache = {}
ai_history = {}

# تنظیمات منشی
away_mode = False
secretary_custom_text = ""  # اگر خالی باشد از هوش مصنوعی استفاده می‌کند

# ══════════════════════════════════════════════════════════════════════════════
# ۳. توابع کمکی
# ══════════════════════════════════════════════════════════════════════════════
def parse_time(time_str):
    """تبدیل 10m یا 2h به ثانیه"""
    match = re.match(r"^(\d+)([mhd])$", time_str.lower())
    if not match: return None
    val, unit = int(match.group(1)), match.group(2)
    if unit == 'm': return val * 60
    if unit == 'h': return val * 3600
    if unit == 'd': return val * 86400
    return None

# ══════════════════════════════════════════════════════════════════════════════
# ۴. موتور هوش مصنوعی دری (Dari AI)
# ══════════════════════════════════════════════════════════════════════════════
async def ai_reply_dari(user_msg, sender_name, user_id):
    if secretary_custom_text:
        return secretary_custom_text
        
    url = "https://text.pollinations.ai/openai"
    
    if user_id not in ai_history: ai_history[user_id] = []
    ai_history[user_id].append({"role": "user", "content": user_msg})
    if len(ai_history[user_id]) > 4: ai_history[user_id].pop(0)
    
    sys_prompt = (
        f"You are the personal AI secretary of {BASE_NAME}. "
        f"The user '{sender_name}' sent a message. "
        f"Reply STRICTLY AND ONLY in Dari (Afghan Persian/Farsi). "
        f"Tell them politely that {BASE_NAME} is currently away and will reply as soon as possible. "
        f"Keep it very short (max 2 sentences)."
    )
    
    payload = {
        "model": "openai",
        "messages": [{"role": "system", "content": sys_prompt}] + ai_history[user_id]
    }
    try:
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(None, lambda: requests.post(url, json=payload, timeout=15))
        if res.status_code == 200:
            reply = res.json()["choices"][0]["message"]["content"]
            ai_history[user_id].append({"role": "assistant", "content": reply})
            return reply
    except Exception as e:
        logger.error(f"AI Error: {e}")
    return f"سلام {sender_name} جان، {BASE_NAME} الان دسترسی ندارد. به زودی جواب می‌دهد."

async def translate_text(text, target="fa"):
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target}&dt=t&q={requests.utils.quote(text)}"
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(None, lambda: requests.get(url, timeout=10))
        if res.status_code == 200:
            return "".join([part[0] for part in res.json()[0]])
    except: pass
    return "❌ خطا در ترجمه."

# ══════════════════════════════════════════════════════════════════════════════
# ۵. منشی هوشمند دری + حالت غیبت + خواندن خودکار
# ══════════════════════════════════════════════════════════════════════════════
@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
async def secretary(event):
    global away_mode
    try:
        # خواندن خودکار پیام (سین زدن)
        await client.send_read_acknowledge(event.chat_id)
        
        if not away_mode: return
        
        sender = await event.get_sender()
        me = await client.get_me()
        if sender.bot or sender.id == me.id: return
        
        now = time.time()
        if sender.id in recent_ai_replies and now - recent_ai_replies[sender.id] < 300: return
        
        reply = await ai_reply_dari(event.raw_text or "[Media]", sender.first_name, sender.id)
        await event.reply(reply)
        recent_ai_replies[sender.id] = now
        logger.info(f"🤖 منشی دری پاسخ داد به {sender.first_name}")
    except Exception as e:
        logger.error(f"Secretary Error: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# ۶. صندوق امانات و ضد حذف
# ══════════════════════════════════════════════════════════════════════════════
@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
async def vault(event):
    try:
        sender = await event.get_sender()
        if sender.id == (await client.get_me()).id: return
        text = event.raw_text or "[رسانه]"
        ts = datetime.now(KABUL_TZ).strftime("%Y-%m-%d %H:%M")
        await client.send_message("me", f"📩 **صندوق امانات**\n👤 از: {sender.first_name} (`{sender.id}`)\n⏰ {ts}\n\n{text}")
    except: pass

@client.on(events.NewMessage(incoming=True))
async def cache_messages(event):
    try:
        if event.raw_text:
            message_cache[(event.chat_id, event.message.id)] = (event.sender_id, event.raw_text)
            if len(message_cache) > 2000: message_cache.pop(next(iter(message_cache)))
    except: pass

@client.on(events.MessageDeleted)
async def anti_delete(event):
    try:
        for msg_id in event.deleted_ids:
            key = (event.chat_id, msg_id)
            if key in message_cache:
                sender_id, text = message_cache.pop(key)
                await client.send_message("me", f"🚨 **پیام حذف‌شده**\n👤 فرستنده: `{sender_id}`\n📝 متن: {text}")
    except: pass

# ══════════════════════════════════════════════════════════════════════════════
# ۷. مدیریت گروه و ری‌اکشن خودکار
# ══════════════════════════════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True, pattern=r"^(بن|سکوت|آزاد|اخطار|حذف|پاکسازی|#react|#info|#pin|#unpin|#ترجمه)$"))
async def moderator(event):
    cmd = event.pattern_match.group(1)
    try:
        if cmd == "پاکسازی" and event.is_group:
            count = 0
            async for msg in client.iter_messages(event.chat_id, limit=50):
                if msg.id == event.id: break
                try: await msg.delete(); count += 1
                except: pass
            return await event.edit(f"🧹 {count} پیام پاک شد.")
            
        if cmd == "#ترجمه" and event.is_reply:
            reply = await event.get_reply_message()
            if reply.raw_text:
                await event.edit("⏳ در حال ترجمه...")
                await event.edit(f"🌐 **ترجمه:**\n{await translate_text(reply.raw_text)}")
            return

        reply = await event.get_reply_message()
        if not reply: return await event.edit("❌ روی یک پیام ریپلای کنید.")

        if cmd == "#react":
            await client(SendReactionRequest(peer=event.chat_id, msg_id=reply.id, reaction=[ReactionEmoji(emoticon="❤️")]))
            await event.delete()
            return
        elif cmd == "#info":
            target = await reply.get_sender()
            await event.edit(f"👤 نام: {target.first_name}\n🆔 آیدی: `{target.id}`\n🔗 یوزرنیم: @{target.username or 'ندارد'}")
            return
        elif cmd == "#pin":
            await client.pin_message(event.chat_id, reply.id)
            await event.edit("📌 پیام پین شد.")
            return
        elif cmd == "#unpin":
            await client.unpin_message(event.chat_id, reply.id)
            await event.edit("📌 پیام آنپین شد.")
            return

        if not event.is_group: return
        target = await reply.get_sender()
        
        if cmd == "بن":
            await client(EditBannedRequest(event.chat_id, target.id, ChatBannedRights(until_date=None, view_messages=True)))
            await event.edit(f"⛔️ {target.first_name} بن شد.")
        elif cmd == "سکوت":
            await client(EditBannedRequest(event.chat_id, target.id, ChatBannedRights(until_date=None, send_messages=True)))
            await event.edit(f"🔇 {target.first_name} سکوت شد.")
        elif cmd == "آزاد":
            await client(EditBannedRequest(event.chat_id, target.id, ChatBannedRights(until_date=None)))
            await event.edit(f"🔊 {target.first_name} آزاد شد.")
        elif cmd == "حذف":
            await reply.delete(); await event.delete()
        elif cmd == "اخطار":
            key = (event.chat_id, target.id)
            user_warns[key] = user_warns.get(key, 0) + 1
            if user_warns[key] >= 3:
                await client(EditBannedRequest(event.chat_id, target.id, ChatBannedRights(until_date=None, view_messages=True)))
                await event.edit(f"⛔️ {target.first_name} با ۳ اخطار بن شد.")
                del user_warns[key]
            else:
                await event.edit(f"⚠️ {target.first_name} اخطار گرفت. ({user_warns[key]}/3)")
    except Exception as e:
        logger.error(f"Mod Error: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# ۸. پنل کنترل از راه دور (فقط برای OWNER_ID)
# ══════════════════════════════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True))
async def remote_control(event):
    text = event.raw_text.strip()
    if not text.startswith("#"): return
    
    try:
        me = await client.get_me()
        if event.chat_id != me.id: return # فقط در Saved Messages
        
        if text == "#away":
            globals()['away_mode'] = True
            await event.edit("🔴 حالت غیبت فعال شد. منشی دری جواب می‌دهد.")
        elif text == "#back":
            globals()['away_mode'] = False
            await event.edit("🟢 حالت غیبت خاموش شد. شما خودتان جواب می‌دهید.")
        elif text == "#status":
            await event.edit(
                f"👑 **وضعیت ربات**\n"
                f"🕒 ساعت: فعال\n"
                f"🤖 حالت غیبت: {'🟢 فعال' if away_mode else '🔴 غیرفعال'}\n"
                f"📝 متن منشی: {secretary_custom_text[:20] + '...' if secretary_custom_text else 'هوش مصنوعی'}"
            )
        elif text.startswith("#set_secretary "):
            globals()['secretary_custom_text'] = text.replace("#set_secretary ", "").strip()
            await event.edit(f"✅ متن منشی تنظیم شد:\n{secretary_custom_text}")
        elif text == "#clear_secretary":
            globals()['secretary_custom_text'] = ""
            await event.edit("✅ متن منشی پاک شد. منشی از هوش مصنوعی دری استفاده می‌کند.")
        elif text.startswith("#schedule "):
            # فرمت: #schedule 10m | @user | متن
            parts = text.replace("#schedule ", "").split("|")
            if len(parts) == 3:
                delay_str, target, msg = parts[0].strip(), parts[1].strip(), parts[2].strip()
                seconds = parse_time(delay_str)
                if seconds:
                    await event.edit(f"⏰ پیام برای {delay_str} دیگر به {target} زمان‌بندی شد.")
                    async def delayed_send():
                        await asyncio.sleep(seconds)
                        await client.send_message(target, msg)
                    asyncio.create_task(delayed_send())
                else:
                    await event.edit("❌ فرمت زمان اشتباه است (مثلاً 10m یا 2h).")
    except Exception as e:
        logger.error(f"Remote Error: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# ۹. حلقه‌های پس‌زمینه (ساعت و تایپ)
# ══════════════════════════════════════════════════════════════════════════════
async def clock_loop():
    while True:
        try:
            now = datetime.now(KABUL_TZ)
            name = f"🕒 {now.strftime('%H:%M')} | {BASE_NAME}"
            await client(UpdateProfileRequest(first_name=name[:64]))
            await client(UpdateStatusRequest(offline=False))
        except Exception as e: logger.error(f"Clock Error: {e}")
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
    logger.info("🔥 Omni-Communication OS v4.0 فعال شد.")
    
    asyncio.create_task(clock_loop())
    asyncio.create_task(typing_loop())
    await client.run_until_disconnected()

if __name__ == "__main__":
    try: client.loop.run_until_complete(main())
    except (KeyboardInterrupt, SystemExit): logger.info("👋 خاموش شد.")
    finally:
        try: client.loop.run_until_complete(client.disconnect())
        except: pass
