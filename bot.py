# ══════════════════════════════════════════════════════════════════════════════
# 🌟 PROJECT OVERMAN - THE ABSOLUTE MASTERPIECE v8.0 (Enterprise Grade)
# ══════════════════════════════════════════════════════════════════════════════
# @Author: 90-Year-Experience Lead Engineer
# @Architecture: Modular, Fault-Tolerant, Cloud-Synced, AI-Driven
# @Features: Live Clock, 24/7 Online, Smart Typing, Dari AI Secretary,
#            Cloud Database, Advanced Moderator, Anti-Delete, Remote Panel.
# ══════════════════════════════════════════════════════════════════════════════

import os
import sys
import json
import base64
import asyncio
import logging
import time
import re
import random
import traceback
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from functools import wraps
from typing import Optional, Dict, Any, List, Union

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.functions.account import UpdateProfileRequest, UpdateStatusRequest
from telethon.tl.functions.messages import SetTypingRequest, SendReactionRequest
from telethon.tl.types import SendMessageTypingAction, ChatBannedRights, ReactionEmoji
from telethon.tl.functions.channels import EditBannedRequest
from telethon.errors import FloodWaitError, ChatAdminRequiredError, RPCError, AuthKeyDuplicatedError

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1: CONFIGURATION & LOGGING
# ══════════════════════════════════════════════════════════════════════════════

class Config:
    """مدیریت متغیرهای محیطی و تنظیمات اولیه."""
    API_ID: int = int(os.getenv("API_ID", "0"))
    API_HASH: str = os.getenv("API_HASH", "")
    SESSION_STRING: str = os.getenv("SESSION_STRING", "")
    BASE_NAME: str = os.getenv("BASE_NAME", "Master")
    OWNER_ID: int = int(os.getenv("OWNER_ID", "0"))
    GH_PAT: str = os.getenv("GH_PAT", "")
    GH_REPO: str = os.getenv("GITHUB_REPOSITORY", "")
    KABUL_TZ: ZoneInfo = ZoneInfo("Asia/Kabul")

    @classmethod
    def validate(cls) -> bool:
        """بررسی صحت متغیرهای حیاتی."""
        if not cls.API_ID or not cls.API_HASH or not cls.SESSION_STRING:
            return False
        return True

class LoggerManager:
    """مدیریت لاگ‌های سیستم برای رصد دقیق در گیت‌هاب."""
    @staticmethod
    def setup() -> logging.Logger:
        logging.basicConfig(
            format="%(asctime)s | %(levelname)-8s | %(message)s",
            level=logging.INFO,
        )
        return logging.getLogger("OvermanMasterpiece")

logger = LoggerManager.setup()

if not Config.validate():
    logger.critical("❌ متغیرهای محیطی (API_ID, API_HASH, SESSION_STRING) یافت نشدند.")
    sys.exit(1)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2: CLOUD DATABASE (GITHUB SYNC)
# ══════════════════════════════════════════════════════════════════════════════

