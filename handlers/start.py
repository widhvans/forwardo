"""
Start Command Handler - Welcome Interface
Using Pyrogram native KeyboardButtonRequestChat
"""

from pyrogram import Client, filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    KeyboardButtonRequestChat  # This is the correct import
)
from database.mongo import db
from config import BOT_USERNAME


# Welcome message
WELCOME_TEXT = """
🤖 **Auto Forwarding Bot में आपका स्वागत है!**

यह bot आपको messages को एक group/channel से दूसरे में auto-forward करने में मदद करता है।

**🔹 Features:**
• **Intent Forward** - Specific keywords वाले messages forward करें
• **Forward All** - सभी messages forward करें
• Maximum 10 sources और 10 targets connect कर सकते हैं
• Bot को source और target दोनों में admin होना जरूरी है

**📋 Commands:**
• /start - Start menu
• /connect - Connect groups/channels  
• /mode - Select forwarding mode
• /myconnections - View all connections
• /status - Current forwarding status
• /stop - Stop forwarding

**⚠️ Note:** Bot को group/channel में admin बनाना न भूलें!
"""


async def start_command(client: Client, message: Message):
    """Handle /start command"""
    user = message.from_user
    
    # Add user to database
    await db.add_user(
        user_id=user.id,
        username=user.username,
        first_name=user.first_name
    )
    
    # Create inline keyboard
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "➕ Add to Group",
                url=f"https://t.me/{BOT_USERNAME}?startgroup=true"
            ),
            InlineKeyboardButton(
                "➕ Add to Channel",
                url=f"https://t.me/{BOT_USERNAME}?startchannel=true"
            )
        ],
        [
            InlineKeyboardButton("Auto Forward", callback_data="select_mode"),
            InlineKeyboardButton("Connect Chat", callback_data="connect_chat")
        ],
        [
            InlineKeyboardButton("My Connections", callback_data="my_connections"),
            InlineKeyboardButton("Status", callback_data="status")
        ]
    ])
    
    await message.reply_text(
        WELCOME_TEXT,
        reply_markup=keyboard,
        disable_web_page_preview=True
    )


async def start_callback(client: Client, callback_query):
    """Handle start menu callback"""
    try:
        # Clear reply keyboard if any
        msg = await callback_query.message.reply_text(".", reply_markup=ReplyKeyboardRemove())
        await msg.delete()
    except:
        pass
    
    await callback_query.message.edit_text(
        WELCOME_TEXT,
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "➕ Add to Group",
                    url=f"https://t.me/{BOT_USERNAME}?startgroup=true"
                ),
                InlineKeyboardButton(
                    "➕ Add to Channel", 
                    url=f"https://t.me/{BOT_USERNAME}?startchannel=true"
                )
            ],
        [
            InlineKeyboardButton("Auto Forward", callback_data="select_mode"),
            InlineKeyboardButton("Connect Chat", callback_data="connect_chat")
        ],
        [
            InlineKeyboardButton("My Connections", callback_data="my_connections"),
            InlineKeyboardButton("Status", callback_data="status")
        ]
        ]),
        disable_web_page_preview=True
    )
    await callback_query.answer()


