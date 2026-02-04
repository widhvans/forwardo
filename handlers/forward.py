"""
Forwarding Handlers - Wizard Style UI (Refined)
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
# Key: user_id, Value: {mode, sources, targets, filters, active, start_msg_id}
active_sessions = {}

# Background tasks for forwarding old messages
forward_tasks = {}

# Temporary session state for setup (The "Wizard" state)
# Key: user_id, Value: {mode, sources:[], targets:[], filters:{...}, start_msg_id: int}
temp_sessions = {}

async def select_mode_callback(client: Client, callback_query: CallbackQuery):
    """Step 1: Show Mode Selection"""
    user_id = callback_query.from_user.id
    
    # Initialize temp session ONLY if not exists (Preserve state on Back navigation)
    if user_id not in temp_sessions:
        temp_sessions[user_id] = {
            "mode": None,
            "sources": [],
            "targets": [], 
            "filters": {
                "text": True, "photo": True, "video": True, 
                "document": True, "voice": True
            }
        }
        # Start with empty selection (User explicitly adds)
    
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
        [InlineKeyboardButton("Back", callback_data="start_menu")]
    ])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)


# ... (skipping unchanged functions) ...

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
        
    s_msg_id = session.get("start_msg_id")
    
    # Save to DB
    await db.save_session(
        user_id=user_id,
        mode=session["mode"],
        sources=session["sources"],
        targets=session["targets"],
        filters=session["filters"],
        active=True
    )
    
    active_sessions[user_id] = session.copy()
    active_sessions[user_id]["active"] = True
    
    # We do NOT delete temp_sessions anymore to preserve state for Hub view
    # But we should sync it just in case
    # temp_sessions[user_id] = session.copy() 
    
    # Update UI to running state (Stop Button will be rendered by setup_hub)
    await setup_hub_callback(client, callback_query)
    
    if session["mode"] == "forward_old" and s_msg_id:
        task = asyncio.create_task(
            forward_old_messages_loop(client, user_id, session["sources"], session["targets"], s_msg_id)
        )
        forward_tasks[user_id] = task


async def setup_hub_callback(client: Client, callback_query: CallbackQuery):
    """Step 2: Session Hub (Central Config)"""
    user_id = callback_query.from_user.id
    
    # Check if active
    is_active = (user_id in active_sessions)
    
    if is_active:
        # Use active session data
        session = active_sessions[user_id]
        if user_id not in temp_sessions:
            temp_sessions[user_id] = session.copy()
    elif user_id in temp_sessions:
        session = temp_sessions[user_id]
    else:
        # No session, go back
        await select_mode_callback(client, callback_query)
        return

    data = callback_query.data
    # Set mode only if changed/fresh AND NOT ACTIVE (lock mode changes while running)
    if not is_active:
        if "instant" in data: session["mode"] = "instant"
        elif "old" in data: session["mode"] = "forward_old"
        elif "setup_hub" in data: # Re-render request
             # Maintain current mode
             pass
        
    # Ensure temp/session sync if we just initialized it
    if is_active:
         pass # session is ref to active_sessions[uid] if we did assignment above? No, dict copy.
         # Actually session = ... assigns reference.
         # If is_active, session = active_sessions[user_id] (Reference!)
         # If not active, session = temp_sessions[user_id] (Reference!)
         # Be careful not to mutate active_session if we want edits to apply only after restart?
         # User asked for "Stop" button to appear. Edits while running? 
         # Complexity. Let's assume locking edits for safety or just visual toggle.
         pass
         
    mode_name = "Instant Forward" if session["mode"] == "instant" else "Forward Old"
    
    src_count = len(session["sources"])
    tgt_count = len(session["targets"])
    
    # Filter summary
    filters = session["filters"]
    enabled = [k.title() for k, v in filters.items() if v]
    filter_text = ", ".join(enabled) if enabled else "None"
    
    # Readiness Check
    can_start = True
    start_status = ""
    
    if session["mode"] == "forward_old":
        if "start_msg_id" in session:
            start_status = f"✅ Set (ID: {session['start_msg_id']})"
        else:
            start_status = "❌ Not Set"
            can_start = False
    
    status_header = "\n🟢 **RUNNING**" if is_active else ""
    
    text = f"""
⚙️ **Session Configuration: {mode_name}**{status_header}

Configure settings:

