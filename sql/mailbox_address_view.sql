-- mailbox_address_view.sql
-- Per-mailbox resolution view.
--
-- The user-facing surface for the __mailbox_address storage table.
-- Joins __address + __mailbox + the optional per-member override in
-- __mailbox_member, with the standard session-user timezone variants
-- on the storage-table datecreated (mirrors the current_user trick
-- from mailbox_view.sql:38-41 and mailbox_member.sql:95-97).
--
-- The per-member override resolution uses COALESCE(override, default)
-- on each event toggle, matching the pattern at mailbox_member.sql:70-74.
-- When no __mailbox_member row exists for the (mailbox_name, current
-- user) pair, the per-mailbox default in __mailbox wins.
--
-- The view is the canonical "resolve a Cyrus mailbox name to its BBS
-- config" surface; application code should SELECT from it instead of
-- joining __address, __mailbox, and __mailbox_member by hand.
--
-- create or replace view is idempotent so re-running the startup chain
-- on an existing DB is safe (matches the view lifecycle in
-- mailbox_view.sql).

create or replace view postoffice.mailbox_address as
    select
        ma.id,
        ma.mailbox_name,
        ma.address,
        a.maillocation,
        a.enabled as address_enabled,

        coalesce(mm.enable_new_message_events, m.enable_new_message_events)
            as enable_new_message_events,
        coalesce(mm.enable_claimed_events, m.enable_claimed_events)
            as enable_claimed_events,
        coalesce(mm.enable_flag_change_events, m.enable_flag_change_events)
            as enable_flag_change_events,
        coalesce(mm.enable_delete_events, m.enable_delete_events)
            as enable_delete_events,

        m.imap_poll_interval_seconds,

        ma.datecreated,
        extract(epoch from ma.datecreated) as datecreated_epoch,
        timezone(currentmember.tz, ma.datecreated) as datecreated_local,

        m.datecreated as mailbox_datecreated,
        m.dateupdated as mailbox_dateupdated,

        mm.member_moniker as override_member_moniker
    from postoffice.__mailbox_address ma
    join postoffice.__address a on a.address = ma.address
    join postoffice.__mailbox m on m.mailbox_name = ma.mailbox_name
    left outer join postoffice.__mailbox_member mm
        on mm.mailbox_name = ma.mailbox_name
       and mm.member_moniker = (select moniker from engine.__member
                                  where loginid = current_user
                                  limit 1)
    left outer join engine.__member currentmember
        on currentmember.loginid = current_user;

grant select on postoffice.mailbox_address to web, term, sysop;
