-- message_config.sql
-- Per-mailbox message event configuration
--
-- Renamed from notification_config.sql as part of the notifyd -> message
-- migration; the transport is now bbsengine6.message.

CREATE TABLE postoffice.message_config (
    id BIGSERIAL PRIMARY KEY,
    mailbox_name TEXT NOT NULL UNIQUE,     -- Exact mailbox name (no patterns)
    enable_new_message_events BOOLEAN DEFAULT TRUE,
    enable_claimed_events BOOLEAN DEFAULT TRUE,
    enable_flag_change_events BOOLEAN DEFAULT FALSE,
    enable_delete_events BOOLEAN DEFAULT FALSE,
    imap_poll_interval_seconds INTEGER DEFAULT 30,
    datecreated TIMESTAMPTZ DEFAULT NOW(),
    dateupdated TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_message_config_mailbox
    ON postoffice.message_config(mailbox_name);

GRANT SELECT ON postoffice.message_config TO web, term;
GRANT SELECT, INSERT, UPDATE, DELETE ON postoffice.message_config TO sysop;
GRANT USAGE ON postoffice.message_config_id_seq TO sysop;
