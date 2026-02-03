"""
Forwarding Handlers - Instant Forward and Forward Old Messages
With Content Type Filters
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
active_sessions = {}
# Background tasks for forwarding old messages
forward_tasks = {}
# Temporary filter state for setup
temp_filters = {}

async def select_mode_callback(client: Client, callback_query: CallbackQuery):
    """Show mode selection menu"""
    user_id = callback_query.from_user.id
    
    # Check connections
    sources = await db.get_user_connections(user_id, "source")
    targets = await db.get_user_connections(user_id, "target")
    
    if not sources or not targets:
        await callback_query.answer("पहले source और target connect करें!", show_alert=True)
        return
    
    session = await db.get_session(user_id)
    current_mode = session.get("mode", "None") if session else "None"
    is_active = session.get("active", False) if session else False
    
    text = f"""
⚙️ **Select Forwarding Mode**

**Current Mode:** {current_mode.replace('_', ' ').title()}
**Status:** {'🟢 Active' if is_active else '🔴 Inactive'}

**Available Modes:**

1️⃣ **Instant Forward (New Messages)**
   - Start करते ही आने वाले **नए messages** forward होंगे
   
2️⃣ **Forward Old Messages (History)**
   - **Old messages** forward करेगा (Reverse order)

_Select a mode to setup filters:_
"""
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("1️⃣ Instant Forward", callback_data="setup_filter_instant"),
            InlineKeyboardButton("2️⃣ Forward Old", callback_data="setup_filter_old")
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="start_menu")]
    ])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)
    await callback_query.answer()


async def setup_filter_callback(client: Client, callback_query: CallbackQuery):
    """Show filter toggle menu"""
    user_id = callback_query.from_user.id
    mode = "instant" if "instant" in callback_query.data else "forward_old"
    
    # Initialize default filters if not set
    if user_id not in temp_filters:
        temp_filters[user_id] = {
            "mode": mode,
            "text": True,
            "photo": True,
            "video": True,
            "document": True,
            "voice": True
        }
    
    # Update mode if changed
    temp_filters[user_id]["mode"] = mode
    filters = temp_filters[user_id]
    
    text = f"""
🛡 **Content Type Filters**

Select kya kya forward karna hai:

1️⃣ **Instant Forward** ke liye
""" if mode == "instant" else f"""
🛡 **Content Type Filters**

Select kya kya forward karna hai:

2️⃣ **Forward Old Messages** ke liye
"""

    # Helper for checkmark
    def status(key):
        return "✅" if filters.get(key) else "❌"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"{status('text')} Text", callback_data="toggle_text"),
            InlineKeyboardButton(f"{status('photo')} Photos", callback_data="toggle_photo")
        ],
        [
            InlineKeyboardButton(f"{status('video')} Videos", callback_data="toggle_video"),
            InlineKeyboardButton(f"{status('document')} Docs", callback_data="toggle_document")
        ],
        [
             InlineKeyboardButton(f"{status('voice')} Audio/Voice", callback_data="toggle_voice")
        ],
        [
            InlineKeyboardButton("▶️ Start Forwarding", callback_data="confirm_filters"),
            InlineKeyboardButton("🔙 Back", callback_data="select_mode")
        ]
    ])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)
    await callback_query.answer()


async def toggle_filter_callback(client: Client, callback_query: CallbackQuery):
    """Toggle a specific filter"""
    user_id = callback_query.from_user.id
    filter_type = callback_query.data.replace("toggle_", "")
    
    if user_id in temp_filters:
        current = temp_filters[user_id].get(filter_type, True)
        temp_filters[user_id][filter_type] = not current
    
    # Refresh menu
    # Re-construct data to call setup_filter_callback logic logic basically reuse
    mode = temp_filters[user_id]["mode"]
    # We can just call setup_filter_callback via a hack or re-render here.
    # Re-rendering to be safe and simple
    await setup_filter_callback(client, callback_query)


async def confirm_filters_callback(client: Client, callback_query: CallbackQuery):
    """Filters confirmed, proceed to start"""
    user_id = callback_query.from_user.id
    
    if user_id not in temp_filters:
        await callback_query.answer("Session expired, please restart", show_alert=True)
        return
        
    filters = temp_filters[user_id]
    mode = filters["mode"]
    
    # Clean temp memory
    # Don't delete yet, need to save to DB in start function
    
    if mode == "instant":
        await start_instant_final(client, callback_query.message, filters)
    else:
        await prepare_forward_old(client, callback_query, filters)


async def start_instant_final(client: Client, message: Message, filters: dict):
    """Final step to start Instant Forward with filters"""
    user_id = message.chat.id  
    
    sources = await db.get_user_connections(user_id, "source")
    targets = await db.get_user_connections(user_id, "target")
    
    source_ids = [s["chat_id"] for s in sources]
    target_ids = [t["chat_id"] for t in targets]
    
    # Save session
    await db.save_session(
        user_id=user_id,
        mode="instant",
        sources=source_ids,
        targets=target_ids,
        keywords=[], # No longer used
        filters=filters,
        active=True
    )
    
    # Update memory
    active_sessions[user_id] = {
        "mode": "instant",
        "sources": source_ids,
        "targets": target_ids,
        "filters": filters
    }
    
    # Readable filters
    enabled = [k.title() for k, v in filters.items() if v and k != "mode"]
    filter_text = ", ".join(enabled) if enabled else "Nothing selected!"
    
    text = f"""
