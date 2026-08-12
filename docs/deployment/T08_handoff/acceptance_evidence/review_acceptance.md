# T07 Paired Review and T09 Deployment Acceptance

## T07 paired review

```text
T07_REVIEWER=
T07_REVIEW_COMMIT=
T07_REVIEW_RESULT=WAIT
T07_FINDINGS=
T08_RESPONSE=
CAPTAIN_ACKNOWLEDGEMENT=WAIT
```

Required checks:

- five questions remain isolated by job/question/actor;
- no evidence/version/execution/export crosses jobs;
- partial/failed/timed-out/unavailable are never completed;
- questions and IDs match the T07 manifest;
- T08 does not parse T07 private filenames.

## T09 deployment acceptance

```text
T09_REVIEWER=
T09_ENVIRONMENT=
T09_REVIEW_COMMIT=
T09_DOCKER_BUILD=WAIT
T09_CLEAN_DEPLOYMENT=WAIT
T09_HEALTHCHECK=WAIT
T09_PERSISTENCE_RESTART=WAIT
T09_IMAGE_SECRET_SCAN=WAIT
T09_RESULT=WAIT
CAPTAIN_ACKNOWLEDGEMENT=WAIT
```

Required evidence:

- Docker build from a clean checkout;
- API/UI healthy;
- non-root user;
- named-volume restart recovery;
- no production secret in build context, image history, logs, or exports;
- 7200-second stability report bound to the same final SHA.

T08 must not fill reviewer names or PASS values on behalf of T07/T09.
