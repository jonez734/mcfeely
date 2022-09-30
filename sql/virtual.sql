\echo virtual
create table if not exists postoffice.virtual (
    pattern text unique primary key not null,
    result text not null,
    enabled boolean default 'f',
    datecreated timestamptz,
    createdbyid bigint constraint fk_postoffice_virtual_createdbyid references engine.__member(id) on update cascade on delete cascade,
    dateupdated timestamptz,
    updatedbyid bigint constraint fk_postoffice_virtual_updatedbyid references engine.__member(id) on update cascade on delete cascade
);
