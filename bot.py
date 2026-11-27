# ══════════════════════════════════════════════════════════════════════════════
# 🌟 PROJECT OVERMAN - OMNI-SECURITY & COMMUNICATION OS v5.0
# ══════════════════════════════════════════════════════════════════════════════
# تمامی دستورات به زبان دری (فارسی افغانی) - ۲۴/۷ پایدار - هوش مصنوعی دری
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
# ۱. تنظیمات اولیه و لاگ
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
# ۲. حافظه‌ها و تنظیمات سراسری
# ══════════════════════════════════════════════════════════════════════════════
recent_ai_replies = {}       # جلوگیری از اسپم منشی
user_warns = {}              # سیستم اخطار: { (chat_id, user_id): count }
message_cache = {}           # ضد حذف: { (chat_id, msg_id): (sender_id, text) }
ai_history = {}              # حافظه هوش مصنوعی

# تنظیمات منشی و گروه
away_mode = False
secretary_custom_text = ""
group_locks = {}             # قفل گروه‌ها: { chat_id: {"link": True, "badword": True} }
bad_words = ["فحش", "بی‌ادب", "کلمه_ممنوعه"] # کلمات ممنوعه را اینجا اضافه کنید

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
# ۴. هوش مصنوعی دری (Dari AI Secretary)
# ══════════════════════════════════════════════════════════════════════════════
async def ai_reply_dari(user_msg, sender_name, user_id):
    if secretary_custom_text: return secretary_custom_text
        
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
    
    payload = {"model": "openai", "messages": [{"role": "system", "content": sys_prompt}] + ai_history[user_id]}
    try:
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(None, lambda: requests.post(url, json=payload, timeout=15))
        if res.status_code == 200:
            reply = res.json()["choices"][0]["message"]["content"]
            ai_history[user_id].append({"role": "assistant", "content": reply})
            return reply
    except Exception as e: logger.error(f"AI Error: {e}")
    return f"سلام {sender_name} جان، {BASE_NAME} الان دسترسی ندارد. به زودی جواب می‌دهد."

