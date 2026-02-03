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


async def connect_group_callback(client: Client, callback_query: CallbackQuery):
    """Handle connect group button"""
    user_id = callback_query.from_user.id
    
    text = """
🔗 **Connect Group**

Group को connect करने के लिए:

**Method 1: Forward Message**
1. उस group का कोई भी message यहां forward करें
2. Bot automatically chat ID detect कर लेगा

**Method 2: Add Bot to Group**
1. Bot को group में add करें
2. Bot को admin बनाएं
3. Group में `/connect` command भेजें

⚠️ Bot को group में admin होना जरूरी है!
"""
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📤 As Source", callback_data="connect_source_group"),
            InlineKeyboardButton("📥 As Target", callback_data="connect_target_group")
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="start_menu")]
    ])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)
    await callback_query.answer()


async def connect_channel_callback(client: Client, callback_query: CallbackQuery):
    """Handle connect channel button"""
    user_id = callback_query.from_user.id
    
    text = """
🔗 **Connect Channel**

Channel को connect करने के लिए:

**Method 1: Forward Message**
1. उस channel का कोई भी message यहां forward करें
2. Bot automatically chat ID detect कर लेगा

**Method 2: Add Bot to Channel**
1. Bot को channel में add करें
2. Bot को admin बनाएं
3. Channel में `/connect` command भेजें (via Linked Group)

⚠️ Bot को channel में admin होना जरूरी है!
"""
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📤 As Source", callback_data="connect_source_channel"),
            InlineKeyboardButton("📥 As Target", callback_data="connect_target_channel")
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="start_menu")]
    ])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)
    await callback_query.answer()


async def connect_source_callback(client: Client, callback_query: CallbackQuery):
    """Handle connect as source"""
    user_id = callback_query.from_user.id
    chat_type = "group" if "group" in callback_query.data else "channel"
    
    user_states[user_id] = {
        "action": "connect_source",
        "chat_type": chat_type
    }
    
    sources = await db.get_user_connections(user_id, "source")
    current_count = len(sources)
    
    text = f"""
📤 **Connect Source {chat_type.title()}**

अभी forward करें उस {chat_type} का कोई भी message जिसे source बनाना है।

📊 Current Sources: {current_count}/{MAX_SOURCES}

⚠️ याद रखें: Bot को {chat_type} में admin होना जरूरी है!
"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_connect")]
    ])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)
    await callback_query.answer()


async def connect_target_callback(client: Client, callback_query: CallbackQuery):
    """Handle connect as target"""
    user_id = callback_query.from_user.id
    chat_type = "group" if "group" in callback_query.data else "channel"
    
    user_states[user_id] = {
        "action": "connect_target",
        "chat_type": chat_type
    }
    
    targets = await db.get_user_connections(user_id, "target")
    current_count = len(targets)
    
    text = f"""
📥 **Connect Target {chat_type.title()}**

अभी forward करें उस {chat_type} का कोई भी message जहां forward करना है।

📊 Current Targets: {current_count}/{MAX_TARGETS}

⚠️ याद रखें: Bot को {chat_type} में admin होना जरूरी है!
"""
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_connect")]
    ])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)
    await callback_query.answer()


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
        await message.reply_text("❌ यह message किसी group/channel से forward नहीं है!")
        return
    
    # Check if bot is admin
    is_admin, error = await check_admin_status(client, chat_id)
    if not is_admin:
        await message.reply_text(f"❌ {error}\n\nBot को पहले {chat_type} में admin बनाएं!")
        return
    
    # Determine connection type
    connection_type = "source" if "source" in action else "target"
    expected_chat_type = state.get("chat_type", "group")
    
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
        emoji = "📤" if connection_type == "source" else "📥"
        await message.reply_text(
            f"✅ **Connection Successful!**\n\n"
            f"{emoji} **{chat_title}**\n"
            f"🆔 Chat ID: `{chat_id}`\n"
            f"📌 Type: {connection_type.title()}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Main Menu", callback_data="start_menu")]
            ])
        )
    else:
        await message.reply_text(f"❌ {msg}")


async def my_connections_callback(client: Client, callback_query: CallbackQuery):
    """Show user's connections"""
    user_id = callback_query.from_user.id
    
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
        [InlineKeyboardButton("🔙 Back", callback_data="start_menu")]
    ])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)
    await callback_query.answer()


