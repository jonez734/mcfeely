-- mailbox_view.sql
-- Per-mailbox message-event configuration (user-facing view).
--
-- Storage:  postoffice.__mailbox         (see mailbox_config.sql)
-- View:     postoffice.mailbox           (this file)
-- Sibling:  postoffice.mailbox_member    (see mailbox_member.sql)
--
-- Follows the postoffice naming convention: tables get __ prefix, views don't.
-- Mirrors the casino/src/casino/sql/table_view.sql pattern of joining
-- engine.__member on current_user to expose per-session-user timezone variants.
--
-- The view exposes every timestamptz column in three forms so callers can pick
-- the right shape for their use case without re-computing in application code:
--   * <col>           timestamptz  -- the underlying UTC value
--   * <col>_epoch     bigint       -- unix epoch seconds (sortable, JSON-friendly)
--   * <col>_local     timestamp    -- rendered in the session user's timezone
--                                    via engine.__member.tz; NULL if the
--                                    current_user is not in engine.__member.

create or replace view postoffice.mailbox as
    select
        m.id,
        m.mailbox_name,

        m.enable_new_message_events,
        m.enable_claimed_events,
        m.enable_flag_change_events,
        m.enable_delete_events,
        m.imap_poll_interval_seconds,

        m.datecreated,
        extract(epoch from m.datecreated) as datecreated_epoch,
        timezone(currentmember.tz, m.datecreated) as datecreated_local,

        m.dateupdated,
        extract(epoch from m.dateupdated) as dateupdated_epoch,
        timezone(currentmember.tz, m.dateupdated) as dateupdated_local
    from postoffice.__mailbox as m
    left outer join engine.__member as currentmember
        on (currentmember.loginid = current_user)
;

grant select on postoffice.mailbox to web, term, sysop;
