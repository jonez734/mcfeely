-- sasl_password.sql
-- SASL-authenticated password storage for mcfeely-authd
-- Stores SHA-512 crypt hashes compatible with saslauthd and PAM

-- This table stores crypt()-hashed passwords for IMAP/SMTP authentication
-- via the mcfeely-authd daemon. It pairs with:
--   - AES-256-GCM encrypted passwords in engine.__member (for Python usage)
--   - PAM fallback for users not yet migrated to database auth

-- Users with entries in this table authenticate via mcfeely-authd
-- Users without entries fall back to PAM (via saslauthd)

-- ============================================================================
-- Table Definition
-- ============================================================================

CREATE TABLE IF NOT EXISTS postoffice.sasl_password (
    -- Member reference (citext for case-insensitive matching)
    member_moniker citext NOT NULL PRIMARY KEY
        REFERENCES engine.__member(moniker) ON DELETE CASCADE,

    -- SHA-512 crypt hash (format: $6$<salt>$<hash>)
    -- Generated using Python's crypt.crypt(password, crypt.mksalt(crypt.METHOD_SHA512))
    crypt_hash text NOT NULL,

    -- Whether this password is enabled for authentication
    enabled boolean NOT NULL DEFAULT true,

    -- Timestamps for audit trail
    datecreated timestamp with time zone NOT NULL DEFAULT now(),
    dateupdated timestamp with time zone NOT NULL DEFAULT now(),

    -- Who last updated the password
    updated_by text
);

-- ============================================================================
-- Indexes
-- ============================================================================

-- Index on enabled status for quick lookups
CREATE INDEX IF NOT EXISTS idx_sasl_password_enabled
    ON postoffice.sasl_password(enabled) WHERE enabled = true;

-- Index on datecreated for auditing
CREATE INDEX IF NOT EXISTS idx_sasl_password_datecreated
    ON postoffice.sasl_password(datecreated DESC);

-- ============================================================================
-- Comments
-- ============================================================================

COMMENT ON TABLE postoffice.sasl_password IS
    'SASL-authenticated passwords for IMAP/SMTP. Stores SHA-512 crypt hashes for use with mcfeely-authd daemon.';

COMMENT ON COLUMN postoffice.sasl_password.member_moniker IS
    'Member moniker (citext, case-insensitive)';

COMMENT ON COLUMN postoffice.sasl_password.crypt_hash IS
    'SHA-512 crypt hash (format: $6$<salt>$<hash>). Generated with crypt.crypt(password, crypt.mksalt(crypt.METHOD_SHA512))';

COMMENT ON COLUMN postoffice.sasl_password.enabled IS
    'If false, authentication will fail even with correct password. Use to disable without deleting.';

-- ============================================================================
-- Grants
-- ============================================================================

-- postoffice role can manage passwords
GRANT ALL ON postoffice.sasl_password TO postoffice;

-- imapd role can read for authentication (daemon only)
GRANT SELECT ON postoffice.sasl_password TO imapd;

-- Allow sequence for primary key (if using serial)
GRANT USAGE, SELECT ON SEQUENCE postoffice.sasl_password_id_seq TO postoffice;

-- ============================================================================
-- Migration Note
-- ============================================================================

-- When a user's IMAP password is set via member_password.set_personal_password(),
-- a corresponding entry should be created in this table with the crypt hash.
-- This enables the mcfeely-authd daemon to verify passwords without PAM.
--
-- For users not yet migrated:
--   - No entry in this table
--   - saslauthd falls back to PAM (using /etc/shadow)
--   - Use mcfeely-authd.conf fallback_pam setting to control this behavior