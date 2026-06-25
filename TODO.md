# TODO

## Tests

- [x] Fix test_postoffice_background_task.py - wrong sys.path and non-existent casino.services.postoffice module imports
- [x] Add logentry integration tests for bbsengine6 Phase 5 structured format
  - [x] test_audit_log.py - TestLogentryIntegration (8 tests)
  - [x] test_password_integration.py - TestLogentryIntegration (3 tests)
  - [x] test_end_to_end.py - TestEndToEndLogentryIntegration (6 tests)

## Restructure

- [x] Restructure postoffice to match casino: instead of `postoffice.service`, use `postoffice.services.<something>`

### Restructure plan (services package)

Replace `src/postoffice/service.py` with a `src/postoffice/services/` package
that follows casino's `casino/services/{table,player,bank,game,poker}.py`
pattern (one cohesive capability per module). Hard-cut over — no shim, no
backward-compat re-exports of the old module path.

#### Final layout

```
src/postoffice/services/
├── __init__.py        # re-exports + get_service() singleton + POSTOFFICE_CHANNEL + reset_service()
├── config.py          # MailboxConfig + load_mailboxes(cfg)
├── imap_client.py     # count_unseen, fetch_envelopes, extract_preview (service-shaped wrappers)
├── notification.py    # build_email_payload, notify_new_messages, message_send
├── mailbox_poller.py  # MailboxPoller (start/stop/_poll_loop/_poll_all_mailboxes)
├── check_mail.py      # async check_mail(moniker) -> dict
└── claim.py           # claim_message + unclaim_message (combined, thin wrappers)
```

`claim.py` is a single combined module (not split into `claim.py` +
`unclaim.py`) because the two functions are tightly coupled: they share
`notifyd_client.format_claim_flag` and `notifyd_client.get_obfuscate_secret`,
and each is only ~30 lines. Splitting them across two files would be
artificial.

#### Symbol migration map

| Old location                                       | New home                                 |
|----------------------------------------------------|------------------------------------------|
| `service.py::MailboxConfig`                        | `services/config.py::MailboxConfig`      |
| `service.py::PostofficeService.__init__/_load_mailboxes` | `services/config.py::load_mailboxes` + `services/__init__.py::get_service` |
| `service.py::PostofficeService.start/stop/_poll_loop/_poll_all_mailboxes/_check_mailbox` | `services/mailbox_poller.py::MailboxPoller` |
| `service.py::_check_mailbox_sync/_check_mailbox_count` | `services/imap_client.py::count_unseen/fetch_envelopes` |
| `service.py::_process_message_envelope/_notify_new_messages` | `services/notification.py::build_email_payload/notify_new_messages` |
| `service.py::handle_check_mail`                    | `services/check_mail.py::check_mail`     |
| `service.py::POSTOFFICE_CHANNEL`                   | `services/__init__.py::POSTOFFICE_CHANNEL` |
| `service.py::_service_instance/get_postoffice_service/start_postoffice_service/stop_postoffice_service` | `services/__init__.py` |
| `imap_client.py::claim_message/unclaim_message` (module-level funcs) | `services/claim.py::claim_message/unclaim_message` (thin wrappers) |

#### Internal callers to update

- `src/postoffice/api/handler.py:17,134,136,138,155,160,176,195`
  → switch to `from postoffice.services import get_service, check_mail` and
  replace `service.handle_check_mail(moniker)` with `await check_mail(moniker)`.

#### Tests to update

- `tests/test_postoffice_service.py` — `from postoffice.service import …` →
  `from postoffice.services import MailboxConfig, MailboxPoller, get_service`;
  `PostofficeService` → `MailboxPoller`; `_service_instance` →
  `reset_service()`.
- `tests/test_postoffice_config.py` — same import migration.
- `tests/test_postoffice_imap_polling.py` — `patch("postoffice.service.message_send")`
  → `patch("postoffice.services.notification.message_send")`; `PostofficeService._check_mailbox_sync`
  → `imap_client.count_unseen` etc.
- `tests/test_postoffice_notification.py` — same `message_send` patch path
  migration; `_process_message_envelope` → `notification.build_email_payload`.
- `tests/test_postoffice_manual_check.py` — `service.handle_check_mail(moniker)`
  → `await check_mail(moniker)`.
- `tests/test_postoffice_background_task.py` — `PostofficeService` → `MailboxPoller`;
  module-level `postoffice_module._service_instance = None` → `reset_service()`.
- `tests/test_postoffice_channel.py` — `POSTOFFICE_CHANNEL` import path.

#### Execution steps

1. Create `src/postoffice/services/` package (7 files).
2. Update `src/postoffice/api/handler.py`.
3. Update 7 test files.
4. Delete `src/postoffice/service.py`.
5. Verify no residual `postoffice.service` references anywhere.
6. Run `pytest tests/ -v` and `ruff check src/postoffice`.

#### Constraint

- postoffice must not reference casino. Confirmed pre-restructure: zero
  `casino.*` imports in `src/postoffice/`. The new services package
  introduces no new casino coupling.

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
