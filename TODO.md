# TODO

## BED bearer token

- [ ] See `bed/TODO.md` "Bearer token" — adopt `bed.api.auth.AuthService` for BED-mode authentication and reconnect. Replaces per-game `auth` implementations. Mistermcfeely benefits strongly: token-bounded IMAP-style sessions, mail-client reconnection without re-entering the IMAP password. Postoffice (which lives in this repo) gets the same win.

## BED `Sink` integration with `bbsengine6.io` (cross-project)

- [ ] See `bbsengine6/TODO.md` "`bbsengine6.io` sink infrastructure
  for thin-client BED conversion" (Phases 0–5) — the
  `bbsengine6.io.sink.Sink` protocol, `set_io_sink` /
  `reset_io_sink` contextvar API, `bbsengine6.io.echo_render` and
  `mci.parse` / `mci.render` public functions, and the
  `MessageRouter` / `MessageRouterMixin` in
  `bbsengine6/net/router.py`.
- [ ] See `bed/TODO.md` "BED `Sink` integration with
  `bbsengine6.io`" — the `BEDSink` (per-connection adapter in
  `bed/sinks/bed_sink.py`) and the `on_connect_hook` installation
  point on the `WebSocketServer`. Postoffice's `key_f2`
  session-level new-messages query is the "new mail" indicator
  (see `bed/TODO.md` "`key_f2` — session-level new-messages
  query" for the per-game adoption).
- [ ] **No code change required for the postoffice `MessageRouter`
  in v1.** Postoffice can opt into `MessageRouterMixin` later (a
  one-line change to its class declaration:
  `class MessageRouter(MessageRouterMixin):`) to gain the session
  API. v1 ships without the mixin; the BED sink infrastructure
  works against the bare `postoffice.api.handler.MessageRouter`.
- [ ] **Backward compat**: door mode (no `BEDSink` installed) uses
  the default `DefaultSink` behavior, which is the current
  `bbsengine6.io` behavior byte-for-byte. The
  `bbsengine6/tests/test_io_backward_compat.py` suite passes for
  the mistermcfeely door-mode pytest corpus.

## Tests

- [x] Fix test_postoffice_background_task.py - wrong sys.path and non-existent casino.services.postoffice module imports
- [x] Add logentry integration tests for bbsengine6 Phase 5 structured format
  - [x] test_audit_log.py - TestLogentryIntegration (8 tests)
  - [x] test_password_integration.py - TestLogentryIntegration (3 tests)
  - [x] test_end_to_end.py - TestEndToEndLogentryIntegration (6 tests)
- [x] Make test_email_auth_integration.py pass cleanly (31 passed, 0 warnings, 0 shutdown errors)
  - [x] Pin `generate_crypt_hash` to rounds=5000 in `src/postoffice/sasl_password.py` so passlib emits the classic 4-part `$6$<salt>$<hash>` format the tests assert on
  - [x] Refactor `tests/test_email_auth_integration.py` to share setUp/tearDown via a `_Base` class that patches `bbsengine6.database.getpool`, eliminating the `psycopg.pool` "invalid connection option" warnings and `PythonFinalizationError` tracebacks from a real `ConnectionPool` racing interpreter finalization
  - [x] Replace deprecated stdlib `crypt` usage in `src/mcfeely_authd/auth_verify.py` with `passlib.hash.sha512_crypt.verify` and drop the now-unused `import crypt` (and its `filterwarnings` shim) from the test file
  - Runtime dropped from ~5.7s to 0.18s
  - Committed as `09b027e`

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

## Cross-project: casino ↔ postoffice coupling

`casino/src/casino/api/handler.py:1281` hard-imports
`postoffice.service.get_postoffice_service` so the casino BED
`MessageRouter` can register a `check_mail` service that asks the
IMAP poller "any new mail for this player?" This makes the casino
test suite depend on a working postoffice install, and is the
root cause of the 40 pre-existing `ModuleNotFoundError: No module
named 'postoffice.service'` failures in `make test-unit` while the
`## Restructure` work above is in flight.

### Short term (option 3 — smallest diff) — DONE in casino 3877661

- [x] After `## Restructure` lands, update the casino import:

  ```python
  # casino/src/casino/api/handler.py:1281
  from postoffice.services import get_service
  from postoffice.services import check_mail as _check_mail
  ```

  Confirmed in commit `3877661`: 25 previously-failing tests now
  pass (40 failed → 1 failed, 587 passed → 626 passed). The 1
  remaining failure is a pre-existing Postgres pool timeout
  unrelated to this work.

### Long term (option 1 — preferred)

The hard import is a layering smell. Casino's router shouldn't know
about IMAP at all. Preferred end state:

- [ ] Move `PostofficeServiceHandler` (casino/api/handler.py:1276–1308)
      and its registration (handler.py:1331, 1365) out of casino into
      `mistermcfeely`'s BED-side adapter layer (e.g.
      `postoffice.api.bed_handler`).
- [ ] The casino `MessageRouter` should accept a `check_mail` handler
      via constructor injection (or a small `register_service(name, handler)`
      extension point) instead of constructing it inline. Mistermcfeely
      then wires the real postoffice handler at server boot.
- [ ] Once that's in, remove `postoffice` from casino's install
      requirements entirely. `make test-unit` in the casino repo
      should pass with `postoffice` not installed.

### Tracked test failures (cleared by the option-3 step)

These are the casino tests that fail today because of the
`postoffice.service` import; they should go green once the
restructure + import update lands:

- `casino/tests/test_api.py::TestIntegration::test_full_auth_flow`
- `casino/tests/test_server.py::TestServerMocked::test_connect_and_auth`
- `casino/tests/test_server.py::TestServerMocked::test_invalid_message`
- `casino/tests/test_server.py::TestServerMocked::test_list_tables`
- `casino/tests/test_server.py::TestServerMocked::test_ping_pong`
- `casino/tests/test_channel_integration.py::TestChannelSubscriptionIntegration`
  (11 tests)
- `casino/tests/test_member_services.py::TestMemberServicesBED` (5 tests)
- `casino/tests/test_player_observer.py::TestPlayerAndObserver` (2 tests)
- `casino/tests/test_postoffice_channel.py` (7 tests)
- `casino/tests/test_postoffice_service.py` (10 tests)
- `casino/tests/test_postoffice_imap_polling.py` (10 tests)
- `casino/tests/test_postoffice_manual_check.py` (7 tests)

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
