# Optional screen-independent developer worker (Windows PC)

**Status:** Source implemented and five isolated tests passed on Windows (2026-11-07). **Not yet authenticated against the OpenAI API or accepted on the owner's actual projects.**

This is a **separate, opt-in execution mode**, NOT a replacement for the proven same-chat ChatGPT phone-keyboard cycle. It cannot create new user turns in the consumer ChatGPT app, cannot reuse ChatGPT Plus subscription authentication, and does not bypass Android's locked-screen UI restrictions.

## Why this mode exists

A consumer ChatGPT composer needs an unlocked interactive screen to accept native keyboard input; Android restricts background activity launches and while-in-use microphone starts. A Windows worker with an authorized API key can run project work while the phone is off because its execution is not tied to the phone's display or the ChatGPT app's foreground activity.

The separate worker uses [OpenAI Responses API](https://platform.openai.com/docs/api-reference/responses/create) over HTTPS and may incur separate API costs. **No API key was found or used in the implementation tests; no charge was incurred by those tests.**

## Start only with explicit authorization

Script: `scripts/opt_in_screen_off_worker.py`.

Prerequisites: installed Python 3, Git, an explicitly selected local project checkout on a **`work/*` branch**, and `OPENAI_API_KEY` configured securely on the Windows worker. Do not enter keys into ChatGPT, source control, process arguments, or bridge JSON command files.

Examples (run on the owner's Windows computer, not through a public endpoint):

```powershell
# First: read-only verification and task analysis, bounded to 8 API responses
py -3 scripts/opt_in_screen_off_worker.py --repo "D:\\Project" --task "Audit this project's next milestone" --max-responses 8

# Only when source writes are approved:
py -3 scripts/opt_in_screen_off_worker.py --repo "D:\\Project" --task "Implement and commit the approved work" --write --max-responses 12
```

To allow a non-force push to the current `work/*` branch, add `--push` as well as `--write`. **Push is disabled by default.** A preexisting dirty checkout is rejected when `--write` is requested.

## Safety and durability

- No phone permission, no app UI requirement, no scheduled auto-start. It is independent of the Asterion Control Android service.
- Only bounded `repo_list`, `repo_read`, `repo_status`, opt-in `repo_write`, `repo_commit`, opt-in `repo_push`. No arbitrary shell-command tool, no force-push, no access to `.git`, `.env`, keys or compiled APKs.
- API responses and local tool actions have explicit iteration/tool caps (maximum 30 responses and 90 tool actions). One verified Git work branch only.
- Progress receipts are written atomically to a local per-project state file outside the repo. A preexisting state file blocks automatic re-entry. API timeout/uncertainty stops work without blindly repeating the same operation.
- A `.stop` file beside the worker state is checked before each API step to request voluntary stop. An in-flight network call may still complete before the stop is observed.
- The worker has no native Android app bridge permission; native app actions remain protected by local owner approval.

## Tested vs not tested

**Passed:** Five offline tests verifying branch selection, safe paths, explicit write permission, scoped commit, and refusal to overwrite a dirty repo; Python compilation.

**Pending:** Real Responses API authentication (not configured), actual AI function-call round trips, project-specific compilation, long-running execution while the phone is locked, integration with the phone's voice commands, and cost/budget acceptance.

## Shared bridge requests

The Android `AppBridge` v1 IPC contract lives in `docs/CONTROL_CROSS_APP_API_V1.md`. Partner implementation requests were filed in all 12 other app/game repositories. Those issues are **requests only**; their source remains unchanged.

## Normal ChatGPT cycles

The proven native-keyboard cycle procedure and the 20/10-message conversation rollover guardrail are documented in the private shared repository `Azrazieliz/Asterion-Control-Bridge/README.md`. Switching to a new **consumer ChatGPT** conversation requires the native UI on an unlocked device; this optional API worker does not fulfill that specific requirement.
