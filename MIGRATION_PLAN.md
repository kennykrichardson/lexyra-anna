# Lexyra-Anna migration plan

Status: migration implemented in the destination; local protocol tests and strict manifest checks pass. The Ubuntu packaging workflow and binary smoke test are added, but cannot be triggered from this Windows-only, non-GitHub checkout. Production-installed Executa sampling and Linux binary execution remain unverified.

## Source and destination

- Read-only source: `K:\My Apps\Lexyra`
- Independent destination: `K:\My Apps\Lexyra-Anna`
- Both paths exist. The source contains the expected React 18, TypeScript, Vite, and FastAPI application. The destination was empty at inspection time.
- Source Git status was clean (`main...origin/main`). No source files were written.

## Findings

- The UI already implements all six requested styles, text input/output, loading/error states, copy, regenerate, and a responsive branded interface.
- The current UI calls a remote HTTP API and displays API connectivity status. The Anna edition should replace that transport with Anna Runtime tool invocation while preserving the components, styles, and interactions.
- The existing FastAPI backend uses a Cloudflare Workers AI request path. The Anna edition must not copy or call that backend as its primary workflow. `backend/.env.example` mentions Hugging Face even though backend source reads Cloudflare variables; this mismatch should be corrected or replaced in the Anna project documentation and must never carry credentials.
- The repository listing contains no backend tests, although its README describes a `backend/tests/test_api.py` file. Tests need to be authored for the new Executa.
- Installed local tooling reports `anna-app` 0.1.61. Its bundled `@anna-ai/app-runtime` package is 0.26.0, and the bundled ACL capability table is version 0.30.0. The installed schema recognizes `llm.sample` and the CLI exposes `validate --strict`; this is local tool evidence, not proof of the server-side schema currently deployed.
- The official examples repository describes Executa as JSON-RPC 2.0 over stdio and includes a Python sampling example. That example advertises v2 sampling at initialization and sends reverse `sampling/createMessage` requests through the host. It declares `llm.sample`; the user's account must grant sampling.

## Proposed destination contents

Copy as source material, then modify only inside `Lexyra-Anna`:

- Frontend source and assets: `frontend/src/**`, `frontend/public/**`, `frontend/index.html`, Vite and TypeScript configuration, `package.json`, and `package-lock.json`.
- Anna app metadata and starting manifest: root `app.json`, `manifest.json`; update them to the installed CLI schema and Anna tool permissions after confirming field names.
- `README.md`, `LICENSE`, and `.gitignore`, rewritten for independent Anna-native setup and distribution.
- Existing screenshots only if useful to project documentation. Keep the visual assets used by the UI.
- Backend writing-style definitions may be used as reference when implementing the Executa, but the Cloudflare client, FastAPI server, and standalone deployment configuration should not be part of the Anna runtime path.
- Do not copy `.git`, `.anna` developer state, `.lexyra` virtual environment, generated bundles/build output, or any `.env` secret file. Keep only sanitized `.env.example` files if still relevant; the native app should need no external model credentials.

## Planned architecture

1. Keep the existing React UI and Vite output as the Anna app bundle. Replace the HTTP API module with a small Anna Runtime adapter that connects using the documented browser SDK URL, invokes the declared bundled Executa handle, and validates the returned tool result before exposing it to the UI.
2. Package a Python Executa under a dedicated destination subdirectory. It will expose a single enhancement tool with validated text and one of the six supported style identifiers.
3. Implement the Executa stdio JSON-RPC protocol and Anna v2 initialization using the official Python SDK/sample pattern where possible. For each request, issue one reverse `sampling/createMessage` call with a system instruction that preserves meaning, facts, names, dates, and qualifications; treats submitted text as content rather than instructions; and applies the selected style. No external model endpoint or key will be used.
4. Validate the sampled response as non-empty bounded text, handle sampling/protocol/timeouts with user-readable errors, and keep one UI request in flight at a time.
5. Declare the bundled Executa and `llm.sample` capability only with field names, handle syntax, and ACL layout verified against the current CLI schema/docs. Build and package a Linux x86_64 Executa artifact from a Linux-compatible build environment; test the extracted artifact itself.
6. Keep Render URLs and deployment assets out of the Anna runtime path. The original Render application remains independently deployed and untouched.

## Planned validations

- Install frontend dependencies from the copied lockfile and run the production TypeScript/Vite build.
- Install Python Executa dependencies in a destination-local environment; add tests for protocol handshakes, invalid input, all six styles, invalid/empty sampling responses, timeouts, and error recovery.
- Exercise `anna-app executa dev` with the mock-sampling fixture for protocol and UI harness checks, and use a logged-in real sampling bridge for model invocation if credentials/account access are available.
- Run `anna-app validate` and `anna-app validate --strict` from the destination using the declared manifest and bundle.
- Build Linux x86_64 and run `describe` plus a safe invocation from the final packaged binary. This local result does not count as Cloud Agent verification.
- Run the full fresh-install flow in Anna Cloud Agent only if the account/platform is available. Otherwise report it as unverified and provide exact manual steps.
- Do not publish, submit for review, release, or overwrite a remote app version.

