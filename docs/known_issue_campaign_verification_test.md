# Known issue: `test_campaign_verification_endpoint` fails with HTTP 401

**Status:** pre-existing, unrelated to the verification work, **not fixed**. It is documented here at the owner's request, and no code was changed.

## Symptom

```
tests/test_campaigns.py:71: assert verify_res.status_code == 200
E   assert 401 == 200
```

It is the only failure in the full suite: 1 failed, 427 passed at the time of writing.

## Cause

- `POST /api/campaigns/{campaign_id}/verify` (`app/routers/campaigns.py`, `verify_campaign`) requires an authenticated user, through `current_user: User = Depends(get_current_user)`. It also checks that the caller is the campaign's creator or an admin.
- The requirement was added on `main` in commit `d649f56` ("Implemented RAG", 2026-11-15). In the initial commit (`09c47b3`), the endpoint took no user.
- The test was not updated. It creates a campaign anonymously, then calls the verify endpoint without an `Authorization` header, so the dependency returns 401 before the handler runs.

The endpoint and the test are identical on `main` and on this branch: `git diff main...HEAD -- app/routers/campaigns.py tests/test_campaigns.py` is empty. The failure therefore also occurs on `main`.

## Why it is not fixed here

The fix belongs to production API code or its tests, not to the development verification packages, and the current instructions exclude unrelated changes. It does not affect any frozen package, benchmark, freeze manifest or the v5 evaluation tooling.

## Suggested fix (for a separate, approved change)

Two options; the first is preferred:

1. **Update the test to match the endpoint's intended access rule.** Register and log in a user, create the campaign as that user, and call `/verify` with the bearer token. Also add a test that an anonymous call returns 401 and another user's call returns 403.
2. **Make the endpoint optional-auth.** This is not recommended: it would expose private campaign evidence to anonymous callers, which the creator/admin check was added to prevent.
