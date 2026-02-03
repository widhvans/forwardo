"""
Forwarding Handlers - Intent Forward and Forward All modes
"""

from pyrogram import Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database.mongo import db
from utils.helpers import check_admin_status
from handlers.connect import user_states


# Active forwarding sessions in memory (restored from DB on startup)
active_sessions = {}


async def select_mode_callback(client: Client, callback_query: CallbackQuery):
    """Show mode selection menu"""
    user_id = callback_query.from_user.id
    
    # Check if user has connections
    sources = await db.get_user_connections(user_id, "source")
    targets = await db.get_user_connections(user_id, "target")
    
    if not sources or not targets:
        await callback_query.answer(
            "पहले source और target connect करें!",
            show_alert=True
        )
        return
    
    session = await db.get_session(user_id)
    current_mode = session.get("mode", "None") if session else "None"
    is_active = session.get("active", False) if session else False
    
    text = f"""
⚙️ **Select Forwarding Mode**

**Current Mode:** {current_mode.replace('_', ' ').title()}
**Status:** {'🟢 Active' if is_active else '🔴 Inactive'}

**Available Modes:**

1️⃣ **Intent Forward**
   - Specific keywords वाले messages forward होंगे
   - Keywords set करने होंगे
   
2️⃣ **Forward All**
   - सभी messages forward होंगे
   - Source से सारे messages target पर जाएंगे
"""
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("1️⃣ Intent Forward", callback_data="mode_intent"),
            InlineKeyboardButton("2️⃣ Forward All", callback_data="mode_forward_all")
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="start_menu")]
    ])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)
    await callback_query.answer()


async def mode_intent_callback(client: Client, callback_query: CallbackQuery):
    """Setup Intent Forward mode"""
    user_id = callback_query.from_user.id
    
    # Set user state for keyword input
    user_states[user_id] = {"action": "set_keywords"}
    
    text = """
1️⃣ **Intent Forward Mode**

यह mode specific keywords वाले messages forward करता है।

अब keywords भेजें (comma separated):
**Example:** buy, sell, trading, urgent

Keywords case-insensitive होंगे।
"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="select_mode")]
    ])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)
    await callback_query.answer()


async def mode_forward_all_callback(client: Client, callback_query: CallbackQuery):
    """Setup Forward All mode"""
    user_id = callback_query.from_user.id
    
    sources = await db.get_user_connections(user_id, "source")
    targets = await db.get_user_connections(user_id, "target")
    
    text = f"""
2️⃣ **Forward All Mode**

यह mode सभी messages forward करता है।

**📤 Sources ({len(sources)}):**
"""
    for s in sources:
        emoji = "📢" if s["chat_type"] == "channel" else "👥"
        text += f"• {emoji} {s['chat_title']}\n"
    
    text += f"\n**📥 Targets ({len(targets)}):**\n"
    for t in targets:
        emoji = "📢" if t["chat_type"] == "channel" else "👥"
        text += f"• {emoji} {t['chat_title']}\n"
    
    text += "\n▶️ Start forwarding?"
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("▶️ Start", callback_data="start_forward_all"),
            InlineKeyboardButton("❌ Cancel", callback_data="select_mode")
        ]
    ])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)
    await callback_query.answer()


async def handle_keywords_input(client: Client, message: Message):
    """Handle keywords input for Intent Forward"""
    user_id = message.from_user.id
    
    if user_id not in user_states:
        return
    
    state = user_states[user_id]
    if state.get("action") != "set_keywords":
        return
    
    # Parse keywords
    keywords = [k.strip().lower() for k in message.text.split(",") if k.strip()]
    
    if not keywords:
        await message.reply_text("❌ कम से कम एक keyword दें!")
        return
    
    # Clear state
    del user_states[user_id]
    
    sources = await db.get_user_connections(user_id, "source")
    targets = await db.get_user_connections(user_id, "target")
    
    text = f"""
1️⃣ **Intent Forward Mode**

**🔑 Keywords:** {', '.join(keywords)}