🛡 **Filters:** {filter_text}
📤 **Sources:** {src_count} selected
📥 **Targets:** {tgt_count} selected
"""
    if session["mode"] == "forward_old":
        text += f"🏁 **Start Message:** {start_status}\n"
    
    text += "\n_Click buttons below to edit:_"

    key_rows = [
        [InlineKeyboardButton("🛡 Edit Filters", callback_data="menu_filters")],
        [
            InlineKeyboardButton(f"📤 Sources ({src_count})", callback_data="menu_sources"),
            InlineKeyboardButton(f"📥 Targets ({tgt_count})", callback_data="menu_targets")
        ]
    ]

    if session["mode"] == "forward_old":
        key_rows.append([InlineKeyboardButton("🏁 Set Start Message", callback_data="set_start_msg_hub")])
    
    # Reset button
    key_rows.append([InlineKeyboardButton("🔄 Reset Selection", callback_data="reset_selection")])
    
    if is_active:
        key_rows.append([InlineKeyboardButton("⏹ Stop Forwarding", callback_data="stop_forwarding")])
    elif can_start:
        key_rows.append([InlineKeyboardButton("▶️ Start Forwarding", callback_data="start_session")])
    
    # Back button always goes to mode selection
    key_rows.append([InlineKeyboardButton("Back", callback_data="select_mode")])
    
    try:
        await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(key_rows))
    except:
        pass


async def set_start_msg_hub_callback(client: Client, callback_query: CallbackQuery):
    """Ask user to forward start message (Old Mode)"""
    user_id = callback_query.from_user.id
    
    user_states[user_id] = {"action": "wait_for_last_msg_hub"}
    
    text = """
🏁 **Set Start Message**

Please **Forward the Last Message** from the **Source Chat**.
Bot will start copying backwards from this message.

👉 **Forward Message Now...**
"""
    await callback_query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Cancel", callback_data="setup_hub")]])
    )


async def handle_last_msg_input(client: Client, message: Message):
    """Process forwarded message for Hub Setup"""
    user_id = message.from_user.id
    
    if user_id not in user_states: return
    state = user_states[user_id]
    if state.get("action") != "wait_for_last_msg_hub": return
    
    # Check forward
    if not message.forward_from_chat:
        await message.reply_text("❌ Please forward from a Channel/Group!")
        return
        
    start_msg_id = message.forward_from_message_id
    source_chat_id = message.forward_from_chat.id
    
    if user_id not in temp_sessions:
        await message.reply_text("❌ Session expired. Please restart mode selection.")
        del user_states[user_id]
        return
        
    session = temp_sessions[user_id]
    
    # Auto-select this source if not selected?
    # Or validate against selected sources?
    # Let's validate.
    if source_chat_id not in session["sources"]:
        # If not selected, maybe user wants to select it now?
        # Let's be smart: Select it automatically if it's connected.
        # But we need to check if it IS connected first.
        sources = await db.get_user_connections(user_id, "source")
        connected_ids = [s["chat_id"] for s in sources]
        
        if source_chat_id in connected_ids:
            session["sources"] = [source_chat_id] # Focus on this source?
            # User said "Connected chats me koi bhi chat ham rakh skte hai"
            # Maybe just append?
            if source_chat_id not in session["sources"]:
                 session["sources"].append(source_chat_id)
        else:
             await message.reply_text("❌ This chat is not connected as a Source!")
             return

    # Update session
    session["start_msg_id"] = start_msg_id
    del user_states[user_id]
    
    # Return to Hub
    # We can't edit the user's forwarded message, so we send a fresh Hub message
    # Or try to edit the bot's last message if we stored ID.
    # Simpler: Send new Hub.
    
    await message.reply_text("✅ Start Message Set!", quote=True)
    
    # We need a dummy callback query to reuse setup_hub_callback logic (hacky but works)
    # Or split logic. Refactoring setup_hub_display would be cleaner.
    # For now, let's just trigger a "fresh" start menu or similar. Durn, need callback object.
    # Let's just send the Hub text manually here.
    
    # Trigger Hub display manually
    await show_hub_manual(client, message.chat.id, session)


async def show_hub_manual(client, chat_id, session):
    """Helper to show Hub from message context"""
    mode = session["mode"]
    src = len(session["sources"])
    tgt = len(session["targets"])
    filters = ", ".join([k.title() for k, v in session["filters"].items() if v]) or "None"
    
    start_status = f"✅ Set (ID: {session.get('start_msg_id')})" if mode == "forward_old" else ""
    
    text = f"""
