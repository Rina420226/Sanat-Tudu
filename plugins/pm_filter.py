import asyncio
import re
import ast
import math
import random
import pytz
from datetime import datetime, timedelta, date, time
from database.users_chats_db import db
from pyrogram.errors.exceptions.bad_request_400 import MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty
from Script import script
import pyrogram
from info import *
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto, WebAppInfo
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, UserIsBlocked, MessageNotModified, PeerIdInvalid
from utils import *
from fuzzywuzzy import process, fuzz
from database.users_chats_db import db
from database.ia_filterdb import Media, Media2, get_file_details, get_search_results, get_bad_files
from logging_helper import LOGGER
from urllib.parse import quote_plus
from Lucia.util.file_properties import get_name, get_hash, get_media_file_size
from database.topdb import silentdb
import requests
import string
import tracemalloc
import atexit
import html as _html
import time as _time

tracemalloc.start()
atexit.register(tracemalloc.stop)

TIMEZONE = "Asia/Kolkata"
BUTTON = {}
BUTTONS = {}
FRESH = {}
SPELL_CHECK = {}
SUGGEST_CACHE = {}   # "chat_id:message_id" -> {"items": [...], "ts": float}  (live "did you mean" messages)
_TITLE_CACHE = {"entries": [], "ts": 0.0}   # [(clean_title, frozenset(prefixes))] built from the database
_TITLE_LOCK = asyncio.Lock()
lock = asyncio.Lock()

