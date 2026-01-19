"""Database connection management for both Langflow and EnGarde PostgreSQL databases"""

import os
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import asyncpg

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Async PostgreSQL connection manager for dual database architecture"""

    def __init__(self):
        # Langflow database (for templates and flows)
        self.langflow_database_url = os.getenv("LANGFLOW_DATABASE_URL")
        if not self.langflow_database_url:
            raise ValueError("LANGFLOW_DATABASE_URL environment variable is required")

        # EnGarde database (for subscription tiers and walker agents)
        self.engarde_database_url = os.getenv("ENGARDE_DATABASE_URL")
        if not self.engarde_database_url:
            raise ValueError("ENGARDE_DATABASE_URL environment variable is required")

        self.langflow_pool = None
        self.engarde_pool = None

    async def create_pools(self):
        """Create connection pools for both databases"""
        if self.langflow_pool is None:
            self.langflow_pool = await asyncpg.create_pool(
                self.langflow_database_url,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
            logger.info("Langflow database connection pool created")

        if self.engarde_pool is None:
            self.engarde_pool = await asyncpg.create_pool(
                self.engarde_database_url,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
            logger.info("EnGarde database connection pool created")

    async def close_pools(self):
        """Close connection pools for both databases"""
        if self.langflow_pool:
            await self.langflow_pool.close()
            self.langflow_pool = None
            logger.info("Langflow database connection pool closed")

        if self.engarde_pool:
            await self.engarde_pool.close()
            self.engarde_pool = None
            logger.info("EnGarde database connection pool closed")

    @asynccontextmanager
    async def get_langflow_connection(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """
        Get a connection to the Langflow database.

        Usage:
            async with db.get_langflow_connection() as conn:
                result = await conn.fetch("SELECT * FROM flow")
        """
        if self.langflow_pool is None:
            await self.create_pools()

        async with self.langflow_pool.acquire() as connection:
            yield connection

    @asynccontextmanager
    async def get_engarde_connection(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """
        Get a connection to the EnGarde database.

        Usage:
            async with db.get_engarde_connection() as conn:
                result = await conn.fetch("SELECT * FROM users")
        """
        if self.engarde_pool is None:
            await self.create_pools()

        async with self.engarde_pool.acquire() as connection:
            yield connection


# Global database connection instance
db = DatabaseConnection()
