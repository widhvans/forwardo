"""
Telegram Auto-Forwarding Bot
Main entry point

Run with: python3 bot.py
"""

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery
from config import BOT_TOKEN, API_ID, API_HASH

# Initialize the bot
app = Client(
    "forwarder_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)


# ==================== Import Handlers ====================
from handlers.start import (
    start_command, start_callback, connect_chat_callback,
    pick_group_callback, pick_channel_callback, handle_peer_selected,
    handle_tile_button, tile_source_callback, tile_target_callback,
    cancel_tile_callback, add_source_callback, add_target_callback,
    handle_chat_shared
)
from handlers.connect import (
    connect_group_callback, connect_channel_callback,
    connect_source_callback, connect_target_callback,
    cancel_connect_callback, handle_forwarded_message,
    my_connections_callback, remove_source_callback,
    remove_target_callback, delete_connection_callback,
    connect_in_chat, quick_connect_callback, user_states
)
from utils.logger import logger
from handlers.forward import (
    select_mode_callback, mode_instant_callback,
    mode_forward_old_callback, start_instant_all_callback,
    start_forward_old_callback, stop_forwarding_callback, 
    status_callback, forward_message_handler, 
    load_sessions_on_startup, stop_command, active_sessions,
    handle_keywords_input
)
from handlers.admin import stats_command, broadcast_command, users_command


# ==================== Message Handlers ====================

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    await start_command(client, message)


@app.on_message(filters.command("stop") & filters.private)
async def stop_handler(client: Client, message: Message):
    await stop_command(client, message)


@app.on_message(filters.command("stats") & filters.private)
async def stats_handler(client: Client, message: Message):
    await stats_command(client, message)


@app.on_message(filters.command("broadcast") & filters.private)
async def broadcast_handler(client: Client, message: Message):
    await broadcast_command(client, message)


@app.on_message(filters.command("users") & filters.private)
async def users_handler(client: Client, message: Message):
    await users_command(client, message)


@app.on_message(filters.command("connect"))
async def connect_handler(client: Client, message: Message):
    await connect_in_chat(client, message)


@app.on_message(filters.command("myconnections") & filters.private)
async def myconnections_handler(client: Client, message: Message):
    """Handle /myconnections command"""
    from database.mongo import db
    from utils.helpers import format_chat_list
    from config import MAX_SOURCES, MAX_TARGETS
    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    user_id = message.from_user.id
    sources = await db.get_user_connections(user_id, "source")
    targets = await db.get_user_connections(user_id, "target")
    
    text = f"""
📋 **Your Connections**

**📤 Sources ({len(sources)}/{MAX_SOURCES}):**
{format_chat_list(sources)}

**📥 Targets ({len(targets)}/{MAX_TARGETS}):**
{format_chat_list(targets)}
"""
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🗑 Remove Source", callback_data="remove_source"),
            InlineKeyboardButton("🗑 Remove Target", callback_data="remove_target")
        ],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="start_menu")]
    ])
    
    await message.reply_text(text, reply_markup=keyboard)


@app.on_message(filters.command("mode") & filters.private)
async def mode_handler(client: Client, message: Message):
    """Handle /mode command"""
    from database.mongo import db
    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    user_id = message.from_user.id
    sources = await db.get_user_connections(user_id, "source")
    targets = await db.get_user_connections(user_id, "target")
    
    if not sources or not targets:
        await message.reply_text("❌ पहले source और target connect करें!")
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
   
2️⃣ **Forward All**
   - सभी messages forward होंगे
