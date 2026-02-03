"""
Admin Handlers - Owner-only commands (broadcast, stats)
"""

from pyrogram import Client
from pyrogram.types import Message
from database.mongo import db
from config import OWNER_ID
from utils.helpers import format_stats
import asyncio


async def is_owner(user_id: int) -> bool:
    """Check if user is the bot owner"""
    return user_id == OWNER_ID


async def stats_command(client: Client, message: Message):
    """Handle /stats command - Owner only"""
    user_id = message.from_user.id
    
    if not await is_owner(user_id):
        await message.reply_text("❌ यह command केवल bot owner use कर सकता है!")
        return
    
    stats = await db.get_stats()
    await message.reply_text(format_stats(stats))


async def broadcast_command(client: Client, message: Message):
    """Handle /broadcast command - Owner only"""
    user_id = message.from_user.id
    
    if not await is_owner(user_id):
        await message.reply_text("❌ यह command केवल bot owner use कर सकता है!")
        return
    
    # Check for reply or text
    if message.reply_to_message:
        broadcast_msg = message.reply_to_message
    elif len(message.text.split(None, 1)) > 1:
        broadcast_text = message.text.split(None, 1)[1]
        broadcast_msg = None
    else:
        await message.reply_text(
            "**Usage:**\n"
            "/broadcast <message>\n"
            "या किसी message को reply करके /broadcast"
        )
        return
    
    # Get all users
    users = await db.get_all_users()
    total = len(users)
    success = 0
    failed = 0
    
    status_msg = await message.reply_text(
        f"📢 **Broadcasting...**\n\n"
        f"Total: {total}\n"
        f"✅ Success: {success}\n"
        f"❌ Failed: {failed}"
    )
    
    for user in users:
        try:
            if broadcast_msg:
                await broadcast_msg.forward(user["user_id"])
            else:
                await client.send_message(user["user_id"], broadcast_text)
            success += 1
        except Exception:
            failed += 1
        
        # Update status every 20 users
        if (success + failed) % 20 == 0:
            try:
                await status_msg.edit_text(
                    f"📢 **Broadcasting...**\n\n"
                    f"Total: {total}\n"
                    f"✅ Success: {success}\n"
                    f"❌ Failed: {failed}"
                )
            except:
                pass
        
        # Rate limiting
        await asyncio.sleep(0.05)
    
    await status_msg.edit_text(
        f"📢 **Broadcast Complete!**\n\n"
        f"Total: {total}\n"
        f"✅ Success: {success}\n"
        f"❌ Failed: {failed}"
    )


async def users_command(client: Client, message: Message):
    """Handle /users command - Show all users (Owner only)"""
    user_id = message.from_user.id
    
    if not await is_owner(user_id):
        await message.reply_text("❌ यह command केवल bot owner use कर सकता है!")
        return
    
    users = await db.get_all_users()
    
    if not users:
        await message.reply_text("कोई users नहीं हैं!")
        return
    
    text = f"👥 **All Users ({len(users)})**\n\n"
    
    for i, user in enumerate(users[:50], 1):  # Limit to 50
        username = f"@{user.get('username')}" if user.get('username') else "No username"
        text += f"{i}. {user.get('first_name', 'Unknown')} ({username}) - `{user['user_id']}`\n"
    
    if len(users) > 50:
        text += f"\n... and {len(users) - 50} more users"
    
    await message.reply_text(text)
