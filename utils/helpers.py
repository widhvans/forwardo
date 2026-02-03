"""
Utility helper functions
"""

from pyrogram import Client
from pyrogram.errors import ChatAdminRequired, UserNotParticipant, ChannelPrivate


async def check_admin_status(client: Client, chat_id: int, user_id: int = None):
    """
    Check if bot (or user) is admin in the chat
    Returns: (is_admin: bool, error_message: str or None)
    """
    try:
        if user_id:
            member = await client.get_chat_member(chat_id, user_id)
        else:
            me = await client.get_me()
            member = await client.get_chat_member(chat_id, me.id)
        
        # Handle both string and Enum status
        status = member.status
        status_str = status.value if hasattr(status, 'value') else str(status)
        
        if status_str.lower() in ["administrator", "owner", "creator"]:
            return True, None
        else:
            return False, "Bot/User is not admin in this chat!"
    except UserNotParticipant:
        return False, "Bot is not a member of this chat!"
    except ChannelPrivate:
        return False, "Cannot access this chat. Make sure bot is a member!"
    except Exception as e:
        err = str(e)
        if "CHANNEL_INVALID" in err:
            return False, "❌ Chat info नहीं मिली. Please make Bot Admin first!"
        return False, f"Error checking admin status: {err}"


async def get_chat_info(client: Client, chat_id: int):
    """
    Get chat information
    Returns: (chat_info: dict or None, error_message: str or None)
    """
    try:
        chat = await client.get_chat(chat_id)
        return {
            "id": chat.id,
            "title": chat.title or chat.first_name or "Unknown",
            "type": chat.type.value,
            "username": chat.username
        }, None
    except Exception as e:
        return None, f"Error getting chat info: {str(e)}"


def format_chat_list(connections: list) -> str:
    """Format connections list for display"""
    if not connections:
        return "No connections found."
    
    text = ""
    for i, conn in enumerate(connections, 1):
        # emoji = "📢" if conn["chat_type"] == "channel" else "👥"
        # Since we removed source/target distinction in UI, we just show type
        c_type = "Channel" if conn["chat_type"] == "channel" else "Group"
        text += f"{i}. **{conn['chat_title']}** (`{conn['chat_id']}`) - {c_type}\n"
    return text


def format_stats(stats: dict) -> str:
    """Format stats for display"""
    return f"""📊 **Bot Statistics**

👥 **Total Users:** {stats['total_users']}
🔗 **Total Connections:** {stats['total_connections']}
▶️ **Active Sessions:** {stats['active_sessions']}
"""