# ══════════════════════════════════════════════════════════════════════════════
# ۵. منشی هوشمند دری + حالت غیبت + خواندن خودکار
# ══════════════════════════════════════════════════════════════════════════════
@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
async def secretary(event):
    global away_mode
    try:
        await client.send_read_acknowledge(event.chat_id) # خواندن خودکار (سین زدن)
        if not away_mode: return
        
        sender = await event.get_sender()
        if sender.bot or sender.id == (await client.get_me()).id: return
        
        now = time.time()
        if sender.id in recent_ai_replies and now - recent_ai_replies[sender.id] < 300: return
        
        reply = await ai_reply_dari(event.raw_text or "[رسانه]", sender.first_name, sender.id)
        await event.reply(reply)
        recent_ai_replies[sender.id] = now
        logger.info(f"🤖 منشی دری پاسخ داد به {sender.first_name}")
    except Exception as e: logger.error(f"Secretary Error: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# ۶. صندوق امانات و ضد حذف پیشرفته
# ══════════════════════════════════════════════════════════════════════════════
@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
async def vault(event):
    try:
        sender = await event.get_sender()
        if sender.id == (await client.get_me()).id: return
        text = event.raw_text or "📷 [رسانه/عکس/ویدیو]"
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
# ۷. سیستم قفل هوشمند گروه (پاکسازی خودکار لینک و کلمات)
# ══════════════════════════════════════════════════════════════════════════════
@client.on(events.NewMessage(incoming=True, func=lambda e: e.is_group))
async def group_locks(event):
    if not event.is_group: return
    chat_id = event.chat_id
    locks = group_locks.get(chat_id, {})
    if not locks: return
    
    try:
        # قفل لینک
        if locks.get("link") and event.raw_text:
            if re.search(r"(https?://|t\.me/|@[a-zA-Z0-9_]+)", event.raw_text):
                await event.delete()
                return
        # قفل کلمات
        if locks.get("badword") and event.raw_text:
            for word in bad_words:
                if word in event.raw_text:
                    await event.delete()
                    return
    except: pass

# ══════════════════════════════════════════════════════════════════════════════
# ۸. دستورات مدیریتی و روتور اصلی (تمام دری)
# ══════════════════════════════════════════════════════════════════════════════
@client.on(events.NewMessage(outgoing=True))
async def command_router(event):
    text = event.raw_text.strip()
    if not text: return
    
    try:
        # ---------- دستورات پنل (فقط در Saved Messages) ----------
        me = await client.get_me()
        if event.chat_id == me.id:
            global away_mode, secretary_custom_text, group_locks
            
            if text == "منشی روشن":
                away_mode = True
                return await event.edit("🟢 منشی روشن شد. (حالت غیبت فعال است)")
            elif text == "منشی خاموش":
                away_mode = False
                return await event.edit("🔴 منشی خاموش شد.")
            elif text.startswith("تنظیم منشی "):
                secretary_custom_text = text.replace("تنظیم منشی ", "").strip()
                return await event.edit(f"✅ متن منشی تنظیم شد:\n{secretary_custom_text}")
            elif text == "حذف منشی":
                secretary_custom_text = ""
                return await event.edit("✅ متن منشی پاک شد. (استفاده از هوش مصنوعی)")
            elif text == "وضعیت":
                return await event.edit(f"👑 **وضعیت ربات**\n\nمنشی: {'🟢 روشن' if away_mode else '🔴 خاموش'}\nمتن منشی: {secretary_custom_text[:20] or 'هوش مصنوعی'}\nپیام‌های کش‌شده: {len(message_cache)}")
            elif text.startswith("ارسال خودکار "):
                # فرمت: ارسال خودکار 10m | @user | متن
                parts = text.replace("ارسال خودکار ", "").split("|")
                if len(parts) == 3:
                    delay_str, target, msg = parts[0].strip(), parts[1].strip(), parts[2].strip()
                    seconds = parse_time(delay_str)
                    if seconds:
                        await event.edit(f"⏰ پیام برای {delay_str} دیگر به {target} زمان‌بندی شد.")
                        async def delayed_send():
                            await asyncio.sleep(seconds)
                            await client.send_message(target, msg)
                        asyncio.create_task(delayed_send())
                    else: await event.edit("❌ فرمت زمان اشتباه است (مثلاً 10m).")
                return

        # ---------- دستورات عمومی (در گروه‌ها و چت‌ها) ----------
        reply = await event.get_reply_message()
        
        if text == "ترجمه" and reply:
            await event.edit("⏳ در حال ترجمه...")
            translated = await translate_text(reply.raw_text or "")
            return await event.edit(f"🌐 **ترجمه:**\n{translated}")
            
        if text == "ری‌اکشن" and reply:
            await client(SendReactionRequest(peer=event.chat_id, msg_id=reply.id, reaction=[ReactionEmoji(emoticon="❤️")]))
            return await event.delete()
            
        if text == "مشخصات" and reply:
            target = await reply.get_sender()
            return await event.edit(f"👤 نام: {target.first_name}\n🆔 آیدی: `{target.id}`\n🔗 یوزرنیم: @{target.username or 'ندارد'}")

        if text == "پین" and reply:
            await client.pin_message(event.chat_id, reply.id)
            return await event.edit("📌 پیام پین شد.")
        if text == "آنپین" and reply:
            await client.unpin_message(event.chat_id, reply.id)
            return await event.edit("📌 پیام آنپین شد.")
            
        if text == "تاس":
            return await event.edit(f"🎲 {random.randint(1,6)}")
        if text == "سکه":
            return await event.edit(f"🪙 {'شیر' if random.choice([True, False]) else 'خط'}")

        # ---------- دستورات گروهی (نیاز به ادمین و ریپلای) ----------
        if not event.is_group: return
        
        # قفل‌ها
        if text == "قفل لینک":
            group_locks.setdefault(event.chat_id, {})["link"] = True
            return await event.edit("🔗 قفل لینک فعال شد.")
        if text == "باز کردن لینک":
            group_locks.setdefault(event.chat_id, {})["link"] = False
            return await event.edit("🔗 قفل لینک غیرفعال شد.")
        if text == "قفل کلمات":
            group_locks.setdefault(event.chat_id, {})["badword"] = True
            return await event.edit("🚫 قفل کلمات ممنوعه فعال شد.")
        if text == "باز کردن کلمات":
            group_locks.setdefault(event.chat_id, {})["badword"] = False
            return await event.edit("🚫 قفل کلمات غیرفعال شد.")
            
        # پاکسازی
        if text == "پاکسازی":
            count = 0
            async for msg in client.iter_messages(event.chat_id, limit=50):
                if msg.id == event.id: break
                try: await msg.delete(); count += 1
                except: pass
            return await event.edit(f"🧹 {count} پیام پاک شد.")

        if not reply: return await event.edit("❌ روی پیام کاربر ریپلای کنید.")
        target = await reply.get_sender()
        
        if text == "بن":
            await client(EditBannedRequest(event.chat_id, target.id, ChatBannedRights(until_date=None, view_messages=True)))
            await event.edit(f"⛔️ {target.first_name} بن شد.")
        elif text == "اخراج":
            await client(EditBannedRequest(event.chat_id, target.id, ChatBannedRights(until_date=None, view_messages=True)))
            await client(EditBannedRequest(event.chat_id, target.id, ChatBannedRights(until_date=None)))
            await event.edit(f"👢 {target.first_name} اخراج شد.")
        elif text == "سکوت":
            await client(EditBannedRequest(event.chat_id, target.id, ChatBannedRights(until_date=None, send_messages=True)))
            await event.edit(f"🔇 {target.first_name} سکوت شد.")
        elif text == "آزاد":
            await client(EditBannedRequest(event.chat_id, target.id, ChatBannedRights(until_date=None)))
            await event.edit(f"🔊 {target.first_name} آزاد شد.")
        elif text == "حذف":
            await reply.delete(); await event.delete()
        elif text == "اخطار":
            key = (event.chat_id, target.id)
            user_warns[key] = user_warns.get(key, 0) + 1
            if user_warns[key] >= 3:
                await client(EditBannedRequest(event.chat_id, target.id, ChatBannedRights(until_date=None, view_messages=True)))
                await event.edit(f"⛔️ {target.first_name} با ۳ اخطار بن شد.")
                del user_warns[key]
            else:
                await event.edit(f"⚠️ {target.first_name} اخطار گرفت. ({user_warns[key]}/3)")
                
    except ChatAdminRequiredError:
        await event.edit("❌ ربات در این گروه ادمین نیست یا دسترسی کافی ندارد.")
    except Exception as e:
        logger.error(f"Command Error: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# ۹. حلقه‌های پس‌زمینه (ساعت و تایپ با مدیریت FloodWait)
# ══════════════════════════════════════════════════════════════════════════════
async def clock_loop():
    while True:
        try:
            now = datetime.now(KABUL_TZ)
            name = f"🕒 {now.strftime('%H:%M')} | {BASE_NAME}"
            await client(UpdateProfileRequest(first_name=name[:64]))
            await client(UpdateStatusRequest(offline=False))
            logger.info(f"⏰ ساعت به‌روز شد: {name}")
        except FloodWaitError as e:
            logger.warning(f"⏳ محدودیت تلگرام: باید {e.seconds} ثانیه صبر کنیم.")
            await asyncio.sleep(e.seconds)
            continue
        except Exception as e: logger.error(f"Clock Error: {e}")
        await asyncio.sleep(60) # هر ۶۰ ثانیه برای جلوگیری از FloodWait

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
# ۱۰. نقطه ورود (Auto-Reconnect)
# ══════════════════════════════════════════════════════════════════════════════
async def main():
    logger.info("🚀 اتصال به تلگرام...")
    while True:
        try:
            await client.connect()
            if await client.is_user_authorized(): break
            else: return
        except Exception as e:
            logger.error(f"اتصال ناموفق: {e}. تلاش مجدد...")
            await asyncio.sleep(10)
            
    me = await client.get_me()
    logger.info(f"✅ متصل شد به: {me.first_name}")
    logger.info("🔥 Omni-Security OS v5.0 فعال شد.")
    
    asyncio.create_task(clock_loop())
    asyncio.create_task(typing_loop())
    await client.run_until_disconnected()

if __name__ == "__main__":
    try: client.loop.run_until_complete(main())
    except (KeyboardInterrupt, SystemExit): logger.info("👋 خاموش شد.")
    finally:
        try: client.loop.run_until_complete(client.disconnect())
        except: pass