class GitHubDB:
    """
    پایگاه داده ابری برای ذخیره‌سازی اطلاعات به صورت دائمی در گیت‌هاب.
    از پاک شدن اطلاعات با ری‌استارت شدن سرورهای Actions جلوگیری می‌کند.
    """
    def __init__(self, token: str, repo: str):
        self.token = token
        self.repo = repo
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.sha: Optional[str] = None
        self.data: Dict[str, Any] = self._load()
        self.lock = asyncio.Lock()

    def _load(self) -> Dict[str, Any]:
        """بارگذاری اطلاعات از فایل db.json در گیت‌هاب."""
        if not self.token or not self.repo:
            return self._default_schema()
        try:
            url = f"https://api.github.com/repos/{self.repo}/contents/db.json"
            res = requests.get(url, headers=self.headers, timeout=15)
            if res.status_code == 200:
                self.sha = res.json()["sha"]
                content = base64.b64decode(res.json()["content"]).decode("utf-8")
                return json.loads(content)
        except Exception as e:
            logger.error(f"خطا در خواندن دیتابیس: {e}")
        return self._default_schema()

    def _default_schema(self) -> Dict[str, Any]:
        """ساختار پیش‌فرض دیتابیس."""
        return {
            "settings": {"away_mode": True, "custom_secretary_text": ""},
            "groups": {},  # { "chat_id": {"lock_link": False, "lock_badwords": False} }
            "warns": {}    # { "chat_id_user_id": count }
        }

    async def save(self) -> None:
        """ذخیره تغییرات در گیت‌هاب با قفل ضد تداخل."""
        if not self.token or not self.repo: return
        async with self.lock:
            try:
                url = f"https://api.github.com/repos/{self.repo}/contents/db.json"
                content_encoded = base64.b64encode(
                    json.dumps(self.data, ensure_ascii=False, indent=2).encode("utf-8")
                ).decode("utf-8")
                
                payload = {"message": "Auto-update DB", "content": content_encoded}
                if self.sha: payload["sha"] = self.sha

                loop = asyncio.get_event_loop()
                res = await loop.run_in_executor(
                    None, lambda: requests.put(url, headers=self.headers, json=payload, timeout=15)
                )
                if res.status_code in (200, 201):
                    self.sha = res.json()["content"]["sha"]
            except Exception as e:
                logger.error(f"خطا در ذخیره دیتابیس: {e}")

# مقداردهی اولیه دیتابیس
db = GitHubDB(Config.GH_PAT, Config.GH_REPO)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3: TELEGRAM CLIENT & STATE MANAGEMENT
# ══════════════════════════════════════════════════════════════════════════════

class BotState:
    """مدیریت وضعیت‌های موقت در حافظه (Cache)."""
    recent_ai_replies: Dict[int, float] = {}
    message_cache: Dict[tuple, tuple] = {}
    ai_history: Dict[int, List[Dict]] = {}
    bad_words: List[str] = ["فحش", "بی‌ادب", "کلمه_ممنوعه"]

client = TelegramClient(StringSession(Config.SESSION_STRING), Config.API_ID, Config.API_HASH, connection_retries=None)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4: HELPER FUNCTIONS & DECORATORS
# ══════════════════════════════════════════════════════════════════════════════

def parse_time(time_str: str) -> Optional[int]:
    """تبدیل فرمت‌هایی مانند 10m یا 2h به ثانیه."""
    match = re.match(r"^(\d+)([mhd])$", time_str.lower())
    if not match: return None
    val, unit = int(match.group(1)), match.group(2)
    return val * {'m': 60, 'h': 3600, 'd': 86400}[unit]

async def report_error(error_msg: str) -> None:
    """ارسال خطاهای بحرانی به Saved Messages مالک."""
    try:
        await client.send_message("me", f"🚨 **خطای سیستم:**\n\n`{error_msg}`")
    except: pass

def safe_divide(a: float, b: float) -> float:
    """جلوگیری از خطای تقسیم بر صفر."""
    return a / b if b else 0

async def translate_text(text: str, target: str = "fa") -> str:
    """ترجمه متن با استفاده از API گوگل."""
    try:
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl={target}&dt=t&q={requests.utils.quote(text)}"
        loop = asyncio.get_event_loop()
        res = await loop.run_in_executor(None, lambda: requests.get(url, timeout=10))
        if res.status_code == 200:
            return "".join([part[0] for part in res.json()[0]])
    except Exception as e:
        logger.error(f"Translate Error: {e}")
    return "❌ خطا در ترجمه."

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5: AI ENGINE (DARI SECRETARY)
# ══════════════════════════════════════════════════════════════════════════════