**📤 Sources ({len(sources)}):**
"""
    for s in sources:
        emoji = "📢" if s["chat_type"] == "channel" else "👥"
        text += f"• {emoji} {s['chat_title']}\n"
    
    text += f"\n**📥 Targets ({len(targets)}):**\n"
    for t in targets:
        emoji = "📢" if t["chat_type"] == "channel" else "👥"
        text += f"• {emoji} {t['chat_title']}\n"
    
    text += "\n▶️ Start forwarding?"
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("▶️ Start", callback_data=f"start_intent_{','.join(keywords)}"),
            InlineKeyboardButton("❌ Cancel", callback_data="select_mode")
        ]
    ])
    
    await message.reply_text(text, reply_markup=keyboard)


async def start_intent_callback(client: Client, callback_query: CallbackQuery):
    """Start Intent Forward mode"""
    user_id = callback_query.from_user.id
    keywords = callback_query.data.replace("start_intent_", "").split(",")
    
    sources = await db.get_user_connections(user_id, "source")
    targets = await db.get_user_connections(user_id, "target")
    
    source_ids = [s["chat_id"] for s in sources]
    target_ids = [t["chat_id"] for t in targets]
    
    # Save session
    await db.save_session(
        user_id=user_id,
        mode="intent",
        sources=source_ids,
        targets=target_ids,
        keywords=keywords,
        active=True
    )
    
    # Add to active sessions
    active_sessions[user_id] = {
        "mode": "intent",
        "sources": source_ids,
        "targets": target_ids,
        "keywords": keywords
    }
    
    await callback_query.message.edit_text(
        f"✅ **Intent Forwarding Started!**\n\n"
        f"🔑 Keywords: {', '.join(keywords)}\n"
        f"📤 Sources: {len(sources)}\n"
        f"📥 Targets: {len(targets)}\n\n"
        f"Messages containing keywords will be forwarded.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⏹ Stop", callback_data="stop_forwarding")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="start_menu")]
        ])
    )
    await callback_query.answer("✅ Forwarding started!")


async def start_forward_all_callback(client: Client, callback_query: CallbackQuery):
    """Start Forward All mode"""
    user_id = callback_query.from_user.id
    
    sources = await db.get_user_connections(user_id, "source")
    targets = await db.get_user_connections(user_id, "target")
    
    source_ids = [s["chat_id"] for s in sources]
    target_ids = [t["chat_id"] for t in targets]
    
    # Save session
    await db.save_session(
        user_id=user_id,
        mode="forward_all",
        sources=source_ids,
        targets=target_ids,
        keywords=[],
        active=True
    )
    
    # Add to active sessions
    active_sessions[user_id] = {
        "mode": "forward_all",
        "sources": source_ids,
        "targets": target_ids,
        "keywords": []
    }
    
    await callback_query.message.edit_text(
        f"✅ **Forward All Started!**\n\n"
        f"📤 Sources: {len(sources)}\n"
        f"📥 Targets: {len(targets)}\n\n"
        f"All messages from sources will be forwarded to targets.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⏹ Stop", callback_data="stop_forwarding")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="start_menu")]
        ])
    )
    await callback_query.answer("✅ Forwarding started!")


async def stop_forwarding_callback(client: Client, callback_query: CallbackQuery):
    """Stop forwarding"""
    user_id = callback_query.from_user.id
    
    await db.stop_session(user_id)
    
    if user_id in active_sessions:
        del active_sessions[user_id]
    
    await callback_query.answer("⏹ Forwarding stopped!", show_alert=True)
    
    # Return to main menu
    from handlers.start import start_callback
    await start_callback(client, callback_query)


async def status_callback(client: Client, callback_query: CallbackQuery):
    """Show current forwarding status"""
    user_id = callback_query.from_user.id
    
    session = await db.get_session(user_id)
    sources = await db.get_user_connections(user_id, "source")
    targets = await db.get_user_connections(user_id, "target")
    
    if not session or not session.get("active"):
        status = "🔴 Inactive"
        mode = "None"
        keywords = []
    else:
        status = "🟢 Active"
        mode = session.get("mode", "Unknown").replace("_", " ").title()
        keywords = session.get("keywords", [])
    
    text = f"""
📊 **Forwarding Status**

**Status:** {status}
**Mode:** {mode}
"""
    
    if keywords:
        text += f"**Keywords:** {', '.join(keywords)}\n"
    
    text += f"""
**📤 Sources:** {len(sources)}
**📥 Targets:** {len(targets)}
"""
    
    buttons = []
    if session and session.get("active"):
        buttons.append([InlineKeyboardButton("⏹ Stop", callback_data="stop_forwarding")])
    else:
        buttons.append([InlineKeyboardButton("▶️ Start", callback_data="select_mode")])
    
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="start_menu")])
    
    await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    await callback_query.answer()


async def forward_message_handler(client: Client, message: Message):
    """
    Main message handler for forwarding
    This should be called for messages in groups/channels
    """
    chat_id = message.chat.id
    
    # Find sessions that have this chat as source
    for user_id, session in active_sessions.items():
        if chat_id not in session.get("sources", []):
            continue
        
        mode = session.get("mode")
        targets = session.get("targets", [])
        keywords = session.get("keywords", [])
        
        should_forward = False
        
        if mode == "forward_all":
            should_forward = True
        elif mode == "intent":
            # Check if message contains any keyword
            text = message.text or message.caption or ""
            text_lower = text.lower()
            for keyword in keywords:
                if keyword in text_lower:
                    should_forward = True
                    break
        
        if should_forward:
            # Forward to all targets
            for target_id in targets:
                try:
                    await message.forward(target_id)
                except Exception as e:
                    print(f"Error forwarding to {target_id}: {e}")


async def load_sessions_on_startup():
    """Load active sessions from database on bot startup"""
    global active_sessions
    sessions = await db.get_all_active_sessions()
    
    for session in sessions:
        user_id = session["user_id"]
        active_sessions[user_id] = {
            "mode": session["mode"],
            "sources": session["sources"],
            "targets": session["targets"],
            "keywords": session.get("keywords", [])
        }
    
    print(f"Loaded {len(active_sessions)} active sessions from database.")


async def stop_command(client: Client, message: Message):
    """Handle /stop command"""
    user_id = message.from_user.id
    
    session = await db.get_session(user_id)
    
    if not session or not session.get("active"):
        await message.reply_text("❌ कोई active forwarding नहीं है!")
        return
    
    await db.stop_session(user_id)
    
    if user_id in active_sessions:
        del active_sessions[user_id]
    
    await message.reply_text(
        "⏹ **Forwarding Stopped!**",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Main Menu", callback_data="start_menu")]
        ])
    )
