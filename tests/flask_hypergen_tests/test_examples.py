from flask_hypergen.liveview import dumps


def test_example_routes_render(client):
    checks = {
        '/hellocoreonly/counter': 'Core-only wiring',
        '/hellohypergen/counter': 'Decorator wiring',
        '/inputs/demo': 'Read values from the browser',
        '/commands/demo': 'Explicit command responses',
        '/apptemplate/counter': 'Context-manager base template',
        '/sqlalchemy-counter/counter': 'SQLAlchemy-backed state',
    }
    for path, marker in checks.items():
        response = client.get(path)
        body = response.get_data(as_text=True)
        assert response.status_code == 200
        assert marker in body
        assert '/flask_hypergen/static/hypergen.js' in body


def test_coreonly_increment_returns_commands(client):
    response = client.post('/hellocoreonly/increment', data={'hypergen_data': dumps({'args': [1]})})
    payload = response.get_data(as_text=True)
    assert response.status_code == 200
    assert response.mimetype == 'application/json'
    assert 'hypergen.morph' in payload
    assert 'Counter value' in payload


def test_hypergen_increment_returns_commands(client):
    response = client.post(
        '/hellohypergen/increment',
        data={'hypergen_data': dumps({'args': [1]})},
        headers={'Referer': 'http://localhost/hellohypergen/counter'},
    )
    payload = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'hypergen.morph' in payload
    assert 'Decorator wiring' in payload


def test_inputs_submit_returns_summary(client):
    response = client.post(
        '/inputs/submit',
        data={'hypergen_data': dumps({'args': ['Ada', 37, True]})},
        headers={'Referer': 'http://localhost/inputs/demo'},
    )
    payload = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'Ada is 37 years old and subscribed=True' in payload


def test_commands_demo_returns_explicit_commands(client):
    response = client.post(
        '/commands/send-command',
        data={'hypergen_data': dumps({'args': []})},
        headers={'Referer': 'http://localhost/commands/demo'},
    )
    payload = response.get_data(as_text=True)
    assert response.status_code == 200
    assert payload.startswith('[[')
    assert 'Updated from an explicit command.' in payload


def test_apptemplate_increment_returns_commands(client):
    response = client.post(
        '/apptemplate/increment',
        data={'hypergen_data': dumps({'args': [1]})},
        headers={'Referer': 'http://localhost/apptemplate/counter'},
    )
    payload = response.get_data(as_text=True)
    assert response.status_code == 200
    assert 'Current value: 2' in payload


def test_sqlalchemy_counter_persists(client):
    first = client.get('/sqlalchemy-counter/counter').get_data(as_text=True)
    client.post(
        '/sqlalchemy-counter/increment',
        data={'hypergen_data': dumps({'args': [1]})},
        headers={'Referer': 'http://localhost/sqlalchemy-counter/counter'},
    )
    second = client.get('/sqlalchemy-counter/counter').get_data(as_text=True)
    assert 'Persisted value: 0' in first
    assert 'Persisted value: 1' in second


def test_liveview_partial_get_returns_json_commands(client):
    response = client.get('/hellohypergen/counter', headers={'X-Hypergen-Partial': '1'})
    assert response.status_code == 200
    assert response.mimetype == 'application/json'
    assert 'hypergen.morph' in response.get_data(as_text=True)