class AIEngine:
    """موتور هوش مصنوعی اختصاصی برای پاسخگویی به زبان دری."""
    
    @staticmethod
    async def get_dari_reply(user_msg: str, sender_name: str, user_id: int) -> str:
        custom_text = db.data["settings"].get("custom_secretary_text", "")
        if custom_text:
            return custom_text

        url = "https://text.pollinations.ai/openai"
        
        if user_id not in BotState.ai_history: 
            BotState.ai_history[user_id] = []
        
        BotState.ai_history[user_id].append({"role": "user", "content": user_msg})
        if len(BotState.ai_history[user_id]) > 4: 
            BotState.ai_history[user_id].pop(0)

        sys_prompt = (
            f"You are the personal AI secretary of {Config.BASE_NAME}. "
            f"The user '{sender_name}' sent a message. "
            f"Reply STRICTLY AND ONLY in Dari (Afghan Persian/Farsi). "
            f"Tell them politely that {Config.BASE_NAME} is currently away and will reply soon. "
            f"Keep it short (max 2 sentences)."
        )
        
        payload = {
            "model": "openai",
            "messages": [{"role": "system", "content": sys_prompt}] + BotState.ai_history[user_id]
        }
        
        try:
            loop = asyncio.get_event_loop()
            res = await loop.run_in_executor(None, lambda: requests.post(url, json=payload, timeout=15))
            if res.status_code == 200:
                reply = res.json()["choices"][0]["message"]["content"]
                BotState.ai_history[user_id].append({"role": "assistant", "content": reply})
                return reply
        except Exception as e:
            logger.error(f"AI Engine Error: {e}")
            
        return f"سلام {sender_name} جان، {Config.BASE_NAME} الان دسترسی ندارد. به زودی جواب می‌دهد."

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6: INCOMING EVENT HANDLERS
# ══════════════════════════════════════════════════════════════════════════════

class IncomingHandlers:
    """مدیریت تمام رویدادهای دریافتی (پیام‌ها، حذف‌ها و...)."""

    @staticmethod
    @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
    async def secretary_handler(event):
        """مدیریت منشی هوشمند دری (پاسخ به همه، حتی ناشناس‌ها)."""
        try:
            await client.send_read_acknowledge(event.chat_id) # خواندن خودکار
            if not db.data["settings"].get("away_mode", True): return
            
            sender = await event.get_sender()
            if sender.bot or sender.id == (await client.get_me()).id: return
            
            now = time.time()
            if sender.id in BotState.recent_ai_replies and now - BotState.recent_ai_replies[sender.id] < 120: 
                return # کول‌داون ۲ دقیقه‌ای
            
            reply = await AIEngine.get_dari_reply(event.raw_text or "[رسانه]", sender.first_name, sender.id)
            
            # ارسال پیام مستقیماً به آی‌دی کاربر (حتی اگر در Message Requests باشد)
            await client.send_message(sender.id, reply)
            BotState.recent_ai_replies[sender.id] = now
            logger.info(f"🤖 منشی پاسخ داد به {sender.first_name}")
        except Exception as e:
            await report_error(f"خطا در منشی: {traceback.format_exc()}")

    @staticmethod
    @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
    async def vault_handler(event):
        """ذخیره پیام‌های خصوصی در Saved Messages (صندوق امانات)."""
        try:
            sender = await event.get_sender()
            if sender.id == (await client.get_me()).id: return
            text = event.raw_text or "📷 [رسانه]"
            ts = datetime.now(Config.KABUL_TZ).strftime("%Y-%m-%d %H:%M")
            await client.send_message("me", f"📩 **صندوق امانات**\n👤 از: {sender.first_name} (`{sender.id}`)\n⏰ {ts}\n\n{text}")
        except: pass

    @staticmethod
    @client.on(events.NewMessage(incoming=True))
    async def cache_handler(event):
        """کش کردن پیام‌ها برای سیستم ضد حذف (Black Box)."""
        try:
            if event.raw_text:
                BotState.message_cache[(event.chat_id, event.message.id)] = (event.sender_id, event.raw_text)
                if len(BotState.message_cache) > 2000: 
                    BotState.message_cache.pop(next(iter(BotState.message_cache)))
        except: pass

    @staticmethod
    @client.on(events.MessageDeleted)
    async def anti_delete_handler(event):
        """ارسال پیام‌های حذف‌شده به Saved Messages."""
        try:
            for msg_id in event.deleted_ids:
                key = (event.chat_id, msg_id)
                if key in BotState.message_cache:
                    sender_id, text = BotState.message_cache.pop(key)
                    await client.send_message("me", f"🚨 **پیام حذف‌شده**\n👤 فرستنده: `{sender_id}`\n📝 متن: {text}")
        except: pass

    @staticmethod
    @client.on(events.NewMessage(incoming=True, func=lambda e: e.is_group))
    async def group_security_handler(event):
        """مدیریت قفل‌های گروه (لینک و کلمات ممنوعه)."""
        try:
            chat_id_str = str(event.chat_id)
            locks = db.data["groups"].get(chat_id_str, {})
            if not locks: return
            
            if locks.get("lock_link") and event.raw_text:
                if re.search(r"(https?://|t\.me/|@[a-zA-Z0-9_]+)", event.raw_text):
                    await event.delete()
                    return
            
            if locks.get("lock_badwords") and event.raw_text:
                for word in BotState.bad_words:
                    if word in event.raw_text:
                        await event.delete()
                        return
        except: pass

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 7: OUTGOING EVENT HANDLERS (COMMANDS)
# ══════════════════════════════════════════════════════════════════════════════

