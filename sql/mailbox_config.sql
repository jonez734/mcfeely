-- mailbox_config.sql
-- Per-mailbox message-event configuration (storage table).
--
-- Renamed from message_config.sql as part of the notifyd -> message migration
-- (the transport is now bbsengine6.message), and again into the postoffice
-- naming convention (tables get __ prefix, views don't):
--   * storage:     postoffice.__mailbox   (this file)
--   * user-facing: postoffice.mailbox     (see mailbox_view.sql)
--
-- Per-member overrides (sibling): see mailbox_member.sql.

create table if not exists postoffice.__mailbox (
    id bigserial primary key,
    mailbox_name text not null unique,             -- exact mailbox name, no patterns
    enable_new_message_events boolean default true,
    enable_claimed_events boolean default true,
    enable_flag_change_events boolean default false,
    enable_delete_events boolean default false,
    imap_poll_interval_seconds integer default 30,
    datecreated timestamp with time zone default now(),
    dateupdated timestamp with time zone default now()
);

create index if not exists idx___mailbox_mailbox_name
    on postoffice.__mailbox(mailbox_name);

grant select on postoffice.__mailbox to web, term;
grant select, insert, update, delete on postoffice.__mailbox to sysop;
grant usage on postoffice.__mailbox_id_seq to sysop;
