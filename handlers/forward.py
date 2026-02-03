"""
Forwarding Handlers - Wizard Style UI
Hub -> Filters / Sources / Targets -> Start
"""

import asyncio
from pyrogram import Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait
from database.mongo import db
from utils.helpers import check_admin_status
from handlers.connect import user_states
from utils.logger import logger

# Active forwarding sessions
# Key: user_id, Value: {mode, sources, targets, filters, active}
active_sessions = {}

# Background tasks for forwarding old messages
forward_tasks = {}

# Temporary session state for setup (The "Wizard" state)
# Key: user_id, Value: {mode, sources:[], targets:[], filters:{...}}
temp_sessions = {}

async def select_mode_callback(client: Client, callback_query: CallbackQuery):
    """Step 1: Show Mode Selection"""
    user_id = callback_query.from_user.id
    
    # Initialize temp session
    temp_sessions[user_id] = {
        "mode": None,
        "sources": [],
        "targets": [], 
        "filters": {
            "text": True, "photo": True, "video": True, 
            "document": True, "voice": True
        }
    }
    
    # Pre-select all connected chats by default
    sources = await db.get_user_connections(user_id, "source")
    targets = await db.get_user_connections(user_id, "target")
    
    temp_sessions[user_id]["sources"] = [s["chat_id"] for s in sources]
    temp_sessions[user_id]["targets"] = [t["chat_id"] for t in targets]

    text = """
⚙️ **Select Forwarding Mode**

Select a mode to configure your session:

1️⃣ **Instant Forward (New Messages)**
   - Real-time forwarding of new messages
   
2️⃣ **Forward Old Messages (History)**
   - Forward past messages (Reverse order)
"""
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("1️⃣ Instant Forward", callback_data="setup_hub_instant"),
            InlineKeyboardButton("2️⃣ Forward Old", callback_data="setup_hub_old")
        ],
        [InlineKeyboardButton("🔙 Broad Menu", callback_data="start_menu")]
    ])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)


async def setup_hub_callback(client: Client, callback_query: CallbackQuery):
    """Step 2: Session Hub (Central Config)"""
    user_id = callback_query.from_user.id
    data = callback_query.data
    
    if user_id not in temp_sessions:
        await select_mode_callback(client, callback_query) # Restart if expired
        return

    # Set mode if coming from select_mode
    if "instant" in data:
        temp_sessions[user_id]["mode"] = "instant"
    elif "old" in data:
        temp_sessions[user_id]["mode"] = "forward_old"
        
    session = temp_sessions[user_id]
    mode_name = "Instant Forward" if session["mode"] == "instant" else "Forward Old"
    
    # Counts
    src_count = len(session["sources"])
    tgt_count = len(session["targets"])
    
    # Filter summary
    filters = session["filters"]
    enabled_filters = [k.title() for k, v in filters.items() if v]
    filter_text = ", ".join(enabled_filters) if enabled_filters else "None"
    
    text = f"""
⚙️ **Session Configuration: {mode_name}**

Configure your settings before starting:

🛡 **Filters:** {filter_text}
📤 **Sources:** {src_count} selected
📥 **Targets:** {tgt_count} selected

_Click buttons below to edit:_
"""

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛡 Edit Filters", callback_data="menu_filters")],
        [
            InlineKeyboardButton(f"📤 Sources ({src_count})", callback_data="menu_sources"),
            InlineKeyboardButton(f"📥 Targets ({tgt_count})", callback_data="menu_targets")
        ],
        [InlineKeyboardButton("▶️ START FORWARDING", callback_data="start_session")],
        [InlineKeyboardButton("🔙 Back to Modes", callback_data="select_mode")]
    ])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)


async def menu_filters_callback(client: Client, callback_query: CallbackQuery):
    """Filter Toggle Menu"""
    user_id = callback_query.from_user.id
    if user_id not in temp_sessions: return
    
    filters = temp_sessions[user_id]["filters"]
    
    def status(key): return "✅" if filters.get(key) else "❌"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"{status('text')} Text", callback_data="toggle_filter_text"),
            InlineKeyboardButton(f"{status('photo')} Photos", callback_data="toggle_filter_photo")
        ],
        [
            InlineKeyboardButton(f"{status('video')} Videos", callback_data="toggle_filter_video"),
            InlineKeyboardButton(f"{status('document')} Docs", callback_data="toggle_filter_document")
        ],
        [InlineKeyboardButton(f"{status('voice')} Audio/Voice", callback_data="toggle_filter_voice")],
        [InlineKeyboardButton("🔙 Back to Hub", callback_data="setup_hub")]
    ])
    
    await callback_query.message.edit_text("🛡 **Edit Filters**\n\nToggle content types:", reply_markup=keyboard)


