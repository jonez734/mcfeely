-- 004_add_member_mailbox_passwords.sql
-- Add member_mailbox_password table for per-member shared mailbox passwords
-- Stores AES-256-GCM encrypted passwords: base64(nonce + ciphertext + auth_tag)

BEGIN;

CREATE TABLE postoffice.member_mailbox_password (
    id SERIAL PRIMARY KEY,
    mailbox_address TEXT NOT NULL,
    member_moniker CITEXT NOT NULL,
    password_type TEXT NOT NULL,
    encrypted_password TEXT NOT NULL,
    set_by_moniker TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    CONSTRAINT fk_mailbox
        FOREIGN KEY (mailbox_address)
        REFERENCES postoffice.mailbox(address) ON DELETE CASCADE,
    
    CONSTRAINT fk_member
        FOREIGN KEY (member_moniker)
        REFERENCES engine.__member(moniker) ON DELETE CASCADE,
    
    CONSTRAINT chk_password_type 
        CHECK (password_type IN ('inbound', 'outbound')),
    
    UNIQUE(mailbox_address, member_moniker, password_type)
);

CREATE INDEX idx_member_mailbox_password
    ON postoffice.member_mailbox_password(mailbox_address, member_moniker);

CREATE INDEX idx_member_mailbox_password_moniker 
    ON postoffice.member_mailbox_password(member_moniker);

CREATE INDEX idx_member_mailbox_password_created 
    ON postoffice.member_mailbox_password(created_at DESC);

COMMIT;