class CommandHandlers:
    """مدیریت دستورات ارسالی توسط مالک."""

    @staticmethod
    @client.on(events.NewMessage(outgoing=True))
    async def remote_control(event):
        """پنل کنترل از راه دور در Saved Messages."""
        text = event.raw_text.strip()
        if not text: return
        
        try:
            me = await client.get_me()
            if event.chat_id != me.id: return # فقط در Saved Messages
            
            if text == "منشی روشن":
                db.data["settings"]["away_mode"] = True
                await db.save()
                return await event.edit("🟢 منشی روشن شد.")
            elif text == "منشی خاموش":
                db.data["settings"]["away_mode"] = False
                await db.save()
                return await event.edit("🔴 منشی خاموش شد.")
            elif text.startswith("تنظیم منشی "):
                db.data["settings"]["custom_secretary_text"] = text.replace("تنظیم منشی ", "").strip()
                await db.save()
                return await event.edit(f"✅ متن منشی تنظیم شد.")
            elif text == "حذف منشی":
                db.data["settings"]["custom_secretary_text"] = ""
                await db.save()
                return await event.edit("✅ متن منشی پاک شد. (استفاده از هوش مصنوعی)")
            elif text == "وضعیت":
                await event.edit(f"👑 **وضعیت سیستم**\n\nمنشی: {'🟢 روشن' if db.data['settings']['away_mode'] else '🔴 خاموش'}\nمخاطبین کش‌شده: {len(BotState.message_cache)}")
            elif text.startswith("ارسال خودکار "):
                # فرمت: ارسال خودکار 10m | @user | متن
                parts = text.replace("ارسال خودکار ", "").split("|")
                if len(parts) == 3:
                    delay_str, target, msg = parts[0].strip(), parts[1].strip(), parts[2].strip()
                    seconds = parse_time(delay_str)
                    if seconds:
                        await event.edit(f"⏰ زمان‌بندی شد.")
                        async def delayed_send():
                            await asyncio.sleep(seconds)
                            await client.send_message(target, msg)
                        asyncio.create_task(delayed_send())
                return
        except Exception as e:
            await report_error(f"خطا در پنل کنترل: {traceback.format_exc()}")

    @staticmethod
    @client.on(events.NewMessage(outgoing=True, pattern=r"^(بن|اخراج|سکوت|آزاد|اخطار|حذف|پاکسازی|قفل لینک|باز کردن لینک|قفل کلمات|باز کردن کلمات|ترجمه|مشخصات|ری‌اکشن|پین|آنپین|تاس|سکه)$"))
    async def moderator(event):
        """دستورات مدیریتی گروه و ابزارهای عمومی."""
        cmd = event.pattern_match.group(1)
        
        try:
            # دستورات عمومی
            if cmd in ["تاس", "سکه"]:
                res = random.randint(1, 6) if cmd == "تاس" else random.choice(["شیر", "خط"])
                return await event.edit(f"{'🎲' if cmd == 'تاس' else '🪙'} {res}")

            reply = await event.get_reply_message()
            
            if cmd == "ترجمه" and reply:
                await event.edit("⏳ در حال ترجمه...")
                return await event.edit(f"🌐 **ترجمه:**\n{await translate_text(reply.raw_text or '')}")
                
            if cmd == "مشخصات" and reply:
                target = await reply.get_sender()
                return await event.edit(f"👤 نام: {target.first_name}\n🆔 آیدی: `{target.id}`\n🔗 یوزرنیم: @{target.username or 'ندارد'}")

            if cmd == "ری‌اکشن" and reply:
                await client(SendReactionRequest(peer=event.chat_id, msg_id=reply.id, reaction=[ReactionEmoji(emoticon="❤️")]))
                return await event.delete()
                
            if cmd == "پین" and reply:
                await client.pin_message(event.chat_id, reply.id)
                return await event.edit("📌 پیام پین شد.")
            if cmd == "آنپین" and reply:
                await client.unpin_message(event.chat_id, reply.id)
                return await event.edit("📌 پیام آنپین شد.")

            # دستورات گروهی
            if not event.is_group: return
            chat_id_str = str(event.chat_id)
            
            if cmd.startswith("قفل") or cmd.startswith("باز"):
                db.data["groups"].setdefault(chat_id_str, {})
                if cmd == "قفل لینک": db.data["groups"][chat_id_str]["lock_link"] = True
                if cmd == "باز کردن لینک": db.data["groups"][chat_id_str]["lock_link"] = False
                if cmd == "قفل کلمات": db.data["groups"][chat_id_str]["lock_badwords"] = True
                if cmd == "باز کردن کلمات": db.data["groups"][chat_id_str]["lock_badwords"] = False
                await db.save()
                return await event.edit(f"✅ تنظیمات گروه به‌روز شد: {cmd}")

            if cmd == "پاکسازی":
                count = 0
                async for msg in client.iter_messages(event.chat_id, limit=50):
                    if msg.id == event.id: break
                    try: await msg.delete(); count += 1
                    except: pass
                return await event.edit(f"🧹 {count} پیام پاک شد.")

            if not reply: return await event.edit("❌ روی پیام کاربر ریپلای کنید.")
            target = await reply.get_sender()
            
            if cmd == "بن":
                await client(EditBannedRequest(event.chat_id, target.id, ChatBannedRights(until_date=None, view_messages=True)))
                await event.edit(f"⛔️ {target.first_name} بن شد.")
            elif cmd == "اخراج":
                await client(EditBannedRequest(event.chat_id, target.id, ChatBannedRights(until_date=None, view_messages=True)))
                await client(EditBannedRequest(event.chat_id, target.id, ChatBannedRights(until_date=None)))
                await event.edit(f"👢 {target.first_name} اخراج شد.")
            elif cmd == "سکوت":
                await client(EditBannedRequest(event.chat_id, target.id, ChatBannedRights(until_date=None, send_messages=True)))
                await event.edit(f"🔇 {target.first_name} سکوت شد.")
            elif cmd == "آزاد":
                await client(EditBannedRequest(event.chat_id, target.id, ChatBannedRights(until_date=None)))
                await event.edit(f"🔊 {target.first_name} آزاد شد.")
            elif cmd == "حذف":
                await reply.delete(); await event.delete()
            elif cmd == "اخطار":
                key = f"{event.chat_id}_{target.id}"
                warns = db.data["warns"].get(key, 0) + 1
                if warns >= 3:
                    await client(EditBannedRequest(event.chat_id, target.id, ChatBannedRights(until_date=None, view_messages=True)))
                    await event.edit(f"⛔️ {target.first_name} با ۳ اخطار بن شد.")
                    del db.data["warns"][key]
                else:
                    db.data["warns"][key] = warns
                    await event.edit(f"⚠️ {target.first_name} اخطار گرفت. ({warns}/3)")
                await db.save()
                
        except ChatAdminRequiredError:
            await event.edit("❌ ربات در این گروه ادمین نیست.")
        except Exception as e:
            await report_error(f"خطا در مدیریت گروه: {traceback.format_exc()}")

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 8: BACKGROUND LOOPS (CLOCK & TYPING)
# ══════════════════════════════════════════════════════════════════════════════

