-- 009_rename_notification_routing_to_message_routing.sql
-- Migration: Rename postoffice.notification_routing -> postoffice.message_routing
-- and postoffice.notification_config -> postoffice.message_config.
-- Indexes, sequences, and grants are renamed to match.
--
-- This accompanies the removal of the notifyd subsystem; the transport
-- is now bbsengine6.message (the "message" replacement for notify),
-- so the routing/config table names follow the new transport's name.

BEGIN;

ALTER TABLE postoffice.notification_routing
    RENAME TO message_routing;

ALTER TABLE postoffice.notification_config
    RENAME TO message_config;

ALTER INDEX postoffice.idx_notification_routing_lookup
    RENAME TO idx_message_routing_lookup;

ALTER INDEX postoffice.idx_notification_routing_actor
    RENAME TO idx_message_routing_actor;

ALTER INDEX postoffice.idx_notification_config_mailbox
    RENAME TO idx_message_config_mailbox;

ALTER SEQUENCE postoffice.notification_routing_id_seq
    RENAME TO message_routing_id_seq;

ALTER SEQUENCE postoffice.notification_config_id_seq
    RENAME TO message_config_id_seq;

DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'web') THEN
        GRANT SELECT ON postoffice.message_routing TO web;
        GRANT SELECT ON postoffice.message_config TO web;
    END IF;
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'term') THEN
        GRANT SELECT ON postoffice.message_routing TO term;
        GRANT SELECT ON postoffice.message_config TO term;
    END IF;
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'sysop') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON postoffice.message_routing TO sysop;
        GRANT USAGE ON postoffice.message_routing_id_seq TO sysop;
        GRANT SELECT, INSERT, UPDATE, DELETE ON postoffice.message_config TO sysop;
        GRANT USAGE ON postoffice.message_config_id_seq TO sysop;
    END IF;
END
$$;

COMMIT;