"""
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("1️⃣ Intent Forward", callback_data="mode_intent"),
            InlineKeyboardButton("2️⃣ Forward All", callback_data="mode_forward_all")
        ],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="start_menu")]
    ])
    
    await message.reply_text(text, reply_markup=keyboard)


@app.on_message(filters.command("status") & filters.private)
async def status_handler(client: Client, message: Message):
    """Handle /status command"""
    from database.mongo import db
    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    
    user_id = message.from_user.id
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
    
    buttons.append([InlineKeyboardButton("🔙 Main Menu", callback_data="start_menu")])
    
    await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))


# ==================== Text Message Handler ====================

@app.on_message(filters.private & filters.text & ~filters.command(["start", "stop", "stats", "broadcast", "users", "connect", "myconnections", "mode", "status"]))
async def text_message_handler(client: Client, message: Message):
    """Handle text messages for keywords input and tile buttons"""
    user_id = message.from_user.id
    text = message.text
    
    # Handle tile buttons (Group/Channel)
    if text in ["👥 Group", "📢 Channel"]:
        await handle_tile_button(client, message)
        return
    
    if user_id in user_states:
        state = user_states[user_id]
        if state.get("action") == "set_keywords":
            await handle_keywords_input(client, message)
            return


# ==================== Forwarded Message Handler ====================

@app.on_message(filters.private & filters.forwarded)
async def forwarded_handler(client: Client, message: Message):
    """Handle forwarded messages for connection"""
    await handle_forwarded_message(client, message)


# ==================== Chat Shared Handler (Native Picker) ====================

@app.on_message(filters.private & filters.chat_shared)
async def chat_shared_handler(client: Client, message: Message):
    """Handle chat_shared from native picker"""
    await handle_chat_shared(client, message)



# ==================== Group/Channel Message Handler ====================

@app.on_message(filters.group | filters.channel)
async def group_channel_handler(client: Client, message: Message):
    """Handle messages in groups/channels for forwarding"""
    await forward_message_handler(client, message)


# ==================== Callback Query Handler ====================

@app.on_callback_query()
async def callback_handler(client: Client, callback_query: CallbackQuery):
    """Handle all callback queries"""
    data = callback_query.data
    
    # Start menu
    if data == "start_menu":
        await start_callback(client, callback_query)
    
    # Connect Chat handlers (new request_peer based)
    elif data == "connect_chat":
        await connect_chat_callback(client, callback_query)
    elif data == "pick_group":
        await pick_group_callback(client, callback_query)
    elif data == "pick_channel":
        await pick_channel_callback(client, callback_query)
    
    # Old Connect handlers (forward based)
    elif data == "connect_group":
        await connect_group_callback(client, callback_query)
    elif data == "connect_channel":
        await connect_channel_callback(client, callback_query)
    elif data in ["connect_source_group", "connect_source_channel"]:
        await connect_source_callback(client, callback_query)
    elif data in ["connect_target_group", "connect_target_channel"]:
        await connect_target_callback(client, callback_query)
    elif data == "cancel_connect":
        await cancel_connect_callback(client, callback_query)
    elif data == "my_connections":
        await my_connections_callback(client, callback_query)
    elif data == "remove_source":
        await remove_source_callback(client, callback_query)
    elif data == "remove_target":
        await remove_target_callback(client, callback_query)
    elif data.startswith("del_source_") or data.startswith("del_target_"):
        await delete_connection_callback(client, callback_query)
    elif data.startswith("quick_source_") or data.startswith("quick_target_"):
        await quick_connect_callback(client, callback_query)
    
    # Tile button callbacks
    elif data.startswith("tile_source_"):
        await tile_source_callback(client, callback_query)
    elif data.startswith("tile_target_"):
        await tile_target_callback(client, callback_query)
    elif data == "cancel_tile":
        await cancel_tile_callback(client, callback_query)
    
    # Native picker callbacks (add_source_/add_target_)
    elif data.startswith("add_source_"):
        await add_source_callback(client, callback_query)
    elif data.startswith("add_target_"):
        await add_target_callback(client, callback_query)
    
    # Mode handlers
    elif data == "select_mode":
        await select_mode_callback(client, callback_query)
    elif data == "mode_instant":
        await mode_instant_callback(client, callback_query)
    elif data == "mode_forward_old":
        await mode_forward_old_callback(client, callback_query)
        
    # Start Handlers
    elif data == "start_instant_all":
        await start_instant_all_callback(client, callback_query)
    elif data.startswith("start_final_instant_"): # If we need this pattern, but currently just start_instant_all or direct
        pass 
    elif data == "start_forward_old":
        await start_forward_old_callback(client, callback_query)
    elif data == "stop_forwarding":
        await stop_forwarding_callback(client, callback_query)
    elif data == "status":
        await status_callback(client, callback_query)


# ==================== Startup ====================

async def main():
    """Main function to start the bot"""
    print("Starting Telegram Auto-Forwarding Bot...")
    
    # Load active sessions from database
    await load_sessions_on_startup()
    
    # Start the bot
    await app.start()
    print("Bot started successfully!")
    print("Press Ctrl+C to stop the bot.")
    
    # Keep the bot running
    from pyrogram import idle
    await idle()
    
    # Stop the bot gracefully
    await app.stop()


if __name__ == "__main__":
    import asyncio
    asyncio.get_event_loop().run_until_complete(main())
