# QEMU Guest-Agent Lab Checks — Foundation Tasks 1–4

> Part of `docs/superpowers/plans/2026-09-22-qemu-guest-agent-checks.md`. Read the main plan and approved spec first. Execute these tasks in order before the integration tasks.

### Task 1: Persistence, revisions, and encrypted secret storage

**Files:**
- Create: `app/lab_check_models.py`
- Create: `app/services/lab_checks/__init__.py`
- Create: `app/services/lab_checks/secrets.py`
- Modify: `app/models.py`
- Create: `app/migrations/0126_lab_check_models.py`
- Modify: `requirements.txt`
- Modify: `test_settings.py`
- Create: `app/tests/lab_checks/__init__.py`
- Create: `app/tests/lab_checks/test_models.py`
- Create: `app/tests/lab_checks/test_secrets.py`

**Interfaces:**
- Produces: `StepCheck`, `ValidationLease`, `ValidationRun`, and `ValidationResult` importable from `app.models`.
- Produces: `encrypt_secret_config(value: Mapping[str, object]) -> str` and `decrypt_secret_config(token: str) -> dict[str, object]`.
- Produces: `StepCheck.bump_revision_if_execution_changed(previous: StepCheck) -> None`.

- [ ] **Step 1: Add failing model relationship, constraint, snapshot, and revision tests**

```python
class StepCheckModelTests(TestCase):
    def test_machine_must_belong_to_step_lab(self):
        check = StepCheck(step=self.step, lab_machine=self.other_machine,
                          check_type="file_state", student_label="File", failure_hint="Create it")
        with self.assertRaisesMessage(ValidationError, "same lab"):
            check.full_clean()

    def test_execution_edit_increments_revision_but_hint_edit_does_not(self):
        check = self.make_check(public_config={"path": "{home}/test.txt"})
        original = copy.copy(check)
        check.failure_hint = "Try again"
        check.bump_revision_if_execution_changed(original)
        self.assertEqual(check.definition_revision, 1)
        original = copy.copy(check)
        check.public_config = {"path": "{home}/done.txt"}
        check.bump_revision_if_execution_changed(original)
        self.assertEqual(check.definition_revision, 2)

    def test_result_snapshots_label_revision_step_and_machine(self):
        result = self.make_result()
        self.assertEqual(result.definition_revision, result.check.definition_revision)
        self.assertEqual(result.public_label_snapshot, result.check.student_label)
```

- [ ] **Step 2: Run the model tests and verify the expected import failure**

Run: `python manage.py test app.tests.lab_checks.test_models --settings=test_settings -v 2`

Expected: FAIL because `StepCheck` and the validation models do not exist.

- [ ] **Step 3: Add the four models, guest OS field, constraints, and migration**

```python
class StepCheck(models.Model):
    step = models.ForeignKey("Step", on_delete=models.CASCADE, related_name="vm_checks")
    lab_machine = models.ForeignKey("LabMachine", on_delete=models.PROTECT, related_name="step_checks")
    check_type = models.CharField(max_length=64)
    public_config = models.JSONField(default=dict)
    secret_config_encrypted = models.TextField(blank=True)
    student_label = models.CharField(max_length=160)
    failure_hint = models.CharField(max_length=500)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    removed_at = models.DateTimeField(null=True, blank=True)
    definition_revision = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class ValidationLease(models.Model):
    lab_instance = models.OneToOneField("LabInstance", on_delete=models.CASCADE, related_name="validation_lease")
    run = models.OneToOneField("ValidationRun", on_delete=models.CASCADE, related_name="lease")
    expires_at = models.DateTimeField(db_index=True)

class ValidationRun(models.Model):
    CONTEXTS = [("student_step", "Student step"), ("finish", "Finish"), ("instructor_preview", "Instructor preview")]
    lab_instance = models.ForeignKey("LabInstance", on_delete=models.CASCADE, related_name="validation_runs")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="lab_validation_runs")
    step = models.ForeignKey("Step", null=True, blank=True, on_delete=models.SET_NULL)
    context = models.CharField(max_length=24, choices=CONTEXTS)
    status = models.CharField(max_length=16, default="running")
    outcome = models.CharField(max_length=32, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    deadline_at = models.DateTimeField()
    finished_at = models.DateTimeField(null=True, blank=True)
    pass_count = models.PositiveIntegerField(default=0)
    fail_count = models.PositiveIntegerField(default=0)
    error_count = models.PositiveIntegerField(default=0)
```

