-- 005_add_shared_mailbox.sql
-- Add shared_mailbox table for shared mailbox management

CREATE TABLE IF NOT EXISTS postoffice.shared_mailbox (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    datecreated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    createdbymoniker TEXT NOT NULL,
    dateupdated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updatedbymoniker TEXT,
    enabled BOOLEAN DEFAULT TRUE
);

-- Index for faster lookups
CREATE INDEX IF NOT EXISTS idx_shared_mailbox_name
    ON postoffice.shared_mailbox(name);

CREATE INDEX IF NOT EXISTS idx_shared_mailbox_datecreated
    ON postoffice.shared_mailbox(datecreated DESC);

-- Grant permissions
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'postoffice') THEN
        GRANT ALL ON postoffice.shared_mailbox TO postoffice;
    END IF;
END $$;