## Documentation cross-checks and remaining verification

- The user supplied the current Anna Developer Hub `llms.txt` index. The official sampling documentation and Python example, plus the installed CLI schema/templates, were checked against the implementation. Runtime invocation uses `AnnaAppRuntime.connect()` and `anna.tools.invoke`, with the bundled handle resolved through `window.__ANNA_TOOL_IDS__`; the Executa now negotiates protocol 2.0 and advertises `capabilities.sampling` in its initialize result.
- Anna markdown page fetches remained unavailable from this network, so the pasted index and official examples plus installed CLI/schema evidence were used for implementation. No unsupported provider or guessed CLI manifest shape was introduced; strict local validation passes.
- `anna-app dev --slug lexyra-anna` registered development app ID 844 (`lexyra-anna`) with Anna Nexus and launched the local harness. This registration was authorized by the user. No publish, release, review submission, or remote version overwrite was performed.
- WSL returned `E_ACCESSDENIED`, and Docker/Podman are unavailable. The destination includes a Linux x86_64 PyInstaller build-and-smoke-test script, but the binary could not be built or executed in this Windows environment.
- Initial real harness checks surfaced two local-runner mismatches: `This Anna host did not negotiate reverse Sampling (Executa protocol 2.0 is required).` and, after opting into a local compatibility path, `manifest does not grant 'llm.complete'`. The installed local harness invokes the bridge without Executa `initialize` and maps sampling to `llm.complete`; production keeps the v2 negotiation requirement and `llm.sample` declaration. For the local test only, `ANNA_DEV_HARNESS_UNNEGOTIATED_SAMPLING=1` enabled sampling without negotiation and a temporary, unshipped manifest granted `llm.complete`. Both temporary files were removed after testing.
- Six real model calls through the registered Anna development UI harness succeeded earlier for the same input (`i enjoy solving hard problems, and i learned a lot from the project.`). These exercised the local harness override and its `llm.complete` route; they are model results, not evidence that the production Executa 2.0 reverse-Sampling protocol works end to end. Exact returned text: Professional — `I find great satisfaction in tackling complex challenges, and I gained significant insights from my experience with this project.`; Recruiter-Friendly — `I possess a strong aptitude for tackling complex challenges and gained significant technical insights and professional growth through my contributions to this project.`; Articulate — `I find great fulfillment in tackling complex challenges, and I derived significant insights from my involvement in this project.`; Concise — `I enjoy solving complex problems and gained significant insights from this project.`; Confident — `I thrive on solving complex challenges, and this project provided me with significant insights and professional growth.`; Academic — `I derive significant satisfaction from addressing complex challenges, and the project served as a substantial learning experience.`
- Cloud Agent acceptance still requires a platform run and appropriate sampling grant. It was not run; these results establish local Anna Nexus dev harness sampling only, not Cloud Agent compatibility.

## Files migrated and created

- Copied the frontend source, UI assets, Vite/TypeScript configuration, package manifest/lockfile, app metadata/manifests, license, and README into the destination. Excluded `.git`, `.anna`, `.lexyra`, `node_modules`, old build output, and the source's actual `.env` / `.env.local` files.
- Modified `app.json`, `manifest.json`, the frontend API adapter, the Vite output path, the app metadata and instructions, and `.gitignore`.
- Created the Python Executa, its local/binary distribution metadata, tests and mock sampling fixture, development dependency manifest, Linux build script, and the generated static bundle.

## Validation completed

- Frontend dependency installation: `npm ci` passed (158 packages audited, zero vulnerabilities).
- Frontend production build: `npm run build` passed; Vite emitted only the static tool-ID sidecar notice and a large lazy chunk advisory.
- Executa tests: eight passed in the project-local virtual environment, covering all six style instructions, input validation, malformed/empty/truncated model results, sampling negotiation and stdio protocol.
- Anna Executa runner: `describe` passed and mocked reverse Sampling returned an enhanced result for each of the six styles.
- Anna CLI strict validation: `anna-app validate --manifest manifest.json --bundle bundle --strict` passed against local app schema dispatcher 0.30.0.
- Anna dev registration: app ID `844`, slug `lexyra-anna`; harness registration and local UI connection succeeded. Six real Anna model sampling invocations succeeded as documented above.
- Protocol audit (2026-11-08): updated the v2 initialize response to advertise `capabilities.sampling`, declared `host_capabilities: ["llm.sample"]` in both App and Executa manifests, and added the documented `metadata.executa_invoke_id` to `sampling/createMessage`. Removed the development-only negotiation bypass and the undocumented `_clientTimeoutS` field.
- Post-audit protocol validation: 10 Executa pytest cases passed; `anna-app validate --manifest manifest.json --bundle bundle --strict` passed with CLI 0.1.61 / schema dispatcher 0.30.0; `anna-app executa dev --describe --json` returned the expected Executa manifest and `llm.sample` declaration.
- The isolated CLI Executa runner negotiated protocol 2.0, but its one-shot invoke omitted `params.context.invoke_id`; the correct plugin rejected Sampling with `Anna did not provide an invoke_id for Sampling attribution.` The installed runner code sends `initialize` with `protocolVersion: "2.0"`, `capabilities.sampling`, and `clientInfo`, but its `invoke()` helper sends only `tool` and `arguments`. Therefore it validates negotiation but cannot complete the current documented per-invoke attribution contract. The App UI harness has a separate limitation: it omits initialize and routes Sampling as `llm.complete`.
- Production verification still requires an Anna-installed/staged app Executa test that supplies the negotiated v2 handshake and invoke context (including `invoke_id` and the platform sampling authorization), followed by a real `sampling/createMessage` response. No version was pushed, published, released, or submitted for review during this audit.
- Source Git status remained clean (`main...origin/main`); no source files were changed. Destination contains no copied `.env` files.