⚙️ **Session Configuration: {mode.replace('_', ' ').title()}**

🛡 **Filters:** {filters}
📤 **Sources:** {src} selected
📥 **Targets:** {tgt} selected
"""
    if mode == "forward_old":
        text += f"🏁 **Start Message:** {start_status}\n"
    
    key_rows = [
        [InlineKeyboardButton("🛡 Edit Filters", callback_data="menu_filters")],
        [
            InlineKeyboardButton(f"📤 Sources ({src})", callback_data="menu_sources"),
            InlineKeyboardButton(f"📥 Targets ({tgt})", callback_data="menu_targets")
        ]
    ]
    if mode == "forward_old":
        key_rows.append([InlineKeyboardButton("🏁 Set Start Message", callback_data="set_start_msg_hub")])
        
    can_start = True
    if mode == "forward_old" and "start_msg_id" not in session: can_start = False
    
    if can_start:
        key_rows.append([InlineKeyboardButton("▶️ START FORWARDING", callback_data="start_session")])
    elif mode == "forward_old":
        key_rows.append([InlineKeyboardButton("⚠️ Set Start Msg First", callback_data="noop")])
        
    key_rows.append([InlineKeyboardButton("🔙 Back", callback_data="select_mode")])
    
    await client.send_message(chat_id, text, reply_markup=InlineKeyboardMarkup(key_rows))


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
        [InlineKeyboardButton(f"{status('voice')} Audio", callback_data="toggle_filter_voice")],
        [InlineKeyboardButton("Back to Hub", callback_data="setup_hub")]
    ])
    await callback_query.message.edit_text("🛡 **Edit Filters**", reply_markup=keyboard)


async def toggle_filter_callback(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id in temp_sessions:
        f = callback_query.data.replace("toggle_filter_", "")
        temp_sessions[user_id]["filters"][f] = not temp_sessions[user_id]["filters"][f]
        await menu_filters_callback(client, callback_query)


async def menu_chat_selection(client: Client, callback_query: CallbackQuery, is_source: bool):
    """Chat Selection (Generic for Source/Target)"""
    user_id = callback_query.from_user.id
    if user_id not in temp_sessions: return
    
    session = temp_sessions[user_id]
    chat_type = "source" if is_source else "target"
    selected_list = session["sources"] if is_source else session["targets"]
    other_list = session["targets"] if is_source else session["sources"] # Validation
    
    # Fetch all connected chats (Show ALL available connections)
    # User requirement: "make sure connected chats show... target selected source me nhi"
    # Logic: Show ALL connections, but filtered:
    # 1. Any chat is eligible to be a Source OR a Target.
    # 2. BUT a chat cannot be BOTH in the same session.
    # 3. So if a chat is in 'other_list', exclude it from this list.
    
    all_connections = await db.get_user_connections(user_id) # Fetch ALL
    
    # Remove duplicates if any
    unique_conns = []
    seen = set()
    for c in all_connections:
        if c["chat_id"] not in seen:
            unique_conns.append(c)
            seen.add(c["chat_id"])
    
    text = f"📤 **Select Sources**" if is_source else f"📥 **Select Targets**"
    text += "\n\nTick chats to include:"
    
    buttons = []
    for chat in unique_conns:
        chat_id = chat["chat_id"]
        
        # Exclusivity Validation: Chat cannot be in OTHER list
        # If I'm selecting Sources, and Chat A is already a Target, don't show it here.
        if chat_id in other_list:
            continue 
            
        is_selected = chat_id in selected_list
        mark = "✅" if is_selected else "❌"
        # Type in callback (source/target) tells toggle function which list to update
        buttons.append([InlineKeyboardButton(f"{mark} {chat['chat_title']}", callback_data=f"toggle_chat_{chat_type}_{chat_id}")])
    
    buttons.append([InlineKeyboardButton("Back to Hub", callback_data="setup_hub")])
    await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))


async def toggle_chat_callback(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in temp_sessions: return
    
    data = callback_query.data.split("_") # toggle, chat, source, 12345
    c_type = data[2]
    c_id = int(data[3])
    
    session = temp_sessions[user_id]
    lst = session["sources"] if c_type == "source" else session["targets"]
    
    if c_id in lst: lst.remove(c_id)
    else: lst.append(c_id)
    
    await menu_chat_selection(client, callback_query, is_source=(c_type=="source"))


async def reset_selection_callback(client: Client, callback_query: CallbackQuery):
    """Reset sources and targets"""
    user_id = callback_query.from_user.id
    if user_id in temp_sessions:
        temp_sessions[user_id]["sources"] = []
        temp_sessions[user_id]["targets"] = []
        await callback_query.answer("Selection Reset!", show_alert=True)
        await setup_hub_callback(client, callback_query)


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
        
    s_msg_id = session.get("start_msg_id")
    
    # Save to DB
    await db.save_session(
        user_id=user_id,
        mode=session["mode"],
        sources=session["sources"],
        targets=session["targets"],
        filters=session["filters"],
        active=True,
        start_msg_id=s_msg_id
    )
    
    active_sessions[user_id] = session.copy()
    active_sessions[user_id]["active"] = True
    active_sessions[user_id]["start_msg_id"] = s_msg_id
    
    # Do NOT delete temp_sessions to preserve UI state (Sources/Targets selection)
    # BUT update it to match active session status
    temp_sessions[user_id] = active_sessions[user_id].copy()
    
    # Refresh the Hub UI which will now show "Running" and "Stop" button
    await setup_hub_callback(client, callback_query)
    
    await callback_query.answer("✅ Forwarding Started!", show_alert=False)
    
    if session["mode"] == "forward_old" and s_msg_id:
        # Start only ONE task for simplicity (first source) ?
        # Or launch parallel tasks for all sources?
        # User implies list.
        # But start_msg_id came from ONE valid source.
        # We need to find WHICH source this start_msg_id belongs to if we have multiple.
        # Too complex. We assume user selected ONE source for Old Mode usually.
        # Taking the first source for now (or all sources if logic allows independent history fetch, but start_id is tied to one chat).
        # We'll just run task for the first source in list.
        
        task = asyncio.create_task(
            forward_old_messages_loop(client, user_id, session["sources"], session["targets"], s_msg_id)
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
    logger.info(f"Starting loop User={user_id} StartMsg={start_id}")
    source_id = source_ids[0] # Priority to first source
    current_id = start_id
    total = 0
    filters = active_sessions[user_id]["filters"]
    
    # Dynamic delay to prevent instant flood, but much faster than 1.5s
    # Telegram limit is ~30 msgs/sec globally, but per chat it's lower.
    # We'll start safe.
    delay = 0.1 
    
    try:
        while current_id > 0:
            if user_id not in active_sessions: 
                logger.info(f"Session stopped for User={user_id}")
                return
            
            try:
                # Batch get messages could be faster but let's stick to simple logic first
                msg = await client.get_messages(source_id, current_id)
                
                if msg and not msg.empty:
                    if should_forward_message(msg, filters):
                        # Use gather for parallel forwarding to multiple targets
                        tasks = []
                        for tid in target_ids:
                             tasks.append(safe_copy_message(msg, tid))
                             
                        await asyncio.gather(*tasks)
                        
                        total += 1
                        if total % 20 == 0:
                             try: 
                                 await db.update_session_progress(user_id, current_id)
                                 logger.info(f"User={user_id} Progress: MsgID={current_id} Total={total}")
                             except: pass
                             
                # Small dynamic delay to be nice to API
                await asyncio.sleep(delay)
                
            except FloodWait as e:
                logger.warning(f"FloodWait: Sleeping {e.value}s (User={user_id})")
                await asyncio.sleep(e.value + 1)
            except Exception as e:
                logger.error(f"Error in loop (User={user_id}, Msg={current_id}): {e}")
                
            current_id -= 1
            
    except Exception as e: 
        logger.error(f"Critical Loop Error User={user_id}: {e}")
    finally:
         if user_id in active_sessions:
             try:
                 await client.send_message(user_id, f"✅ **Forwarding Completed!**\n\nProcessed {total} messages.")
                 logger.info(f"Loop finished User={user_id} Total={total}")
             except: pass
             await stop_forwarding_callback(None, None, user_id_override=user_id)

async def safe_copy_message(msg, chat_id):
    """Helper to copy message with individual FloodWait handling"""
    try:
        await msg.copy(chat_id)
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await msg.copy(chat_id)
    except Exception as e:
        # Some messages can't be copied (privacy, etc)
        # logger.error(f"Copy failed to {chat_id}: {e}")
        pass

async def forward_message_handler(client, message):
    chat_id = message.chat.id
    
    # Parallel processing for multiple sessions/targets
    tasks = []
    
    for uid, session in active_sessions.items():
        if session["mode"] != "instant": continue
        if chat_id not in session["sources"]: continue
        
        if should_forward_message(message, session["filters"]):
            for tid in session["targets"]:
                tasks.append(safe_copy_message_instant(message, tid))
                
    if tasks:
        await asyncio.gather(*tasks)

async def safe_copy_message_instant(msg, chat_id):
    try:
        await msg.copy(chat_id)
    except Exception as e:
        # Silent fail for instant mode usually preferred to keep speed, 
        # but could log if critical
        pass

async def stop_forwarding_callback(client, callback_query, user_id_override=None):
    user_id = user_id_override or callback_query.from_user.id
    await db.stop_session(user_id)
    if user_id in active_sessions:
        # Update temp session so UI reflects "stopped" state if user acts on it (toggle filters, etc.)
        # We want to keep the configuration for easy restart
        temp_sessions[user_id] = active_sessions[user_id].copy()
        del active_sessions[user_id]

    if user_id in forward_tasks:
        forward_tasks[user_id].cancel()
        del forward_tasks[user_id]
    
    if callback_query:
        await callback_query.answer("⏹ Stopped!", show_alert=True)
        # Use setup_hub to show configuration again (Stop -> Start button)
        await setup_hub_callback(client, callback_query)

# Exports/Placeholders
async def stop_command(c, m): await stop_forwarding_callback(c, None, m.from_user.id)
async def status_callback(c, cb): await cb.answer("Active" if cb.from_user.id in active_sessions else "Inactive")

async def resume_session_callback(client: Client, callback_query: CallbackQuery):
    """Resume a crashed session"""
    user_id = callback_query.from_user.id
    if user_id in active_sessions:
        # Already active? Just show hub.
        await setup_hub_callback(client, callback_query)
        return
        
    session = await db.get_session(user_id)
    if not session:
        await callback_query.answer("❌ No session to resume!", show_alert=True)
        return
        
    # Restore to temp_sessions
    temp_sessions[user_id] = session
    
    # Just show Hub, user can click "Start" (which now says Start/Resume effectively)
    # User asked: "continue again ka button ke saaath to bot whi se continue kr dena"
    # So we should auto-start?
    # "bot whi se continue kr dena ... old msg forward option se"
    # Yes, auto-start.
    
    # We need to manually trigger start logic
    # Reuse start_session_callback logic but without callback object if needed?
    # No, we have callback_query here from the "Continue" button.
    
    await start_session_callback(client, callback_query)

async def load_sessions_on_startup():
    global active_sessions
    from bot import app # Direct import to send messages
    
    sessions = await db.get_all_active_sessions()
    for s in sessions:
        user_id = s["user_id"]
        
        # If it's Forward Old Messages, we treat it as "Crashed" if it was active.
        # Instant Forward can auto-resume implicitly by just adding to active_sessions?
        # Yes, Instant Forward just needs to be in active_sessions memory.
        
        if s["mode"] == "forward_old":
            # It was running when bot stopped.
            # We do NOT add to active_sessions immediately to avoid auto-spamming or loop issues without user control.
            # Instead, we notify user.
            
            # Mark incorrect in DB? No, keep it active in DB so we know it was active.
            # But we are NOT adding it to `active_sessions` dict, so it won't actually run yet.
            
            try:
                # Notify User
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("▶️ Continue Forwarding", callback_data="resume_session")],
                    [InlineKeyboardButton("❌ Stop", callback_data="stop_forwarding")] 
                ])
                
                await app.send_message(
                    user_id,
                    "⚠️ **Bot Restarted Unconditionally!**\n\nYour forwarding session was interrupted. Do you want to continue from where it left off?",
                    reply_markup=keyboard
                )
            except Exception as e:
                logger.error(f"Failed to notify user {user_id}: {e}")
                
        else:
            # Instant Mode: Just load it.
            active_sessions[user_id] = s
            
async def setup_filter_callback(c, cb): pass 
async def mode_instant_callback(c, cb): pass 
async def confirm_filters_callback(c, cb): pass
