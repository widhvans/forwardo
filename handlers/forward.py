"""
Forwarding Handlers - Instant Forward and Forward Old Messages
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
   - Text, Media, Files सब support करता है
   - Optional: Specific keywords set कर सकते हैं
   
2️⃣ **Forward Old Messages (History)**
   - **Old messages** (History) forward करेगा
   - Last message से शुरू होकर पीछे (Reverse) जाएगा
   - धीरे-धीरे एक-एक करके forward करेगा
"""
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("1️⃣ Instant Forward", callback_data="mode_instant"),
            InlineKeyboardButton("2️⃣ Forward Old", callback_data="mode_forward_old")
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="start_menu")]
    ])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)
    await callback_query.answer()


async def mode_instant_callback(client: Client, callback_query: CallbackQuery):
    """Setup Instant Forward mode (was Intent)"""
    user_id = callback_query.from_user.id
    
    # Set user state for keyword input if they want
    user_states[user_id] = {"action": "set_keywords"}
    
    text = """
1️⃣ **Instant Forward Mode**

यह mode **नए messages** forward करेगा।

क्या आप specific keywords use करना चाहते हैं?
(Example: movie, series, urgent)

अगर **हाँ**, तो keywords भेजें (comma separated).
अगर **नहीं** (Sab kuch forward karna hai), तो "Skip" click करें।
"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⏭ Skip (Forward All)", callback_data="start_instant_all")],
        [InlineKeyboardButton("❌ Cancel", callback_data="select_mode")]
    ])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)
    await callback_query.answer()


async def handle_keywords_input(client: Client, message: Message):
    """Handle keywords input"""
    user_id = message.from_user.id
    
    if user_id not in user_states:
        return
    
    state = user_states[user_id]
    if state.get("action") != "set_keywords":
        return
    
    # Parse keywords
    keywords = [k.strip().lower() for k in message.text.split(",") if k.strip()]
    
    if not keywords:
        await message.reply_text("❌ Valid characters use करें!")
        return
    
    # Clear state
    del user_states[user_id]
    
    await start_instant_final(client, message, keywords)


async def start_instant_all_callback(client: Client, callback_query: CallbackQuery):
    """Start Instant Forward without keywords"""
    await start_instant_final(client, callback_query.message, [])


async def start_instant_final(client: Client, message: Message, keywords: list):
    """Final step to start Instant Forward"""
    user_id = message.chat.id  # For message object, chat.id is user_id in private
    
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
        keywords=keywords,
        active=True
    )
    
    # Update memory
    active_sessions[user_id] = {
        "mode": "instant",
        "sources": source_ids,
        "targets": target_ids,
        "keywords": keywords
    }
    
    keyword_text = ", ".join(keywords) if keywords else "All Messages"
    
    text = f"""
✅ **Instant Forwarding Started!**

📤 **Sources:** {len(sources)}
📥 **Targets:** {len(targets)}
🔑 **Filter:** {keyword_text}

Bot अब **नए messages** forward करेगा।
"""
    
    # If message is CallbackQuery message (message.edit_text works)
    # If standard message (message.reply_text)
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
    
    logger.info(f"User {user_id} started Instant Forward. Keywords: {keywords}")


async def mode_forward_old_callback(client: Client, callback_query: CallbackQuery):
    """Setup Forward Old Messages mode"""
    user_id = callback_query.from_user.id
    
    sources = await db.get_user_connections(user_id, "source")
    
    text = f"""
2️⃣ **Forward Old Messages**

यह mode **History** (Old messages) forward करेगा।
Bot **Last Message** से शुरू करके **First Message** तक (Reverse order) जाएगा।

⚠️ **Note:**
- यह process slow हो सकता है (Telegram Limits)
- Large chats में time लगेगा
- Progress logs मिलते रहेंगे

