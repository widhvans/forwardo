"""
MongoDB Database Operations for Telegram Forwarder Bot
"""

from motor.motor_asyncio import AsyncIOMotorClient
from config import MONGO_URI, DB_NAME
from datetime import datetime


class Database:
    def __init__(self):
        self.client = AsyncIOMotorClient(MONGO_URI)
        self.db = self.client[DB_NAME]
        self.users = self.db["fwd_users"]
        self.connections = self.db["fwd_connections"]
        self.sessions = self.db["fwd_sessions"]

    # ==================== User Operations ====================
    
    async def add_user(self, user_id: int, username: str = None, first_name: str = None):
        """Add a new user or update existing user"""
        user = await self.users.find_one({"user_id": user_id})
        if user:
            await self.users.update_one(
                {"user_id": user_id},
                {"$set": {"username": username, "first_name": first_name, "last_active": datetime.utcnow()}}
            )
        else:
            await self.users.insert_one({
                "user_id": user_id,
                "username": username,
                "first_name": first_name,
                "joined_at": datetime.utcnow(),
                "last_active": datetime.utcnow()
            })

    async def get_user(self, user_id: int):
        """Get user data"""
        return await self.users.find_one({"user_id": user_id})

    async def get_all_users(self):
        """Get all users for broadcasting"""
        return await self.users.find({}).to_list(length=None)

    async def get_total_users(self):
        """Get total user count"""
        return await self.users.count_documents({})

    # ==================== Connection Operations ====================
    
    async def add_connection(self, user_id: int, chat_id: int, chat_title: str, 
                            chat_type: str, connection_type: str):
        """
        Add a source or target connection
        chat_type: 'group' or 'channel'
        connection_type: 'source' or 'target'
        """
        existing = await self.connections.find_one({
            "user_id": user_id,
            "chat_id": chat_id,
            "connection_type": connection_type
        })
        
        if existing:
            return False, "यह chat पहले से connected है!"
        
        # Count existing connections
        count = await self.connections.count_documents({
            "user_id": user_id,
            "connection_type": connection_type
        })
        
        from config import MAX_SOURCES, MAX_TARGETS
        max_limit = MAX_SOURCES if connection_type == "source" else MAX_TARGETS
        
        if count >= max_limit:
            return False, f"Maximum {max_limit} {connection_type} connections allowed!"
        
        await self.connections.insert_one({
            "user_id": user_id,
            "chat_id": chat_id,
            "chat_title": chat_title,
            "chat_type": chat_type,
            "connection_type": connection_type,
            "connected_at": datetime.utcnow()
        })
        return True, "Connection added successfully!"

    async def remove_connection(self, user_id: int, chat_id: int, connection_type: str):
        """Remove a connection"""
        result = await self.connections.delete_one({
            "user_id": user_id,
            "chat_id": chat_id,
            "connection_type": connection_type
        })
        return result.deleted_count > 0

    async def get_user_connections(self, user_id: int, connection_type: str = None):
        """Get user's connections"""
        query = {"user_id": user_id}
        if connection_type:
            query["connection_type"] = connection_type
        return await self.connections.find(query).to_list(length=None)

    async def get_total_connections(self):
        """Get total connections count"""
        return await self.connections.count_documents({})

    # ==================== Session Operations ====================
    
    async def save_session(self, user_id: int, mode: str, sources: list, 
                          targets: list, keywords: list = None, filters: dict = None, active: bool = True):
        """
        Save forwarding session
        mode: 'instant' or 'forward_old'
        """
        # Delete existing session
        await self.sessions.delete_one({"user_id": user_id})
        
        await self.sessions.insert_one({
            "user_id": user_id,
            "mode": mode,
            "sources": sources,
            "targets": targets,
            "keywords": keywords or [],
            "filters": filters or {},
            "active": active,
            "created_at": datetime.utcnow()
        })

    async def get_session(self, user_id: int):
        """Get user's active session"""
        return await self.sessions.find_one({"user_id": user_id, "active": True})

    async def get_all_active_sessions(self):
        """Get all active forwarding sessions"""
        return await self.sessions.find({"active": True}).to_list(length=None)

    async def stop_session(self, user_id: int):
        """Stop user's session"""
        await self.sessions.update_one(
            {"user_id": user_id},
            {"$set": {"active": False}}
        )

    async def get_active_sessions_count(self):
        """Get count of active sessions"""
        return await self.sessions.count_documents({"active": True})

    # ==================== Stats ====================
    
    async def get_stats(self):
        """Get bot statistics"""
        return {
            "total_users": await self.get_total_users(),
            "total_connections": await self.get_total_connections(),
            "active_sessions": await self.get_active_sessions_count()
        }


# Global database instance
db = Database()
