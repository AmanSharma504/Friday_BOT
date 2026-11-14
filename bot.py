import os
import sys
import json
import logging
import asyncio
import re
from pathlib import Path

import telegram.error
import io
from telegram import (
    Update,
    InputFile,
    constants,
    ChatPermissions,
    ChatMemberAdministrator,
    ChatMemberOwner,
)
from telegram.request import HTTPXRequest
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ChatMemberHandler,
    ContextTypes,
    filters,
)

from config import (
    BASE_DIR,
    TELEGRAM_BOT_TOKEN,
    GEMINI_API_KEY,
    TEMP_AUDIO_DIR,
    CARTESIA_VOICE_ID,
    BOT_OWNER_ID,
    validate_config,
)
from ai_agent import FridayAgent
from voice_engine import text_to_speech, text_to_speech_bytes
from media_engine import (
    generate_ai_image,
    generate_ai_video,
    generate_ai_logo,
    generate_ai_emoji,
    generate_stylish_fonts,
)
from memory_engine import memory_engine
from web_dashboard import FridayWebDashboard

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("FridayBot")

# Global instances
agent = None
user_voices = {}
group_paused = {}  # chat_id -> bool
active_tags = {}   # chat_id -> bool (to stop /tagall)

# Persistent Chat, Member & Owner Database
CHATS_FILE = BASE_DIR / "registered_chats.json"