class BackgroundTasks:
    """حلقه‌های پس‌زمینه برای ساعت زنده و تایپ مداوم."""

    @staticmethod
    async def clock_loop():
        """آپدیت ساعت کابل و وضعیت آنلاین (با مدیریت FloodWait)."""
        while True:
            try:
                now = datetime.now(Config.KABUL_TZ)
                name = f"🕒 {now.strftime('%H:%M')} | {Config.BASE_NAME}"
                await client(UpdateProfileRequest(first_name=name[:64]))
                await client(UpdateStatusRequest(offline=False))
                logger.info(f"⏰ ساعت به‌روز شد: {name}")
            except FloodWaitError as e:
                logger.warning(f"⏳ محدودیت تلگرام: {e.seconds} ثانیه صبر می‌کنیم.")
                await asyncio.sleep(e.seconds)
                continue
            except Exception as e:
                logger.error(f"Clock Error: {e}")
            await asyncio.sleep(60) # هر ۶۰ ثانیه

    @staticmethod
    async def typing_loop():
        """ارسال مداوم سیگنال تایپ کردن."""
        peer = None
        while True:
            try:
                if peer is None:
                    dialogs = await client.get_dialogs(limit=1)
                    peer = dialogs[0].entity if dialogs else await client.get_me()
                await client(SetTypingRequest(peer=peer, action=SendMessageTypingAction()))
            except: 
                peer = None
            await asyncio.sleep(5)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 9: APPLICATION ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

