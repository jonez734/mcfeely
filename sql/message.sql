create table __message (
    id text unique not null primary key,
    claimedbyid bigint constraint fk_mcfeely_message_claimedbyid references engine(id) on update cascade on delete set null,
    dateclaimed timestamptz
);
    