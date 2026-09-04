create table if not exists postoffice.__address (
    "address" text primary key unique not null,
    "maillocation" text not null,
    "enabled" boolean default 't'
);

create table if not exists postoffice.mailbox_password (
    "member_moniker" citext not null constraint fk_postoffice_mailbox_password_member references engine.__member(moniker) on update cascade on delete cascade,
    "address" text not null constraint fk_postoffice_mailbox_password_address references postoffice.__address(address) on update cascade on delete cascade,
    "password" text not null,
    "enabled" boolean default 't',
    "kind" text not null
);

create unique index if not exists idx_postoffice_mailbox_password on postoffice.mailbox_password(member_moniker, address, kind);
