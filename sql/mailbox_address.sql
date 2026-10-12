-- mailbox_address.sql
-- Per-mailbox resolution storage table.
--
-- Pairs postoffice.__address rows (BBS-side mailbox registry) with
-- postoffice.__mailbox rows (per-mailbox event config) so the
-- postoffice.mailbox_address view (see mailbox_address_view.sql) can
-- resolve a Cyrus mailbox name to its full BBS-side config in one
-- SELECT.
--
-- Naming convention (per the postoffice table_view pattern from
-- casino/sql/table_view.sql): tables get the __ prefix, views do
-- not. This file owns the storage; mailbox_address_view.sql owns
-- the user-facing view.
--
-- The table is empty by default. The application side is expected
-- to INSERT into this table at the same time it creates a Cyrus
-- mailbox via CyrusAdmin.create_mailbox().

create table if not exists postoffice.__mailbox_address (
    id bigserial primary key,
    mailbox_name text not null
        references postoffice.__mailbox(mailbox_name)
        on update cascade on delete cascade,
    address text not null
        references postoffice.__address(address)
        on update cascade on delete cascade,
    datecreated timestamp with time zone not null default now(),
    unique (mailbox_name, address)
);

create index if not exists idx___mailbox_address_address
    on postoffice.__mailbox_address(address);

create index if not exists idx___mailbox_address_mailbox_name
    on postoffice.__mailbox_address(mailbox_name);

grant select on postoffice.__mailbox_address to web, term;
grant select, insert, update, delete on postoffice.__mailbox_address to sysop;
grant usage on postoffice.__mailbox_address_id_seq to sysop;
