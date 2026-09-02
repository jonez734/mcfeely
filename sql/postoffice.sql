\set imapd jam --dovecot
\set postoffice jam

\i schema.sql
\i mailbox.sql
\i virtual.sql
\i message.sql
\i message_routing.sql
\i message_config.sql
