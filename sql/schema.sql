-- postoffice Schema
-- Database schema for the postoffice IMAP management system

create schema if not exists postoffice;

-- ============================================================================
-- User Mailboxes
-- ============================================================================

-- Individual user mailboxes (e.g., user.jam, user.alice)
create table if not exists postoffice.mailbox (
    address text primary key unique not null,
    maillocation text not null,
    enabled boolean default true
);

-- Passwords for mailboxes (inbound/outbound authentication)
create table if not exists postoffice.mailbox_password (
    member_moniker citext not null,
    address text not null,
    password text not null,
    enabled boolean default true,
    kind text not null,  -- 'inbound' or 'outbound'
    created_at timestamp with time zone default now(),
    updated_at timestamp with time zone default now(),
    constraint fk_postoffice_map_mailbox_moniker 
        foreign key (member_moniker) 
        references engine.__member(moniker) 
        on update cascade on delete cascade,
    constraint fk_postoffice_map_mailbox_address 
        foreign key (address) 
        references postoffice.mailbox(address) 
        on update cascade on delete cascade
);

create unique index if not exists idx_postoffice_mailbox_password 
    on postoffice.mailbox_password(member_moniker, address, kind);

-- ============================================================================
-- Shared Mailboxes
-- ============================================================================

-- Shared mailboxes that multiple users can access
create table if not exists postoffice.shared_mailbox (
    id bigserial primary key,
    name text not null unique,
    description text,
    datecreated timestamp with time zone default now(),
    createdbymoniker text not null,
    dateupdated timestamp with time zone default now(),
    updatedbymoniker text,
    enabled boolean default true
);

create index if not exists idx_shared_mailbox_name 
    on postoffice.shared_mailbox(name);

create index if not exists idx_shared_mailbox_datecreated 
    on postoffice.shared_mailbox(datecreated desc);

-- ============================================================================
-- Permissions
-- ============================================================================

-- Grant permissions to postoffice role
grant all on postoffice.mailbox to postoffice;
grant all on postoffice.mailbox_password to postoffice;
grant all on postoffice.shared_mailbox to postoffice;

-- Grant read access to imapd role
grant select on postoffice.mailbox to imapd;