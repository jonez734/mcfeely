# TODO

## Tests

- [x] Fix test_postoffice_background_task.py - wrong sys.path and non-existent casino.services.postoffice module imports
- [x] Add logentry integration tests for bbsengine6 Phase 5 structured format
  - [x] test_audit_log.py - TestLogentryIntegration (8 tests)
  - [x] test_password_integration.py - TestLogentryIntegration (3 tests)
  - [x] test_end_to_end.py - TestEndToEndLogentryIntegration (6 tests)

## Restructure

- [ ] Restructure postoffice to match casino: instead of `postoffice.service`, use `postoffice.services.<something>` (e.g., `postoffice.services.service` or `postoffice.services.check_mail`)

## GPG Signing and Encryption

- [ ] Integrate with bbsengine6 GPG key system (see bbsengine6/TODO.md)
- [ ] Add GPG key configuration to postoffice service
  - [ ] Load member's GPG public key from bbsengine6.member
  - [ ] Support encryption of fetched emails using recipient's GPG key
- [ ] Add GPG signing for outgoing notifications
  - [ ] Sign notification messages with member's GPG key
  - [ ] Recipients can verify sender authenticity via GPG signature
- [ ] Handle encrypted email processing
  - [ ] Detect PGP encrypted emails during IMAP fetch
  - [ ] Decrypt using member's private key (session-scoped passphrase)
  - [ ] Store decrypted content securely
- [ ] Add message types
  - [ ] `gpg_encrypt` - encrypt message for recipient
  - [ ] `gpg_decrypt` - decrypt received encrypted message
  - [ ] `gpg_sign` - sign message with user's GPG key
  - [ ] `gpg_verify` - verify GPG signature on message
