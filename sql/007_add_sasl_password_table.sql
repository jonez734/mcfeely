-- 007_add_sasl_password_table.sql
-- Migration: Add postoffice.sasl_password table for mcfeely-authd SASL authentication

BEGIN;

CREATE TABLE IF NOT EXISTS postoffice.sasl_password (
    member_moniker citext PRIMARY KEY,
    crypt_hash text NOT NULL,
    enabled boolean DEFAULT true,
    datecreated timestamp with time zone DEFAULT now(),
    dateupdated timestamp with time zone DEFAULT now(),
    updated_by text NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sasl_password_enabled
    ON postoffice.sasl_password(enabled) WHERE enabled = true;

-- Grant to postoffice role if it exists
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'postoffice') THEN
        GRANT ALL ON postoffice.sasl_password TO postoffice;
    END IF;
END
$$;

COMMIT;