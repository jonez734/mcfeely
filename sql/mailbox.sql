create table if not exists postoffice.mailbox (
    "address" text unique not null,
    "maildir" text not null,
    "virtual" boolean default 'f',
    "enabled" boolean default 't'
);

create table if not exists postoffice.map_mailbox_memberid (
    "memberid" bigint constraint fk_postoffice_map_mailbox_memberid references engine.__member(id) on update cascade on delete cascade,
    "address" text constraint fk_postoffice_map_mailbox_address references postoffice.mailbox(address) on update cascade on delete cascade
);