✅ **Instant Forwarding Started!**

📤 **Sources:** {len(sources)}
📥 **Targets:** {len(targets)}
🛡 **Filters:** {filter_text}

Bot ab **New Messages** forward karega based on filters.
"""
    
    if hasattr(message, "edit_text"):
        await message.edit_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⏹ Stop", callback_data="stop_forwarding")],
                [InlineKeyboardButton("🔙 Menu", callback_data="start_menu")]
            ])
        )
    else:
        await message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⏹ Stop", callback_data="stop_forwarding")],
                [InlineKeyboardButton("🔙 Menu", callback_data="start_menu")]
            ])
        )
    
    logger.info(f"User {user_id} started Instant Forward with filters: {filters}")


async def prepare_forward_old(client: Client, callback_query: CallbackQuery, filters: dict):
    """Ask for last message for Forward Old mode"""
    user_id = callback_query.from_user.id
    
    # Set state to waiting for start message
    user_states[user_id] = {
        "action": "wait_for_last_msg",
        "filters": filters
    }
    
    text = """
2️⃣ **Forward Old Messages**

Bot chat history directly read nahi kar sakta.
Isliye, **Source Chat** ka wo **Last Message** forward karein jahan se aap copying start karna chahte hain.

Bot us message se lekar uupar (history) ke messages copy karega.

