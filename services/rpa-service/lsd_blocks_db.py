"""
Database operations for lsd_blocks table
"""
import logging
from typing import Optional
from datetime import datetime
import asyncpg

logger = logging.getLogger(__name__)


async def save_lsd_block(
    conn: asyncpg.Connection,
    lsd_config_id: int,
    block_type: str,
    blocked_url: str,
    order_id: Optional[int] = None,
    user_id: Optional[int] = None,
    http_status: Optional[int] = None,
    block_reason: Optional[str] = None,
    html_snippet: Optional[str] = None
) -> Optional[int]:
    """
    Save LSD block information to database
    
    Args:
        conn: asyncpg connection
        lsd_config_id: ID of the blocked LSD config
        block_type: Type of block (qrator, cloudflare, etc.)
        blocked_url: URL that was blocked
        order_id: Optional order ID context
        user_id: Optional user ID context
        http_status: HTTP status code
        block_reason: Human-readable reason
        html_snippet: First 1000 chars of blocked page
    
    Returns:
        ID of created lsd_blocks record or None on error
    """
    try:
        result = await conn.fetchrow(
            """
            INSERT INTO lsd_blocks (
                lsd_config_id, order_id, user_id,
                block_type, http_status, block_reason,
                blocked_url, html_snippet
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id
            """,
            lsd_config_id, order_id, user_id,
            block_type, http_status, block_reason,
            blocked_url, html_snippet
        )
        
        block_id = result['id']
        logger.info(f"💾 Saved lsd_block record: id={block_id}, lsd={lsd_config_id}, type={block_type}")
        return block_id
        
    except Exception as e:
        logger.error(f"❌ Error saving lsd_block: {e}")
        return None


async def get_recent_blocks(
    conn: asyncpg.Connection,
    lsd_config_id: int,
    hours: int = 24
) -> list:
    """
    Get recent blocks for an LSD within last N hours
    
    Returns:
        List of block records
    """
    try:
        result = await conn.fetch(
            """
            SELECT *
            FROM lsd_blocks
            WHERE lsd_config_id = $1
              AND detected_at > NOW() - INTERVAL '%s hours'
            ORDER BY detected_at DESC
            """,
            lsd_config_id, hours
        )
        return [dict(r) for r in result]
        
    except Exception as e:
        logger.error(f"❌ Error getting recent blocks: {e}")
        return []
