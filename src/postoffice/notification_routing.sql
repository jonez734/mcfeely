-- notification_routing.sql
-- Flexible routing rules for mcfeely notifications
-- Supports pattern-based mailbox names and wildcard event types

CREATE TABLE postoffice.notification_routing (
    id BIGSERIAL PRIMARY KEY,
    mailbox_name TEXT NOT NULL,            -- Pattern: 'shared/support@%', 'shared/%', etc.
    event_type TEXT NOT NULL,              -- 'message-new', 'message-claimed', '*' for all
    actor_moniker CITEXT,                    -- Specific user or NULL for any
    recipient_moniker CITEXT NOT NULL,       -- Who gets notified
    notification_type TEXT,                -- Template type (optional, auto-generated if NULL)
    urgency TEXT DEFAULT 'ROUTINE',        -- ROUTINE, IMPORTANT, URGENT, CRITICAL
    delivery_method TEXT DEFAULT 'engine', -- 'engine' (engine.__notify) or future: 'email', 'chat'
    enabled BOOLEAN DEFAULT TRUE,
    datecreated TIMESTAMPTZ DEFAULT NOW(),
    dateupdated TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (actor_moniker) REFERENCES engine.__member(moniker) ON UPDATE CASCADE ON DELETE SET NULL,
    FOREIGN KEY (recipient_moniker) REFERENCES engine.__member(moniker) ON UPDATE CASCADE ON DELETE CASCADE,
    UNIQUE(mailbox_name, event_type, recipient_moniker)
);

CREATE INDEX idx_notification_routing_lookup 
    ON postoffice.notification_routing(mailbox_name, event_type, recipient_moniker)
    WHERE enabled = TRUE;

CREATE INDEX idx_notification_routing_actor 
    ON postoffice.notification_routing(actor_moniker)
    WHERE enabled = TRUE;

GRANT SELECT ON postoffice.notification_routing TO web, term;
GRANT SELECT, INSERT, UPDATE, DELETE ON postoffice.notification_routing TO sysop;
GRANT USAGE ON postoffice.notification_routing_id_seq TO sysop;
