\set imapd jam --dovecot
\set postoffice jam

\i schema.sql
\i mailbox.sql
\i virtual.sql
\i message.sql
\i notification_routing.sql
\i notification_config.sql