@Client.on_message(filters.group & filters.text & filters.incoming)
async def give_filter(client, message):
    bot_id = client.me.id
    if EMOJI_MODE:
        try:
            await message.react(emoji=random.choice(REACTIONS))
        except Exception:
            pass
    maintenance_mode = await db.get_maintenance_status(bot_id)
    if maintenance_mode and message.from_user.id not in ADMINS:
        await message.reply_text("ɪ ᴀᴍ ᴄᴜʀʀᴇɴᴛʟʏ ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ 🛠️. ɪ ᴡɪʟʟ ʙᴇ ʙᴀᴄᴋ ꜱᴏᴏɴ 🔜")
        return
    await silentdb.update_top_messages(message.from_user.id, message.text)
    if message.chat.id != SUPPORT_CHAT_ID:
        settings = await get_settings(message.chat.id)
        if settings['auto_ffilter']:
            if re.search(r'https?://\S+|www\.\S+|t\.me/\S+', message.text):
                if await is_check_admin(client, message.chat.id, message.from_user.id):
                    return
                return await message.delete()   
            await auto_filter(client, message)
    else:
        search = message.text
        temp_files, temp_offset, total_results = await get_search_results(chat_id=message.chat.id, query=search.lower(), offset=0, filter=True)
        if total_results == 0:
            return
        else:
            return await message.reply_text(f"<b>Hᴇʏ {message.from_user.mention},\n\nʏᴏᴜʀ ʀᴇǫᴜᴇꜱᴛ ɪꜱ ᴀʟʀᴇᴀᴅʏ ᴀᴠᴀɪʟᴀʙʟᴇ ✅\n\n📂 ꜰɪʟᴇꜱ ꜰᴏᴜɴᴅ : {str(total_results)}\n🔍 ꜱᴇᴀʀᴄʜ :</b> <code>{search}</code>\n\n<b>‼️ ᴛʜɪs ɪs ᴀ <u>sᴜᴘᴘᴏʀᴛ ɢʀᴏᴜᴘ</u> sᴏ ᴛʜᴀᴛ ʏᴏᴜ ᴄᴀɴ'ᴛ ɢᴇᴛ ғɪʟᴇs ғʀᴏᴍ ʜᴇʀᴇ...\n\n📝 ꜱᴇᴀʀᴄʜ ʜᴇʀᴇ : 👇</b>",   
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔍 ᴊᴏɪɴ ᴀɴᴅ ꜱᴇᴀʀᴄʜ ʜᴇʀᴇ 🔎", url=GRP_LNK)]]))


@Client.on_message(filters.private & filters.text & filters.incoming)
async def pm_text(bot, message):
    bot_id = bot.me.id
    content = message.text
    user = message.from_user.first_name
    user_id = message.from_user.id
    if EMOJI_MODE:
        try:
            await message.react(emoji=random.choice(REACTIONS))
        except Exception:
            pass
    maintenance_mode = await db.get_maintenance_status(bot_id)
    if maintenance_mode and message.from_user.id not in ADMINS:
        await message.reply_text("ɪ ᴀᴍ ᴄᴜʀʀᴇɴᴛʟʏ ᴜɴᴅᴇʀ ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ 🛠️. ɪ ᴡɪʟʟ ʙᴇ ʙᴀᴄᴋ ꜱᴏᴏɴ 🔜")
        return
    if content.startswith(("/", "#")):
        return  
    try:
        await silentdb.update_top_messages(user_id, content)
        pm_search = await db.pm_search_status(bot_id)
        if pm_search:
            await auto_filter(bot, message)
        else:
            await message.reply_text(
             text=f"<b><i>ɪ ᴀᴍ ɴᴏᴛ ᴡᴏʀᴋɪɴɢ ʜᴇʀᴇ 🚫.\nᴊᴏɪɴ ᴍʏ ɢʀᴏᴜᴘ ꜰʀᴏᴍ ʙᴇʟᴏᴡ ʙᴜᴛᴛᴏɴ ᴀɴᴅ ꜱᴇᴀʀᴄʜ ᴛʜᴇʀᴇ !</i></b>",   
             reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📝 ꜱᴇᴀʀᴄʜ ʜᴇʀᴇ ", url=GRP_LNK)]])
            )
    except Exception as e:
        LOGGER.error(f"An error occurred: {str(e)}")


async def build_pagination_buttons(btn, total_results, current_offset, next_offset, req, key, settings):
    limit = 10 if settings.get('max_btn') else int(MAX_B_TN)
    total_pages = math.ceil(total_results / limit)
    current_page = math.ceil(current_offset / limit) + 1
    pagination_row = []
    if current_offset > 0:
        prev_offset = max(0, current_offset - limit)
        pagination_row.append(InlineKeyboardButton("⋞ ʙᴀᴄᴋ", callback_data=f"next_{req}_{key}_{prev_offset}"))
    pagination_row.append(InlineKeyboardButton(f"{current_page} / {total_pages}", callback_data="pages"))
    if next_offset is not None and next_offset != 0 and next_offset < total_results:
         pagination_row.append(InlineKeyboardButton("ɴᴇxᴛ ⋟", callback_data=f"next_{req}_{key}_{next_offset}"))
    elif next_offset == 0 and current_offset + limit < total_results:
         pass
    if len(pagination_row) == 1 and pagination_row[0].text.startswith(str(current_page)):
         if total_pages > 1:
             btn.append(pagination_row)
         else:
             btn.append([InlineKeyboardButton(text="↭ ɴᴏ ᴍᴏʀᴇ ᴘᴀɢᴇꜱ ᴀᴠᴀɪʟᴀʙʟᴇ ↭", callback_data="pages")])
    else:
         btn.append(pagination_row)

async def generic_filter_handler(client, query, key, offset, search_query):
    files, n_offset, total_results = await get_search_results(query.message.chat.id, search_query, offset=offset, filter=True)
    if not files:
        await query.answer("🚫 ɴᴏ ꜰɪʟᴇꜱ ᴡᴇʀᴇ ꜰᴏᴜɴᴅ 🚫", show_alert=1)
        return
    temp.GETALL[key] = files
    chat_id = query.message.chat.id
    settings = await get_settings(chat_id)
    req = query.from_user.id
    btn = []
    if settings.get('button'):
        for file in files:
            btn.append([InlineKeyboardButton(
                text=f"{silent_size(file.file_size)} | {extract_tag(file.file_name)} {clean_filename(file.file_name)}",
                callback_data=f'file#{file.file_id}'
            )])
    btn.insert(0, [
        InlineKeyboardButton("ᴘɪxᴇʟ", callback_data=f"qualities#{key}#0"),
        InlineKeyboardButton("ʟᴀɴɢᴜᴀɢᴇ", callback_data=f"languages#{key}#0"),
        InlineKeyboardButton("ꜱᴇᴀꜱᴏɴ",  callback_data=f"seasons#{key}#0")
    ])
    btn.insert(1, [InlineKeyboardButton("📥 Sᴇɴᴅ Aʟʟ 📥", callback_data=f"sendfiles#{key}")])
    await build_pagination_buttons(btn, total_results, offset, n_offset, req, key, settings)
    cap = ""
    if not settings.get('button'):
        curr_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
        time_difference = timedelta(hours=curr_time.hour, minutes=curr_time.minute, seconds=(curr_time.second+(curr_time.microsecond/1000000))) - timedelta(hours=curr_time.hour, minutes=curr_time.minute, seconds=(curr_time.second+(curr_time.microsecond/1000000)))
        remaining_seconds = "{:.2f}".format(time_difference.total_seconds())
        cap = await get_cap(settings, remaining_seconds, files, query, total_results, search_query, offset)
        try:
            await query.message.edit_text(text=cap, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True, parse_mode=enums.ParseMode.HTML)
        except MessageNotModified:
            pass
    else:
        try:
            await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
        except MessageNotModified:
            pass

async def open_category_handler(client, query, items, prefix, title_text):
    try:
        if int(query.from_user.id) not in [query.message.reply_to_message.from_user.id, 0]:
             return await query.answer(
                f"⚠️ ʜᴇʟʟᴏ {query.from_user.first_name},\nᴛʜɪꜱ ɪꜱ ɴᴏᴛ ʏᴏᴜʀ ᴍᴏᴠɪᴇ ʀᴇǫᴜᴇꜱᴛ,\nʀᴇǫᴜᴇꜱᴛ ʏᴏᴜʀ'ꜱ...",
                show_alert=True,
            )
    except Exception:
        pass
    _, key, offset = query.data.split("#")
    btn = []
    for i in range(0, len(items)-1, 2):
        btn.append([
            InlineKeyboardButton(
                text=items[i].title(),
                callback_data=f"{prefix}#{items[i].lower()}#{key}#0"
            ),
            InlineKeyboardButton(
                text=items[i+1].title(),
                callback_data=f"{prefix}#{items[i+1].lower()}#{key}#0"
            ),
        ])
    btn.insert(0, [InlineKeyboardButton(text=f"⇊ {title_text} ⇊", callback_data="ident")])
    btn.append([InlineKeyboardButton(text="↭ ʙᴀᴄᴋ ᴛᴏ ꜰɪʟᴇs ↭", callback_data=f"{prefix}#homepage#{key}#0")])
    await query.edit_message_reply_markup(InlineKeyboardMarkup(btn))

async def filter_selection_handler(client, query, prefix):
    _, value, key, offset = query.data.split("#")
    if not value:
        await query.answer()
        return
    offset = int(offset)
    if value == "homepage":
        search = FRESH.get(key)
    else:
        search = BUTTONS.get(key) if BUTTONS.get(key) else FRESH.get(key)
    if not search:
        await query.answer(script.OLD_ALRT_TXT.format(query.from_user.first_name), show_alert=True)
        return
    search = search.replace("_", " ")
    search = re.sub(r'\s+', ' ', search).strip()
    if value != "homepage":
        category_list = []
        if prefix == "fq":
            category_list = [x for x in QUALITIES if x]
        elif prefix == "fl":
            category_list = [x for x in LANGUAGES if x]
        elif prefix == "fs":
            category_list = [x for x in SEASONS if x]
        is_present = False
        match_pattern = ""
        if prefix == "fs":
            season_search = re.search(r"(?i)season\s*(\d+)", value)
            if season_search:
                season_num = int(season_search.group(1))
                added_regex = f"(s0?{season_num}|season\\s*{season_num})(?:e\\d+)?"
                pattern_combined = re.escape(added_regex)
                if re.search(pattern_combined, search):
                    is_present = True
                    match_pattern = pattern_combined
            else:
                pattern = r'(?i)\b' + re.escape(value) + r'\b'
                if re.search(pattern, search):
                    is_present = True
                    match_pattern = pattern
        elif value.lower().startswith("s") and value[1:].isdigit() and len(value) > 1:
             if value.lower().startswith("s0") and len(value) == 3:
                 short_val = "s" + str(int(value[1:]))
                 added_regex = f"s0?{short_val[1:]}(?:e\\d+)?"
                 pattern_combined = re.escape(added_regex)
                 if re.search(pattern_combined, search):
                     is_present = True
                     match_pattern = pattern_combined
             else:
                pattern = r'(?i)\b' + re.escape(value) + r'\b'
                if re.search(pattern, search):
                    is_present = True
                    match_pattern = pattern
        else:
            pattern = r'(?i)\b' + re.escape(value) + r'\b'
            if re.search(pattern, search):
                is_present = True
                match_pattern = pattern
        if is_present:
            search = re.sub(match_pattern, '', search, count=1)
        else:
            for item in category_list:
                if item.lower() == value.lower():
                    continue
                item_val = item
                if prefix == "fs":
                     season_search = re.search(r"(?i)season\s*(\d+)", item_val)
                     if season_search:
                         season_num = int(season_search.group(1))
                         added_regex = f"(s0?{season_num}|season\\s*{season_num})(?:e\\d+)?"
                         pattern_combined = re.escape(added_regex)
                         search = re.sub(pattern_combined, '', search)
                     elif item_val.lower().startswith("s0") and len(item_val) == 3:
                         short_val = "s" + str(int(item_val[1:]))
                         added_regex = f"s0?{short_val[1:]}(?:e\\d+)?"
                         pattern_combined = re.escape(added_regex)
                         search = re.sub(pattern_combined, '', search)
                     else:
                        pattern = r'(?i)\b' + re.escape(item_val) + r'\b'
                        search = re.sub(pattern, '', search)
                else:
                    pattern = r'(?i)\b' + re.escape(item_val) + r'\b'
                    search = re.sub(pattern, '', search)
            if prefix == "fs":
                 season_search = re.search(r"(?i)season\s*(\d+)", value)
                 if season_search:
                     season_num = int(season_search.group(1))
                     search = f"{search} (s0?{season_num}|season\\s*{season_num})(?:e\\d+)?"
                 else:
                     search = f"{search} {value}"
            elif value.lower().startswith("s") and value[1:].isdigit() and len(value) > 1:
                 if value.lower().startswith("s0") and len(value) == 3:
                     short_val = "s" + str(int(value[1:]))
                     search = f"{search} s0?{short_val[1:]}(?:e\\d+)?"
                 else:
                     search = f"{search} {value}"
            else:
                search = f"{search} {value}"
    search = re.sub(r'\s+', ' ', search).strip()
    BUTTONS[key] = search
    await generic_filter_handler(client, query, key, offset, search)

async def handle_alert_status(client, query, status_text, alert_message, log_hashtag, is_hindi=False):
    ident, from_user = query.data.split("#")
    btn = [[InlineKeyboardButton(status_text, callback_data=f"{ident}alert#{from_user}")]]
    try:
        link = await client.create_chat_invite_link(int(REQST_CHANNEL))
        invite_url = link.invite_link
    except Exception:
        invite_url = GRP_LNK
    btn2 = [[
        InlineKeyboardButton('ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ', url=invite_url),
        InlineKeyboardButton("ᴠɪᴇᴡ ꜱᴛᴀᴛᴜꜱ", url=f"{query.message.link}")
    ]]
    if is_hindi or "Available" in status_text or "Uploaded" in status_text:
         btn2.append([InlineKeyboardButton("🔍 ꜱᴇᴀʀᴄʜ ʜᴇʀᴇ 🔎", url=GRP_LNK)])
    if query.from_user.id in ADMINS:
        user = await client.get_users(from_user)
        reply_markup = InlineKeyboardMarkup(btn)
        content = query.message.text
        await query.message.edit_text(f"<b><strike>{content}</strike></b>")
        await query.message.edit_reply_markup(reply_markup)
        simple_status = status_text.replace("•", "").strip()
        await query.answer(f"Sᴇᴛ ᴛᴏ {simple_status} !")
        content = extract_request_content(query.message.text)
        alert_text = alert_message.format(user_mention=user.mention, content=content)
        try:
            await client.send_message(
                chat_id=int(from_user),
                text=f"{alert_text}\n\n{log_hashtag}",
                reply_markup=InlineKeyboardMarkup(btn2)
            )
        except UserIsBlocked:
             await client.send_message(
                chat_id=int(SUPPORT_CHAT_ID),
                text=f"{alert_text}\n\n{log_hashtag}\n\n<small>Bʟᴏᴄᴋᴇᴅ? Uɴʙʟᴏᴄᴋ ᴛʜᴇ ʙᴏᴛ ᴛᴏ ʀᴇᴄᴇɪᴠᴇ ᴍᴇꜱꜱᴀɢᴇꜱ.</small>",
                reply_markup=InlineKeyboardMarkup(btn2)
            )
    else:
        await query.answer("Yᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ sᴜғғɪᴄɪᴀɴᴛ ʀɪɢʜᴛs ᴛᴏ ᴅᴏ ᴛʜɪs !", show_alert=True)


@Client.on_callback_query(filters.regex(r"^next"))
async def next_page(bot, query):
    try:
        ident, req, key, offset = query.data.split("_")
        if int(req) not in [query.from_user.id, 0]:
            return await query.answer(script.ALRT_TXT.format(query.from_user.first_name), show_alert=True)
        try:
            offset = int(offset)
        except (ValueError, TypeError):
            offset = 0

        if BUTTONS.get(key)!=None:
            search = BUTTONS.get(key)
        else:
            search = FRESH.get(key)

        if not search:
            await query.answer(script.OLD_ALRT_TXT.format(query.from_user.first_name),show_alert=True)
            return

        await generic_filter_handler(bot, query, key, offset, search)
        await query.answer()
    except Exception as e:
        LOGGER.error(f"Error In Next Function - {e}")


@Client.on_callback_query(filters.regex(r"^qualities#"))
async def qualities_cb_handler(client: Client, query: CallbackQuery):
    await open_category_handler(client, query, QUALITIES, "fq", "ꜱᴇʟᴇᴄᴛ ǫᴜᴀʟɪᴛʏ")

@Client.on_callback_query(filters.regex(r"^fq#"))
async def filter_qualities_cb_handler(client: Client, query: CallbackQuery):
    await filter_selection_handler(client, query, "fq")

@Client.on_callback_query(filters.regex(r"^languages#"))
async def languages_cb_handler(client: Client, query: CallbackQuery):
    await open_category_handler(client, query, LANGUAGES, "fl", "ꜱᴇʟᴇᴄᴛ ʟᴀɴɢᴜᴀɢᴇ")

@Client.on_callback_query(filters.regex(r"^fl#"))
async def filter_languages_cb_handler(client: Client, query: CallbackQuery):
    await filter_selection_handler(client, query, "fl")
        
@Client.on_callback_query(filters.regex(r"^seasons#"))
async def season_cb_handler(client: Client, query: CallbackQuery):
    await open_category_handler(client, query, SEASONS, "fs", "ꜱᴇʟᴇᴄᴛ Sᴇᴀsᴏɴ")

@Client.on_callback_query(filters.regex(r"^fs#"))
async def filter_season_cb_handler(client: Client, query: CallbackQuery):
    await filter_selection_handler(client, query, "fs")

# ======================= "No exact results / Did you mean" callbacks =======================
# spol#<imdb_id>#<user>   -> IMDb suggestion picked
# spdb#<user>#<index>     -> database suggestion picked
# spcancel#<user>         -> Cancel button
# NOTE: these must stay above the catch-all `cb_handler` (first matching handler wins).

def _sg_key(msg):
    return f"{msg.chat.id}:{msg.id}"

async def _sg_user_ok(query, user, allow_admin=False):
    """Only the user who searched can press the buttons (bot admins may also cancel)."""
    uid = query.from_user.id
    if int(user) == 0 or uid == int(user) or (allow_admin and uid in ADMINS):
        return True
    await query.answer(script.ALRT_TXT.format(query.from_user.first_name), show_alert=True)
    return False

async def _safe_delete(msg):
    try:
        if msg:
            await msg.delete()
    except Exception:
        pass

async def _sg_failed(query, text="⚠️ Something went wrong, please search again."):
    """Last-resort path so a suggestion button never ends in a silent dead end."""
    try:
        await query.answer(text, show_alert=True)
    except Exception:
        pass
    await _safe_delete(query.message)

async def _run_suggestion(bot, query, title):
    """Search the database for the picked title -> normal results, or an auto-deleting 'Not Found'."""
    orig = query.message.reply_to_message
    if not orig or not orig.from_user:      # the user's original message was deleted
        return await _sg_failed(query, "⚠️ Your original message was deleted, please search again.")
    title = re.sub(r"[:\-]", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    await query.answer(script.TOP_ALRT_MSG)
    files, offset, total_results = await get_search_results(query.message.chat.id, title, offset=0, filter=True)
    if files:
        return await auto_filter(bot, query, (title, files, offset, total_results))
    await _show_not_found(bot, query.message, orig, title, query.from_user)

@Client.on_callback_query(filters.regex(r"^spol#"))
async def advantage_spoll_choker(bot, query):
    try:
        _, imdb_id, user = query.data.split('#')
        if not await _sg_user_ok(query, user):
            return
        entry = SUGGEST_CACHE.pop(_sg_key(query.message), None)
        title = None
        if entry:                                   # title is already known, no extra IMDb call
            title = next((i["title"] for i in entry["items"] if i.get("imdb_id") == imdb_id), None)
        if not title:                               # stateless fallback (e.g. after a bot restart)
            details = await get_poster(imdb_id, id=True)
            title = details.get('title') if details else None
        if not title:
            return await _sg_failed(query)
        await _run_suggestion(bot, query, title)
    except Exception as e:
        LOGGER.error(f"spol callback error: {e}")
        await _sg_failed(query)

@Client.on_callback_query(filters.regex(r"^spdb#"))
async def suggestion_db_choice(bot, query):
    try:
        _, user, idx = query.data.split('#')
        if not await _sg_user_ok(query, user):
            return
        entry = SUGGEST_CACHE.pop(_sg_key(query.message), None)
        if not entry:
            return await _sg_failed(query, "⌛ This suggestion has expired, please search again.")
        await _run_suggestion(bot, query, entry["items"][int(idx)]["title"])
    except Exception as e:
        LOGGER.error(f"spdb callback error: {e}")
        await _sg_failed(query)

@Client.on_callback_query(filters.regex(r"^spcancel#"))
async def suggestion_cancel(bot, query):
    try:
        _, user = query.data.split('#')
        if not await _sg_user_ok(query, user, allow_admin=True):
            return
        SUGGEST_CACHE.pop(_sg_key(query.message), None)
        orig = query.message.reply_to_message
        await query.answer("❌ Cancelled")
        await _safe_delete(query.message)
        await _safe_delete(orig)
    except Exception as e:
        LOGGER.error(f"spcancel callback error: {e}")
        await _sg_failed(query)


@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    lazyData = query.data
    try:
        link = await client.create_chat_invite_link(int(REQST_CHANNEL))
    except Exception:
        pass
    if query.data == "close_data":
        await query.message.delete()     
        
    if query.data.startswith("file"):
        ident, file_id = query.data.split("#")
        user = query.message.reply_to_message.from_user.id
        if int(user) != 0 and query.from_user.id != int(user):
            return await query.answer(script.ALRT_TXT.format(query.from_user.first_name), show_alert=True)
        await query.answer(url=f"https://t.me/{temp.U_NAME}?start=file_{query.message.chat.id}_{file_id}")          
                            
    elif query.data.startswith("sendfiles"):
        clicked = query.from_user.id
        ident, key = query.data.split("#") 
        try:
            await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start=allfiles_{query.message.chat.id}_{key}")
            return
        except UserIsBlocked:
            await query.answer('Uɴʙʟᴏᴄᴋ ᴛʜᴇ ʙᴏᴛ ᴍᴀʜɴ !', show_alert=True)
        except PeerIdInvalid:
            await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start=sendfiles3_{key}")
        except Exception as e:
            LOGGER.error(e)
            await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start=sendfiles4_{key}")
            
    elif query.data.startswith("del"):
        ident, file_id = query.data.split("#")
        files_ = await get_file_details(file_id)
        if not files_:
            return await query.answer('Nᴏ sᴜᴄʜ ғɪʟᴇ ᴇxɪsᴛ.')
        files = files_[0]
        title = files.file_name
        size = get_size(files.file_size)
        f_caption = files.caption
        if CUSTOM_FILE_CAPTION:
            try:
                f_caption = CUSTOM_FILE_CAPTION.format(file_name='' if title is None else title,
                                                       file_size='' if size is None else size,
                                                       file_caption='' if f_caption is None else f_caption)
            except Exception as e:
                LOGGER.error(e)
            f_caption = f_caption
        if f_caption is None:
            f_caption = f"{files.file_name}"
        await query.answer(url=f"https://telegram.me/{temp.U_NAME}?start=file_{file_id}")

    elif query.data == "pages":
        await query.answer()    
    
    elif query.data.startswith("killfilesdq"):
        ident, keyword = query.data.split("#")
        await query.message.edit_text(f"<b>Fetching Files for your query {keyword} on DB... Please wait...</b>")
        files, total = await get_bad_files(keyword)
        await query.message.edit_text("<b>ꜰɪʟᴇ ᴅᴇʟᴇᴛɪᴏɴ ᴘʀᴏᴄᴇꜱꜱ ᴡɪʟʟ ꜱᴛᴀʀᴛ ɪɴ 5 ꜱᴇᴄᴏɴᴅꜱ !</b>")
        await asyncio.sleep(5)
        deleted = 0
        async with lock:
            try:
                for file in files:
                    file_ids = file.file_id
                    file_name = file.file_name
                    result = await Media.collection.delete_one({
                        '_id': file_ids,
                    })
                    if not result.deleted_count and MULTIPLE_DB:
                        result = await Media2.collection.delete_one({
                            '_id': file_ids,
                        })
                    if result.deleted_count:
                        LOGGER.info(f'ꜰɪʟᴇ ꜰᴏᴜɴᴅ ꜰᴏʀ ʏᴏᴜʀ ǫᴜᴇʀʏ {keyword}! ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ {file_name} ꜰʀᴏᴍ ᴅᴀᴛᴀʙᴀꜱᴇ.')
                    deleted += 1
                    if deleted % 20 == 0:
                        await query.message.edit_text(f"<b>ᴘʀᴏᴄᴇꜱꜱ ꜱᴛᴀʀᴛᴇᴅ ꜰᴏʀ ᴅᴇʟᴇᴛɪɴɢ ꜰɪʟᴇꜱ ꜰʀᴏᴍ ᴅʙ. ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ {str(deleted)} ꜰɪʟᴇꜱ ꜰʀᴏᴍ ᴅʙ ꜰᴏʀ ʏᴏᴜʀ ǫᴜᴇʀʏ {keyword} !\n\nᴘʟᴇᴀꜱᴇ ᴡᴀɪᴛ...</b>")
            except Exception as e:
                LOGGER.error(f"Error In killfiledq -{e}")
                await query.message.edit_text(f'Error: {e}')
            else:
                await query.message.edit_text(f"<b>ᴘʀᴏᴄᴇꜱꜱ ᴄᴏᴍᴘʟᴇᴛᴇᴅ ꜰᴏʀ ꜰɪʟᴇ ᴅᴇʟᴇᴛᴀᴛɪᴏɴ !\n\nꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ {str(deleted)} ꜰɪʟᴇꜱ ꜰʀᴏᴍ ᴅʙ ꜰᴏʀ ʏᴏᴜʀ ǫᴜᴇʀʏ {keyword}.</b>")
    
    elif query.data.startswith("show_option"):
        ident, from_user = query.data.split("#")
        btn = [[
                InlineKeyboardButton("• ᴜɴᴀᴠᴀɪʟᴀʙʟᴇ •", callback_data=f"unavailable#{from_user}"),
                InlineKeyboardButton("• ᴜᴘʟᴏᴀᴅᴇᴅ •", callback_data=f"uploaded#{from_user}")
             ],[
                InlineKeyboardButton("• ᴀʟʀᴇᴀᴅʏ ᴀᴠᴀɪʟᴀʙʟᴇ •", callback_data=f"already_available#{from_user}")
             ],[
                InlineKeyboardButton("• ɴᴏᴛ ʀᴇʟᴇᴀꜱᴇᴅ •", callback_data=f"Not_Released#{from_user}"),
                InlineKeyboardButton("• ᴛʏᴘᴇ ᴄᴏʀʀᴇᴄᴛ ꜱᴘᴇʟʟɪɴɢ •", callback_data=f"Type_Correct_Spelling#{from_user}")
             ],[
                InlineKeyboardButton("• ɴᴏᴛ ᴀᴠᴀɪʟᴀʙʟᴇ ɪɴ ʜɪɴᴅɪ •", callback_data=f"Not_Available_In_The_Hindi#{from_user}")
             ]]
        if query.from_user.id in ADMINS:
            reply_markup = InlineKeyboardMarkup(btn)
            await query.message.edit_reply_markup(reply_markup)
            await query.answer("Hᴇʀᴇ ᴀʀᴇ ᴛʜᴇ ᴏᴘᴛɪᴏɴs !")
        else:
            await query.answer("Yᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ sᴜғғɪᴄɪᴀɴᴛ ʀɪɢʜᴛs ᴛᴏ ᴅᴏ ᴛʜɪs !", show_alert=True)
        
    elif query.data.startswith("unavailable"):
        await handle_alert_status(client, query, "• ᴜɴᴀᴠᴀɪʟᴀʙʟᴇ •",
                                  "<b>Hᴇʏ {user_mention},</b>\n\n<u>{content}</u> Hᴀs Bᴇᴇɴ Mᴀʀᴋᴇᴅ Aᴅ ᴜɴᴀᴠᴀɪʟᴀʙʟᴇ...💔",
                                  "#Uɴᴀᴠᴀɪʟᴀʙʟᴇ ⚠️")

    elif query.data.startswith("Not_Released"):
        await handle_alert_status(client, query, "📌 Not Released 📌",
                                  "<b>Hᴇʏ {user_mention}\n\n<code>{content}</code>, ʏᴏᴜʀ ʀᴇǫᴜᴇꜱᴛ ʜᴀꜱ ɴᴏᴛ ʙᴇᴇɴ ʀᴇʟᴇᴀꜱᴇᴅ ʏᴇᴛ</b>",
                                  "#CᴏᴍɪɴɢSᴏᴏɴ...🕊️✌️")

    elif query.data.startswith("Type_Correct_Spelling"):
        await handle_alert_status(client, query, "♨️ Type Correct Spelling ♨️",
                                  "<b>Hᴇʏ {user_mention}\n\nWᴇ Dᴇᴄʟɪɴᴇᴅ Yᴏᴜʀ Rᴇǫᴜᴇsᴛ <code>{content}</code>, Bᴇᴄᴀᴜsᴇ Yᴏᴜʀ Sᴘᴇʟʟɪɴɢ Wᴀs Wʀᴏɴɢ 😢</b>",
                                  "#Wʀᴏɴɢ_Sᴘᴇʟʟɪɴɢ 😑")

    elif query.data.startswith("Not_Available_In_The_Hindi"):
        await handle_alert_status(client, query, " Not Available In The Hindi ",
                                  "<b>Hᴇʏ {user_mention}\n\nYᴏᴜʀ Rᴇǫᴜᴇsᴛ <code>{content}</code> ɪs Nᴏᴛ Aᴠᴀɪʟᴀʙʟᴇ ɪɴ Hɪɴᴅɪ ʀɪɢʜᴛ ɴᴏᴡ. Sᴏ ᴏᴜʀ ᴍᴏᴅᴇʀᴀᴛᴏʀs ᴄᴀɴ'ᴛ ᴜᴘʟᴏᴀᴅ ɪᴛ</b>",
                                  "#Hɪɴᴅɪ_ɴᴏᴛ_ᴀᴠᴀɪʟᴀʙʟᴇ ❌", is_hindi=True)

    elif query.data.startswith("uploaded"):
        await handle_alert_status(client, query, "• ᴜᴘʟᴏᴀᴅᴇᴅ •",
                                  "<b>Hᴇʏ {user_mention},\n\n<u>{content}</u> Yᴏᴜʀ ʀᴇǫᴜᴇꜱᴛ ʜᴀꜱ ʙᴇᴇɴ ᴜᴘʟᴏᴀᴅᴇᴅ ʙʏ ᴏᴜʀ ᴍᴏᴅᴇʀᴀᴛᴏʀs.\nKɪɴᴅʟʏ sᴇᴀʀᴄʜ ɪɴ ᴏᴜʀ Gʀᴏᴜᴘ.</b>",
                                  "#Uᴘʟᴏᴀᴅᴇᴅ✅")

    elif query.data.startswith("already_available"):
        await handle_alert_status(client, query, "• ᴀʟʀᴇᴀᴅʏ ᴀᴠᴀɪʟᴀʙʟᴇ •",
                                  "<b>Hᴇʏ {user_mention},\n\n<u>{content}</u> Yᴏᴜʀ ʀᴇǫᴜᴇꜱᴛ ɪꜱ ᴀʟʀᴇᴀᴅʏ ᴀᴠᴀɪʟᴀʙʟᴇ ɪɴ ᴏᴜʀ ʙᴏᴛ'ꜱ ᴅᴀᴛᴀʙᴀꜱᴇ.\nKɪɴᴅʟʏ sᴇᴀʀᴄʜ ɪɴ ᴏᴜʀ Gʀᴏᴜᴘ.</b>",
                                  "#Aᴠᴀɪʟᴀʙʟᴇ 💗")
            
    
    elif query.data.startswith("alalert"):
        ident, from_user = query.data.split("#")
        if int(query.from_user.id) == int(from_user):
            user = await client.get_users(from_user)
            await query.answer(f"Hᴇʏ {user.first_name}, Yᴏᴜʀ ʀᴇǫᴜᴇꜱᴛ ɪꜱ Aʟʀᴇᴀᴅʏ Aᴠᴀɪʟᴀʙʟᴇ ✅", show_alert=True)
        else:
            await query.answer("Yᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ sᴜғғɪᴄɪᴇɴᴛ ʀɪɢʜᴛs ᴛᴏ ᴅᴏ ᴛʜɪs ❌", show_alert=True)

    elif query.data.startswith("upalert"):
        ident, from_user = query.data.split("#")
        if int(query.from_user.id) == int(from_user):
            user = await client.get_users(from_user)
            await query.answer(f"Hᴇʏ {user.first_name}, Yᴏᴜʀ ʀᴇǫᴜᴇꜱᴛ ɪꜱ Uᴘʟᴏᴀᴅᴇᴅ 🔼", show_alert=True)
        else:
            await query.answer("Yᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ sᴜғғɪᴄɪᴇɴᴛ ʀɪɢʜᴛs ᴛᴏ ᴅᴏ ᴛʜɪs ❌", show_alert=True)

    elif query.data.startswith("unalert"):
        ident, from_user = query.data.split("#")
        if int(query.from_user.id) == int(from_user):
            user = await client.get_users(from_user)
            await query.answer(f"Hᴇʏ {user.first_name}, Yᴏᴜʀ Rᴇǫᴜᴇꜱᴛ ɪꜱ Uɴᴀᴠᴀɪʟᴀʙʟᴇ ⚠️", show_alert=True)
        else:
            await query.answer("Yᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ sᴜғғɪᴄɪᴇɴᴛ ʀɪɢʜᴛs ᴛᴏ ᴅᴏ ᴛʜɪs ❌", show_alert=True)

    elif query.data.startswith("hnalert"):
        ident, from_user = query.data.split("#")
        if int(query.from_user.id) == int(from_user):
            user = await client.get_users(from_user)
            await query.answer(f"Hᴇʏ {user.first_name}, Tʜɪꜱ ɪꜱ Nᴏᴛ Aᴠᴀɪʟᴀʙʟᴇ ɪɴ Hɪɴᴅɪ ❌", show_alert=True)
        else:
            await query.answer("Nᴏᴛ ᴀʟʟᴏᴡᴇᴅ — ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴛʜᴇ ʀᴇǫᴜᴇꜱᴛᴇʀ ❌", show_alert=True)

    elif query.data.startswith("nralert"):
        ident, from_user = query.data.split("#")
        if int(query.from_user.id) == int(from_user):
            user = await client.get_users(from_user)
            await query.answer(f"Hᴇʏ {user.first_name}, Tʜᴇ Mᴏᴠɪᴇ/ꜱʜᴏᴡ ɪꜱ Nᴏᴛ Rᴇʟᴇᴀꜱᴇᴅ Yᴇᴛ 🆕", show_alert=True)
        else:
            await query.answer("Yᴏᴜ ᴄᴀɴ'ᴛ ᴅᴏ ᴛʜɪꜱ ᴀꜱ ʏᴏᴜ ᴀʀᴇ ɴᴏᴛ ᴛʜᴇ ᴏʀɪɢɪɴᴀʟ ʀᴇǫᴜᴇꜱᴛᴇʀ ❌", show_alert=True)

    elif query.data.startswith("wsalert"):
        ident, from_user = query.data.split("#")
        if int(query.from_user.id) == int(from_user):
            user = await client.get_users(from_user)
            await query.answer(f"Hᴇʏ {user.first_name}, Yᴏᴜʀ Rᴇǫᴜᴇꜱᴛ ᴡᴀꜱ ʀᴇᴊᴇᴄᴛᴇᴅ ᴅᴜᴇ ᴛᴏ ᴡʀᴏɴɢ sᴘᴇʟʟɪɴɢ ❗", show_alert=True)
        else:
            await query.answer("Yᴏᴜ ᴅᴏɴ'ᴛ ʜᴀᴠᴇ ᴘᴇʀᴍɪssɪᴏɴ ᴛᴏ sᴇᴇ ᴛʜɪꜱ ❌", show_alert=True)

    
    elif lazyData.startswith("streamfile"):
        _, file_id = lazyData.split(":")
        try:
            user_id = query.from_user.id
            username =  query.from_user.mention 
            silent_msg = await client.send_cached_media(
                chat_id=BIN_CHANNEL,
                file_id=file_id,
            )
            fileName = {quote_plus(get_name(silent_msg))}
            silent_stream = f"{URL}watch/{str(silent_msg.id)}/{quote_plus(get_name(silent_msg))}?hash={get_hash(silent_msg)}"
            silent_download = f"{URL}{str(silent_msg.id)}/{quote_plus(get_name(silent_msg))}?hash={get_hash(silent_msg)}"
            btn= [[
                InlineKeyboardButton("𝖲𝗍𝗋𝖾𝖺𝗆", url=silent_stream),
                InlineKeyboardButton("𝖣𝗈𝗐𝗇𝗅𝗈𝖺𝖽", url=silent_download)        
	    ]]
            await query.edit_message_reply_markup(
                reply_markup=InlineKeyboardMarkup(btn)
	    )
            await silent_msg.reply_text(
                text=f"•• ʟɪɴᴋ ɢᴇɴᴇʀᴀᴛᴇᴅ ꜰᴏʀ ɪᴅ #{user_id} \n•• ᴜꜱᴇʀɴᴀᴍᴇ : {username} \n\n•• ᖴᎥᒪᗴ Nᗩᗰᗴ : {fileName}",
                quote=True,
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup(btn)
	    )                
        except Exception as e:
            LOGGER.error(e)
            await query.answer(f"⚠️ SOMETHING WENT WRONG \n\n{e}", show_alert=True)
            return
           
    
    elif query.data == "pagesn1":
        await query.answer(text=script.PAGE_TXT, show_alert=True)

    elif query.data == "start":
        buttons = [[
                    InlineKeyboardButton('+ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘ +', url=f'http://telegram.me/{temp.U_NAME}?startgroup=true')
                ],[
                    InlineKeyboardButton('♻️ ᴅᴍᴄᴀ', callback_data='disclaimer'),
                    InlineKeyboardButton('🎬 ᴍᴏᴠɪᴇ ɢʀᴏᴜᴘ', url=GRP_LNK)
                ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await client.edit_message_media(
            query.message.chat.id, 
            query.message.id, 
            InputMediaPhoto(random.choice(PICS))
        )
        await query.message.edit_text(
            text=script.START_TXT.format(query.from_user.mention, temp.U_NAME, temp.B_NAME),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
  
    elif query.data == "earn":
        try:
            btn = [[ 
                InlineKeyboardButton('⇋ ʙᴀᴄᴋ ᴛᴏ ʜᴏᴍᴇ ⇋', callback_data='start')
            ]]
            reply_markup = InlineKeyboardMarkup(btn)
            await query.message.edit_text(
                text=script.EARN_INFO.format(temp.B_LINK),
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.HTML
			)
        except Exception as e:
            LOGGER.error(e)
                    
    elif query.data == "me":
        buttons = [[
            InlineKeyboardButton ('🎁 sᴏᴜʀᴄᴇ', callback_data='source'),
        ],[
            InlineKeyboardButton('⇋ ʙᴀᴄᴋ ᴛᴏ ʜᴏᴍᴇ ⇋', callback_data='start')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.ABOUT_TXT.format(temp.U_NAME, temp.B_NAME, OWNER_LNK),
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )
        
    elif query.data == "source":
        buttons = [[
            InlineKeyboardButton('ꜱᴏᴜʀᴄᴇ ᴄᴏᴅᴇ 📜', url='https://github.com/NBBotz/Auto-Filter-Bot.git'),
            InlineKeyboardButton('⇋ ʙᴀᴄᴋ ⇋', callback_data='me')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(
            text=script.SOURCE_TXT,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.HTML
        )

    
    
    elif query.data == "disclaimer":
            btn = [[
                    InlineKeyboardButton("⇋ ʙᴀᴄᴋ ⇋", callback_data="start")
                  ]]
            reply_markup = InlineKeyboardMarkup(btn)
            await query.message.edit_text(
                text=(script.DISCLAIMER_TXT),
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.HTML 
            )
		
    await query.answer(MSG_ALRT)

    
async def auto_filter(client, msg, spoll=False):
    curr_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
    if not spoll:
        message = msg
        if message.text.startswith("/"): return
        if re.findall(r"((^\/|^,|^!|^\.|^[\U0001F600-\U000E007F]).*)", message.text):
            return
        if len(message.text) < 100:
            search = await replace_words(message.text)
            search = search.lower()
            search = search.replace("-", " ")
            search = search.replace(":", "")
            search = search.replace("'", "")
            search = re.sub(r'\s+', ' ', search).strip()
            m=await message.reply_text(f'<b>Wait {message.from_user.mention} Searching Your Query: <i>{search}...</i></b>', reply_to_message_id=message.id)
            files, offset, total_results = await get_search_results(message.chat.id ,search, offset=0, filter=True)
            settings = await get_settings(message.chat.id)
            if not files:
                if not settings["spell_check"]:
                    return await _show_not_found(client, m, message, search, message.from_user)
                if AUTO_SPELL_FIX:
                    ai_sts = await m.edit('🤖 ᴘʟᴇᴀꜱᴇ ᴡᴀɪᴛ, ᴀɪ ɪꜱ ᴄʜᴇᴄᴋɪɴɢ ʏᴏᴜʀ ꜱᴘᴇʟʟɪɴɢ...')
                    is_misspelled = await ai_spell_check(chat_id = message.chat.id,wrong_name=search)
                    if is_misspelled:
                        await ai_sts.edit(f'<b><i>✅ Aɪ Sᴜɢɢᴇsᴛᴇᴅ ᴍᴇ<code> {is_misspelled}</code> \nSᴏ Iᴍ Sᴇᴀʀᴄʜɪɴɢ ғᴏʀ <code>{is_misspelled}</code></i></b>')
                        await asyncio.sleep(2)
                        message.text = is_misspelled
                        await ai_sts.delete()
                        return await auto_filter(client, message)
                    m = ai_sts   # reuse the same message for the suggestion list
                return await advantage_spell_chok(client, message, m, search)
        else:
            return
    else:
        message = msg.message.reply_to_message
        search, files, offset, total_results = spoll
        m=await message.reply_text(f'<b>Wait {message.from_user.mention} Searching You Query:<i>{search}...</i></b>', reply_to_message_id=message.id)
        settings = await get_settings(message.chat.id)
        await msg.message.delete()
    
    key = f"{message.chat.id}-{message.id}"
    FRESH[key] = search
    temp.GETALL[key] = files
    temp.SHORT[message.from_user.id] = message.chat.id
    btn = []
    
    if settings.get('button'):
        for file in files:
            btn.append([InlineKeyboardButton(
                text=f"{silent_size(file.file_size)} | {extract_tag(file.file_name)} {clean_filename(file.file_name)}",
                callback_data=f'file#{file.file_id}'
            )])
    
    btn.insert(0, [
        InlineKeyboardButton("ᴘɪxᴇʟ", callback_data=f"qualities#{key}#0"),
        InlineKeyboardButton("ʟᴀɴɢᴜᴀɢᴇ", callback_data=f"languages#{key}#0"),
        InlineKeyboardButton("ꜱᴇᴀꜱᴏɴ",  callback_data=f"seasons#{key}#0")
    ])
    btn.insert(1, [InlineKeyboardButton("📥 Sᴇɴᴅ Aʟʟ 📥", callback_data=f"sendfiles#{key}")])

    if offset != "":
        req = message.from_user.id if message.from_user else 0
        await build_pagination_buttons(btn, total_results, 0, offset, req, key, settings)
    else:
        btn.append([InlineKeyboardButton(text="↭ ɴᴏ ᴍᴏʀᴇ ᴘᴀɢᴇꜱ ᴀᴠᴀɪʟᴀʙʟᴇ ↭",callback_data="pages")])
    
    imdb = await get_poster(search, file=(files[0]).file_name) if settings["imdb"] else None
    cur_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
    time_difference = timedelta(hours=cur_time.hour, minutes=cur_time.minute, seconds=(cur_time.second+(cur_time.microsecond/1000000))) - timedelta(hours=curr_time.hour, minutes=curr_time.minute, seconds=(curr_time.second+(curr_time.microsecond/1000000)))
    remaining_seconds = "{:.2f}".format(time_difference.total_seconds())
    DELETE_TIME = settings.get("auto_del_time", AUTO_DELETE_TIME)
    TEMPLATE = script.IMDB_TEMPLATE_TXT    
    poster_url = None
    if imdb:
        if IS_LANDSCAPE_POSTER:
            tmdb_data = await fetch_tmdb_data(search, imdb.get('year'))
            if tmdb_data:
                backdrop_url = await get_best_visual(tmdb_data)
                if backdrop_url:
                    poster_url = backdrop_url        
            if not poster_url:
                poster_url = imdb.get('poster')  
        else:
            poster_url = imdb.get('poster')
    if imdb:
        cap = TEMPLATE.format(
            query=search,
            title=imdb['title'],
            votes=imdb['votes'],
            aka=imdb["aka"],
            seasons=imdb["seasons"],
            box_office=imdb['box_office'],
            localized_title=imdb['localized_title'],
            kind=imdb['kind'],
            imdb_id=imdb["imdb_id"],
            cast=imdb["cast"],
            runtime=imdb["runtime"],
            countries=imdb["countries"],
            certificates=imdb["certificates"],
            languages=imdb["languages"],
            director=imdb["director"],
            writer=imdb["writer"],
            producer=imdb["producer"],
            composer=imdb["composer"],
            cinematographer=imdb["cinematographer"],
            music_team=imdb["music_team"],
            distributors=imdb["distributors"],
            release_date=imdb['release_date'],
            year=imdb['year'],
            genres=imdb['genres'],
            poster=imdb['poster'],
            plot=imdb['plot'],
            rating=imdb['rating'],
            url=imdb['url'],
            **locals()
        )
        temp.IMDB_CAP[message.from_user.id] = cap
        if not settings.get('button'):
            for file_num, file in enumerate(files, start=1):
                cap += f"\n\n<b>{file_num}. <a href='https://telegram.me/{temp.U_NAME}?start=file_{message.chat.id}_{file.file_id}'>{get_size(file.file_size)} | {clean_filename(file.file_name)}</a></b>"
    else:
        if settings.get('button'):
            cap = f"<b><blockquote>Hᴇʏ,{message.from_user.mention}</blockquote>\n\n📂 Hᴇʀᴇ I Fᴏᴜɴᴅ Fᴏʀ Yᴏᴜʀ Sᴇᴀʀᴄʜ <code>{search}</code></b>\n\n"
        else:
            cap = f"<b><blockquote>Hᴇʏ,{message.from_user.mention}</blockquote>\n\n📂 Hᴇʀᴇ I Fᴏᴜɴᴅ Fᴏʀ Yᴏᴜʀ Sᴇᴀʀᴄʜ <code>{search}</code></b>\n\n"            
            for file_num, file in enumerate(files, start=1):
                cap += f"<b>{file_num}. <a href='https://telegram.me/{temp.U_NAME}?start=file_{message.chat.id}_{file.file_id}'>{get_size(file.file_size)} | {clean_filename(file.file_name)}\n\n</a></b>"                  
    try:
        if imdb and poster_url:
            try:
                hehe = await message.reply_photo(
                    photo=poster_url,
                    caption=cap, 
                    reply_markup=InlineKeyboardMarkup(btn), 
                    parse_mode=enums.ParseMode.HTML
                )
                await m.delete()
                if settings['auto_delete']:
                    asyncio.create_task(delete_after_delay(hehe, DELETE_TIME))
                    asyncio.create_task(delete_after_delay(message, DELETE_TIME))
            except (MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty):
                pic = imdb.get('poster')
                if pic:
                    poster = pic.replace('.jpg', "._V1_UX360.jpg")
                    hmm = await message.reply_photo(
                        photo=poster, 
                        caption=cap, 
                        reply_markup=InlineKeyboardMarkup(btn), 
                        parse_mode=enums.ParseMode.HTML
                    )
                    await m.delete()
                    if settings['auto_delete']:
                        asyncio.create_task(delete_after_delay(hmm, DELETE_TIME))
                        asyncio.create_task(delete_after_delay(message, DELETE_TIME))
                else:
                    fek = await m.edit_text(
                        text=cap, 
                        reply_markup=InlineKeyboardMarkup(btn), 
                        parse_mode=enums.ParseMode.HTML
                    )
                    if settings['auto_delete']:
                        asyncio.create_task(delete_after_delay(fek, DELETE_TIME))
                        asyncio.create_task(delete_after_delay(message, DELETE_TIME))
            except Exception as e:
                LOGGER.error(e)
                fek = await m.edit_text(
                    text=cap, 
                    reply_markup=InlineKeyboardMarkup(btn), 
                    parse_mode=enums.ParseMode.HTML
                )
                if settings['auto_delete']:
                    asyncio.create_task(delete_after_delay(fek, DELETE_TIME))
                    asyncio.create_task(delete_after_delay(message, DELETE_TIME))
        else:
            fuk = await m.edit_text(
                text=cap, 
                reply_markup=InlineKeyboardMarkup(btn), 
                disable_web_page_preview=True, 
                parse_mode=enums.ParseMode.HTML
            )
            if settings['auto_delete']:
                asyncio.create_task(delete_after_delay(fuk, DELETE_TIME))
                asyncio.create_task(delete_after_delay(message, DELETE_TIME))
    except KeyError:
        await save_group_settings(message.chat.id, 'auto_delete', True)
        pass

async def ai_spell_check(chat_id, wrong_name):
    async def search_movie(wrong_name):
        search_results = await asyncio.to_thread(imdb.search_movie, wrong_name)
        movie_list = [movie.title for movie in search_results.titles]
        return movie_list
    movie_list = await search_movie(wrong_name)
    if not movie_list:
        return
    for _ in range(5):
        closest_match = process.extractOne(wrong_name, movie_list)
        if not closest_match or closest_match[1] <= 80:
            return 
        movie = closest_match[0]
        files, offset, total_results = await get_search_results(chat_id=chat_id, query=movie)
        if files:
            return movie
        movie_list.remove(movie)

# ======================= "No exact results / Did you mean" engine =======================

_JUNK_RE = re.compile(
    r"\b(?:19|20)\d{2}\b|\b(?:480|576|720|1080|2160)p?\b|\b4k\b|\buhd\b|\bs\d{1,2}(?:e\d{1,3})?\b|"
    r"\bseasons?\b|\bepisodes?\b|\bweb ?dl\b|\bwebrip\b|\bweb\b|\bhdrip\b|\bhdtv\b|\bblu ?ray\b|\bbrrip\b|"
    r"\bdvdrip\b|\bhdcam\b|\bcamrip\b|\bpredvd\b|\bhevc\b|\bx26[45]\b|\bh ?26[45]\b|\b10bit\b|"
    r"\b(?:hindi|tamil|telugu|malayalam|kannada|bengali|english|punjabi|marathi|gujarati|dual|multi|audio|"
    r"esubs?|subs?|dubbed|amzn|zee5|hotstar|sonyliv)\b", re.I)

def _suggest_key(text):
    """Lower-case, letters/digits only - used to compare titles."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", (text or "").lower())).strip()

def _suggest_title(name):
    """'[Grp] Kabuliwala (2023) 1080p AMZN WEB-DL' -> 'kabuliwala' (base title without year/quality/language)."""
    t = (name or "").lower()
    t = re.sub(r"https?://\S+|www\.\S+|@\w+|\[[^\]]*\]|\{[^}]*\}", " ", t)
    t = re.sub(r"[._\-+~|:,()']+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    for mt in _JUNK_RE.finditer(t):
        if mt.start() >= 3:                       # ignore junk words that are part of the title start
            t = t[:mt.start()]
            break
    t = _suggest_key(t)
    return t if len(t) >= 3 else ""

async def _rebuild_title_index():
    async with _TITLE_LOCK:
        if _TITLE_CACHE["entries"] and _time.monotonic() - _TITLE_CACHE["ts"] < SUGGEST_REFRESH:
            return                                  # somebody else just refreshed it
        try:
            titles = set()
            cols = [Media.collection] + ([Media2.collection] if MULTIPLE_DB else [])
            for col in cols:
                n = 0
                async for doc in col.find({}, {"file_name": 1}):
                    t = _suggest_title(doc.get("file_name") or "")
                    if t:
                        titles.add(t)
                    n += 1
                    if n % 2000 == 0:
                        await asyncio.sleep(0)      # keep the bot responsive while scanning
            _TITLE_CACHE["entries"] = [(t, frozenset(w[:3] for w in t.split() if len(w) >= 3)) for t in titles]
            _TITLE_CACHE["ts"] = _time.monotonic()
        except Exception as e:
            LOGGER.error(f"title index build failed: {e}")

async def _get_title_index():
    if not _TITLE_CACHE["entries"]:                 # first use: wait for the build
        if _TITLE_LOCK.locked():
            async with _TITLE_LOCK:
                pass
        else:
            await _rebuild_title_index()
    elif _time.monotonic() - _TITLE_CACHE["ts"] >= SUGGEST_REFRESH and not _TITLE_LOCK.locked():
        asyncio.create_task(_rebuild_title_index())  # stale: serve old data, refresh in background
    return _TITLE_CACHE["entries"]

async def _db_fuzzy_titles(query, limit):
    """Close titles that really exist in the database (typo tolerant)."""
    q = _suggest_key(query)
    if len(q) < 3 or limit <= 0:
        return []
    entries = await _get_title_index()
    if not entries:
        return []
    def _work():
        qp = {w[:3] for w in q.split() if len(w) >= 3}
        cands = [t for t, p in entries if p & qp]
        if not cands:
            return []
        res = process.extract(q, cands, scorer=fuzz.WRatio, limit=limit * 3)
        return [t for t, score in res if score >= SUGGEST_MIN_SCORE]
    return await asyncio.to_thread(_work)

async def _build_suggestions(search):
    """IMDb matches first, then close titles from the database. One entry per title (no variants)."""
    base = _suggest_title(search) or search
    items, seen = [], []                            # seen = [(title_key, year)]
    try:
        movies = await get_poster(base, bulk=True)
    except Exception as e:
        LOGGER.error(f"IMDb suggestion lookup failed: {e}")
        movies = None
    for mv in (movies or []):
        title = getattr(mv, "title", None)
        imdb_id = getattr(mv, "imdb_id", None)
        year = getattr(mv, "year", None)
        if not title or not imdb_id:
            continue
        key = _suggest_key(title)
        if (key, year) in seen:
            continue
        items.append({"title": title, "year": year, "imdb_id": str(imdb_id)})
        seen.append((key, year))
        if len(items) >= SUGGEST_MAX:
            break
    if SUGGEST_DB_FUZZY and len(items) < SUGGEST_MAX:
        try:
            hits = await _db_fuzzy_titles(base, SUGGEST_MAX - len(items))
        except Exception as e:
            LOGGER.error(f"database suggestion lookup failed: {e}")
            hits = []
        for t in hits:
            if any(fuzz.ratio(t, k) >= 85 for k, _ in seen):
                continue
            items.append({"title": t.title(), "year": None, "imdb_id": None})
            seen.append((t, None))
            if len(items) >= SUGGEST_MAX:
                break
    return items

async def _show_not_found(client, bot_msg, orig_msg, title, requester=None):
    """'Not Found' notice that deletes itself (and the user's query) after NOT_FOUND_DELETE_TIME seconds."""
    if NO_RESULTS_MSG and requester:
        try:
            await client.send_message(BIN_CHANNEL, script.NORSLTS.format(requester.id, requester.mention, _html.escape(title)))
        except Exception as e:
            LOGGER.error(e)
    text = script.NOT_FOUND_TXT.format(title=_html.escape(title)[:80], sec=NOT_FOUND_DELETE_TIME)
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("🔰 Cʟɪᴄᴋ ʜᴇʀᴇ & ʀᴇǫᴜᴇsᴛ ᴛᴏ ᴀᴅᴍɪɴ🔰", url=OWNER_LNK)]])
    sent = None
    try:
        if bot_msg:
            sent = await bot_msg.edit_text(text, reply_markup=markup, parse_mode=enums.ParseMode.HTML)
    except Exception:
        sent = None
    if sent is None:
        try:
            sent = await orig_msg.reply_text(text, reply_markup=markup, parse_mode=enums.ParseMode.HTML)
        except Exception as e:
            LOGGER.error(e)
    if sent:
        asyncio.create_task(delete_after_delay(sent, NOT_FOUND_DELETE_TIME))
    if orig_msg:
        asyncio.create_task(delete_after_delay(orig_msg, NOT_FOUND_DELETE_TIME))

async def _expire_suggestion(sent, orig):
    """Remove an unused suggestion message; does nothing if the user already clicked/cancelled."""
    await asyncio.sleep(SUGGEST_DELETE_TIME)
    if SUGGEST_CACHE.pop(_sg_key(sent), None) is None:
        return
    await _safe_delete(sent)
    await _safe_delete(orig)

async def advantage_spell_chok(client, message, m=None, search=None):
    """'No exact results ... Did you mean one of these?' message with clickable suggestions."""
    search = search or (message.text or "").strip()
    user = message.from_user.id if message.from_user else 0
    items = await _build_suggestions(search)
    if not items:                                   # nothing similar anywhere -> Not Found
        return await _show_not_found(client, m, message, search, message.from_user)
    rows = []
    for i, it in enumerate(items):
        label = f"🔍 {it['title']}" + (f" ({it['year']})" if it.get("year") else "")
        cb = f"spol#{it['imdb_id']}#{user}" if it.get("imdb_id") else f"spdb#{user}#{i}"
        rows.append([InlineKeyboardButton(label[:60], callback_data=cb)])
    rows.append([InlineKeyboardButton("❌ Cancel", callback_data=f"spcancel#{user}")])
    text = script.SUGGEST_TXT.format(query=_html.escape(message.text or search)[:60])
    markup = InlineKeyboardMarkup(rows)
    try:
        if m:
            sent = await m.edit_text(text, reply_markup=markup, parse_mode=enums.ParseMode.HTML)
        else:
            sent = await message.reply_text(text, reply_markup=markup, parse_mode=enums.ParseMode.HTML, reply_to_message_id=message.id)
    except Exception as e:
        LOGGER.error(f"could not send suggestions: {e}")
        return await _show_not_found(client, None, message, search, message.from_user)
    now = _time.monotonic()
    for k in [k for k, v in SUGGEST_CACHE.items() if now - v["ts"] > SUGGEST_DELETE_TIME * 2]:
        SUGGEST_CACHE.pop(k, None)                  # housekeeping
    SUGGEST_CACHE[_sg_key(sent)] = {"items": items, "ts": now}
    asyncio.create_task(_expire_suggestion(sent, message))