Add `LabMachine.GUEST_OS_LINUX`, `LabMachine.GUEST_OS_WINDOWS`, choices, and nullable `guest_os`. Add `ValidationResult` with the check FK, check-type/revision/label/step/machine snapshots, outcome, safe code, and duration; enforce unique `(run, check)` results and useful run/history indexes. Import the new model classes at the end of `app/models.py`, matching the existing cleanup-model split. Generate migration `0126_lab_check_models.py` without a data backfill.

- [ ] **Step 4: Run model tests and migration checks**

Run: `python manage.py test app.tests.lab_checks.test_models --settings=test_settings -v 2`

Expected: PASS.

Run: `python manage.py makemigrations --check --dry-run`

Expected: `No changes detected`.

- [ ] **Step 5: Add failing authenticated-encryption and redaction tests**

```python
@override_settings(LAB_CHECK_SECRET_KEY=Fernet.generate_key().decode("ascii"))
def test_secret_round_trip_does_not_embed_plaintext(self):
    token = encrypt_secret_config({"expected": "flag{private}"})
    self.assertNotIn("flag{private}", token)
    self.assertEqual(decrypt_secret_config(token), {"expected": "flag{private}"})

@override_settings(LAB_CHECK_SECRET_KEY="")
def test_missing_key_fails_closed(self):
    with self.assertRaises(ImproperlyConfigured):
        encrypt_secret_config({"expected": "secret"})
```

- [ ] **Step 6: Add cryptography and implement canonical JSON encryption**

Add a pinned compatible `cryptography` lower bound to `requirements.txt`, set a test-only Fernet key in `test_settings.py`, and implement:

```python
def encrypt_secret_config(value: Mapping[str, object]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _fernet().encrypt(payload).decode("ascii")

def decrypt_secret_config(token: str) -> dict[str, object]:
    try:
        return json.loads(_fernet().decrypt(token.encode("ascii")))
    except (InvalidToken, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SecretConfigError("secret_config_unreadable") from exc
```

- [ ] **Step 7: Run focused tests and commit**

Run: `python manage.py test app.tests.lab_checks.test_models app.tests.lab_checks.test_secrets --settings=test_settings -v 2`

Expected: PASS.

```bash
git add app/models.py app/lab_check_models.py app/migrations/0126_lab_check_models.py app/services/lab_checks app/tests/lab_checks requirements.txt test_settings.py
git commit -m "feat: add lab check persistence and encrypted configuration"
```

---

### Task 2: Typed registry, configuration schemas, and safe command contracts

**Files:**
- Create: `app/services/lab_checks/types.py`
- Create: `app/services/lab_checks/registry.py`
- Create: `app/services/lab_checks/validators.py`
- Create: `app/tests/lab_checks/test_registry.py`
- Create: `app/tests/lab_checks/test_config_validation.py`

**Interfaces:**
- Produces: `GuestCommand(executable: str, arguments: tuple[str, ...], stdin: bytes | None, timeout_seconds: int)`.
- Produces: `GuestCommandResult(exit_code: int, stdout: bytes, stderr: bytes, duration_ms: int)`.
- Produces: `CheckDecision(outcome: str, code: str)` where outcome is `pass`, `fail`, `infrastructure_error`, or `configuration_error`.
- Produces: `CheckValidator.normalize(guest_os, public_config, secret_config) -> NormalizedCheck`.
- Produces: `CheckValidator.build_commands(normalized, username) -> tuple[GuestCommand, ...]` and `evaluate(normalized, results) -> CheckDecision`.
- Produces: `get_validator(type_id: str) -> CheckValidator` and `registered_validators() -> tuple[CheckValidator, ...]`.

