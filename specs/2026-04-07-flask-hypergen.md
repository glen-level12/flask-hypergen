# Spec: Flask + SQLAlchemy support for Hypergen

## Goal

Build a standalone `flask_hypergen` library in this repo, with Flask integration, packaged static assets, self-contained examples, and an implementation path that supports modern SQLAlchemy 2.0 style models in those examples.

## Decisions confirmed

- The Flask Hypergen implementation will live in `src/flask_hypergen` as its own module.
- The importable Python package path uses `_`, even if the project/distribution name uses `-`.
- Preserve Hypergen API names such as `liveview`, `action`, and `callback`.
- Example apps should be self-contained and not Boothby-specific.
- Any example models should live with the example code, and represent Hypergen + Flask + SQLAlchemy usage.
- Example apps should live at `src/flask_hypergen/examples`.
- Defer a Flask `autourls` equivalent until after explicit-route examples are working.
- Static assets should ship as library assets from `src/flask_hypergen/static`, following normal Flask library packaging practices.

## Repo-hosting constraints

- `flask_hypergen` is library code hosted inside this repo for now.
- The library dependencies will be kept in a designated group in the main project's `pyproject.toml`.
- The importable package lives at `src/flask_hypergen`.
- Self-contained example apps live at `src/flask_hypergen/examples`.
- Static assets ship from `src/flask_hypergen/static`.
- Tests for the library and examples will also live in this repo.
- The operator has explicitly authorized the agent to run required `uv add` commands during implementation/testing without pausing for approval.

## Hypergen findings from reference context

### Likely framework-agnostic core

- `hypergen.context` provides the thread-local context store.
- `hypergen.template` provides HTML generation, HTML joining, and plugin execution.
- The client command protocol and JSON serialization are reusable concepts.
- The browser runtime in `hypergen.js` is not Django-specific.

### Django-coupled pieces to replace or isolate

- `hypergen.liveview` depends on Django `HttpResponse` classes, `request.META`, URL resolving, static URL helpers, and Django permission helpers.
- `hypergen.hypergen` depends on Django URL reversing/path registration and Django permission exceptions/decorators.
- `hypergen.templatetags` and `hypergen.apps` are Django-only.
- Example apps assume Django URL modules and Django request/response objects.

## Proposed direction

Treat this as an adapter project, not a Flask rewrite of all Hypergen internals.

### Adapter boundary

Keep or extract a framework-neutral Hypergen core for:

- context handling
- template rendering
- callback command serialization
- command response payload generation
- client JS runtime

Add a Flask integration layer for:

- request/context initialization
- full-page liveview responses
- action POST endpoints returning JSON command lists
- URL registration + reverse lookup
- static asset delivery
- optional auth/permission hooks

## Library package target

The library should provide:

- Flask integration for Hypergen-powered views and actions
- packaged static asset serving from the library static path
- request/context initialization during Flask request handling
- example apps that demonstrate the supported integration patterns

## SQLAlchemy direction

For this project, prefer modern typed SQLAlchemy mappings:

- `Mapped[...]`
- `mapped_column(...)`
- declarative models in SQLAlchemy 2.0 style

Do not model new examples after older untyped `db.Model` patterns from legacy reference apps.

### Initial implication

Because the library examples should be self-contained, SQLAlchemy support should be treated as:

1. framework compatibility with Flask request/app/session lifecycle
2. a small typed example model inside a self-contained example package once a DB-backed example is selected

## Phased implementation plan

### Phase 1: establish the Flask adapter

- define a Flask response contract for liveviews and actions
- provide request context initialization compatible with Hypergen core expectations
- provide a Flask-friendly `liveview` decorator
- provide a Flask-friendly `action` decorator
- support `callback(...)` posting JSON payloads to Flask endpoints
- serve/load the Hypergen JS bundle in Flask

### Phase 2: get one no-DB example working

Port the simplest examples first:

1. `hellocoreonly`
2. `hellohypergen`

Rationale:

- they validate the render pipeline and callback loop
- they keep scope small
- they separate “manual endpoint wiring” from “decorator ergonomics”

### Phase 3: add Flask ergonomics

- add URL reversing for Hypergen callbacks and links
- decide whether to support an `autourls` equivalent in Flask
- support base templates / target IDs / partial updates cleanly

### Phase 4: add one SQLAlchemy-backed example

After non-DB examples work, port one small example that proves DB mutation + re-rendering under Flask.

Preferred shape:

- a deliberately small self-contained example package
- example-local typed SQLAlchemy models
- typed SQLAlchemy mappings
- simple create/update interaction from a Hypergen action

This is a better first SQLAlchemy target than porting a large Django example like `booking` immediately.

## Example priorities

### First examples to port

- `hellocoreonly`: best first target because it avoids decorator magic and proves the minimal contract.
- `hellohypergen`: next target because it exercises `@liveview`, `@action`, and callback wiring.

### Smoke-test example suite

Use these five examples as the primary implementation smoke-test set, in roughly this order:

