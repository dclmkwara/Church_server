from app.db.session import engine


def test_sqlalchemy_echo_is_disabled_to_prevent_bound_values_in_logs():
    assert engine.echo is False