async def main():
    """نقطه ورود اصلی برنامه با مکانیزم اتصال مجدد."""
    logger.info("🚀 شروع فرآیند راه‌اندازی...")
    
    while True:
        try:
            await client.connect()
            if await client.is_user_authorized():
                break
            else:
                logger.critical("❌ سشن نامعتبر است.")
                return
        except Exception as e:
            logger.error(f"اتصال ناموفق: {e}. تلاش مجدد در ۱۰ ثانیه...")
            await asyncio.sleep(10)

    me = await client.get_me()
    logger.info(f"✅ متصل شد به: {me.first_name}")
    logger.info("🔥 The Absolute Masterpiece v8.0 فعال شد.")
    
    # اجرای همزمان تسک‌های پس‌زمینه
    asyncio.create_task(BackgroundTasks.clock_loop())
    asyncio.create_task(BackgroundTasks.typing_loop())
    
    await client.run_until_disconnected()

if __name__ == "__main__":
    try:
        client.loop.run_until_complete(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("👋 خاموش شد.")
    except AuthKeyDuplicatedError:
        logger.critical("❌ خطای سشن تکراری (AuthKeyDuplicated). لطفاً SESSION_STRING را آپدیت کنید.")
    finally:
        try: client.loop.run_until_complete(client.disconnect())
        except: pass