1. `hellocoreonly`
   - proves the lowest-level Flask contract for `hypergen(...)`, manual action endpoints, JSON command responses, and DOM target updates
2. `hellohypergen`
   - proves preserved Hypergen API names and the basic Flask `liveview` + `action` decorator flow
3. `inputs`
   - proves client-to-server argument extraction, coercion, nested payload serialization, and input element coverage
4. `apptemplate`
   - proves base-template support, `target_id` conventions, `THIS` element value capture, and a realistic small app structure
   - **Goal:** The Flask port of this example should demonstrate the recommended Flask Blueprint structure for a `flask_hypergen` app, showing users the "right way" to organize their code.
5. `commands`
   - proves server-to-client command generation, command ordering, and the Flask adapter's JSON command response behavior

These five give broad coverage without pulling in Django-template integration, websockets, or a large persistence-heavy app too early.

### Next wave after the smoke-test suite

- `partialload`
  - good follow-up once the explicit-route examples are stable, because it exercises partial navigation, history integration, and the `X-Hypergen-Partial` request flow

### Examples to defer

- `booking`
- websocket examples
- Django template integration examples

These should wait until the Flask adapter contract is stable.

## Architectural decisions to make during implementation

### 1. URL registration strategy

Start with explicit Flask routes if that reduces risk. The recommended API is to pass a `Blueprint` or `Flask` app object to the decorators to preserve Hypergen API names (e.g., `@liveview(bp, perm=...)` or `@action(bp, ...)`).

Only add a Flask `autourls` equivalent after basic liveview/action behavior works.

### 2. Request context strategy

Hypergen currently expects `request` in its context store. For Flask, we likely need one of:

- a blueprint/app `before_request` hook
- a small wrapper around the liveview/action decorators

### 3. Response types

Define Flask-native equivalents for:

- full HTML page response
- JSON command response
- redirect encoded as a Hypergen command response when needed

### 4. Static assets

Need a stable way to serve the Hypergen JS asset path expected by rendered pages. For Phase 1, simply copying the existing built `hypergen.js` bundle from the reference context (`src/hypergen/static/hypergen/hypergen.js`) into `src/flask_hypergen/static` is sufficient.

Current direction:

- copy pre-built `hypergen.js` from `src/hypergen/static/hypergen/hypergen.js` to `src/flask_hypergen/static/hypergen.js`
- expose them using Flask library/static best practices
- avoid making assets Boothby-specific

## Testing plan

- unit tests for Flask liveview/action wrappers
    - Ensure you cover every test from hypergen/test_all.py
    - If a hypergen test doesn't apply b/c of flask/django differences, create the body anyway with an assert False and xfail it.
- request tests for the example routes using a library-owned Flask test app/client pattern
- callback/action tests that assert JSON command payloads
- one end-to-end-ish request cycle for the counter example
- playwright for end-to-end testing

## Risks / unknowns

- Existing Hypergen examples rely heavily on Django URL and response conventions.
- Partial loading/history support may require extra Flask-specific adaptation beyond the first example ports.

## Questions for follow-up

1. Should the example apps be written against plain Flask only, or is using `flask-flac` acceptable in examples if it keeps the implementation cleaner?
    - Examples should be flask only.
2. For the initial `perm` story on `liveview` / `action`, do you want unsupported Django-style permission behavior to be a hard error, or should Phase 1 treat permissions as an optional no-op hook?
    - You have SetHub in your context.  It has flask authentication.  See what libraries it uses
      for auth, I think it's flask-login, and build an authentication flow around that.
    - Ignore authorization/permissions for now.  Provide a NO_PERM_REQUIRED constant and error
      out if anything else is given.  Keep a task open for doing permissions.
3. For callback routing in the first working version, is endpoint-name-based reverse lookup via Flask `url_for(...)` sufficient, or do you want function-based `callback(my_action, ...)` ergonomics working in the first decorator milestone?
    - url_for() is sufficient but keep a task/todo open for improving the DevX
4. Should the first public Flask adapter expose only the preserved Hypergen decorators (`liveview`, `action`, `callback`), or do you also want lower-level helpers surfaced for explicit-route/manual wiring use cases?
    - If lower-level helpers seem like they would be useful, surface them.
    - But, for clarity, nothing should be "buried" either.  I'm not a big fan of lots of private
      stuff in a library.
5. Is copying the current built `hypergen.js` file into `src/flask_hypergen/static/hypergen.js` manually acceptable for Phase 1, or do you want a repo task/script to keep that asset synced from the reference source?
    - Just copy for now.  No sync/copy script needed.
6. Do you want the first example/test app fixtures to live under `tests/flask_hypergen_tests/` with Flask's built-in test client...
    - yes

## Initial recommended execution order

1. build `src/flask_hypergen` Flask integration scaffold
2. port `hellocoreonly` to Flask with explicit routes
3. add Flask `liveview` / `action` wrappers with preserved API names
4. port `hellohypergen`
5. add one small self-contained SQLAlchemy-backed example
