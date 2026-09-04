-- mailbox.sql
-- Per-user IMAP mailboxes (e.g., user.jam, user.alice).
--
-- Renamed from postoffice.mailbox -> postoffice.__address as part of the
-- "tables get __ prefix, views don't" naming convention adopted from
-- casino/src/casino/sql/table_view.sql. The user-facing name `mailbox` is
-- reserved for the per-mailbox message-event configuration view defined in
-- mailbox_view.sql.
--
-- Per-user mailbox records are kept here, keyed by address. This file also
-- declares the legacy postoffice.mailbox_password table that pairs a member
-- with an address and a kind (inbound/outbound).

\echo __address
create table if not exists postoffice.__address (
    "address" text primary key unique not null,
    "maillocation" text not null, --- maildir:~jam
    "enabled" boolean default 't'
);

create table if not exists postoffice.mailbox_password (
    "memberid" bigint not null constraint fk_postoffice_map_mailbox_memberid references engine.__member(id) on update cascade on delete cascade,
    "address" text not null constraint fk_postoffice_map_mailbox_address references postoffice.__address(address) on update cascade on delete cascade,
    "password" text not null,
    "enabled" boolean default 't',
    "kind" text not null -- inbound, outbound
);

\echo mailbox index
create unique index if not exists idx_postoffice_mailbox_password on postoffice.mailbox_password(memberid, address, kind);

grant all on postoffice.__address to :postoffice;
grant select on postoffice.map_address_password to :imapd;
grant select on postoffice.__address to :imapd;