📤 **Sources ({len(sources)}):**
"""
    for s in sources:
        text += f"• {s['chat_title']}\n"
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("▶️ Start Forwarding", callback_data="start_forward_old")],
        [InlineKeyboardButton("❌ Cancel", callback_data="select_mode")]
    ])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)
    await callback_query.answer()


async def start_forward_old_callback(client: Client, callback_query: CallbackQuery):
    """Start Forward Old Messages task"""
    user_id = callback_query.from_user.id
    
    sources = await db.get_user_connections(user_id, "source")
    targets = await db.get_user_connections(user_id, "target")
    
    source_ids = [s["chat_id"] for s in sources]
    target_ids = [t["chat_id"] for t in targets]
    
    # Save session
    await db.save_session(
        user_id=user_id,
        mode="forward_old",
        sources=source_ids,
        targets=target_ids,
        keywords=[],
        active=True
    )
    
    active_sessions[user_id] = {
        "mode": "forward_old",
        "sources": source_ids,
        "targets": target_ids
    }
    
    await callback_query.message.edit_text(
        "🚀 **Forwarding Started (Old Messages)!**\n\nCheck logs for progress...",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⏹ Stop", callback_data="stop_forwarding")],
            [InlineKeyboardButton("📊 Status", callback_data="status")]
        ])
    )
    
    # Start background task
    task = asyncio.create_task(forward_old_messages_loop(client, user_id, source_ids, target_ids))
    forward_tasks[user_id] = task
    logger.info(f"User {user_id} started Forward Old Messages")


async def forward_old_messages_loop(client: Client, user_id: int, source_ids: list, target_ids: list):
    """Background task to iterate and forward old messages"""
    logger.info(f"Starting background loop for user {user_id}")
    
    total_forwarded = 0
    
    try:
        for source_id in source_ids:
            # Check if stopped
            if user_id not in active_sessions or active_sessions[user_id]["mode"] != "forward_old":
                break
                
            logger.info(f"Processing source {source_id} for user {user_id}")
            
            # Get last message ID
            last_msg_id = 0
            async for msg in client.get_chat_history(source_id, limit=1):
                last_msg_id = msg.id
            
            if last_msg_id == 0:
                continue
            
            logger.info(f"Source {source_id} last message ID: {last_msg_id}")
            
            # Iterate backwards
            # Batch size for efficiency? iterating 1 by 1 is safe but slow.
            # User asked: "vo us chat id ka last msg id le leta hai then uski link me se id numer se ek ke krke kam krta tha"
            # Implies 1 by 1 iteration.
            
            current_id = last_msg_id
            
            while current_id > 0:
                # Check stop signal
                if user_id not in active_sessions:
                    logger.info("Session stopped by user")
                    return

                try:
                    # Fetch and forward
                    messages = await client.get_messages(source_id, current_id)
                    
                    if messages and not messages.empty:
                         for target_id in target_ids:
                            try:
                                await messages.copy(target_id)
                                # await client.forward_messages(target_id, source_id, current_id)
                                logger.info(f"Forwarded msg {current_id} from {source_id} to {target_id}")
                            except FloodWait as e:
                                logger.warning(f"FloodWait: Sleeping {e.value}s")
                                await asyncio.sleep(e.value)
                                # Retry
                                await messages.copy(target_id)
                            except Exception as e:
                                logger.error(f"Failed to forward {current_id}: {e}")
                         
                         total_forwarded += 1
                         if total_forwarded % 50 == 0:
                             await client.send_message(user_id, f"📊 Progress: {total_forwarded} messages forwarded...")
                    
                except Exception as e:
                    logger.error(f"Error fetching msg {current_id}: {e}")
                
                current_id -= 1
                await asyncio.sleep(2.0) # Safe delay to avoid flood
                
    except Exception as e:
        logger.error(f"Fatal error in loop for user {user_id}: {e}")
    finally:
        logger.info(f"Loop finished for user {user_id}. Total: {total_forwarded}")
        if user_id in active_sessions:
             await client.send_message(user_id, f"✅ **Forwarding Completed!**\nTotal: {total_forwarded} messages.")
             # Cleanup
             await db.stop_session(user_id)
             del active_sessions[user_id]


async def stop_forwarding_callback(client: Client, callback_query: CallbackQuery):
    """Stop forwarding"""
    user_id = callback_query.from_user.id
    
    await db.stop_session(user_id)
    
    if user_id in active_sessions:
        del active_sessions[user_id]
        
    # Cancel task if exists
    if user_id in forward_tasks:
        forward_tasks[user_id].cancel()
        del forward_tasks[user_id]
    
    await callback_query.answer("⏹ Forwarding stopped!", show_alert=True)
    
    # Return to main menu
    from handlers.start import start_callback
    await start_callback(client, callback_query)


async def forward_message_handler(client: Client, message: Message):
    """Main handler for NEW messages (Instant Forward)"""
    chat_id = message.chat.id
    
    for user_id, session in active_sessions.items():
        # Only process if mode is Instant
        if session.get("mode") != "instant":
            continue
            
        if chat_id not in session.get("sources", []):
            continue
            
        targets = session.get("targets", [])
        keywords = session.get("keywords", [])
        
        should_forward = True
        
        # Keyword filter
        if keywords:
            text = message.text or message.caption or ""
            if not any(k in text.lower() for k in keywords):
                should_forward = False
        
        if should_forward:
            for target_id in targets:
                try:
                    await message.copy(target_id)
                    logger.info(f"Instant forward from {chat_id} to {target_id}")
                except Exception as e:
                    logger.error(f"Instant forward failed: {e}")


# Placeholder for old functions to avoid import errors (until bot.py updated)
async def mode_intent_callback(c, m): pass
async def mode_forward_all_callback(c, m): pass
async def start_intent_callback(c, m): pass
async def start_forward_all_callback(c, m): pass

# Export required functions
async def stop_command(client, message):
    await stop_forwarding_callback(client, message)

async def status_callback(client, cb):
    # Simplified status
    user_id = cb.from_user.id
    if user_id in active_sessions:
        await cb.answer("Active", show_alert=True)
    else:
        await cb.answer("Inactive", show_alert=True)

async def load_sessions_on_startup():
    global active_sessions
    sessions = await db.get_all_active_sessions()
    for s in sessions:
        active_sessions[s["user_id"]] = s
    logger.info(f"Restored {len(active_sessions)} sessions")
