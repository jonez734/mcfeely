-- address_manager Schema
-- Generic email address management for multiple domains
-- Supports projects.zoidtechnologies.com, members.zoidtechnologies.com, etc.
--
-- UNUSED: See 007_projects.sql for legacy single-domain schema

CREATE SCHEMA IF NOT EXISTS mistermcfeely;

-- ============================================================================
-- Address Domains
-- ============================================================================

-- Domains like 'projects.zoidtechnologies.com'
CREATE TABLE IF NOT EXISTS mistermcfeely.address_domain (
    id          BIGSERIAL PRIMARY KEY,
    name        TEXT UNIQUE NOT NULL,
    description TEXT,
    enabled     BOOLEAN DEFAULT true,
    datecreated TIMESTAMPTZ DEFAULT now(),
    createdby   TEXT,
    dateupdated TIMESTAMPTZ DEFAULT now(),
    updatedby   TEXT
);

CREATE INDEX IF NOT EXISTS idx_address_domain_name
    ON mistermcfeely.address_domain(name);

CREATE INDEX IF NOT EXISTS idx_address_domain_enabled
    ON mistermcfeely.address_domain(enabled);

-- ============================================================================
-- Addresses
-- ============================================================================

-- Email addresses within a domain
-- Full address = local_part + '@' + domain.name
CREATE TABLE IF NOT EXISTS mistermcfeely.address (
    id          BIGSERIAL PRIMARY KEY,
    domain_id   BIGINT NOT NULL REFERENCES mistermcfeely.address_domain(id) ON DELETE CASCADE,
    local_part  TEXT NOT NULL,
    destination TEXT NOT NULL,
    kind        TEXT NOT NULL CHECK (kind IN ('imap', 'mailman', 'both')),
    description TEXT,
    enabled     BOOLEAN DEFAULT true,
    datecreated TIMESTAMPTZ DEFAULT now(),
    createdby   TEXT,
    dateupdated TIMESTAMPTZ DEFAULT now(),
    updatedby   TEXT,
    UNIQUE (domain_id, local_part)
);

CREATE INDEX IF NOT EXISTS idx_address_domain_id
    ON mistermcfeely.address(domain_id);

CREATE INDEX IF NOT EXISTS idx_address_local_part
    ON mistermcfeely.address(local_part);

CREATE INDEX IF NOT EXISTS idx_address_enabled
    ON mistermcfeely.address(enabled);

-- ============================================================================
-- Initial Data
-- ============================================================================

-- Insert legacy projects domain
-- Note: This corresponds to the old 007_projects.sql schema
INSERT INTO mistermcfeely.address_domain (name, description, datecreated, createdby)
VALUES (
    'projects.zoidtechnologies.com',
    'Legacy domain - migrated from 007_projects.sql (UNUSED)',
    NOW(),
    'system'
) ON CONFLICT (name) DO NOTHING;

-- ============================================================================
-- Permissions (may fail in test DB without postoffice role)
-- ============================================================================

DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'postoffice') THEN
        GRANT ALL ON mistermcfeely.address_domain TO postoffice;
        GRANT ALL ON mistermcfeely.address TO postoffice;
        GRANT USAGE ON SEQUENCE mistermcfeely.address_domain_id_seq TO postoffice;
        GRANT USAGE ON SEQUENCE mistermcfeely.address_id_seq TO postoffice;
    END IF;
END
$$;
