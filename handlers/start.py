"""
Start Command Handler - Welcome Interface
Using Pyrogram native RequestChat (for updated version)
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
    try:
        await callback_query.message.reply_text(
            "🔙",
            reply_markup=ReplyKeyboardRemove()
        )
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
    """Show Connect Chat with native picker tiles"""
    
    # Using KeyboardButton.RequestChat (requires Pyrogram v2.1+)
    try:
        keyboard = ReplyKeyboardMarkup(
            [
                [
                    KeyboardButton(
                        text="👥 Select Group",
                        request_chat=KeyboardButton.RequestChat(
                            request_id=1,
                            chat_is_channel=False,
                            bot_is_member=True
                        )
                    ),
                    KeyboardButton(
                        text="📢 Select Channel",
                        request_chat=KeyboardButton.RequestChat(
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

नीचे के tiles पर click करें और list से chat select करें:

**👥 Select Group** - Group picker (Choose a Group)
**📢 Select Channel** - Channel picker (Choose a Channel)

⚠️ **Note:** Bot ko pehle chat me add/admin banana zaroori hai!
"""
        await callback_query.message.reply_text(text, reply_markup=keyboard)
        
    except Exception as e:
        # Fallback for older pyrogram if upgrade failed
        await callback_query.message.reply_text(
            f"❌ Error: {e}\nFalling back to text buttons...",
            reply_markup=ReplyKeyboardRemove()
        )
        # Use simpler text buttons
        await tile_fallback(client, callback_query)

    await callback_query.answer()


async def tile_fallback(client: Client, callback_query):
    """Fallback text buttons if native picker fails"""
    keyboard = ReplyKeyboardMarkup(
        [
            [KeyboardButton("👥 Select Group (Text)"), KeyboardButton("📢 Select Channel (Text)")],
            [KeyboardButton("❌ Cancel")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await callback_query.message.reply_text(
        "Select Type (Text Callback):",
        reply_markup=keyboard
    )


async def handle_chat_shared(client: Client, message: Message):
    """Handle when user selects a chat from native picker"""
    from utils.helpers import check_admin_status
    
    user_id = message.from_user.id
    
    # Get shared chat info (updated attr names for recent pyrogram)
    chat_shared = getattr(message, "chat_shared", None) or getattr(message, "user_shared", None)
    
    if chat_shared:
        chat_id = chat_shared.chat_id
        # request_id sent in the button
        request_id = getattr(chat_shared, "request_id", 0) 
        
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
            await message.reply_text(
                f"❌ {error}\n\nBot को पहले **{chat_title}** में admin बनाएं!",
                reply_markup=ReplyKeyboardRemove()
            )
            return
        
        # Ask source or target
        await message.reply_text(
            f"✅ **Chat Selected!**\n\n"
            f"**{chat_title}**\n"
            f"🆔 `{chat_id}`\n\n"
            f"इसे किस तरह connect करना है?",
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("📤 As Source", callback_data=f"add_source_{chat_id}"),
                    InlineKeyboardButton("📥 As Target", callback_data=f"add_target_{chat_id}")
                ],
                [InlineKeyboardButton("❌ Cancel", callback_data="start_menu")]
            ])
        )
        
        # Remove reply keyboard
        await message.reply_text("⬆️", reply_markup=ReplyKeyboardRemove())


async def handle_tile_button(client: Client, message: Message):
    """Fallback handler for text buttons"""
    text = message.text
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


# Placeholders for old callbacks to prevent errors if clicked
async def pick_group_callback(client, callback_query): pass
async def pick_channel_callback(client, callback_query): pass
async def tile_source_callback(client, callback_query): pass
async def tile_target_callback(client, callback_query): pass
async def cancel_tile_callback(client, callback_query): 
    await callback_query.message.reply_text("Cancelled", reply_markup=ReplyKeyboardRemove())
async def handle_peer_selected(client, message): pass
