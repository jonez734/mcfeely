\set imapd jam --dovecot
\set postoffice jam

\i schema.sql
\i mailbox.sql
\i virtual.sql
\i message.sql
\i message_routing.sql
\i mailbox_config.sql
\i mailbox_view.sql
\i mailbox_member.sql
