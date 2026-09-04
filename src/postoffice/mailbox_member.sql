-- mailbox_member.sql
-- Per-member overrides for mailbox message-event configuration.
--
-- Mirrors the canonical file at sql/mailbox_member.sql. See that file's
-- header for the full design rationale. The in-package copy exists so the
-- message daemon can import the schema directly from the installed package
-- without depending on the repository layout.
--
-- Per-mailbox defaults (storage + view): see mailbox_config.sql and
-- mailbox_view.sql respectively.

create table if not exists postoffice.__mailbox_member (
    id bigserial primary key,
    mailbox_name text not null
        constraint fk___mailbox_member_mailbox_name
        references postoffice.__mailbox(mailbox_name)
        on update cascade on delete cascade,
    member_moniker citext not null
        references engine.__member(moniker)
        on update cascade on delete cascade,
    enable_new_message_events boolean default true,
    enable_claimed_events boolean default true,
    enable_flag_change_events boolean default false,
    enable_delete_events boolean default false,
    datecreated timestamp with time zone default now(),
    dateupdated timestamp with time zone default now(),
    unique (mailbox_name, member_moniker)
);

create index if not exists idx___mailbox_member_mailbox_name
    on postoffice.__mailbox_member(mailbox_name);

create index if not exists idx___mailbox_member_member_moniker
    on postoffice.__mailbox_member(member_moniker);

create or replace view postoffice.mailbox_member as
    select
        mm.id,
        mm.mailbox_name,
        mm.member_moniker,

        coalesce(mm.enable_new_message_events, m.enable_new_message_events)
            as enable_new_message_events,
        coalesce(mm.enable_claimed_events, m.enable_claimed_events)
            as enable_claimed_events,
        coalesce(mm.enable_flag_change_events, m.enable_flag_change_events)
            as enable_flag_change_events,
        coalesce(mm.enable_delete_events, m.enable_delete_events)
            as enable_delete_events,

        m.imap_poll_interval_seconds,

        m.datecreated as mailbox_datecreated,
        m.dateupdated as mailbox_dateupdated,
        mm.datecreated as override_datecreated,
        mm.dateupdated as override_dateupdated,

        mm.datecreated as datecreated,
        extract(epoch from mm.datecreated) as datecreated_epoch,
        timezone(currentmember.tz, mm.datecreated) as datecreated_local,

        mm.dateupdated as dateupdated,
        extract(epoch from mm.dateupdated) as dateupdated_epoch,
        timezone(currentmember.tz, mm.dateupdated) as dateupdated_local
    from postoffice.__mailbox_member as mm
    join postoffice.__mailbox as m
        on m.mailbox_name = mm.mailbox_name
    left outer join engine.__member as currentmember
        on (currentmember.loginid = current_user)
;

grant select on postoffice.__mailbox_member to web, term;
grant select, insert, update, delete on postoffice.__mailbox_member to sysop;
grant usage on postoffice.__mailbox_member_id_seq to sysop;

grant select on postoffice.mailbox_member to web, term, sysop;
