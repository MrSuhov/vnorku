-- Migration: Add lsd_blocks table for tracking LSD access blocks (Qrator, Cloudflare, etc.)
-- Date: 2025-10-02

CREATE TABLE IF NOT EXISTS lsd_blocks (
    id SERIAL PRIMARY KEY,
    lsd_config_id INTEGER NOT NULL REFERENCES lsd_configs(id) ON DELETE CASCADE,
    order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    
    -- Block details
    block_type VARCHAR(50) NOT NULL,  -- 'qrator', 'cloudflare', 'captcha', 'rate_limit', 'forbidden', 'other'
    http_status INTEGER,               -- HTTP status code (403, 429, 503, etc.)
    block_reason TEXT,                 -- Human-readable reason or error message
    
    -- Context
    blocked_url TEXT,                  -- URL that was blocked
    html_snippet TEXT,                 -- First 1000 chars of blocked page HTML
    
    -- Timestamps
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_lsd_blocks_lsd_config_id ON lsd_blocks(lsd_config_id);
CREATE INDEX idx_lsd_blocks_order_id ON lsd_blocks(order_id);
CREATE INDEX idx_lsd_blocks_user_id ON lsd_blocks(user_id);
CREATE INDEX idx_lsd_blocks_detected_at ON lsd_blocks(detected_at);
CREATE INDEX idx_lsd_blocks_block_type ON lsd_blocks(block_type);

-- Comments
COMMENT ON TABLE lsd_blocks IS 'Tracks when LSD access is blocked by anti-bot systems (Qrator, Cloudflare, etc.)';
COMMENT ON COLUMN lsd_blocks.block_type IS 'Type of block: qrator, cloudflare, captcha, rate_limit, forbidden, other';
COMMENT ON COLUMN lsd_blocks.http_status IS 'HTTP status code received (403, 429, 503, etc.)';
COMMENT ON COLUMN lsd_blocks.block_reason IS 'Human-readable description of the block';
COMMENT ON COLUMN lsd_blocks.html_snippet IS 'First 1000 characters of the blocked page for debugging';
