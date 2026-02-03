"""
Start Command Handler - Welcome Interface
"""

from pyrogram import Client, filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    RequestPeerTypeChannel, RequestPeerTypeChat
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
        # Add to group/channel buttons
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
        # Connect Chat button
        [
            InlineKeyboardButton("🔗 Connect Chat", callback_data="connect_chat")
        ],
        # Mode selection
        [
            InlineKeyboardButton("⚙️ Select Mode", callback_data="select_mode")
        ],
        # View connections and status
        [
            InlineKeyboardButton("📋 My Connections", callback_data="my_connections"),
            InlineKeyboardButton("📊 Status", callback_data="status")
        ]
    ])
    
    await message.reply_text(
        WELCOME_TEXT,
        reply_markup=keyboard,
        disable_web_page_preview=True
    )


async def start_callback(client: Client, callback_query):
    """Handle start menu callback"""
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
                InlineKeyboardButton("🔗 Connect Chat", callback_data="connect_chat")
            ],
            [
                InlineKeyboardButton("⚙️ Select Mode", callback_data="select_mode")
            ],
            [
                InlineKeyboardButton("📋 My Connections", callback_data="my_connections"),
                InlineKeyboardButton("📊 Status", callback_data="status")
            ]
        ]),
        disable_web_page_preview=True
    )
    await callback_query.answer()


async def connect_chat_callback(client: Client, callback_query):
    """Show Connect Chat options with tiles"""
    text = """
🔗 **Connect Chat**

नीचे के buttons से group या channel choose करें।
Telegram का official interface खुलेगा जहां से आप directly select कर सकते हैं।

**📤 Source** = जहां से messages आएंगे
**📥 Target** = जहां messages जाएंगे
"""
    
    await callback_query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [
                InlineKeyboardButton("👥 Connect Group", callback_data="pick_group"),
                InlineKeyboardButton("📢 Connect Channel", callback_data="pick_channel")
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="start_menu")]
        ])
    )
    await callback_query.answer()


async def pick_group_callback(client: Client, callback_query):
    """Show request_peer keyboard for group selection"""
    user_id = callback_query.from_user.id
    
    # Create reply keyboard with request_peer buttons
    keyboard = ReplyKeyboardMarkup(
        [
            [
                KeyboardButton(
                    "📤 Select Source Group",
                    request_peer=RequestPeerTypeChat(
                        is_creator=None,
                        is_bot_participant=True,
                        button_id=1  # Source group
                    )
                ),
                KeyboardButton(
                    "📥 Select Target Group", 
                    request_peer=RequestPeerTypeChat(
                        is_creator=None,
                        is_bot_participant=True,
                        button_id=2  # Target group
                    )
                )
            ],
            [
                KeyboardButton("❌ Cancel")
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await callback_query.message.reply_text(
        "👥 **Group Connect**\n\n"
        "नीचे के button से group select करें:\n\n"
        "• **Source Group** - जहां से messages आएंगे\n"
        "• **Target Group** - जहां messages जाएंगे\n\n"
        "⚠️ Bot को group में पहले से होना जरूरी है!",
        reply_markup=keyboard
    )
    await callback_query.answer()


async def pick_channel_callback(client: Client, callback_query):
    """Show request_peer keyboard for channel selection"""
    user_id = callback_query.from_user.id
    
    # Create reply keyboard with request_peer buttons
    keyboard = ReplyKeyboardMarkup(
        [
            [
                KeyboardButton(
                    "📤 Select Source Channel",
                    request_peer=RequestPeerTypeChannel(
                        is_creator=None,
                        is_username=None,
                        button_id=3  # Source channel
                    )
                ),
                KeyboardButton(
                    "📥 Select Target Channel",
                    request_peer=RequestPeerTypeChannel(
                        is_creator=None,
                        is_username=None,
                        button_id=4  # Target channel
                    )
                )
            ],
            [
                KeyboardButton("❌ Cancel")
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await callback_query.message.reply_text(
        "📢 **Channel Connect**\n\n"
        "नीचे के button से channel select करें:\n\n"
        "• **Source Channel** - जहां से messages आएंगे\n"
        "• **Target Channel** - जहां messages जाएंगे\n\n"
        "⚠️ Bot को channel में admin होना जरूरी है!",
        reply_markup=keyboard
    )
    await callback_query.answer()


async def handle_peer_selected(client: Client, message: Message):
    """Handle when user selects a peer from request_peer"""
    from pyrogram.types import ReplyKeyboardRemove
    from utils.helpers import check_admin_status
    
    user_id = message.from_user.id
    
    # Check if this is a peer shared message
    if message.chat_shared:
        chat_id = message.chat_shared.chat_id
        button_id = message.chat_shared.button_id
        
        # Get chat info
        try:
            chat = await client.get_chat(chat_id)
            chat_title = chat.title or "Unknown"
            chat_type = "group" if chat.type.value in ["group", "supergroup"] else "channel"
        except Exception as e:
            await message.reply_text(
                f"❌ Chat info नहीं मिली: {e}",
                reply_markup=ReplyKeyboardRemove()
            )
            return
        
        # Check if bot is admin
        is_admin, error = await check_admin_status(client, chat_id)
        if not is_admin:
            await message.reply_text(
                f"❌ {error}\n\nBot को पहले {chat_type} में admin बनाएं!",
                reply_markup=ReplyKeyboardRemove()
            )
            return
        
        # Determine connection type based on button_id
        # 1 = Source Group, 2 = Target Group, 3 = Source Channel, 4 = Target Channel
        if button_id in [1, 3]:
            connection_type = "source"
        else:
            connection_type = "target"
        
        # Add connection
        success, msg = await db.add_connection(
            user_id=user_id,
            chat_id=chat_id,
            chat_title=chat_title,
            chat_type=chat_type,
            connection_type=connection_type
        )
        
        if success:
            emoji = "📤" if connection_type == "source" else "📥"
            await message.reply_text(
                f"✅ **Connection Successful!**\n\n"
                f"{emoji} **{chat_title}**\n"
                f"🆔 Chat ID: `{chat_id}`\n"
                f"📌 Type: {connection_type.title()}\n"
                f"💬 Chat Type: {chat_type.title()}",
                reply_markup=ReplyKeyboardRemove()
            )
        else:
            await message.reply_text(
                f"❌ {msg}",
                reply_markup=ReplyKeyboardRemove()
            )
    
    elif message.text == "❌ Cancel":
        from pyrogram.types import ReplyKeyboardRemove
        await message.reply_text(
            "❌ Cancelled!",
            reply_markup=ReplyKeyboardRemove()
        )