async def toggle_filter_callback(client: Client, callback_query: CallbackQuery):
    """Toggle filter state"""
    user_id = callback_query.from_user.id
    if user_id not in temp_sessions: return
    
    f_type = callback_query.data.replace("toggle_filter_", "")
    current = temp_sessions[user_id]["filters"].get(f_type, True)
    temp_sessions[user_id]["filters"][f_type] = not current
    
    await menu_filters_callback(client, callback_query)


async def menu_chat_selection(client: Client, callback_query: CallbackQuery, is_source: bool):
    """Generic Chat Selection Menu Source/Target"""
    user_id = callback_query.from_user.id
    if user_id not in temp_sessions: return
    
    session = temp_sessions[user_id]
    chat_type = "source" if is_source else "target"
    selected_list = session["sources"] if is_source else session["targets"]
    
    # Fetch all connected chats
    all_connected = await db.get_user_connections(user_id, chat_type)
    
    text = f"📤 **Select Sources**" if is_source else f"📥 **Select Targets**"
    text += "\n\nTick chats to include in this session:"
    
    buttons = []
    for chat in all_connected:
        is_selected = chat["chat_id"] in selected_list
        mark = "✅" if is_selected else "❌"
        # callback: toggle_chat_source_12345 or toggle_chat_target_12345
        cb_data = f"toggle_chat_{chat_type}_{chat['chat_id']}"
        buttons.append([InlineKeyboardButton(f"{mark} {chat['chat_title']}", callback_data=cb_data)])
        
    buttons.append([InlineKeyboardButton("🔙 Back to Hub", callback_data="setup_hub")])
    
    await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))


async def toggle_chat_callback(client: Client, callback_query: CallbackQuery):
    """Toggle chat selection"""
    user_id = callback_query.from_user.id
    if user_id not in temp_sessions: return
    
    data = callback_query.data # toggle_chat_source_12345
    parts = data.split("_") # ['toggle', 'chat', 'source', '12345']
    chat_type = parts[2]
    try:
        chat_id = int(parts[3])
    except:
        chat_id = int(f"-{parts[4]}") # Handle negative IDs if split messed up? unlikely with _ separator if id has -
        # Actually pyrogram buttons might have issue with - in callback data if we aren't careful.
        # But let's assume standard split works. If ID is negative, split might give ['...', 'source', '-100...']
        # No, update: split("_") on "toggle_chat_source_-100123" gives ['toggle', 'chat', 'source', '-100123']
        chat_id = int(parts[3])

    selected_list = temp_sessions[user_id]["sources"] if chat_type == "source" else temp_sessions[user_id]["targets"]
    
    if chat_id in selected_list:
        selected_list.remove(chat_id)
    else:
        selected_list.append(chat_id)
        
    # Refresh menu
    await menu_chat_selection(client, callback_query, is_source=(chat_type=="source"))


async def start_session_callback(client: Client, callback_query: CallbackQuery):
    """Start the configured session"""
    user_id = callback_query.from_user.id
    if user_id not in temp_sessions: return
    
    session = temp_sessions[user_id]
    
    if not session["sources"]:
        await callback_query.answer("❌ Select at least one Source!", show_alert=True)
        return
    if not session["targets"]:
        await callback_query.answer("❌ Select at least one Target!", show_alert=True)
        return
        
    # Save to DB
    await db.save_session(
        user_id=user_id,
        mode=session["mode"],
        sources=session["sources"],
        targets=session["targets"],
        filters=session["filters"],
        active=True
    )
    
    # Update Active Memory
    active_sessions[user_id] = session.copy()
    active_sessions[user_id]["active"] = True
    
    # Clear temp
    del temp_sessions[user_id]
    
    if session["mode"] == "instant":
        await show_instant_started(client, callback_query.message, session)
    else:
        await prepare_forward_old(client, callback_query.message, session)


async def show_instant_started(client, message, session):
    text = f"""
✅ **Instant Forwarding Started!**

📤 **Sources:** {len(session['sources'])}
📥 **Targets:** {len(session['targets'])}
🛡 **Filters Active**

Bot is now forwarding new messages.
"""
    await message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⏹ Stop", callback_data="stop_forwarding")]
        ])
    )
    logger.info(f"User {message.chat.id} started Instant Forward")


async def prepare_forward_old(client, message, session):
    """Ask for last message for Forward Old mode"""
    user_id = message.chat.id
    
    # Set state to wait for input
    # We need to temporarily store the session config in user_states because active_sessions is for RUNNING sessions
    # Actually we already saved to active_sessions/DB. 
    # So we just need to wait for the trigger message.
    
    user_states[user_id] = {
        "action": "wait_for_last_msg"
        # Config is already in active_sessions[user_id]
    }
    
    text = """
2️⃣ **Forward Old Messages**

**Step 2:**
Please **Forward the Last Message** (oldest one you want to start from) from the **Source Chat**.
Bot will start copying from there and move backwards (upwards).

👉 **Forward Message Now...**
"""
    await message.edit_text(
        text, 
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="stop_forwarding")]])
    )