def load_registered_chats() -> dict:
    if CHATS_FILE.exists():
        try:
            with open(CHATS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                data.setdefault("owner_id", BOT_OWNER_ID or None)
                data.setdefault("groups", {})
                data.setdefault("channels", {})
                data.setdefault("users", {})
                data.setdefault("group_members", {})
                data.setdefault("banned_users", {})
                return data
        except Exception as e:
            logger.warning(f"Failed to read registered_chats.json: {e}")
    return {
        "owner_id": BOT_OWNER_ID or None,
        "groups": {},
        "channels": {},
        "users": {},
        "group_members": {},
        "banned_users": {},
    }

def save_registered_chats(data: dict):
    try:
        with open(CHATS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Failed to save registered_chats.json: {e}")

def register_chat(chat, user=None):
    """Silently registers any DM, group, channel, and tracks group members."""
    if not chat:
        return
    data = load_registered_chats()
    cid = str(chat.id)
    changed = False

    if chat.type in [constants.ChatType.GROUP, constants.ChatType.SUPERGROUP]:
        if cid not in data["groups"] or data["groups"][cid].get("title") != chat.title:
            data["groups"][cid] = {"title": chat.title or "Group"}
            changed = True
        if user and not user.is_bot:
            members = data.setdefault("group_members", {}).setdefault(cid, {})
            uid = str(user.id)
            if uid not in members or members[uid].get("name") != user.first_name:
                members[uid] = {
                    "name": user.first_name or "Member",
                    "username": user.username or "",
                }
                changed = True
    elif chat.type == constants.ChatType.CHANNEL:
        channels = data.setdefault("channels", {})
        if cid not in channels or channels[cid].get("title") != chat.title:
            channels[cid] = {"title": chat.title or "Channel"}
            changed = True
    elif chat.type == constants.ChatType.PRIVATE:
        if cid not in data["users"]:
            data["users"][cid] = {
                "name": user.first_name if user else "User",
                "username": user.username if user else "",
            }
            changed = True

    if changed:
        save_registered_chats(data)

def is_bot_owner(user_id: int) -> bool:
    """Strictly checks if user is the Bot Owner."""
    data = load_registered_chats()
    owner = data.get("owner_id") or BOT_OWNER_ID
    if not owner:
        return False
    return str(user_id) == str(owner)

# Available voices: Cartesia AI High-Fidelity Ultra-Natural Voices (Male & Female)
AVAILABLE_VOICES = {
    "friday_001": {
        "id": "e6b71342-48f1-4c70-a13a-d197b176ff24",
        "desc": "FRIDAY 001 (Refined Pure Conversational Indian Female, Crystal-Clear)",
        "gender": "Female",
    },
    "jacqueline": {
        "id": "9626c31c-bec5-4cca-baa8-f8ba9e84c8bc",
        "desc": "Jacqueline (Warm, Expressive & Tactically Composed, Default)",
        "gender": "Female",
    },
    "kavya": {
        "id": "ce45ddca-5f4b-4047-ada3-3fce2bc78acd",
        "desc": "Kavya (Crisp & High-Intellect Indian Female)",
        "gender": "Female",
    },
    "siya": {
        "id": "4459a9a5-69d6-4680-b970-e13dc51845b6",
        "desc": "Siya (100% Native Everyday Conversational Female)",
        "gender": "Female",
    },
    "ananya": {
        "id": "ffa0d297-8cf9-4ec9-8e4e-99a59e939b02",
        "desc": "Ananya (Smooth, Polished Professional Female)",
        "gender": "Female",
    },
    "kaira": {
        "id": "bc4324cb-08c4-4869-8fed-58436d02fdc2",
        "desc": "Kaira (Warm Operational Specialist Female)",
        "gender": "Female",
    },
    "varun": {
        "id": "4cd9f881-58f7-4969-876a-00983214c362",
        "desc": "Varun (Tactical, Razor-Sharp Indian Male — J.A.R.V.I.S. Style)",
        "gender": "Male",
    },
    "sagar": {
        "id": "6303e5fb-a0a7-48f9-bb1a-dd42c216dc5d",
        "desc": "Sagar (100% Native Real Indian Everyday Male)",
        "gender": "Male",
    },
    "aryan": {
        "id": "9bde82b6-70e6-4df6-b964-e897cc526b2b",
        "desc": "Aryan (Deep, Composed Executive Male)",
        "gender": "Male",
    },
    "soham": {
        "id": "b5fbb8ab-ef8c-4b92-b040-31b5ec2ec2e9",
        "desc": "Soham (Friendly & Crisp Indian Male)",
        "gender": "Male",
    },
    "rohan": {
        "id": "4877b818-c7fe-4c89-b1cf-eadf8e23da72",
        "desc": "Rohan (Calm & Confident Indian Male)",
        "gender": "Male",
    },
}

# Aliases for quick selection
VOICE_ALIASES = {
    "001": "friday_001",
    "friday001": "friday_001",
    "friday 001": "friday_001",
    "female": "friday_001",
    "ladki": "friday_001",
    "women": "friday_001",
    "girl": "friday_001",
    "male": "varun",
    "ladka": "varun",
    "men": "varun",
    "boy": "varun",
    "jarvis": "varun",
}

async def is_admin(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Checks if a user is an admin or creator of the chat."""
    try:
        member = await context.bot.get_chat_member(chat_id, user_id)
        return isinstance(member, (ChatMemberAdministrator, ChatMemberOwner))
    except Exception:
        return False

async def keep_chat_action(bot, chat_id, action, stop_event: asyncio.Event):
    """Continuously sends chat action every 4 seconds until stop_event is set."""
    while not stop_event.is_set():
        try:
            await bot.send_chat_action(chat_id=chat_id, action=action)
        except Exception:
            pass
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=4.0)
        except asyncio.TimeoutError:
            pass

# ==================== BASIC COMMANDS ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    register_chat(chat, user)

    first_name = user.first_name if user else "Friend"
    greeting = (
        f"👋 नमस्ते {first_name}! मैं **Friday** हूँ — आपकी पर्सनल AI असिस्टेंट।\n\n"
        f"⚡ **सुपर-फास्ट मुख्य फीचर्स:**\n"
        f"• ✍️ **टेक्स्ट बातचीत:** कोई भी सवाल पूछें, काम का सवाल हो या आम बातचीत, तुरंत सटीक जवाब मिलेगा।\n"
        f"• 🎙️ **वॉइस नोट्स:** वॉइस नोट भेजें, मैं सुनकर 100% मानवीय आवाज़ में बोलकर जवाब दूंगी।\n"
        f"• 🗣️ **सभी भारतीय भाषाएं:** हिंदी, पंजाबी, हरियाणवी, भोजपुरी, मराठी, तेलुगु, गुजराती व इंग्लिश में सहज बातचीत।\n"
        f"• 🎨 **AI इमेज जनरेशन:** `/image <प्रॉम्प्ट>` से कोई भी 8K फोटो या आर्टवर्क जनरेट करें।\n"
        f"• 🎬 **AI वीडियो क्लिप्स:** `/video <प्रॉम्प्ट>` से सिनेमैटिक वीडियो क्लिप्स बनाएं (अधिकतम 2 मिनट)।\n"
        f"• 🏷️ **लोगो मेकर:** `/logo <नाम/ब्रांड>` से 3D आधुनिक लोगो बनाएं।\n"
        f"• 😃 **3D इमोजी मेकर:** `/emoji <आइडिया>` से कस्टम इमोजी और स्टिकर्स बनाएं।\n"
        f"• ✨ **स्टाइलिश फॉन्ट्स:** `/font <नाम या टेक्स्ट>` से 8+ फैंसी फॉन्ट स्टाइल्स बनाएं।\n"
        f"• 👥 **ग्रुप चैट्स:** ग्रुप में मुझे जोड़ें और बेझिझक बात करें।\n\n"
        f"🛡️ *सभी जेनरेटेड मीडिया पर सुरक्षा हेतु Friday AI का वॉटरमार्क रहता है।*\n"
        f"💡 सभी कमांड्स देखने के लिए `/help` टाइप करें।"
    )
    await update.message.reply_text(greeting, parse_mode=constants.ParseMode.MARKDOWN)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat = update.effective_chat
    register_chat(chat, user)

    help_text = (
        "ℹ️ **Friday AI Commands Guide:**\n\n"
        "💬 **सामान्य & वॉइस:**\n"
        "• `/voice` - Friday की आवाज़ बदलें (Jacqueline, Siya, Sagar, Neha)\n"
        "• `/reset` - पिछली बातचीत की याददाश्त रीसेट करें\n"
        "• 🎙️ **वॉइस नोट्स:** किसी भी भाषा (हिंदी, पंजाबी, हरियाणवी आदि) में वॉइस नोट भेजें, मैं बोलकर जवाब दूंगी।\n\n"
        "🎨 **क्रिएटिव & मीडिया टूल्स (New):**\n"
        "• `/image <प्रॉम्प्ट>` - 8K AI फोटो जनरेट करें\n"
        "• `/video <प्रॉम्प्ट>` - AI वीडियो क्लिप्स बनाएं (अधिकतम 2 मिनट)\n"
        "• `/logo <नाम>` - आधुनिक 3D ब्रांड लोगो बनाएं\n"
        "• `/emoji <आइडिया>` - कस्टम 3D इमोजी व स्टिकर बनाएं\n"
        "• `/font <टेक्स्ट>` - नाम को 8+ स्टाइलिश फॉन्ट्स में बदलें\n"
    )

    if chat and chat.type in [constants.ChatType.GROUP, constants.ChatType.SUPERGROUP]:
        is_adm = await is_admin(chat.id, user.id, context) if user else False
        if is_adm or (user and is_bot_owner(user.id)):
            help_text += (
                "\n👥 **ग्रुप एडमिन & मॉडरेशन टूल्स:**\n"
                "• `/admin` या `/promote` - सदस्य को एडमिन बनाएं\n"
                "• `/demote` - एडमिन अधिकार हटाएं\n"
                "• `/muteall` / `/unmuteall` - पूरे ग्रुप को म्यूट / अनम्यूट करें\n"
                "• `/banall` / `/unbanall` - पूरे ग्रुप को बैन / अनबैन करें\n"
                "• `/clear` या `/purge [संख्या]` - चैट के मैसेज साफ़ करें\n"
                "• `/tagall [मैसेज]` - ग्रुप मेंबर्स को मेंशन करें\n"
                "• `/stoptag` - टैगिंग रोकें\n"
                "• `/ban` / `/unban` - व्यक्तिगत बैन/अनबैन करें\n"
                "• `/mute` / `/unmute` - व्यक्तिगत म्यूट/अनम्यूट करें\n"
                "• `/pause` / `/resume` - ग्रुप में AI को रोकें या चालू करें\n"
            )

    if user and is_bot_owner(user.id):
        help_text += (
            "\n👑 **बोट ओनर टूल्स:**\n"
            "• `/broadcast <मैसेज>` - सभी ग्रुप्स, चैनल्स और पर्सनल DMs में ब्रॉडकास्ट\n"
            "• `/broadcast_groups <मैसेज>` - केवल सभी ग्रुप्स में ब्रॉडकास्ट\n"
            "• `/broadcast_channels <मैसेज>` - केवल सभी चैनल्स में ब्रॉडकास्ट\n"
            "• `/broadcast_users <मैसेज>` - केवल पर्सनल DMs में ब्रॉडकास्ट\n"
            "• `/stats` - कुल रजिस्टर्ड चैट्स, ग्रुप्स और चैनल्स देखें\n"
            "• `/transferowner <ID>` - ओनरशिप ट्रांसफर करें\n"
        )

    await update.message.reply_text(help_text, parse_mode=constants.ParseMode.MARKDOWN)

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if agent:
        agent.reset_chat(chat_id)
    await update.message.reply_text("🔄 मेमोरी रीसेट हो गई है! अब नए सिरे से बात कर सकते हैं।")

async def voice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    args = context.args

    if not args:
        current = user_voices.get(chat_id, CARTESIA_VOICE_ID or "friday_001")
        # Categorize
        females = [f"• `/voice {k}` — {v['desc']}" for k, v in AVAILABLE_VOICES.items() if v.get("gender") == "Female"]
        males = [f"• `/voice {k}` — {v['desc']}" for k, v in AVAILABLE_VOICES.items() if v.get("gender") == "Male"]

        msg = (
            f"🎙️ **F.R.I.D.A.Y. Voice Engine (Pristine High-Fidelity Neural Speech)**\n\n"
            f"✨ **वर्तमान आवाज़:** `{current}`\n\n"
            f"👩 **Female Voice Models:**\n" + "\n".join(females) + "\n\n"
            f"👨 **Male Voice Models:**\n" + "\n".join(males) + "\n\n"
            f"⚡ **त्वरित स्विचिंग:**\n"
            f"• `/voice female` या `/voice 001` — शुद्ध व रिफाइंड फीमेल वॉइस\n"
            f"• `/voice male` या `/voice jarvis` — शार्प व टैक्टिकल मेल वॉइस\n"
            f"💡 *आप बोलकर या वॉइस नोट में भी 'मेल की आवाज़ में बोलो' या 'फीमेल की आवाज़ में बोलो' कह सकते हैं!*"
        )
        await update.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)
        return

    raw_choice = " ".join(args).lower().strip()
    choice = VOICE_ALIASES.get(raw_choice, raw_choice)

    if choice in AVAILABLE_VOICES:
        selected_id = AVAILABLE_VOICES[choice]["id"]
        user_voices[chat_id] = selected_id
        await update.message.reply_text(
            f"✅ **Voice Profile Updated Successfully!**\n"
            f"🎙️ **सक्रिय आवाज़:** {AVAILABLE_VOICES[choice]['desc']}\n"
            f"अब Friday आपसे इसी रिफाइंड आवाज़ में संवाद करेगी।",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
    else:
        valid = ", ".join(list(AVAILABLE_VOICES.keys()) + ["male", "female", "001"])
        await update.message.reply_text(f"❌ अमान्य विकल्प। कृपया इनमें से चुनें:\n`{valid}`")

# ==================== COGNITIVE & PREFERENCE COMMANDS (TIMEZONE, LANGUAGE, CLOCK, DASHBOARD) ====================

async def time_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Returns accurate real-time clock according to user's configured timezone."""
    chat = update.effective_chat
    user = update.effective_user
    register_chat(chat, user)
    time_str = memory_engine.get_current_time_str(chat.id)
    await update.message.reply_text(f"🕒 **F.R.I.D.A.Y. Real-Time Clock:**\n`{time_str}`", parse_mode=constants.ParseMode.MARKDOWN)

async def timezone_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Views or dynamically sets timezone for the user/chat."""
    chat = update.effective_chat
    user = update.effective_user
    register_chat(chat, user)

    if not context.args:
        current_tz = memory_engine.get_timezone(chat.id)
        current_time = memory_engine.get_current_time_str(chat.id)
        await update.message.reply_text(
            f"🌍 **Current Timezone:** `{current_tz}`\n"
            f"🕒 **Current Time:** `{current_time}`\n\n"
            f"बदलने के लिए: `/timezone <city या timezone>`\n"
            f"उदाहरण: `/timezone Delhi` या `/timezone New York` या `/timezone Dubai`",
            parse_mode=constants.ParseMode.MARKDOWN
        )
        return

    tz_input = " ".join(context.args).strip()
    res = memory_engine.set_timezone(chat.id, tz_input)
    if res:
        time_str = memory_engine.get_current_time_str(chat.id)
        await update.message.reply_text(
            f"✅ **Timezone Successfully Updated!**\n"
            f"🌍 **New Timezone:** `{res}`\n"
            f"🕒 **Current Time:** `{time_str}`",
            parse_mode=constants.ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            f"❌ अमान्य टाइमज़ोन: `{tz_input}`। कृपया कोई मान्य शहर (जैसे Delhi, Mumbai, Dubai, London, New York) या IANA टाइमज़ोन (Asia/Kolkata) लिखें।",
            parse_mode=constants.ParseMode.MARKDOWN
        )

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sets preferred conversational language for Friday."""
    chat = update.effective_chat
    user = update.effective_user
    register_chat(chat, user)

    if not context.args:
        curr_lang = memory_engine.get_language(chat.id)
        await update.message.reply_text(
            f"🗣️ **Current Preferred Language:** `{curr_lang}`\n\n"
            f"बदलने के लिए: `/language <language>`\n"
            f"उदाहरण: `/language Hindi`, `/language English`, `/language Punjabi`, `/language auto`",
            parse_mode=constants.ParseMode.MARKDOWN
        )
        return

    new_lang = " ".join(context.args).strip()
    memory_engine.set_language(chat.id, new_lang)
    await update.message.reply_text(
        f"✅ **भाषा प्राथमिकता अपडेट हो गई!**\nअब Friday आपसे प्राथमिकता अनुसार `{new_lang}` में संवाद करेगी।",
        parse_mode=constants.ParseMode.MARKDOWN
    )

async def dashboard_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Provides link and info for the Live Central Web Dashboard."""
    user = update.effective_user
    if not user or not is_bot_owner(user.id):
        await update.message.reply_text("⛔ यह कमांड केवल बोट ओनर के लिए है।")
        return

    port = os.environ.get("PORT", "8080")
    railway_url = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")
    url_info = f"https://{railway_url}" if railway_url else f"http://0.0.0.0:{port}"

    msg = (
        f"⚡ **F.R.I.D.A.Y. Central Web Dashboard (Live Two-Way Sync)**\n\n"
        f"🌐 **Dashboard URL:** `{url_info}`\n"
        f"🔌 **Internal Port:** `{port}`\n"
        f"🛡️ **Status:** Active & Linked with Live Telegram Polling\n\n"
        f"इस वेब डैशबोर्ड से आप सभी रजिस्टर्ड ग्रुप्स, चैनल्स, यूजर्स लाइव देख सकते हैं, "
        f"ग्रुप्स से बोट को रिमोटली लीव करा सकते हैं, और सीधे ब्राउज़र से ब्रॉडकास्ट भेज सकते हैं।"
    )
    await update.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)

# ==================== MEDIA & CREATIVE TOOLS (IMAGE, VIDEO, LOGO, EMOJI, FONT) ====================

async def image_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generates an AI image with Friday watermark."""
    chat = update.effective_chat
    user = update.effective_user
    register_chat(chat, user)

    prompt = " ".join(context.args).strip() if context.args else ""
    if not prompt:
        await update.message.reply_text("💡 उपयोग: `/image <प्रॉम्प्ट>` (उदा. `/image a futuristic cyberpunk lion with neon lighting`)")
        return

    status_msg = await update.message.reply_text("🎨 **AI इमेज तैयार हो रही है...**")
    try:
        loop = asyncio.get_event_loop()
        img_bytes = await loop.run_in_executor(None, generate_ai_image, prompt)
        photo_file = InputFile(io.BytesIO(img_bytes), filename="ai_image.jpg")
        caption = f"✨ **Friday AI Generated Image**\n📝 `{prompt}`\n\n🛡️ *Verified AI Generated Content*"
        await update.message.reply_photo(photo=photo_file, caption=caption, parse_mode=constants.ParseMode.MARKDOWN)
        await status_msg.delete()
    except Exception as e:
        logger.error(f"Error in image_command: {e}")
        await status_msg.edit_text(f"❌ इमेज बनाने में त्रुटि: {e}")

async def video_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generates an AI video (max 2 minutes) with Friday watermark."""
    chat = update.effective_chat
    user = update.effective_user
    register_chat(chat, user)

    prompt = " ".join(context.args).strip() if context.args else ""
    if not prompt:
        await update.message.reply_text("💡 उपयोग: `/video <प्रॉम्प्ट>` (उदा. `/video sunset over ocean with flying birds`)\n(अधिकतम अवधि: 2 मिनट)")
        return

    status_msg = await update.message.reply_text("🎬 **AI वीडियो क्लिप रेंडर हो रही है...** (कृपया थोड़ा इंतज़ार करें)")
    try:
        loop = asyncio.get_event_loop()
        vid_path = await loop.run_in_executor(None, generate_ai_video, prompt, 15)
        with open(vid_path, "rb") as f:
            vid_bytes = f.read()
        try:
            os.remove(vid_path)
        except Exception:
            pass

        video_file = InputFile(io.BytesIO(vid_bytes), filename="ai_video.mp4")
        caption = f"🎬 **Friday AI Generated Video**\n📝 `{prompt}`\n\n🛡️ *Verified AI Generated Media (Max 2min)*"
        await update.message.reply_video(video=video_file, caption=caption, parse_mode=constants.ParseMode.MARKDOWN)
        await status_msg.delete()
    except Exception as e:
        logger.error(f"Error in video_command: {e}")
        await status_msg.edit_text(f"❌ वीडियो बनाने में त्रुटि: {e}")

async def logo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generates a professional logo emblem."""
    chat = update.effective_chat
    user = update.effective_user
    register_chat(chat, user)

    name = " ".join(context.args).strip() if context.args else ""
    if not name:
        await update.message.reply_text("💡 उपयोग: `/logo <ब्रांड या नाम>` (उदा. `/logo Apex Legends` या `/logo Yash Tech neon 3D`)")
        return

    status_msg = await update.message.reply_text("🏷️ **लोगो डिज़ाइन किया जा रहा है...**")
    try:
        loop = asyncio.get_event_loop()
        logo_bytes = await loop.run_in_executor(None, generate_ai_logo, name)
        photo_file = InputFile(io.BytesIO(logo_bytes), filename="ai_logo.jpg")
        caption = f"🏷️ **Friday AI Brand Logo**\n👑 Name: `{name}`\n\n🛡️ *Verified AI Design*"
        await update.message.reply_photo(photo=photo_file, caption=caption, parse_mode=constants.ParseMode.MARKDOWN)
        await status_msg.delete()
    except Exception as e:
        logger.error(f"Error in logo_command: {e}")
        await status_msg.edit_text(f"❌ लोगो बनाने में त्रुटि: {e}")

async def emoji_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generates custom 3D emoji or sticker graphic."""
    chat = update.effective_chat
    user = update.effective_user
    register_chat(chat, user)

    prompt = " ".join(context.args).strip() if context.args else ""
    if not prompt:
        await update.message.reply_text("💡 उपयोग: `/emoji <आइडिया>` (उदा. `/emoji laughing robot with sunglasses`)")
        return

    status_msg = await update.message.reply_text("😃 **कस्टम 3D इमोजी तैयार हो रहा है...**")
    try:
        loop = asyncio.get_event_loop()
        emoji_bytes = await loop.run_in_executor(None, generate_ai_emoji, prompt)
        photo_file = InputFile(io.BytesIO(emoji_bytes), filename="ai_emoji.jpg")
        caption = f"😃 **Friday Custom 3D Emoji**\n✨ `{prompt}`"
        await update.message.reply_photo(photo=photo_file, caption=caption, parse_mode=constants.ParseMode.MARKDOWN)
        await status_msg.delete()
    except Exception as e:
        logger.error(f"Error in emoji_command: {e}")
        await status_msg.edit_text(f"❌ इमोजी बनाने में त्रुटि: {e}")

async def font_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Converts text into multiple fancy stylish fonts."""
    chat = update.effective_chat
    user = update.effective_user
    register_chat(chat, user)

    text = " ".join(context.args).strip() if context.args else ""
    if not text:
        await update.message.reply_text("💡 उपयोग: `/font <टेक्स्ट या नाम>` (उदा. `/font Friday AI` या `/font Yash`)")
        return

    styled_text = generate_stylish_fonts(text)
    await update.message.reply_text(styled_text, parse_mode=constants.ParseMode.MARKDOWN)

# ==================== BOT OWNER & BROADCAST COMMANDS ====================

async def setowner_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allows claiming ownership if no owner is configured yet."""
    user = update.effective_user
    data = load_registered_chats()

    current_owner = data.get("owner_id") or BOT_OWNER_ID
    if current_owner and str(current_owner) != str(user.id):
        await update.message.reply_text("⛔ बोट का ओनर पहले से सेट है। केवल वर्तमान ओनर ही ओनरशिप ट्रांसफर कर सकता है।")
        return

    data["owner_id"] = user.id
    save_registered_chats(data)
    await update.message.reply_text(
        f"👑 बधाई हो {user.first_name}! आपको **Friday Bot का आधिकारिक Owner** सेट कर दिया गया है (`ID: {user.id}`)।\n\n"
        f"अब केवल आप `/broadcast`, `/stats` और `/transferowner` का उपयोग कर सकते हैं।"
    )

async def transferowner_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Transfers bot ownership to another user (Owner Only)."""
    user = update.effective_user
    if not is_bot_owner(user.id):
        await update.message.reply_text("⛔ केवल वर्तमान बोट ओनर ही ओनरशिप ट्रांसफर कर सकते हैं।")
        return

    target_id = None
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        target_id = update.message.reply_to_message.from_user.id
    elif context.args and context.args[0].isdigit():
        target_id = int(context.args[0])

    if not target_id:
        await update.message.reply_text("💡 उपयोग: `/transferowner <नई_यूज़र_ID>` या नए ओनर के मैसेज पर रिप्लाई करें।")
        return

    data = load_registered_chats()
    data["owner_id"] = target_id
    save_registered_chats(data)

    await update.message.reply_text(
        f"👑 बोट ओनरशिप सफलतापूर्वक यूज़र ID `{target_id}` को ट्रांसफर कर दी गई है!\n"
        f"अब वे ही नए बोट ओनर हैं।"
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Shows statistics of registered chats and owner info (Owner Only)."""
    user = update.effective_user
    if not is_bot_owner(user.id):
        await update.message.reply_text("⛔ यह जानकारी केवल बोट ओनर के लिए है।")
        return

    data = load_registered_chats()
    groups_cnt = len(data.get("groups", {}))
    users_cnt = len(data.get("users", {}))
    channels_cnt = len(data.get("channels", {}))
    owner = data.get("owner_id", "Not set")

    msg = (
        f"📊 **Friday Bot Statistics & Reach**\n\n"
        f"👑 **Owner ID:** `{owner}`\n"
        f"👤 **पर्सनल DMs (Users):** `{users_cnt}`\n"
        f"👥 **ग्रुप्स (Groups):** `{groups_cnt}`\n"
        f"📢 **चैनल्स (Channels):** `{channels_cnt}`\n"
        f"🌐 **कुल रीच (Total Reach):** `{users_cnt + groups_cnt + channels_cnt}`"
    )
    await update.message.reply_text(msg, parse_mode=constants.ParseMode.MARKDOWN)

async def _send_broadcast_payload(bot, target_id: str, update: Update, custom_text: str = None) -> bool:
    """Helper to forward or copy message with text, media, or links to a target chat."""
    try:
        # If replied to a message, copy it directly (preserves photo, video, buttons, links)
        if update.message.reply_to_message:
            await bot.copy_message(
                chat_id=int(target_id),
                from_chat_id=update.message.chat_id,
                message_id=update.message.reply_to_message.message_id,
            )
            return True
        elif custom_text:
            await bot.send_message(
                chat_id=int(target_id),
                text=custom_text,
                parse_mode=constants.ParseMode.MARKDOWN,
            )
            return True
    except telegram.error.RetryAfter as e:
        logger.warning(f"Rate limited on {target_id}. Sleeping {e.retry_after}s...")
        await asyncio.sleep(e.retry_after + 1)
        return await _send_broadcast_payload(bot, target_id, update, custom_text)
    except Exception as e:
        logger.warning(f"Broadcast failed for {target_id}: {e}")
        return False
    return False

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcasts to ALL registered users (DMs), groups, and channels (Owner Only)."""
    user = update.effective_user
    if not is_bot_owner(user.id):
        await update.message.reply_text("⛔ **अनधिकृत:** ब्रॉडकास्ट केवल बोट ओनर (Owner) कर सकते हैं।")
        return

    custom_text = " ".join(context.args) if context.args else None
    if not custom_text and not update.message.reply_to_message:
        await update.message.reply_text(
            "💡 **ब्रॉडकास्ट कैसे करें:**\n"
            "1. टाइप करें: `/broadcast [आपका प्रमोशनल मैसेज और लिंक]`\n"
            "2. या किसी भी फ़ोटो, वीडियो, ऑडियो या पोस्ट पर रिप्लाई करके लिखें: `/broadcast`"
        )
        return

    data = load_registered_chats()
    users = list(data.get("users", {}).keys())
    groups = list(data.get("groups", {}).keys())
    channels = list(data.get("channels", {}).keys())
    total_targets = len(users) + len(groups) + len(channels)

    if total_targets == 0:
        await update.message.reply_text("⚠️ कोई भी ग्रुप, चैनल या यूजर अभी तक रजिस्टर्ड नहीं है।")
        return

    status_msg = await update.message.reply_text(
        f"🚀 **ब्रॉडकास्ट शुरू हो रहा है...**\n"
        f"कुल लक्ष्य: `{total_targets}` (DMs: {len(users)}, Groups: {len(groups)}, Channels: {len(channels)})"
    )

    u_succ, u_fail = 0, 0
    g_succ, g_fail = 0, 0
    c_succ, c_fail = 0, 0

    # 1. Send to private DMs
    for uid in users:
        ok = await _send_broadcast_payload(context.bot, uid, update, custom_text)
        if ok:
            u_succ += 1
        else:
            u_fail += 1
        await asyncio.sleep(0.05)

    # 2. Send to groups
    for gid in groups:
        ok = await _send_broadcast_payload(context.bot, gid, update, custom_text)
        if ok:
            g_succ += 1
        else:
            g_fail += 1
        await asyncio.sleep(0.05)

    # 3. Send to channels
    for cid in channels:
        ok = await _send_broadcast_payload(context.bot, cid, update, custom_text)
        if ok:
            c_succ += 1
        else:
            c_fail += 1
        await asyncio.sleep(0.05)

    report = (
        f"📢 **ब्रॉडकास्ट संपन्न!**\n\n"
        f"👤 **पर्सनल DMs:** `{u_succ}` सफल | `{u_fail}` विफल\n"
        f"👥 **ग्रुप्स (Groups):** `{g_succ}` सफल | `{g_fail}` विफल\n"
        f"📢 **चैनल्स (Channels):** `{c_succ}` सफल | `{c_fail}` विफल\n"
        f"✨ **कुल सफलतापूर्वक डिलीवर:** `{u_succ + g_succ + c_succ}` / `{total_targets}`"
    )
    await status_msg.edit_text(report, parse_mode=constants.ParseMode.MARKDOWN)

async def broadcast_groups_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcasts to Groups ONLY (Owner Only)."""
    user = update.effective_user
    if not is_bot_owner(user.id):
        await update.message.reply_text("⛔ केवल बोट ओनर ही ब्रॉडकास्ट कर सकते हैं।")
        return

    custom_text = " ".join(context.args) if context.args else None
    if not custom_text and not update.message.reply_to_message:
        await update.message.reply_text("💡 उपयोग: `/broadcast_groups [मैसेज व लिंक]`")
        return

    data = load_registered_chats()
    targets = list(data.get("groups", {}).keys())
    if not targets:
        await update.message.reply_text("⚠️ कोई भी ग्रुप रजिस्टर्ड नहीं है।")
        return

    succ, fail = 0, 0
    status_msg = await update.message.reply_text(f"🚀 ग्रुप्स में ब्रॉडकास्ट चालू... कुल: `{len(targets)}`")
    for tid in targets:
        ok = await _send_broadcast_payload(context.bot, tid, update, custom_text)
        if ok:
            succ += 1
        else:
            fail += 1
        await asyncio.sleep(0.05)

    await status_msg.edit_text(f"📢 **ग्रुप ब्रॉडकास्ट पूरा हुआ!**\nसफल: `{succ}` | विफल: `{fail}`")

async def broadcast_channels_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcasts to Channels ONLY (Owner Only)."""
    user = update.effective_user
    if not is_bot_owner(user.id):
        await update.message.reply_text("⛔ केवल बोट ओनर ही ब्रॉडकास्ट कर सकते हैं।")
        return

    custom_text = " ".join(context.args) if context.args else None
    if not custom_text and not update.message.reply_to_message:
        await update.message.reply_text("💡 उपयोग: `/broadcast_channels [मैसेज व लिंक]` या पोस्ट पर रिप्लाई करें।")
        return

    data = load_registered_chats()
    targets = list(data.get("channels", {}).keys())
    if not targets:
        await update.message.reply_text("⚠️ कोई भी चैनल अभी तक रजिस्टर्ड नहीं है। बोट को चैनल में एडमिन बनाकर पोस्ट करें।")
        return

    status_msg = await update.message.reply_text(f"🚀 चैनल्स में ब्रॉडकास्ट चालू... कुल: `{len(targets)}`")
    succ, fail = 0, 0
    for tid in targets:
        ok = await _send_broadcast_payload(context.bot, tid, update, custom_text)
        if ok:
            succ += 1
        else:
            fail += 1
        await asyncio.sleep(0.08)

    await status_msg.edit_text(f"📢 **चैनल ब्रॉडकास्ट पूरा हुआ!**\nसफल: `{succ}` | विफल: `{fail}`")

async def broadcast_users_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Broadcasts to DM Users ONLY (Owner Only)."""
    user = update.effective_user
    if not is_bot_owner(user.id):
        await update.message.reply_text("⛔ केवल बोट ओनर ही ब्रॉडकास्ट कर सकते हैं।")
        return

    custom_text = " ".join(context.args) if context.args else None
    if not custom_text and not update.message.reply_to_message:
        await update.message.reply_text("💡 उपयोग: `/broadcast_users [मैसेज व लिंक]`")
        return

    data = load_registered_chats()
    targets = list(data.get("users", {}).keys())
    if not targets:
        await update.message.reply_text("⚠️ कोई भी पर्सनल DM यूजर रजिस्टर्ड नहीं है।")
        return

    succ, fail = 0, 0
    status_msg = await update.message.reply_text(f"🚀 पर्सनल DMs में ब्रॉडकास्ट चालू... कुल: `{len(targets)}`")
    for tid in targets:
        ok = await _send_broadcast_payload(context.bot, tid, update, custom_text)
        if ok:
            succ += 1
        else:
            fail += 1
        await asyncio.sleep(0.05)

    await status_msg.edit_text(f"📢 **DM ब्रॉडकास्ट पूरा हुआ!**\nसफल: `{succ}` | विफल: `{fail}`")

# ==================== GROUP ADMIN & MODERATION COMMANDS ====================

async def pause_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    register_chat(chat, user)
    if chat.type in [constants.ChatType.GROUP, constants.ChatType.SUPERGROUP]:
        if not await is_admin(chat.id, user.id, context):
            await update.message.reply_text("⚠️ यह कमांड केवल ग्रुप एडमिन इस्तेमाल कर सकते हैं।")
            return
    group_paused[chat.id] = True
    await update.message.reply_text("⏸️ Friday AI को इस चैट में पॉज़ कर दिया गया है। चालू करने के लिए `/resume` भेजें।")

async def resume_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    register_chat(chat, user)
    if chat.type in [constants.ChatType.GROUP, constants.ChatType.SUPERGROUP]:
        if not await is_admin(chat.id, user.id, context):
            await update.message.reply_text("⚠️ यह कमांड केवल ग्रुप एडमिन इस्तेमाल कर सकते हैं।")
            return
    group_paused[chat.id] = False
    await update.message.reply_text("▶️ Friday AI अब एक्टिव है!")

async def promote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Promotes a member to Administrator with full rights (/admin or /promote)."""
    chat = update.effective_chat
    sender = update.effective_user
    register_chat(chat, sender)

    if chat.type not in [constants.ChatType.GROUP, constants.ChatType.SUPERGROUP]:
        await update.message.reply_text("⚠️ यह कमांड सिर्फ ग्रुप्स में काम करता है।")
        return

    if not await is_admin(chat.id, sender.id, context):
        await update.message.reply_text("⚠️ केवल ग्रुप एडमिन ही अन्य सदस्यों को एडमिन बना सकते हैं।")
        return

    target_id = None
    target_name = "User"
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        target_id = update.message.reply_to_message.from_user.id
        target_name = update.message.reply_to_message.from_user.first_name
    elif context.args and context.args[0].isdigit():
        target_id = int(context.args[0])
        target_name = f"User ({target_id})"
    elif context.args and context.args[0].startswith("@"):
        uname = context.args[0][1:].lower()
        data = load_registered_chats()
        cid = str(chat.id)
        for uid_str, uinfo in data.get("group_members", {}).get(cid, {}).items():
            if uinfo.get("username", "").lower() == uname:
                target_id = int(uid_str)
                target_name = uinfo.get("name", uname)
                break

    if not target_id:
        await update.message.reply_text("💡 किसी यूजर के मैसेज पर रिप्लाई करके `/admin` लिखें या यूजर ID / @username दें।")
        return

    try:
        await context.bot.promote_chat_member(
            chat_id=chat.id,
            user_id=target_id,
            can_manage_chat=True,
            can_delete_messages=True,
            can_manage_video_chats=True,
            can_restrict_members=True,
            can_promote_members=True,
            can_change_info=True,
            can_invite_users=True,
            can_pin_messages=True,
        )
        await update.message.reply_text(f"⭐ **{target_name}** को ग्रुप का एडमिन बना दिया गया है (Admin Rights Activated)!")
    except Exception as e:
        await update.message.reply_text(f"❌ एडमिन बनाने में त्रुटि: {e}\nसुनिश्चित करें कि बोट के पास 'Add New Admins' अधिकार हैं।")

async def demote_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    sender = update.effective_user
    register_chat(chat, sender)

    if not await is_admin(chat.id, sender.id, context):
        await update.message.reply_text("⚠️ केवल एडमिन ही डिमोट कर सकते हैं।")
        return

    target_user = None
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
    elif context.args and context.args[0].isdigit():
        target_user = await context.bot.get_chat_member(chat.id, int(context.args[0]))
        target_user = target_user.user

    if not target_user:
        await update.message.reply_text("💡 एडमिन के मैसेज पर रिप्लाई करके `/demote` लिखें।")
        return

    try:
        await context.bot.promote_chat_member(
            chat_id=chat.id,
            user_id=target_user.id,
            can_manage_chat=False,
            can_delete_messages=False,
            can_manage_video_chats=False,
            can_restrict_members=False,
            can_change_info=False,
            can_invite_users=False,
            can_pin_messages=False,
        )
        await update.message.reply_text(f"⬇️ **{target_user.first_name}** के एडमिन अधिकार हटा दिए गए हैं।")
    except Exception as e:
        await update.message.reply_text(f"❌ डिमोट करने में त्रुटि: {e}")

async def muteall_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mutes the entire group instantly by disabling send permissions for non-admins."""
    chat = update.effective_chat
    sender = update.effective_user
    register_chat(chat, sender)

    if chat.type not in [constants.ChatType.GROUP, constants.ChatType.SUPERGROUP]:
        await update.message.reply_text("⚠️ यह कमांड सिर्फ ग्रुप्स में काम करता है।")
        return

    if not await is_admin(chat.id, sender.id, context):
        await update.message.reply_text("⚠️ केवल ग्रुप एडमिन ही पूरे ग्रुप को म्यूट कर सकते हैं।")
        return

    try:
        perms = ChatPermissions(
            can_send_messages=False,
            can_send_media_messages=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False,
        )
        await context.bot.set_chat_permissions(chat_id=chat.id, permissions=perms)
        await update.message.reply_text("🔇 **पूरा ग्रुप म्यूट कर दिया गया है!**\nअब सामान्य सदस्य मैसेज नहीं भेज सकते, केवल एडमिन बोल सकते हैं।")
    except Exception as e:
        await update.message.reply_text(f"❌ ग्रुप म्यूट करने में त्रुटि: {e}")

async def unmuteall_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unmutes the entire group instantly."""
    chat = update.effective_chat
    sender = update.effective_user
    register_chat(chat, sender)

    if chat.type not in [constants.ChatType.GROUP, constants.ChatType.SUPERGROUP]:
        await update.message.reply_text("⚠️ यह कमांड सिर्फ ग्रुप्स में काम करता है।")
        return

    if not await is_admin(chat.id, sender.id, context):
        await update.message.reply_text("⚠️ केवल ग्रुप एडमिन ही पूरे ग्रुप को अनम्यूट कर सकते हैं।")
        return

    try:
        perms = ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
            can_send_polls=True,
            can_invite_users=True,
        )
        await context.bot.set_chat_permissions(chat_id=chat.id, permissions=perms)
        await update.message.reply_text("🔊 **पूरा ग्रुप अनम्यूट कर दिया गया है!**\nअब सभी सदस्य सामान्य रूप से बात कर सकते हैं।")
    except Exception as e:
        await update.message.reply_text(f"❌ ग्रुप अनम्यूट करने में त्रुटि: {e}")

async def banall_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mass bans all tracked non-admin members from the group."""
    chat = update.effective_chat
    sender = update.effective_user
    register_chat(chat, sender)

    if chat.type not in [constants.ChatType.GROUP, constants.ChatType.SUPERGROUP]:
        await update.message.reply_text("⚠️ यह कमांड सिर्फ ग्रुप्स में काम करता है।")
        return

    if not await is_admin(chat.id, sender.id, context):
        await update.message.reply_text("⚠️ केवल ग्रुप एडमिन ही यह कमांड चला सकते हैं।")
        return

    try:
        bot_member = await context.bot.get_chat_member(chat.id, context.bot.id)
        if not isinstance(bot_member, (ChatMemberAdministrator, ChatMemberOwner)) or not bot_member.can_restrict_members:
            await update.message.reply_text("⚠️ मेरे पास मेंबर्स को बैन करने की एडमिन पावर (Restrict/Ban Members) नहीं है। कृपया पहले मुझे यह अधिकार दें।")
            return
    except Exception as e:
        logger.error(f"Error checking bot permissions: {e}")

    data = load_registered_chats()
    cid = str(chat.id)
    group_members = data.get("group_members", {}).get(cid, {})

    if not group_members:
        await update.message.reply_text("⚠️ इस ग्रुप में अभी कोई नॉन-एडमिन सदस्य ट्रैक नहीं हुआ है। जैसे-जैसे सदस्य मैसेज भेजेंगे, वे ट्रैक हो जाएंगे।")
        return

    status_msg = await update.message.reply_text("⏳ सभी मेंबर्स को बैन किया जा रहा है...")

    try:
        admins = await context.bot.get_chat_administrators(chat.id)
        admin_ids = {a.user.id for a in admins}
    except Exception:
        admin_ids = {sender.id, context.bot.id}

    banned_count = 0
    banned_list = data.setdefault("banned_users", {}).setdefault(cid, [])

    for uid_str, uinfo in list(group_members.items()):
        uid = int(uid_str)
        if uid in admin_ids or uid == context.bot.id:
            continue
        try:
            await context.bot.ban_chat_member(chat_id=chat.id, user_id=uid)
            banned_count += 1
            if uid not in banned_list:
                banned_list.append(uid)
            await asyncio.sleep(0.08)
        except Exception as e:
            logger.warning(f"Failed to ban member {uid}: {e}")

    save_registered_chats(data)
    await status_msg.edit_text(f"🚫 **Ban All संपन्न!**\nकुल `{banned_count}` सदस्यों को ग्रुप से बैन कर दिया गया है।")

async def unbanall_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unbans all recorded banned members and clears chat restrictions."""
    chat = update.effective_chat
    sender = update.effective_user
    register_chat(chat, sender)

    if chat.type not in [constants.ChatType.GROUP, constants.ChatType.SUPERGROUP]:
        await update.message.reply_text("⚠️ यह कमांड सिर्फ ग्रुप्स में काम करता है।")
        return

    if not await is_admin(chat.id, sender.id, context):
        await update.message.reply_text("⚠️ केवल ग्रुप एडमिन ही अनबैन कर सकते हैं।")
        return

    data = load_registered_chats()
    cid = str(chat.id)
    banned_list = data.get("banned_users", {}).get(cid, [])

    if not banned_list:
        await update.message.reply_text("ℹ️ इस ग्रुप में कोई भी बैन किया हुआ सदस्य रिकॉर्ड में नहीं है।")
        return

    status_msg = await update.message.reply_text(f"⏳ कुल `{len(banned_list)}` सदस्यों को अनबैन किया जा रहा है...")
    unbanned_count = 0

    for uid in list(banned_list):
        try:
            await context.bot.unban_chat_member(chat_id=chat.id, user_id=uid, only_if_banned=True)
            unbanned_count += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.warning(f"Failed to unban {uid}: {e}")

    data["banned_users"][cid] = []
    save_registered_chats(data)

    await status_msg.edit_text(f"✅ **Unban All संपन्न!**\nकुल `{unbanned_count}` सदस्यों की सभी रिस्ट्रिक्शंस हटा दी गई हैं और उन्हें अनबैन कर दिया गया है।")

async def tagall_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Real Tag Bot function: mentions members in batches of 5 with clickable links."""
    chat = update.effective_chat
    user = update.effective_user
    register_chat(chat, user)

    if chat.type not in [constants.ChatType.GROUP, constants.ChatType.SUPERGROUP]:
        await update.message.reply_text("⚠️ यह कमांड सिर्फ ग्रुप्स में काम करता है।")
        return

    if not await is_admin(chat.id, user.id, context):
        await update.message.reply_text("⚠️ केवल ग्रुप एडमिन ही सभी को टैग कर सकते हैं।")
        return

    custom_msg = " ".join(context.args) if context.args else "ध्यान दें सभी सदस्य!"
    active_tags[chat.id] = True

    data = load_registered_chats()
    cid = str(chat.id)
    members_dict = data.get("group_members", {}).get(cid, {}).copy()

    # Also fetch current admins
    try:
        admins = await context.bot.get_chat_administrators(chat.id)
        for a in admins:
            if not a.user.is_bot:
                members_dict[str(a.user.id)] = {
                    "name": a.user.first_name or "Admin",
                    "username": a.user.username or "",
                }
    except Exception as e:
        logger.warning(f"Error fetching admins for tagall: {e}")

    if not members_dict:
        await update.message.reply_text(f"📢 **{custom_msg}**\n\n@all @everyone")
        return

    members_list = list(members_dict.items())
    total = len(members_list)
    await update.message.reply_text(
        f"🏷️ **टैगिंग शुरू हो रही है...** (कुल {total} सदस्य)\n"
        f"रोकने के लिए `/stoptag` या `/cancel` भेजें।"
    )

    batch_size = 5
    for i in range(0, total, batch_size):
        if not active_tags.get(chat.id, True):
            await update.message.reply_text("🛑 टैगिंग रोक दी गई है।")
            break

        batch = members_list[i : i + batch_size]
        mentions = []
        for uid_str, info in batch:
            name = (info.get("name") or "Member").replace("[", "").replace("]", "")
            mentions.append(f"[{name}](tg://user?id={uid_str})")

        text = f"📢 **{custom_msg}**\n" + " • ".join(mentions)
        try:
            await context.bot.send_message(
                chat_id=chat.id,
                text=text,
                parse_mode=constants.ParseMode.MARKDOWN,
            )
        except Exception as e:
            logger.warning(f"Error sending tag batch: {e}")

        await asyncio.sleep(1.8)

    active_tags[chat.id] = False

async def stoptag_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    active_tags[chat.id] = False
    await update.message.reply_text("🛑 टैगिंग प्रोसेस रोक दी गई है।")

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    sender = update.effective_user
    register_chat(chat, sender)

    if not await is_admin(chat.id, sender.id, context):
        await update.message.reply_text("⚠️ आपके पास बैन करने के अधिकार नहीं हैं।")
        return

    target_id = None
    target_name = "User"
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        target_id = update.message.reply_to_message.from_user.id
        target_name = update.message.reply_to_message.from_user.first_name
    elif context.args and context.args[0].isdigit():
        target_id = int(context.args[0])

    if not target_id:
        await update.message.reply_text("💡 किसी यूजर के मैसेज पर रिप्लाई करके `/ban` लिखें या यूजर ID दें।")
        return

    try:
        await context.bot.ban_chat_member(chat_id=chat.id, user_id=target_id)
        # Record into banned_users
        data = load_registered_chats()
        b_list = data.setdefault("banned_users", {}).setdefault(str(chat.id), [])
        if target_id not in b_list:
            b_list.append(target_id)
            save_registered_chats(data)
        await update.message.reply_text(f"🚫 **{target_name}** (`{target_id}`) को ग्रुप से बैन कर दिया गया है।")
    except Exception as e:
        await update.message.reply_text(f"❌ बैन करने में असमर्थ: {e}")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    sender = update.effective_user
    register_chat(chat, sender)

    if not await is_admin(chat.id, sender.id, context):
        await update.message.reply_text("⚠️ केवल एडमिन ही अनबैन कर सकते हैं।")
        return

    target_id = None
    if update.message.reply_to_message and update.message.reply_to_message.from_user:
        target_id = update.message.reply_to_message.from_user.id
    elif context.args and context.args[0].isdigit():
        target_id = int(context.args[0])

    if not target_id:
        await update.message.reply_text("💡 अनबैन करने के लिए यूजर ID दें: `/unban 12345678`")
        return

    try:
        await context.bot.unban_chat_member(chat_id=chat.id, user_id=target_id, only_if_banned=True)
        # Remove from banned_users if present
        data = load_registered_chats()
        cid = str(chat.id)
        if cid in data.get("banned_users", {}) and target_id in data["banned_users"][cid]:
            data["banned_users"][cid].remove(target_id)
            save_registered_chats(data)
        await update.message.reply_text(f"✅ यूजर (`{target_id}`) को सफलतापूर्वक अनबैन कर दिया गया है।")
    except Exception as e:
        await update.message.reply_text(f"❌ अनबैन करने में त्रुटि: {e}")

async def mute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    sender = update.effective_user
    register_chat(chat, sender)

    if not await is_admin(chat.id, sender.id, context):
        await update.message.reply_text("⚠️ केवल एडमिन ही म्यूट कर सकते हैं।")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("💡 जिस यूजर को म्यूट करना है, उसके मैसेज पर रिप्लाई करके `/mute` लिखें।")
        return

    target_user = update.message.reply_to_message.from_user
    try:
        perms = ChatPermissions(can_send_messages=False)
        await context.bot.restrict_chat_member(chat_id=chat.id, user_id=target_user.id, permissions=perms)
        await update.message.reply_text(f"🔇 **{target_user.first_name}** को म्यूट कर दिया गया है।")
    except Exception as e:
        await update.message.reply_text(f"❌ म्यूट करने में त्रुटि: {e}")

async def unmute_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    sender = update.effective_user
    register_chat(chat, sender)

    if not await is_admin(chat.id, sender.id, context):
        await update.message.reply_text("⚠️ केवल एडमिन ही अनम्यूट कर सकते हैं।")
        return

    if not update.message.reply_to_message:
        await update.message.reply_text("💡 यूजर के मैसेज पर रिप्लाई करके `/unmute` लिखें।")
        return

    target_user = update.message.reply_to_message.from_user
    try:
        perms = ChatPermissions(
            can_send_messages=True,
            can_send_media_messages=True,
            can_send_other_messages=True,
            can_add_web_page_previews=True,
        )
        await context.bot.restrict_chat_member(chat_id=chat.id, user_id=target_user.id, permissions=perms)
        await update.message.reply_text(f"🔊 **{target_user.first_name}** को अनम्यूट कर दिया गया है।")
    except Exception as e:
        await update.message.reply_text(f"❌ अनम्यूट करने में त्रुटि: {e}")

async def purge_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clears messages up to specified count or from replied message."""
    chat = update.effective_chat
    sender = update.effective_user
    register_chat(chat, sender)

    if chat.type not in [constants.ChatType.GROUP, constants.ChatType.SUPERGROUP]:
        await update.message.reply_text("⚠️ यह कमांड ग्रुप्स में काम करता है।")
        return

    if not await is_admin(chat.id, sender.id, context):
        await update.message.reply_text("⚠️ चैट डिलीट करने की अनुमति केवल एडमिन को है।")
        return

    current_msg_id = update.message.message_id
    if update.message.reply_to_message:
        from_msg_id = update.message.reply_to_message.message_id
        count = min(current_msg_id - from_msg_id + 1, 100)
    elif context.args and context.args[0].isdigit():
        count = min(int(context.args[0]), 100)
    else:
        count = 10

    deleted = 0
    for msg_id in range(current_msg_id, current_msg_id - count - 1, -1):
        try:
            await context.bot.delete_message(chat_id=chat.id, message_id=msg_id)
            deleted += 1
        except Exception:
            pass

    notify = await context.bot.send_message(chat_id=chat.id, text=f"🧹 `{deleted}` संदेश साफ़ कर दिए गए!")
    await asyncio.sleep(3)
    try:
        await notify.delete()
    except Exception:
        pass

# ==================== CHANNEL & CHAT MEMBER TRACKING ====================

async def chat_member_updated(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Automatically registers any channel or group when the bot is added or updated."""
    chat = update.effective_chat
    if not chat:
        return
    register_chat(chat, update.effective_user)
    logger.info(f"Chat status updated: {chat.title} ({chat.id}) [{chat.type}]")

async def channel_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Registers channel when a post is detected."""
    chat = update.effective_chat
    if chat:
        register_chat(chat, None)

# ==================== MESSAGE HANDLERS ====================

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return

    chat = update.effective_chat
    sender = update.effective_user
    register_chat(chat, sender)

    if group_paused.get(chat.id, False):
        return

    is_group = chat.type in [constants.ChatType.GROUP, constants.ChatType.SUPERGROUP]
    text = update.message.text
    bot_user = await context.bot.get_me()
    bot_username = bot_user.username.lower()

    if is_group:
        is_reply_to_bot = (
            update.message.reply_to_message
            and update.message.reply_to_message.from_user
            and update.message.reply_to_message.from_user.id == bot_user.id
        )
        is_mentioned = (
            f"@{bot_username}" in text.lower()
            or text.lower().startswith("friday")
            or " friday " in f" {text.lower()} "
        )

        if not (is_reply_to_bot or is_mentioned):
            return

        clean_text = text.replace(f"@{bot_username}", "").replace(f"@{bot_user.username}", "").strip()
        user_text = clean_text or text
    else:
        user_text = text

    # Intelligent Media Intent Detection (Captures natural Hindi/English queries anywhere in text)
    low_text = user_text.lower().strip()

    has_img_word = any(w in low_text for w in ["image", "photo", "picture", "pic", "तस्वीर", "फोटो", "इमेज", "चित्र", "wallpaper", "drawing"])
    has_vid_word = any(w in low_text for w in ["video", "वीडियो", "clip", "क्लिप", "animation", "reel"])
    has_logo_word = any(w in low_text for w in ["logo", "लोगो", "emblem", "icon"])
    has_emoji_word = any(w in low_text for w in ["emoji", "इमोजी", "sticker", "स्टिकर"])
    has_font_word = any(w in low_text for w in ["font", "फॉन्ट", "stylish text", "fancy text", "स्टाइलिश"])
    has_make_word = any(w in low_text for w in ["banao", "bana", "generate", "create", "make", "dikhao", "dikhana", "karo", "chahiye", "do", "draw", "bhejo"])

    # 1. Video Request
    if has_vid_word and has_make_word:
        clean_p = re.sub(r"(video|वीडियो|clip|क्लिप|banao|bana|generate|create|make|dikhao|karo|chahiye|ek|mujhe|ki|ka|ke)", "", user_text, flags=re.IGNORECASE).strip(" :-")
        context.args = clean_p.split() if clean_p else user_text.split()
        await video_command(update, context)
        return

    # 2. Logo Request
    if has_logo_word and has_make_word:
        clean_p = re.sub(r"(logo|लोगो|emblem|icon|banao|bana|generate|create|make|design|karo|chahiye|ek|mujhe|ki|ka|ke)", "", user_text, flags=re.IGNORECASE).strip(" :-")
        context.args = clean_p.split() if clean_p else user_text.split()
        await logo_command(update, context)
        return

    # 3. Emoji Request
    if has_emoji_word and has_make_word:
        clean_p = re.sub(r"(emoji|इमोजी|sticker|स्टिकर|banao|bana|generate|create|make|karo|chahiye|ek|mujhe|ki|ka|ke)", "", user_text, flags=re.IGNORECASE).strip(" :-")
        context.args = clean_p.split() if clean_p else user_text.split()
        await emoji_command(update, context)
        return

    # 4. Image / Photo Request (Handles 'robot ki photo banao', 'lion ki image', etc.)
    if has_img_word and has_make_word:
        clean_p = re.sub(r"(image|photo|picture|pic|तस्वीर|फोटो|इमेज|चित्र|wallpaper|banao|bana|generate|create|make|dikhao|dikhana|karo|chahiye|do|draw|ek|mujhe|ki|ka|ke)", "", user_text, flags=re.IGNORECASE).strip(" :-")
        context.args = clean_p.split() if clean_p else user_text.split()
        await image_command(update, context)
        return

    # 5. Font Styling Request
    if has_font_word:
        clean_p = re.sub(r"(font|फॉन्ट|stylish text|fancy text|स्टाइलिश|badlo|karo|banao|likho|me|mein)", "", user_text, flags=re.IGNORECASE).strip(" :-")
        context.args = clean_p.split() if clean_p else user_text.split()
        await font_command(update, context)
        return

    # 6. Natural Voice Switching Request ("voice badlo", "male voice karo", "female awaz me bolo")
    has_voice_word = any(w in low_text for w in ["voice", "आवाज़", "आवाज", "awaz"])
    has_change_word = any(w in low_text for w in ["change", "badlo", "badal", "switch", "karo", "kar do", "me", "mein"])
    if has_voice_word and has_change_word:
        if any(w in low_text for w in ["male", "ladka", "man", "men", "boy", "varun", "sagar"]):
            user_voices[chat.id] = AVAILABLE_VOICES["varun"]["id"]
            await update.message.reply_text("✅ Friday की आवाज़ पुरुष मॉडल (**Varun — J.A.R.V.I.S. Tactical Male**) में सेट कर दी गई है!")
            return
        elif any(w in low_text for w in ["female", "ladki", "woman", "women", "girl", "001", "friday_001", "jacqueline", "kavya", "siya"]):
            user_voices[chat.id] = AVAILABLE_VOICES["friday_001"]["id"]
            await update.message.reply_text("✅ Friday की आवाज़ महिला मॉडल (**FRIDAY 001 — Refined Pure Conversational Female**) में सेट कर दी गई है!")
            return
        else:
            curr_voice = user_voices.get(chat.id, AVAILABLE_VOICES["friday_001"]["id"])
            if curr_voice == AVAILABLE_VOICES["varun"]["id"]:
                user_voices[chat.id] = AVAILABLE_VOICES["friday_001"]["id"]
                await update.message.reply_text("✅ Friday की आवाज़ बदल कर महिला मॉडल (**FRIDAY 001**) पर सेट कर दी गई है!")
            else:
                user_voices[chat.id] = AVAILABLE_VOICES["varun"]["id"]
                await update.message.reply_text("✅ Friday की आवाज़ बदल कर पुरुष मॉडल (**Varun Tactical Male**) पर सेट कर दी गई है!")
            return

    stop_typing = asyncio.Event()
    typing_task = asyncio.create_task(
        keep_chat_action(context.bot, chat.id, constants.ChatAction.TYPING, stop_typing)
    )

    try:
        reply_text = await agent.generate_text_reply(chat.id, user_text)
        try:
            await update.message.reply_text(
                reply_text,
                parse_mode=constants.ParseMode.MARKDOWN,
                reply_to_message_id=update.message.message_id if is_group else None,
            )
        except Exception:
            await update.message.reply_text(
                reply_text,
                reply_to_message_id=update.message.message_id if is_group else None,
            )
    except Exception as e:
        logger.error(f"Error in text reply: {e}", exc_info=True)
        await update.message.reply_text(f"माफ़ कीजिए, समस्या आई: {e}")
    finally:
        stop_typing.set()
        await typing_task

async def handle_voice_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    sender = update.effective_user
    register_chat(chat, sender)

    if group_paused.get(chat.id, False):
        return

    voice_obj = update.message.voice or update.message.audio
    if not voice_obj:
        return

    is_group = chat.type in [constants.ChatType.GROUP, constants.ChatType.SUPERGROUP]
    bot_user = await context.bot.get_me()
    bot_username = bot_user.username.lower()

    if is_group:
        is_reply_to_bot = (
            update.message.reply_to_message
            and update.message.reply_to_message.from_user
            and update.message.reply_to_message.from_user.id == bot_user.id
        )
        caption = (update.message.caption or "").lower()
        is_mentioned = f"@{bot_username}" in caption or "friday" in caption

        if not (is_reply_to_bot or is_mentioned):
            return

    stop_action = asyncio.Event()
    action_task = asyncio.create_task(
        keep_chat_action(context.bot, chat.id, constants.ChatAction.RECORD_VOICE, stop_action)
    )

    try:
        # 1. Download voice note directly to memory (Zero Disk I/O)
        file_info = await context.bot.get_file(voice_obj.file_id)
        audio_byte_array = await file_info.download_as_bytearray()
        audio_bytes = bytes(audio_byte_array)

        mime_type = "audio/ogg" if update.message.voice else "audio/mp3"

        # 2. Ultra-fast AI response via Gemini 3.1 Flash Lite (In-Memory)
        reply_raw = await agent.generate_voice_reply_bytes(chat.id, audio_bytes, mime_type=mime_type)

        # Parse potential media action tag [ACTION:TYPE|PARAM]
        action_match = re.search(r"\[ACTION:(IMAGE|VIDEO|LOGO|EMOJI|FONT)\|([^\]]+)\]", reply_raw)
        media_action = None
        media_param = None
        reply_text = reply_raw
        if action_match:
            media_action = action_match.group(1).upper()
            media_param = action_match.group(2).strip()
            reply_text = re.sub(r"\[ACTION:[^\]]+\]", "", reply_raw).strip()

        if not reply_text:
            reply_text = "जी, मैंने आपका काम कर दिया है!"

        # 3. High-speed Cartesia synthesis directly to memory (Zero Disk I/O, 24kHz, Keep-Alive Session)
        active_voice = user_voices.get(chat.id, AVAILABLE_VOICES["friday_001"]["id"])
        tts_bytes = await text_to_speech_bytes(reply_text, voice=active_voice)

        caption = reply_text if len(reply_text) <= 1024 else (reply_text[:1020] + "...")

        if tts_bytes:
            voice_file = InputFile(io.BytesIO(tts_bytes), filename="voice.mp3")
            try:
                await update.message.reply_voice(
                    voice=voice_file,
                    caption=caption,
                    reply_to_message_id=update.message.message_id if is_group else None,
                )
            except Exception as voice_err:
                logger.warning(f"reply_voice fallback: {voice_err}")
                audio_file = InputFile(io.BytesIO(tts_bytes), filename="audio.mp3")
                await update.message.reply_audio(
                    audio=audio_file,
                    caption=caption,
                    reply_to_message_id=update.message.message_id if is_group else None,
                )
        else:
            await update.message.reply_text(reply_text, reply_to_message_id=update.message.message_id if is_group else None)

        # 4. Seamlessly deliver the requested creative media directly into the chat!
        if media_action and media_param:
            loop = asyncio.get_event_loop()
            try:
                if media_action == "IMAGE":
                    img_data = await loop.run_in_executor(None, generate_ai_image, media_param)
                    await update.message.reply_photo(
                        photo=InputFile(io.BytesIO(img_data), filename="ai_image.jpg"),
                        caption=f"🎨 **Friday AI Generated Image**\n📝 `{media_param}`\n\n🛡️ *Verified AI Generated Content*",
                        parse_mode=constants.ParseMode.MARKDOWN,
                    )
                elif media_action == "VIDEO":
                    vid_path = await loop.run_in_executor(None, generate_ai_video, media_param, 15)
                    with open(vid_path, "rb") as f:
                        vid_b = f.read()
                    try:
                        os.remove(vid_path)
                    except Exception:
                        pass
                    await update.message.reply_video(
                        video=InputFile(io.BytesIO(vid_b), filename="ai_video.mp4"),
                        caption=f"🎬 **Friday AI Generated Video**\n📝 `{media_param}`\n\n🛡️ *Verified AI Generated Media*",
                        parse_mode=constants.ParseMode.MARKDOWN,
                    )
                elif media_action == "LOGO":
                    logo_data = await loop.run_in_executor(None, generate_ai_logo, media_param)
                    await update.message.reply_photo(
                        photo=InputFile(io.BytesIO(logo_data), filename="ai_logo.jpg"),
                        caption=f"🏷️ **Friday AI Brand Logo**\n👑 Name: `{media_param}`\n\n🛡️ *Verified AI Design*",
                        parse_mode=constants.ParseMode.MARKDOWN,
                    )
                elif media_action == "EMOJI":
                    emoji_data = await loop.run_in_executor(None, generate_ai_emoji, media_param)
                    await update.message.reply_photo(
                        photo=InputFile(io.BytesIO(emoji_data), filename="ai_emoji.jpg"),
                        caption=f"😃 **Friday Custom 3D Emoji**\n✨ `{media_param}`",
                        parse_mode=constants.ParseMode.MARKDOWN,
                    )
                elif media_action == "FONT":
                    styled = generate_stylish_fonts(media_param)
                    await update.message.reply_text(styled, parse_mode=constants.ParseMode.MARKDOWN)
            except Exception as media_err:
                logger.error(f"Error delivering media action {media_action}: {media_err}")
    except Exception as e:
        logger.error(f"Error processing voice: {e}", exc_info=True)
        await update.message.reply_text(f"वॉइस प्रोसेस करने में त्रुटि: {e}")
    finally:
        stop_action.set()
        await action_task

async def memory_cleanup_job(context: ContextTypes.DEFAULT_TYPE):
    """Periodically purges chats inactive for > 20 minutes to save server RAM."""
    if agent:
        agent.cleanup_expired_memory()

def main():
    global agent

    print("\n" + "="*50)
    print("🚀 Initializing Friday AI Agent (Groups + Channels + Admin + Broadcast)...")
    print("="*50)

    if not validate_config():
        sys.exit(1)

    agent = FridayAgent(api_key=GEMINI_API_KEY)

    request_config = HTTPXRequest(
        connect_timeout=60.0,
        read_timeout=600.0,
        write_timeout=600.0,
        pool_timeout=600.0,
    )

    dashboard = FridayWebDashboard(
        bot_app=None,
        chats_file_path=str(CHATS_FILE),
        group_paused_dict=group_paused,
    )

    async def post_init(application):
        dashboard.bot_app = application
        port = int(os.environ.get("PORT", "8080"))
        await dashboard.start(host="0.0.0.0", port=port)
        logger.info(f"⚡ F.R.I.D.A.Y. Central Web Dashboard active on port {port}")

    async def post_shutdown(application):
        await dashboard.stop()

    app = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .request(request_config)
        .get_updates_request(request_config)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # Basic Commands
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CommandHandler("voice", voice_command))

    # Cognitive, Clock & Web Dashboard Commands
    app.add_handler(CommandHandler("time", time_command))
    app.add_handler(CommandHandler("timezone", timezone_command))
    app.add_handler(CommandHandler("tz", timezone_command))
    app.add_handler(CommandHandler("language", language_command))
    app.add_handler(CommandHandler("lang", language_command))
    app.add_handler(CommandHandler("dashboard", dashboard_command))

    # Media & Creative Commands (Image, Video, Logo, Emoji, Font)
    app.add_handler(CommandHandler("image", image_command))
    app.add_handler(CommandHandler("img", image_command))
    app.add_handler(CommandHandler("video", video_command))
    app.add_handler(CommandHandler("vid", video_command))
    app.add_handler(CommandHandler("logo", logo_command))
    app.add_handler(CommandHandler("emoji", emoji_command))
    app.add_handler(CommandHandler("font", font_command))
    app.add_handler(CommandHandler("text", font_command))

    # Owner & Broadcast Commands
    app.add_handler(CommandHandler("setowner", setowner_command))
    app.add_handler(CommandHandler("transferowner", transferowner_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("broadcast_groups", broadcast_groups_command))
    app.add_handler(CommandHandler("broadcast_channels", broadcast_channels_command))
    app.add_handler(CommandHandler("broadcast_users", broadcast_users_command))

    # Admin & Group Moderation Commands
    app.add_handler(CommandHandler("admin", promote_command))
    app.add_handler(CommandHandler("promote", promote_command))
    app.add_handler(CommandHandler("demote", demote_command))
    app.add_handler(CommandHandler("ban", ban_command))
    app.add_handler(CommandHandler("unban", unban_command))
    app.add_handler(CommandHandler("banall", banall_command))
    app.add_handler(CommandHandler("unbanall", unbanall_command))
    app.add_handler(CommandHandler("mute", mute_command))
    app.add_handler(CommandHandler("unmute", unmute_command))
    app.add_handler(CommandHandler("muteall", muteall_command))
    app.add_handler(CommandHandler("unmuteall", unmuteall_command))
    app.add_handler(CommandHandler("clear", purge_command))
    app.add_handler(CommandHandler("purge", purge_command))
    app.add_handler(CommandHandler("clearchat", purge_command))
    app.add_handler(CommandHandler("tagall", tagall_command))
    app.add_handler(CommandHandler("tag", tagall_command))
    app.add_handler(CommandHandler("mentionall", tagall_command))
    app.add_handler(CommandHandler("stoptag", stoptag_command))
    app.add_handler(CommandHandler("cancel", stoptag_command))
    app.add_handler(CommandHandler("pause", pause_command))
    app.add_handler(CommandHandler("resume", resume_command))

    # Channel & Member Tracking
    app.add_handler(ChatMemberHandler(chat_member_updated, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.ChatType.CHANNEL, channel_post_handler))

    # User & Group Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice_message))

    # Periodic background memory garbage collection (every 5 minutes)
    if app.job_queue:
        app.job_queue.run_repeating(memory_cleanup_job, interval=300, first=60)
        logger.info("Auto-memory cleaner scheduled (20-min TTL purge).")

    print("✅ Friday Bot is LIVE with Owner Broadcast, Group Moderation & Voice AI!")
    print("Press Ctrl+C to stop.")
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
