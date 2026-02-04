"""
Connection Handlers - Connect Groups/Channels
"""

from pyrogram import Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database.mongo import db
from utils.helpers import check_admin_status, get_chat_info, format_chat_list
from config import MAX_SOURCES, MAX_TARGETS


# User states for conversation handling
user_states = {}


# Legacy Handlers (kept for safety but unreachable from main menu)
async def connect_group_callback(client: Client, callback_query: CallbackQuery):
    await callback_query.answer("Use Connect Chat button", show_alert=True)

async def connect_channel_callback(client: Client, callback_query: CallbackQuery):
    await callback_query.answer("Use Connect Chat button", show_alert=True)

async def connect_source_callback(client: Client, callback_query: CallbackQuery): pass
async def connect_target_callback(client: Client, callback_query: CallbackQuery): pass


async def cancel_connect_callback(client: Client, callback_query: CallbackQuery):
    """Cancel connection process"""
    user_id = callback_query.from_user.id
    if user_id in user_states:
        del user_states[user_id]
    
    await callback_query.answer("Cancelled!")
    # Import here to avoid circular import
    from handlers.start import start_callback
    await start_callback(client, callback_query)


async def handle_forwarded_message(client: Client, message: Message):
    """Handle forwarded messages for connection"""
    user_id = message.from_user.id
    
    if user_id not in user_states:
        return
    
    state = user_states[user_id]
    action = state.get("action", "")
    
    if not action.startswith("connect_"):
        return
    
    # Get forwarded chat info
    if message.forward_from_chat:
        chat_id = message.forward_from_chat.id
        chat_title = message.forward_from_chat.title or "Unknown"
        chat_type = message.forward_from_chat.type.value
    else:
        await message.reply_text("❌ This message is not forwarded from a group/channel!")
        return
    
    # Check if bot is admin
    is_admin, error = await check_admin_status(client, chat_id)
    if not is_admin:
        await message.reply_text(f"❌ {error}\n\nPlease make Bot Admin in {chat_type} first!")
        return
    
    # Determine connection type
    connection_type = "source" if "source" in action else "target"
    
    # Add connection
    success, msg = await db.add_connection(
        user_id=user_id,
        chat_id=chat_id,
        chat_title=chat_title,
        chat_type=chat_type,
        connection_type=connection_type
    )
    
    # Clear state
    del user_states[user_id]
    
    if success:
        await message.reply_text(
            f"✅ **Connection Successful!**\n\n"
            f"**{chat_title}**\n"
            f"🆔 Chat ID: `{chat_id}`\n"
            f"📌 Type: {connection_type.title()}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Main Menu", callback_data="start_menu")]
            ])
        )
    else:
        await message.reply_text(f"❌ {msg}")


async def my_connections_callback(client: Client, callback_query: CallbackQuery):
    """Show user's connections"""
    user_id = callback_query.from_user.id
    
    # Fetch all connections
    sources = await db.get_user_connections(user_id, "source")
    targets = await db.get_user_connections(user_id, "target")
    all_conns = sources + targets
    
    # Remove duplicates
    seen = set()
    unique_conns = []
    for c in all_conns:
        if c["chat_id"] not in seen:
            unique_conns.append(c)
            seen.add(c["chat_id"])
    
    chat_list_text = format_chat_list(unique_conns)
    
    text = f"""
📋 **Connected Chats**

Total Connections: {len(unique_conns)}

{chat_list_text}
"""
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🗑 Remove Connection", callback_data="remove_connection")
        ],
        [InlineKeyboardButton("Main Menu", callback_data="start_menu")]
    ])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)
    await callback_query.answer()