async def remove_source_callback(client: Client, callback_query: CallbackQuery):
    """Show sources for removal"""
    user_id = callback_query.from_user.id
    sources = await db.get_user_connections(user_id, "source")
    
    if not sources:
        await callback_query.answer("कोई source नहीं है!", show_alert=True)
        return
    
    buttons = []
    for conn in sources:
        emoji = "📢" if conn["chat_type"] == "channel" else "👥"
        buttons.append([
            InlineKeyboardButton(
                f"{emoji} {conn['chat_title'][:30]}",
                callback_data=f"del_source_{conn['chat_id']}"
            )
        ])
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="my_connections")])
    
    await callback_query.message.edit_text(
        "🗑 **Remove Source**\n\nSelect source to remove:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    await callback_query.answer()


async def remove_target_callback(client: Client, callback_query: CallbackQuery):
    """Show targets for removal"""
    user_id = callback_query.from_user.id
    targets = await db.get_user_connections(user_id, "target")
    
    if not targets:
        await callback_query.answer("कोई target नहीं है!", show_alert=True)
        return
    
    buttons = []
    for conn in targets:
        emoji = "📢" if conn["chat_type"] == "channel" else "👥"
        buttons.append([
            InlineKeyboardButton(
                f"{emoji} {conn['chat_title'][:30]}",
                callback_data=f"del_target_{conn['chat_id']}"
            )
        ])
    buttons.append([InlineKeyboardButton("🔙 Back", callback_data="my_connections")])
    
    await callback_query.message.edit_text(
        "🗑 **Remove Target**\n\nSelect target to remove:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    await callback_query.answer()


async def delete_connection_callback(client: Client, callback_query: CallbackQuery):
    """Delete a connection"""
    user_id = callback_query.from_user.id
    data = callback_query.data
    
    if data.startswith("del_source_"):
        chat_id = int(data.replace("del_source_", ""))
        connection_type = "source"
    else:
        chat_id = int(data.replace("del_target_", ""))
        connection_type = "target"
    
    success = await db.remove_connection(user_id, chat_id, connection_type)
    
    if success:
        await callback_query.answer("✅ Connection removed!", show_alert=True)
    else:
        await callback_query.answer("❌ Error removing connection!", show_alert=True)
    
    # Refresh connections view
    await my_connections_callback(client, callback_query)


async def connect_in_chat(client: Client, message: Message):
    """Handle /connect command in groups/channels"""
    chat = message.chat
    user = message.from_user
    
    if chat.type.value == "private":
        await message.reply_text("यह command groups/channels में use करें!")
        return
    
    # In channels, from_user can be None
    if user is None:
        await message.reply_text(
            "❌ Channel में directly /connect use नहीं कर सकते।\n\n"
            "Bot के PM में जाएं और channel का message forward करें।"
        )
        return
    
    # Check if user is admin
    is_admin, error = await check_admin_status(client, chat.id, user.id)
    if not is_admin:
        await message.reply_text("❌ आप इस chat में admin नहीं हैं!")
        return
    
    # Check if bot is admin
    is_bot_admin, error = await check_admin_status(client, chat.id)
    if not is_bot_admin:
        await message.reply_text(f"❌ {error}")
        return
    
    chat_type = "channel" if chat.type.value == "channel" else "group"
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📤 As Source", callback_data=f"quick_source_{chat.id}"),
            InlineKeyboardButton("📥 As Target", callback_data=f"quick_target_{chat.id}")
        ]
    ])
    
    await message.reply_text(
        f"✅ Bot को इस {chat_type} में connect किया जा सकता है।\n\n"
        f"**{chat.title}**\n"
        f"🆔 Chat ID: `{chat.id}`\n\n"
        f"Select connection type:",
        reply_markup=keyboard
    )


async def quick_connect_internal(client: Client, callback_query: CallbackQuery, chat_id: int, connection_type: str):
    """Shared internal logic for adding connection"""
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
        
        # Check if we should edit text or reply based on context
        try:
            await callback_query.message.edit_text(
                f"✅ **Connected Successfully!**\n\n"
                f"**{chat_info['title']}** added as {connection_type}.\n"
                f"You can now select this in the start menu.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Main Menu", callback_data="start_menu")]
                ])
            )
        except:
             await callback_query.message.reply_text(
                f"✅ **Connected Successfully!**\n\n"
                f"**{chat_info['title']}** added as {connection_type}.\n"
                f"You can now select this in the start menu.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Main Menu", callback_data="start_menu")]
                ])
            )
    else:
        await callback_query.answer(f"❌ {msg}", show_alert=True)


async def quick_connect_callback(client: Client, callback_query: CallbackQuery):
    """Quick connect from within a chat"""
    data = callback_query.data
    
    if data.startswith("quick_source_"):
        chat_id = int(data.replace("quick_source_", ""))
        connection_type = "source"
    else:
        chat_id = int(data.replace("quick_target_", ""))
        connection_type = "target"
        
    await quick_connect_internal(client, callback_query, chat_id, connection_type)
