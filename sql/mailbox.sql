create or replace table postoffice.mailbox (
    "address" text unique not null,
    "maildir" text not null,
    "status" text
);

create or replace table postoffice.map_mailbox_memberid (
    "memberid" bigint constraint postoffice.fk_postoffice_map_mailbox_memberid foreign key engine.member(id) on update cascade on delete cascade,
    "address" bigint constraint postoffice.fk_postoffice_map_mailbox_address foreign key postoffice.mailbox(address) on update cascade on delete cascade
);

    