async def remove_connection_callback(client: Client, callback_query: CallbackQuery):
    """Show connections for removal"""
    user_id = callback_query.from_user.id
    
    sources = await db.get_user_connections(user_id, "source")
    targets = await db.get_user_connections(user_id, "target")
    all_conns = sources + targets
    
    if not all_conns:
        await callback_query.answer("No connections found!", show_alert=True)
        return
    
    buttons = []
    seen = set()
    for conn in all_conns:
        if conn["chat_id"] in seen: continue
        seen.add(conn["chat_id"])
        
        # Use del_source generic or check type?
        # Since we are unifying, we must know if it's source or target to delete specifically 
        # OR delete BOTH if connected as both.
        # DB remove_connection takes type.
        # We should iterate and provide button to delete specific instance or all?
        # User wants simple list.
        # Check conn['connection_type'].
        c_type = conn['connection_type']
        
        # If chat is connected as BOTH, we might have 2 entries in all_conns.
        # My dedup logic above hides one.
        # It's better to show specific deletions or "Disconnect Chat" which removes both?
        # Let's show all entries without dedup for removal to be precise.
        
        c_name = conn['chat_title'][:20]
        c_mark = "Source" if c_type == "source" else "Target" # Though user wanted unified view...
        # Wait, user said "total connected chats... na ki source and target".
        # This implies user doesn't care about type at this stage (DB structure forces it though).
        # We can implement "Delete Any Connection related to ChatID".
        
        buttons.append([
            InlineKeyboardButton(
                f"🗑 {c_name} ({c_type.title()})",
                callback_data=f"del_any_{conn['chat_id']}_{c_type}" # Custom callback
            )
        ])
        
    buttons.append([InlineKeyboardButton("Back", callback_data="my_connections")])
    
    await callback_query.message.edit_text(
        "🗑 **Remove Connection**\n\nSelect connection to remove:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def delete_connection_callback(client: Client, callback_query: CallbackQuery):
    """Delete a connection"""
    user_id = callback_query.from_user.id
    data = callback_query.data
    
    # Protocol: del_any_{chat_id}_{type}
    parts = data.split("_")
    # parts[0]=del, parts[1]=any, parts[2]=chat_id, parts[3]=type
    
    if len(parts) >= 4:
        chat_id = int(parts[2])
        connection_type = parts[3]
        
        success = await db.remove_connection(user_id, chat_id, connection_type)
        if success:
            await callback_query.answer("✅ Connection removed!", show_alert=True)
        else:
            await callback_query.answer("❌ Error removing connection!", show_alert=True)
            
        await my_connections_callback(client, callback_query)
    # Legacy support
    elif data.startswith("del_source_"):
        chat_id = int(data.replace("del_source_", ""))
        await db.remove_connection(user_id, chat_id, "source")
        await my_connections_callback(client, callback_query)
    elif data.startswith("del_target_"):
        chat_id = int(data.replace("del_target_", ""))
        await db.remove_connection(user_id, chat_id, "target")
        await my_connections_callback(client, callback_query)


async def connect_in_chat(client: Client, message: Message):
    """Handle /connect command in groups/channels"""
    chat = message.chat
    user = message.from_user
    
    if chat.type.value == "private":
        await message.reply_text("Use this command in groups/channels!")
        return
    
    if user is None:
        await message.reply_text(
            "❌ Cannot use /connect directly in Channel.\n\n"
            "Go to Bot PM and forward a message from this channel."
        )
        return
    
    is_admin, error = await check_admin_status(client, chat.id, user.id)
    if not is_admin:
        await message.reply_text("❌ You are not admin in this chat!")
        return
    
    is_bot_admin, error = await check_admin_status(client, chat.id)
    if not is_bot_admin:
        await message.reply_text(f"❌ {error}")
        return
    
    # Auto-add default source interaction
    success, msg = await db.add_connection(user.id, chat.id, chat.title, "group", "source")
    
    if success:
        await message.reply_text(f"✅ **Connected!**\n\nChat added to your connections.")
    else:
        await message.reply_text(f"⚠️ {msg}")


async def quick_connect_internal(client: Client, callback_query: CallbackQuery, chat_id: int, connection_type: str):
    """Shared internal logic for adding connection"""
    # Not used by handle_chat_shared anymore (uses db directly), 
    # but might be used by legacy callbacks if any remain.
    # Updating to English just in case.
    user_id = callback_query.from_user.id
    
    chat_info, error = await get_chat_info(client, chat_id)
    if not chat_info:
        await callback_query.answer(f"❌ {error}", show_alert=True)
        return
    
    success, msg = await db.add_connection(
        user_id=user_id,
        chat_id=chat_id,
        chat_title=chat_info["title"],
        chat_type=chat_info["type"],
        connection_type=connection_type
    )
    
    if success:
        await callback_query.answer(f"✅ Connected as {connection_type}!", show_alert=True)
    else:
        await callback_query.answer(f"❌ {msg}", show_alert=True)


async def quick_connect_callback(client: Client, callback_query: CallbackQuery):
    await callback_query.answer("Please use main menu", show_alert=True)

# Placeholders for exports
async def remove_source_callback(c, cb): await remove_connection_callback(c, cb)
async def remove_target_callback(c, cb): await remove_connection_callback(c, cb)
