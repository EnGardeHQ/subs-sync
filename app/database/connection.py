"""Database connection management for Langflow PostgreSQL database"""

import os
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import asyncpg

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """Async PostgreSQL connection manager"""

    def __init__(self):
        self.database_url = os.getenv("LANGFLOW_DATABASE_URL")
        if not self.database_url:
            raise ValueError("LANGFLOW_DATABASE_URL environment variable is required")

        self.pool = None

    async def create_pool(self):
        """Create connection pool"""
        if self.pool is None:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
            logger.info("Database connection pool created")

    async def close_pool(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Database connection pool closed")

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """
        Get a database connection from the pool.

        Usage:
            async with db.get_connection() as conn:
                result = await conn.fetch("SELECT * FROM flow")
        """
        if self.pool is None:
            await self.create_pool()

        async with self.pool.acquire() as connection:
            yield connection


# Global database connection instance
db = DatabaseConnection()