async def connect_chat_callback(client: Client, callback_query):
    """Show Connect Chat with native picker tiles"""
    
    # Using separate KeyboardButtonRequestChat class
    keyboard = ReplyKeyboardMarkup(
        [
            [
                KeyboardButton(
                    text="👥 Select Group",
                    request_chat=KeyboardButtonRequestChat(
                        request_id=1,
                        chat_is_channel=False,
                        bot_is_member=True
                    )
                ),
                KeyboardButton(
                    text="📢 Select Channel",
                    request_chat=KeyboardButtonRequestChat(
                        request_id=2,
                        chat_is_channel=True,
                        bot_is_member=True
                    )
                )
            ],
            [KeyboardButton("❌ Cancel")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    text = """
🔗 **Connect Chat**

नीचे के tiles पर click करें:

**👥 Select Group** - Group list खुलेगी
**📢 Select Channel** - Channel list खुलेगी

⚠️ Bot को chat में पहले से member/admin होना जरूरी है!
"""
    
    await callback_query.message.reply_text(text, reply_markup=keyboard)
    await callback_query.answer()


async def handle_chat_shared(client: Client, message: Message):
    """Handle when user selects a chat from native picker"""
    from utils.helpers import check_admin_status
    
    user_id = message.from_user.id
    
    # Get shared chat info - pyrotgfork uses 'chats' list
    chat_shared = message.chat_shared
    if not chat_shared:
        return
    
    # Try different attribute names based on pyrotgfork version
    chat_id = None
    if hasattr(chat_shared, 'chats') and chat_shared.chats:
        # Newer versions use chats list
        chat_id = chat_shared.chats[0].id if chat_shared.chats else None
    elif hasattr(chat_shared, 'chat_id'):
        chat_id = chat_shared.chat_id
    elif hasattr(chat_shared, 'id'):
        chat_id = chat_shared.id
    
    if not chat_id:
        # Debug: print available attributes
        attrs = [attr for attr in dir(chat_shared) if not attr.startswith('_')]
        await message.reply_text(
            f"❌ Chat ID नहीं मिली!\n\nAvailable attrs: {attrs}",
            reply_markup=ReplyKeyboardRemove()
        )
        return
    
    # Get chat details
    try:
        chat = await client.get_chat(chat_id)
        chat_title = chat.title or "Unknown"
    except Exception as e:
        await message.reply_text(
            f"❌ Chat info नहीं मिली: {e}",
            reply_markup=ReplyKeyboardRemove()
        )
        return
    
    # Check if bot is admin
    is_admin, error = await check_admin_status(client, chat_id)
    if not is_admin:
        msg = await message.reply_text(
            f"❌ {error}\n\nBot को पहले **{chat_title}** में admin बनाएं!",
            reply_markup=ReplyKeyboardRemove()
        )
        return
    
    # Auto-add as 'source' (used as generic connection due to limits/DB structure)
    # User requested removal of choice buttons, so we default to adding it.
    from handlers.connect import quick_connect_internal
    # We can't use quick_connect_internal easily because it expects CallbackQuery.
    # We'll use db directly.
    
    success, msg_text = await db.add_connection(
        user_id=user_id,
        chat_id=chat_id,
        chat_title=chat_title,
        chat_type=chat.type.value,
        connection_type="source" # Defaulting to source
    )
    
    if success:
        await message.reply_text(
            f"✅ **Chat Selected!**\n\n"
            f"**{chat_title}**\n"
            f"🆔 `{chat_id}`\n\n"
            f"Added to connections.",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        # If already exists or limit reached, try target?
        # If "already connected", it's fine.
        await message.reply_text(
            f"⚠️ {msg_text}\n\n"
            f"**{chat_title}**\n"
            f"🆔 `{chat_id}`",
            reply_markup=ReplyKeyboardRemove()
        )


async def handle_tile_button(client: Client, message: Message):
    """Fallback handler for text buttons"""
    text = message.text
    if "Cancel" in text:
        await message.reply_text("❌ Cancelled!", reply_markup=ReplyKeyboardRemove())
        return
        
    if "Group" in text:
        chat_type = "group"
    elif "Channel" in text:
        chat_type = "channel"
    else:
        return

    from handlers.connect import user_states
    user_id = message.from_user.id
    user_states[user_id] = {"action": "connect_source", "chat_type": chat_type}
    
    await message.reply_text(
        f"**Connect {chat_type.title()}**\n\nForward message now.",
        reply_markup=ReplyKeyboardRemove()
    )


# Callbacks for add_source / add_target from picker flow
async def add_source_callback(client: Client, callback_query):
    user_id = callback_query.from_user.id
    chat_id = int(callback_query.data.replace("add_source_", ""))
    from handlers.connect import quick_connect_internal
    await quick_connect_internal(client, callback_query, chat_id, "source")

async def add_target_callback(client: Client, callback_query):
    user_id = callback_query.from_user.id
    chat_id = int(callback_query.data.replace("add_target_", ""))
    from handlers.connect import quick_connect_internal
    await quick_connect_internal(client, callback_query, chat_id, "target")


# Placeholders
async def pick_group_callback(client, callback_query): pass
async def pick_channel_callback(client, callback_query): pass
async def tile_source_callback(client, callback_query): pass
async def tile_target_callback(client, callback_query): pass
async def cancel_tile_callback(client, callback_query): 
    await callback_query.message.reply_text("Cancelled", reply_markup=ReplyKeyboardRemove())
async def handle_peer_selected(client, message): pass
