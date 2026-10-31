# Cyber City SOC integration validation (dev only)

This suite checks the joined Blue Team analyst workflow using Django's isolated test database. It does **not** connect to Proxmox, QEMU, Wazuh, Checkmk, Mosquitto or an ESP32.

Run in the existing LabTech development virtual environment (do not recreate it):

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
python manage.py test app.tests.test_cybercity_soc_workflow_integration
python manage.py test app.tests.test_cybercity_soc_analyst_workspace app.tests.test_cybercity_soc_analyst_triage app.tests.test_cybercity_soc_incident_evidence app.tests.test_cybercity_soc_response_plan app.tests.test_cybercity_soc_response_review app.tests.test_cybercity_soc_response_runbook app.tests.test_cybercity_soc_response_rehearsal app.tests.test_cybercity_soc_rehearsal_outcomes app.tests.test_cybercity_soc_scenario_response_rules
```

Expected contract: instructor authors an expected response rule; student can open assigned queue/case, submit triage, write response plan, record runbook progress, rehearse, and receive deterministic scenario feedback. Incident state remains unchanged; no machine actions run. Cross-team access is forbidden.

## Physical integration pilot — not yet executed

Use a dedicated disposable Cyber City VM and single test ESP32 building on an isolated lab VLAN. Obtain instructor approval before any real disruption. Record time and event IDs at every hop:

1. QEMU Guest Agent returns an explicitly configured monitor result for the target VM.
2. LabTech monitor evaluator stores the observation; verify whether it is associated with a trigger (a condition match alone is not a confirmed incident).
3. Authorized alert/incident mapping displays the event to the assigned SOC team.
4. The instructor-configured action pipeline emits a test MQTT command with an exercise correlation ID.
5. ESP32 receives and acknowledges the command and reports status back; LabTech displays the status.
6. Reset the VM from an approved snapshot/linked-clone template; confirm recovery in monitoring and close the drill.

Do not claim this live path is complete until steps 1–6 have been demonstrated and logs captured. Do not run physical or VM disruption from the Django test suite.
