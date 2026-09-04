-- mailbox_config.sql
-- Per-mailbox message-event configuration (storage table).
--
-- Mirrors the canonical file at sql/mailbox_config.sql. See that file's
-- header for the full naming-convention rationale. The in-package copy exists
-- so the message daemon can import the schema directly from the installed
-- package without depending on the repository layout.

create table if not exists postoffice.__mailbox (
    id bigserial primary key,
    mailbox_name text not null unique,
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
