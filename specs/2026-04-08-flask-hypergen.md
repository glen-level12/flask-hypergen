# Spec: Flask-Hypergen Day 2

## Background

See ./2026-04-07-flask-hypergen.md for the original spec and progress we've made.

## Task: Improve reviewing the examples

- [x] Add a readme to src/flask_hypergen with instructions on how to run the examples
- [x] Add an index view which lists all the examples with links to them.  Add a CDN css framework
  and do some basic styling to make it look nice.  Should work for light and dark modes, pick a
  color theme, maybe an electric blue or burnt orange.

## Task: Refine flask-hypergen's usability and dev experience

- [ ] Don't import EVERYTHING into flask_hypergen/__init__.py.  Evaluate the example usage patterns
  and let's figure out a sane import strategy for what's available at the top level.
- [ ] Don't import tags at the top level.  Instead, require the dev to do an explicit import from
    of or from the tags module so the idiom can be `from flask_hypergen impor tags as t` or
    `from flask_hypergen.tags import p, div` depending on what the dev wants.

## Implementation notes (2026-04-07)

- Expanded `src/flask_hypergen/README.md` with direct example-run instructions for both `mise exec`
  and an already-activated `mise` shell.
- Reworked `src/flask_hypergen/examples/index.py` into a styled example index with generated links,
  Pico CSS via CDN, and light/dark-friendly azure theming.
- Simplified the examples index further into a plain table and made the view name itself the link.
- Added request-test coverage for the example index in `tests/flask_hypergen_tests/test_examples.py`.
