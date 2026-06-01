-- notification_config.sql
-- Per-mailbox notification event configuration

CREATE TABLE postoffice.notification_config (
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

CREATE INDEX idx_notification_config_mailbox 
    ON postoffice.notification_config(mailbox_name);

GRANT SELECT ON postoffice.notification_config TO web, term;
GRANT SELECT, INSERT, UPDATE, DELETE ON postoffice.notification_config TO sysop;
GRANT USAGE ON postoffice.notification_config_id_seq TO sysop;
