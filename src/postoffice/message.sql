create table postoffice.__message (
    id text unique not null primary key,
    claimedbymoniker citext constraint fk_mcfeely_message_claimedbymoniker references engine.__member(moniker) on update cascade on delete set null,
    dateclaimed timestamptz,
    metadata jsonb default null
);
