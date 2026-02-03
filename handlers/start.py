"""
Start Command Handler - Welcome Interface
"""

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
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
        # Connect Chat button - opens submenu with group/channel tiles
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
    """Show Connect Chat options with group/channel tiles"""
    text = """
🔗 **Connect Chat**

नीचे से चुनें कि आप क्या connect करना चाहते हैं:

**👥 Connect Group** - Group को source/target बनाएं
**📢 Connect Channel** - Channel को source/target बनाएं

Select करने के बाद उस chat का कोई message forward करें।
"""
    
    keyboard = InlineKeyboardMarkup([
        # Two tiles - Connect Group and Connect Channel
        [
            InlineKeyboardButton("👥 Connect Group", callback_data="connect_group"),
            InlineKeyboardButton("📢 Connect Channel", callback_data="connect_channel")
        ],
        [InlineKeyboardButton("🔙 Back", callback_data="start_menu")]
    ])
    
    await callback_query.message.edit_text(text, reply_markup=keyboard)
    await callback_query.answer()


# For backwards compatibility - these are imported in bot.py
async def pick_group_callback(client, callback_query):
    """Redirect to connect_group"""
    from handlers.connect import connect_group_callback
    await connect_group_callback(client, callback_query)


async def pick_channel_callback(client, callback_query):
    """Redirect to connect_channel"""
    from handlers.connect import connect_channel_callback
    await connect_channel_callback(client, callback_query)


async def handle_peer_selected(client, message):
    """Placeholder for peer selection - not used in this version"""
    pass