async def handle_last_msg_input(client: Client, message: Message):
    """Handle the forwarded last message input"""
    user_id = message.from_user.id
    
    if user_id not in user_states: return
    state = user_states[user_id]
    if state.get("action") != "wait_for_last_msg": return
    
    # Check if forwarded
    if not message.forward_from_chat:
        await message.reply_text("❌ Please forward a message from a Channel/Group.")
        return
        
    start_msg_id = message.forward_from_message_id
    source_chat_id = message.forward_from_chat.id
    
    # Check if this source matches SELECTED sources
    session = active_sessions.get(user_id)
    if not session:
        await message.reply_text("❌ Session not found. Restart bot.")
        return
        
    if source_chat_id not in session["sources"]:
        await message.reply_text(f"❌ This chat is not in your selected Sources list!")
        return
        
    del user_states[user_id]
    
    # Only single source supported for Old Mode parallel task (simplicity)
    # But our architecture allows list. We will just start task for this list.
    # Note: If user selected multiple sources, they have to provide start msg for EACH?
    # Complex. Let's assume for OLD mode, user picks ONE source usually. 
    # Or, we just start the loop for the source matching this message.
    
    await message.reply_text(
        f"🚀 **Forwarding Started!**\nStart ID: {start_msg_id}",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⏹ Stop", callback_data="stop_forwarding")]])
    )
    
    task = asyncio.create_task(
        forward_old_messages_loop(client, user_id, [source_chat_id], session["targets"], start_msg_id)
    )
    forward_tasks[user_id] = task


# ---------------- Logic Helpers ----------------

def should_forward_message(message: Message, filters: dict) -> bool:
    if not filters: return True
    if message.text and not filters.get("text", True): return False
    if message.photo and not filters.get("photo", True): return False
    if message.video and not filters.get("video", True): return False
    if message.document and not filters.get("document", True): return False
    if (message.voice or message.audio) and not filters.get("voice", True): return False
    return True

async def forward_old_messages_loop(client, user_id, source_ids, target_ids, start_id):
    logger.info(f"Starting loop User={user_id} Source={source_ids[0]}")
    source_id = source_ids[0]
    current_id = start_id
    total = 0
    filters = active_sessions[user_id]["filters"]
    
    try:
        while current_id > 0:
            if user_id not in active_sessions: return
            try:
                msg = await client.get_messages(source_id, current_id)
                if msg and not msg.empty:
                    if should_forward_message(msg, filters):
                        for tid in target_ids:
                            try:
                                await msg.copy(tid)
                            except FloodWait as e:
                                await asyncio.sleep(e.value)
                                await msg.copy(tid)
                            except Exception as e:
                                logger.error(f"Copy failed: {e}")
                        total += 1
                        if total % 20 == 0:
                            try: await client.send_message(user_id, f"📊 Progress: {total} msgs...")
                            except: pass
            except Exception as e:
                logger.error(f"Error {current_id}: {e}")
            current_id -= 1
            await asyncio.sleep(1.5)
    except Exception as e:
         logger.error(f"Loop fatal: {e}")
    finally:
         if user_id in active_sessions:
             await client.send_message(user_id, "✅ Done!")
             await stop_forwarding_callback(None, None, user_id_override=user_id)

async def forward_message_handler(client, message):
    """Instant Forward Logic"""
    chat_id = message.chat.id
    for uid, session in active_sessions.items():
        if session["mode"] != "instant": continue
        if chat_id not in session["sources"]: continue
        if should_forward_message(message, session["filters"]):
            for tid in session["targets"]:
                try: await message.copy(tid)
                except: pass

async def stop_forwarding_callback(client, callback_query, user_id_override=None):
    user_id = user_id_override or callback_query.from_user.id
    await db.stop_session(user_id)
    if user_id in active_sessions: del active_sessions[user_id]
    if user_id in forward_tasks:
        forward_tasks[user_id].cancel()
        del forward_tasks[user_id]
    
    if callback_query:
        await callback_query.answer("⏹ Stopped!", show_alert=True)
        from handlers.start import start_callback
        await start_callback(client, callback_query)

# Exports & Placeholders for safe imports
async def stop_command(c, m): await stop_forwarding_callback(c, None, m.from_user.id)
async def status_callback(c, cb): await cb.answer("Active" if cb.from_user.id in active_sessions else "Inactive")
async def load_sessions_on_startup():
    global active_sessions
    for s in await db.get_all_active_sessions(): active_sessions[s["user_id"]] = s

# Interface Wrappers
async def setup_filter_callback(c, cb): pass # replaced by hub
async def mode_instant_callback(c, cb): pass 
async def confirm_filters_callback(c, cb): pass