- [ ] **Step 1: Write failing registry and hostile-input tests**

```python
def test_duplicate_type_id_is_rejected(self):
    registry = CheckRegistry()
    registry.register(FakeValidator("file_state"))
    with self.assertRaisesMessage(RegistryError, "duplicate"):
        registry.register(FakeValidator("file_state"))

def test_unknown_fields_and_control_characters_fail_closed(self):
    validator = get_validator("service_state")
    with self.assertRaises(ConfigError):
        validator.normalize("linux", {"service": "sshd\n/bin/sh", "extra": True}, {})

def test_port_range_and_protocol_are_strict(self):
    validator = get_validator("listening_port")
    with self.assertRaises(ConfigError):
        validator.normalize("windows", {"port": 70000, "protocol": "icmp"}, {})
```

Cover path length/encoding, absolute or `{home}/...` paths only, usernames/service/package/process names, IP literals, exact enum values, 64 KiB expected content, and unsupported OS/type combinations.

- [ ] **Step 2: Run tests and verify imports fail**

Run: `python manage.py test app.tests.lab_checks.test_registry app.tests.lab_checks.test_config_validation --settings=test_settings -v 2`

Expected: FAIL because registry/types do not exist.

- [ ] **Step 3: Implement immutable types, strict helpers, protocol, and registry**

```python
@dataclass(frozen=True)
class GuestCommand:
    executable: str
    arguments: tuple[str, ...] = ()
    stdin: bytes | None = None
    timeout_seconds: int = 5

class CheckValidator(Protocol):
    type_id: str
    supported_os: frozenset[str]
    secret_fields: frozenset[str]
    def normalize(self, guest_os: str, public_config: Mapping[str, object],
                  secret_config: Mapping[str, object]) -> NormalizedCheck: ...
    def build_commands(self, normalized: NormalizedCheck, username: str) -> tuple[GuestCommand, ...]: ...
    def evaluate(self, normalized: NormalizedCheck,
                 results: Sequence[GuestCommandResult]) -> CheckDecision: ...
```

Use explicit per-type allowed-key sets and validators; never coerce unknown strings to booleans, integers, paths, protocols, or states. Register immutable IDs: `file_state`, `file_content`, `service_state`, `identity_state`, `package_state`, `process_state`, and `listening_port`.

- [ ] **Step 4: Add command-shape tests proving instructor data cannot select executables**

```python
def test_all_executables_come_from_allowlist(self):
    for case in valid_catalog_cases():
        commands = get_validator(case.type_id).build_commands(case.normalized, case.username)
        self.assertTrue(commands)
        self.assertTrue(all(command.executable in ALLOWED_EXECUTABLES for command in commands))

def test_expected_file_content_uses_stdin_not_arguments(self):
    command = build_file_content_command(expected="flag{private}")
    self.assertNotIn("flag{private}", " ".join(command.arguments))
    self.assertIn(b"flag{private}", command.stdin)
```

- [ ] **Step 5: Run focused tests and commit**

Run: `python manage.py test app.tests.lab_checks.test_registry app.tests.lab_checks.test_config_validation --settings=test_settings -v 2`

Expected: PASS.

```bash
git add app/services/lab_checks app/tests/lab_checks
git commit -m "feat: add typed lab check registry"
```

---

### Task 3: Linux and Windows built-in validators

**Files:**
- Modify: `app/services/lab_checks/validators.py`
- Create: `app/services/lab_checks/windows_scripts.py`
- Create: `app/tests/lab_checks/test_linux_validators.py`
- Create: `app/tests/lab_checks/test_windows_validators.py`

