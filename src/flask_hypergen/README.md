# Flask-Hypergen

Flask integration for Hypergen, including a small example suite under `src/flask_hypergen/examples`.

## Run the examples

If `mise` is not already active in your shell:

```bash
mise exec -- flask --app src/flask_hypergen/examples/app.py run --debug
```

If you already have `mise` active:

```bash
flask --app src/flask_hypergen/examples/app.py run --debug
```

Then open `http://127.0.0.1:5000/` to use the example index.

## Included examples

- Hello Core Only
- Hello Hypergen
- Inputs
- Commands
- App Template
- Partial Load
- Auth
- SQLAlchemy Counter
