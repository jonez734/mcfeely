\echo mailbox
create table if not exists postoffice.mailbox (
    "address" text primary key unique not null,
    "maillocation" text not null, --- maildir:~jam
    "enabled" boolean default 't'
);

create table if not exists postoffice.map_mailbox_memberid (
    "memberid" bigint not null constraint fk_postoffice_map_mailbox_memberid references engine.__member(id) on update cascade on delete cascade,
    "address" text not null constraint fk_postoffice_map_mailbox_address references postoffice.mailbox(address) on update cascade on delete cascade,
    "password" text not null
);

\echo mailbox index
create unique index if not exists idx_postoffice_mailbox_address_memberid on postoffice.map_mailbox_memberid(memberid, address);

grant all on postoffice.mailbox to postoffice;
grant select on postoffice.map_mailbox_memberid to dovecot;
grant select on postoffice.mailbox to dovecot;