**Interfaces:**
- Consumes: Task 2 command/result/decision types and registry.
- Produces: complete implementations for all seven type IDs on supported Linux and Windows guests.
- Produces: `encode_windows_script(script_id: str) -> str`; only identifiers defined in `WINDOWS_SCRIPTS` are accepted.

- [ ] **Step 1: Write table-driven Linux command and parser tests for every catalog entry**

```python
LINUX_CASES = [
    ("file_state", {"path": "{home}/test.txt", "kind": "file", "state": "present"}, "/usr/bin/test"),
    ("service_state", {"service": "sshd", "state": "running"}, "/usr/bin/systemctl"),
    ("process_state", {"process": "sshd", "state": "running"}, "/usr/bin/pgrep"),
    ("listening_port", {"port": 22, "protocol": "tcp", "state": "listening"}, "/usr/sbin/ss"),
]

def test_linux_command_and_decision(self):
    for type_id, config, executable in LINUX_CASES:
        validator = get_validator(type_id)
        normalized = validator.normalize("linux", config, {})
        commands = validator.build_commands(normalized, "student")
        self.assertEqual(commands[0].executable, executable)
        self.assertEqual(validator.evaluate(normalized, [ok_result()]).outcome, "pass")
```

Add explicit tests for directory absence, exact/contains file content, user existence, group existence, membership, dpkg/rpm/apk package fallbacks, stopped/absent negative probes, UDP, address filtering, invalid UTF-8, and output cap signals.

- [ ] **Step 2: Implement Linux command builders and parsers without a shell**

Use only fixed executable constants and argument tuples. Resolve `{home}` to `/home/<validated username>`; do not expand arbitrary variables. Send file-content patterns through stdin to fixed-string grep. For package state, emit bounded fallback probes for dpkg-query, rpm, and apk and classify `configuration_error` only when no supported inventory tool can execute.

```python
def linux_file_content_command(path: str, match: str, expected: str) -> GuestCommand:
    flag = "-Fxq" if match == "exact" else "-Fq"
    return GuestCommand(
        executable="/usr/bin/grep",
        arguments=(flag, "--", path),
        stdin=(expected + "\n").encode("utf-8"),
    )
```

- [ ] **Step 3: Run Linux tests and verify all catalog cases pass**

Run: `python manage.py test app.tests.lab_checks.test_linux_validators --settings=test_settings -v 2`

Expected: PASS.

- [ ] **Step 4: Write Windows static-script and payload-isolation tests**

```python
def test_windows_uses_only_static_encoded_script_and_json_stdin(self):
    normalized = get_validator("file_state").normalize(
        "windows", {"path": r"C:\\Users\\student\\test.txt", "kind": "file", "state": "present"}, {})
    command = get_validator("file_state").build_commands(normalized, "student")[0]
    self.assertEqual(command.executable.lower(), "powershell.exe")
    self.assertNotIn("test.txt", " ".join(command.arguments))
    self.assertIn(b"test.txt", command.stdin)

def test_unknown_script_identifier_is_rejected(self):
    with self.assertRaises(KeyError):
        encode_windows_script("instructor supplied")
```

Cover file/directory, content, Get-Service, local users/groups/membership, uninstall-registry package inventory, Get-Process, and Get-NetTCPConnection/Get-NetUDPEndpoint results, including malicious quote/backtick/semicolon payloads.

- [ ] **Step 5: Implement static PowerShell scripts and Windows decisions**

Each script reads a UTF-8 JSON object from standard input, uses `ConvertFrom-Json`, emits one compact application-defined JSON result, and never invokes `Invoke-Expression`, `cmd.exe`, `Start-Process`, or a payload-provided command. Encode only the static script source with UTF-16LE Base64 for `-EncodedCommand`.

```python
def windows_command(script_id: str, payload: Mapping[str, object]) -> GuestCommand:
    return GuestCommand(
        executable="powershell.exe",
        arguments=("-NoLogo", "-NoProfile", "-NonInteractive", "-EncodedCommand", encode_windows_script(script_id)),
        stdin=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
    )
```