👉 **Abhi Last Message forward karein...**
"""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="select_mode")]
    ])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)


async def handle_last_msg_input(client: Client, message: Message):
    """Handle the forwarded last message input"""
    user_id = message.from_user.id
    
    if user_id not in user_states:
        return
        
    state = user_states[user_id]
    if state.get("action") != "wait_for_last_msg":
        return
        
    # Check if forwarded
    if not message.forward_from_chat:
        await message.reply_text(
            "❌ Ye message kisi chat se forwarded nahi lag raha.\n"
            "Please source channel/group se message forward karein."
        )
        return
        
    start_msg_id = message.forward_from_message_id
    source_chat_id = message.forward_from_chat.id
    source_title = message.forward_from_chat.title
    filters = state.get("filters", {})
    
    if not start_msg_id:
         await message.reply_text("❌ Message ID detect nahi kar paya. Kya ye channel message hai?")
         return

    # Verify this source is connected
    sources = await db.get_user_connections(user_id, "source")
    connected = False
    for s in sources:
        if s["chat_id"] == source_chat_id:
            connected = True
            break
    
    if not connected:
        await message.reply_text(f"❌ Ye chat ({source_title}) connected sources mein nahi hai!")
        return
    
    # Store filters locally before deleting state
    final_filters = filters.copy() if filters else {}

    del user_states[user_id]
    
    # Start forwarding
    await start_forward_old_task(client, message, source_chat_id, start_msg_id, final_filters)


async def start_forward_old_task(client: Client, message: Message, source_id: int, start_id: int, filters: dict):
    """Initialize Forward Old Task with filters"""
    user_id = message.chat.id
    
    targets = await db.get_user_connections(user_id, "target")
    if not targets:
        await message.reply_text("❌ No blocking targets found!")
        return
        
    target_ids = [t["chat_id"] for t in targets]
    
    # Save session
    await db.save_session(
        user_id=user_id,
        mode="forward_old",
        sources=[source_id],
        targets=target_ids,
        filters=filters,
        active=True
    )
    
    active_sessions[user_id] = {
        "mode": "forward_old",
        "sources": [source_id],
        "targets": target_ids,
        "filters": filters
    }
    
    enabled = [k.title() for k, v in filters.items() if v and k != "mode"]
    filter_text = ", ".join(enabled) if enabled else "None"
    
    await message.reply_text(
        f"🚀 **Forwarding Started!**\n\n"
        f"Source: `{source_id}`\n"
        f"Starting ID: `{start_id}` (Going backwards)\n"
        f"Filters: {filter_text}\n\n"
        f"Check status for updates.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⏹ Stop", callback_data="stop_forwarding")]
        ])
    )
    
    task = asyncio.create_task(
        forward_old_messages_loop(client, user_id, [source_id], target_ids, start_id)
    )
    forward_tasks[user_id] = task
    logger.info(f"User {user_id} started Forward Old from msg {start_id}")


def should_forward_message(message: Message, filters: dict) -> bool:
    """Check if message matches content filters"""
    if not filters:
        return True # Default allow all if no filters set
        
    if message.text and not filters.get("text", True): return False
    if message.photo and not filters.get("photo", True): return False
    if message.video and not filters.get("video", True): return False
    if message.document and not filters.get("document", True): return False
    if (message.voice or message.audio) and not filters.get("voice", True): return False
    
    return True


async def forward_old_messages_loop(client: Client, user_id: int, source_ids: list, target_ids: list, start_id: int = 0):
    """Background task to iterate and forward old messages"""
    logger.info(f"Starting background loop for user {user_id} from ID {start_id}")
    
    total_forwarded = 0
    source_id = source_ids[0]
    current_id = start_id
    
    filters = active_sessions[user_id].get("filters", {})
    
    try:
        while current_id > 0:
            if user_id not in active_sessions: return

            try:
                message = await client.get_messages(source_id, current_id)
                
                if message and not message.empty:
                    # Check Filter
                    if should_forward_message(message, filters):
                        for target_id in target_ids:
                            try:
                                await message.copy(target_id)
                                logger.info(f"Forwarded msg {current_id}")
                            except FloodWait as e:
                                await asyncio.sleep(e.value)
                                await message.copy(target_id)
                            except Exception as e:
                                logger.error(f"Failed to copy {current_id}: {e}")
                        
                        total_forwarded += 1
                        if total_forwarded % 20 == 0:
                            try:
                                await client.send_message(user_id, f"📊 Progress: {total_forwarded} msgs...\nCurrent ID: {current_id}")
                            except: pass
                    else:
                        logger.info(f"Skipped msg {current_id} (Filter mismatch)")
                else:
                    logger.info(f"Msg {current_id} empty/deleted")

            except Exception as e:
                logger.error(f"Error msg {current_id}: {e}")
            
            current_id -= 1
            await asyncio.sleep(1.5) 
                
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        if user_id in active_sessions:
             await client.send_message(user_id, f"✅ **Completed!**\nTotal: {total_forwarded}")
             await db.stop_session(user_id)
             del active_sessions[user_id]


async def forward_message_handler(client: Client, message: Message):
    """Main handler for NEW messages (Instant Forward)"""
    chat_id = message.chat.id
    
    for user_id, session in active_sessions.items():
        if session.get("mode") != "instant": continue
        if chat_id not in session.get("sources", []): continue
            
        targets = session.get("targets", [])
        filters = session.get("filters", {})
        
        should_forward = should_forward_message(message, filters)
        
        if should_forward:
            for target_id in targets:
                try:
                    await message.copy(target_id)
                except Exception as e:
                    logger.error(f"Instant forward failed: {e}")


async def stop_forwarding_callback(client: Client, callback_query: CallbackQuery):
    """Stop forwarding"""
    user_id = callback_query.from_user.id
    await db.stop_session(user_id)
    if user_id in active_sessions: del active_sessions[user_id]
    if user_id in forward_tasks:
        forward_tasks[user_id].cancel()
        del forward_tasks[user_id]
    await callback_query.answer("⏹ Stopped!", show_alert=True)
    from handlers.start import start_callback
    await start_callback(client, callback_query)


# Exports
async def stop_command(client, message): await stop_forwarding_callback(client, message)
async def status_callback(client, cb): 
    uid = cb.from_user.id
    state = "Active" if uid in active_sessions else "Inactive"
    await cb.answer(state, show_alert=True)

async def load_sessions_on_startup():
    global active_sessions
    sessions = await db.get_all_active_sessions()
    for s in sessions:
        active_sessions[s["user_id"]] = s
    logger.info(f"Restored {len(active_sessions)} sessions")

# Placeholders
async def mode_instant_callback(c, m): pass # Replaced by setup_filter_callback
async def handle_keywords_input(c, m): pass # Removed
async def start_instant_all_callback(c, m): pass # Removed
