-- projects Schema
-- Address management for projects.zoidtechnologies.com
-- Primary: PostgreSQL lookup via Postfix pgsql maps
-- Fallback: Static file /etc/postfix/projects_static (commented in main.cf)

create schema if not exists mistermcfeely;

create table if not exists mistermcfeely.project (
    id          bigserial primary key,
    address     text unique not null,
    description text,
    destination text not null,
    kind        text not null check (kind in ('imap', 'mailman', 'both')),
    enabled     boolean default true,
    datecreated timestamp with time zone default now(),
    createdby   text,
    dateupdated timestamp with time zone default now(),
    updatedby   text
);

create index if not exists idx_project_address
    on mistermcfeely.project(address);

create index if not exists idx_project_kind
    on mistermcfeely.project(kind);

create index if not exists idx_project_enabled
    on mistermcfeely.project(enabled);

-- Example entries (commented out)
-- insert into mistermcfeely.project (address, description, destination, kind, enabled)
-- values ('webmaster@projects.zoidtechnologies.com', 'Webmaster contact', 'admin@zoidtechnologies.com', 'imap', true);