- [ ] **Step 6: Run validator suites and commit**

Run: `python manage.py test app.tests.lab_checks.test_linux_validators app.tests.lab_checks.test_windows_validators --settings=test_settings -v 2`

Expected: PASS.

```bash
git add app/services/lab_checks/validators.py app/services/lab_checks/windows_scripts.py app/tests/lab_checks
git commit -m "feat: add Linux and Windows lab validators"
```

---

### Task 4: Bounded Proxmox guest-agent executor

**Files:**
- Modify: `app/proxmox_guac_api.py`
- Create: `app/services/lab_checks/executor.py`
- Create: `app/tests/lab_checks/test_executor.py`

**Interfaces:**
- Consumes: Task 2 `GuestCommand`.
- Produces: `QemuGuestExecutor.execute(machine: LabInstanceMachine, command: GuestCommand) -> GuestCommandResult`.
- Produces exceptions: `GuestUnavailable`, `GuestTimeout`, `GuestProtocolError`, and `GuestOutputLimit`; orchestration maps all four to `infrastructure_error`.

- [ ] **Step 1: Write failing mocked Proxmox execution tests**

```python
def test_exec_posts_fixed_command_polls_status_and_returns_bounded_bytes(self):
    self.agent_exec.post.return_value = {"pid": 41}
    self.agent_status.get.return_value = {"exited": 1, "exitcode": 0, "out-data": "ok"}
    result = self.executor.execute(self.machine, GuestCommand("/usr/bin/test", ("-f", "/tmp/x")))
    self.assertEqual(result.exit_code, 0)
    self.assertEqual(result.stdout, b"ok")

def test_timeout_and_oversized_output_fail_as_infrastructure(self):
    self.agent_status.get.return_value = {"exited": 0}
    with self.assertRaises(GuestTimeout):
        self.executor.execute(self.machine, self.command)
    self.agent_status.get.return_value = {"exited": 1, "exitcode": 0, "out-data": "x" * 65537}
    with self.assertRaises(GuestOutputLimit):
        self.executor.execute(self.machine, self.command)
```

Also test missing/stopped VM, agent disabled, malformed/no PID response, stderr cap, nonzero exit returned to the validator, and that exceptions/log records do not contain command arguments or output.

- [ ] **Step 2: Run executor tests and verify failure**

Run: `python manage.py test app.tests.lab_checks.test_executor --settings=test_settings -v 2`

Expected: FAIL because `QemuGuestExecutor` does not exist.

- [ ] **Step 3: Add the focused executor using the existing Proxmox client factory**

Reuse `get_proxmox_api_client` from `app/proxmox_guac_api.py`; add only a small helper there if the current client factory cannot address `nodes/<node>/qemu/<vmid>/agent/exec` and `exec-status`. Poll with `time.monotonic()`, cap decoded stdout and stderr before returning, and pass stdin through Proxmox `input-data` using the API's required encoding.

```python
class QemuGuestExecutor:
    def execute(self, machine: LabInstanceMachine, command: GuestCommand) -> GuestCommandResult:
        self._assert_allowed(command)
        client = get_proxmox_api_client(machine.proxmox_server)
        pid = self._start(client, machine, command)
        raw = self._poll_until_exit(client, machine, pid, command.timeout_seconds)
        return self._bounded_result(raw)
```

The allow-list check compares exact executable strings generated by validators. Logging includes machine/run identifiers and safe exception codes only.

- [ ] **Step 4: Run executor and validator tests and commit**

Run: `python manage.py test app.tests.lab_checks.test_executor app.tests.lab_checks.test_linux_validators app.tests.lab_checks.test_windows_validators --settings=test_settings -v 2`

Expected: PASS.

```bash
git add app/proxmox_guac_api.py app/services/lab_checks/executor.py app/tests/lab_checks/test_executor.py
git commit -m "feat: execute bounded QEMU guest checks"
```

---


