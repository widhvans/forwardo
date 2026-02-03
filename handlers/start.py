"""
Start Command Handler - Welcome Interface
"""

from pyrogram import Client, filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
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
        # Connect Chat button - opens tiles at bottom
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
    # Remove any existing reply keyboard
    await callback_query.message.reply_text(
        "🔙 Main Menu",
        reply_markup=ReplyKeyboardRemove()
    )
    
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
    """Show Connect Chat with bottom tiles for Group/Channel"""
    
    # Send message with reply keyboard tiles at bottom
    tile_keyboard = ReplyKeyboardMarkup(
        [
            [
                KeyboardButton("👥 Group"),
                KeyboardButton("📢 Channel")
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=False
    )
    
    text = """
🔗 **Connect Chat**

नीचे के tiles से चुनें:
• **👥 Group** - Group connect करने के लिए
• **📢 Channel** - Channel connect करने के लिए

फिर उस chat का कोई message forward करें।
"""
    
    await callback_query.message.reply_text(
        text,
        reply_markup=tile_keyboard
    )
    await callback_query.answer()


async def handle_tile_button(client: Client, message: Message):
    """Handle when user clicks Group or Channel tile button"""
    from handlers.connect import user_states
    
    user_id = message.from_user.id
    text = message.text
    
    if "Group" in text:
        user_states[user_id] = {
            "action": "connect_source",
            "chat_type": "group"
        }
        
        await message.reply_text(
            "👥 **Connect Group**\n\n"
            "अब उस **Group** का कोई message forward करें जिसे connect करना है।\n\n"
            "**📤 Source** के तौर पर connect होगा।\n"
            "Target set करने के लिए फिर से यही process करें।\n\n"
            "⚠️ Bot को group में admin होना जरूरी है!",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📤 As Source", callback_data="tile_source_group"),
                    InlineKeyboardButton("📥 As Target", callback_data="tile_target_group")
                ],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel_tile")]
            ])
        )
    
    elif "Channel" in text:
        user_states[user_id] = {
            "action": "connect_source",
            "chat_type": "channel"
        }
        
        await message.reply_text(
            "📢 **Connect Channel**\n\n"
            "अब उस **Channel** का कोई message forward करें जिसे connect करना है।\n\n"
            "**📤 Source** के तौर पर connect होगा।\n"
            "Target set करने के लिए फिर से यही process करें।\n\n"
            "⚠️ Bot को channel में admin होना जरूरी है!",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📤 As Source", callback_data="tile_source_channel"),
                    InlineKeyboardButton("📥 As Target", callback_data="tile_target_channel")
                ],
                [InlineKeyboardButton("❌ Cancel", callback_data="cancel_tile")]
            ])
        )


async def tile_source_callback(client: Client, callback_query):
    """Set connection type to Source"""
    from handlers.connect import user_states
    
    user_id = callback_query.from_user.id
    data = callback_query.data
    chat_type = "group" if "group" in data else "channel"
    
    user_states[user_id] = {
        "action": "connect_source",
        "chat_type": chat_type
    }
    
    await callback_query.message.edit_text(
        f"📤 **Source {chat_type.title()} Connect**\n\n"
        f"अब उस {chat_type} का कोई message **forward** करें।\n\n"
        f"⚠️ Bot को {chat_type} में admin होना जरूरी है!"
    )
    await callback_query.answer("✅ Source mode selected")


async def tile_target_callback(client: Client, callback_query):
    """Set connection type to Target"""
    from handlers.connect import user_states
    
    user_id = callback_query.from_user.id
    data = callback_query.data
    chat_type = "group" if "group" in data else "channel"
    
    user_states[user_id] = {
        "action": "connect_target",
        "chat_type": chat_type
    }
    
    await callback_query.message.edit_text(
        f"📥 **Target {chat_type.title()} Connect**\n\n"
        f"अब उस {chat_type} का कोई message **forward** करें।\n\n"
        f"⚠️ Bot को {chat_type} में admin होना जरूरी है!"
    )
    await callback_query.answer("✅ Target mode selected")


async def cancel_tile_callback(client: Client, callback_query):
    """Cancel tile selection"""
    from handlers.connect import user_states
    
    user_id = callback_query.from_user.id
    if user_id in user_states:
        del user_states[user_id]
    
    await callback_query.message.edit_text("❌ Cancelled!")
    await callback_query.message.reply_text(
        "🔙 Returning to main menu...",
        reply_markup=ReplyKeyboardRemove()
    )
    await callback_query.answer()


# For backwards compatibility
async def pick_group_callback(client, callback_query):
    pass

async def pick_channel_callback(client, callback_query):
    pass

async def handle_peer_selected(client, message):
    pass
