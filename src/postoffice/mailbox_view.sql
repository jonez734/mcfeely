-- mailbox_view.sql
-- Per-mailbox message-event configuration (user-facing view).
--
-- Mirrors the canonical file at sql/mailbox_view.sql. See that file's header
-- for the full naming-convention rationale. The in-package copy exists so the
-- message daemon can import the schema directly from the installed package
-- without depending on the repository layout.

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