## Tool/schema inspection commands observed

- `anna-app --version` → `0.1.61`
- `anna-app validate --help` → supports `--strict`
- `anna-app executa dev --help` → supports development runner and mock/real sampling options

## Final compatibility audit and Linux packaging (2026-11-08)

- The two user-specified sources agree in the current retrieved text: sampling docs list v2 negotiation, `host_capabilities: ["llm.sample"]`, and the per-Executa sampling grant as prerequisites; the official example declares `llm.sample`, negotiates protocol 2.0 with `capabilities.sampling`, and enables the grant in its instructions. A “no declaration or user switch required” sentence was not present in either retrieved source. If that claim comes from another page or a newer platform behavior, it remains unresolved rather than assumed.
- The sampling page specifies `invoke_id` and `sampling_token` in `invoke.params.context`. The reverse request's documented `params` does not include `sampling_token`; it includes `metadata.executa_invoke_id` for attribution/caps. The official Python example reads `ctx["invoke_id"]` and passes it as sampling metadata, matching the revised plugin.
- The docs say users enable `sampling_grant.enabled` per Executa in Anna Admin and describe `maxCalls`/`maxTokensTotal`. Local CLI help distinguishes an App dev registration from `anna-app executa register`, which creates a HARNESS AnnaApp of kind `executa` so a local plugin can mint real-mode tokens. Local `.anna/dev-app.json` records App ID 844 (`lexyra-anna`); that alone does not establish the grant or identify a production Executa identity. Read-only `anna-app apps status/grants/versions lexyra-anna` calls failed with `network error contacting https://anna.partners: fetch failed`, so the account-specific grant and remote binding could not be confirmed. No registration or permission-setting action was attempted.
- The v2 response advertises `capabilities.sampling` (not `client_capabilities.sampling`; that latter spelling occurs only in a stale comment in the installed CLI scaffold template). Current CLI 0.1.61's protocol-aware runner sends `protocolVersion: "2.0"`, `capabilities.sampling`, and `clientInfo`. The project returns the same version and sampling capability.
- There is a documented identity-key spelling discrepancy: the official Sampling Python example emits `serverInfo`, while the installed CLI 0.1.61 Python template emits `server_info`; the CLI runner only reads `protocolVersion`. Anna's own pre-release inspection guide says both spellings exist and should not be enforced without a version baseline. The project currently follows its installed CLI template (`server_info`); the accepted spelling on the production Nexus host remains unverified.
- The supplied Sampling page explicitly requires the Executa `describe` manifest declaration and user grant; it does not state that those are unnecessary. It does not clearly say that the App manifest must duplicate the capability. The current installed `AppManifest` schema accepts top-level `host_capabilities`, so the existing App-level `llm.sample` declaration is schema-valid, while the Executa's own `describe` declaration satisfies the documented requirement.
- The single stdin reader dispatches frames with a `method` to host-request handling and frames without a method to the pending reverse-request table. Sampling uses unique UUID string IDs and a locked pending map. A new test overlaps two requests and returns responses in reverse order; each invocation receives its matching response.
- The project does not depend on `executa_sdk`; it implements an equivalent JSON-RPC stdio reader/writer using the official wire pattern. It keeps reading while worker threads await Sampling, routes host responses by ID, includes invoke attribution metadata, and returns invocation results without exiting early. Tests cover the protocol contract and concurrent response matching.
- Added `.github/workflows/build-linux-executa.yml` for Ubuntu 24.04. It runs protocol tests, builds a one-file PyInstaller binary, packages only `lexyra-writer`, verifies the extracted executable is ELF 64-bit x86-64, checks tar contents/hash, and runs a protocol-aware offline host smoke test covering initialize, describe, reverse Sampling correlation, invoke, health, and EOF.
- The workflow itself and packaged ELF could not be executed here: `Lexyra-Anna` has no `.git` checkout or configured GitHub Actions remote/runner, `gh` is unavailable, and prior WSL startup returned `E_ACCESSDENIED`; Docker/Podman are unavailable. The workflow is ready for CI but there is no resulting binary artifact yet. Anna Cloud Agent testing remains a separate required platform check.
