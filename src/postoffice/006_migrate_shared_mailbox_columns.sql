-- 006_migrate_shared_mailbox_columns.sql
-- Migrate shared_mailbox table columns to match engine.__member naming convention
-- Created: 2026-05-21
-- Previous: created_by -> createdbymoniker, created_at -> datecreated, updated_at -> dateupdated

-- Create schema if not exists (for initial setup)
CREATE SCHEMA IF NOT EXISTS postoffice;

BEGIN;

-- Create table if not exists (initial setup for new installs)
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

-- Rename columns only if they exist (for existing tables)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_schema = 'postoffice' AND table_name = 'shared_mailbox' AND column_name = 'created_by') THEN
        ALTER TABLE postoffice.shared_mailbox RENAME COLUMN created_by TO createdbymoniker;
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_schema = 'postoffice' AND table_name = 'shared_mailbox' AND column_name = 'created_at') THEN
        ALTER TABLE postoffice.shared_mailbox RENAME COLUMN created_at TO datecreated;
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_schema = 'postoffice' AND table_name = 'shared_mailbox' AND column_name = 'updated_at') THEN
        ALTER TABLE postoffice.shared_mailbox RENAME COLUMN updated_at TO dateupdated;
    END IF;
    
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_schema = 'postoffice' AND table_name = 'shared_mailbox' AND column_name = 'updatedbymoniker')
    THEN
        -- Column already exists, skip
    ELSE
        ALTER TABLE postoffice.shared_mailbox ADD COLUMN IF NOT EXISTS updatedbymoniker TEXT;
    END IF;
END $$;

-- Recreate indexes
DROP INDEX IF EXISTS idx_shared_mailbox_created;
CREATE INDEX IF NOT EXISTS idx_shared_mailbox_datecreated
    ON postoffice.shared_mailbox(datecreated DESC);

-- Grant permissions (only if role exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'postoffice') THEN
        GRANT ALL ON postoffice.shared_mailbox TO postoffice;
    END IF;
END $$;

COMMIT;

-- Verify the migration
\d postoffice.shared_mailbox
