from app.security import hash_password, session_token, verify_password, verify_session_token


def test_password_hash_and_verify():
    stored = hash_password("secret")
    assert stored.startswith("pbkdf2_sha256$")
    assert verify_password("secret", stored)
    assert not verify_password("wrong", stored)


def test_session_token_depends_on_hash():
    stored = hash_password("secret")
    token = session_token(stored)
    assert verify_session_token(token, stored)
    assert not verify_session_token("bad", stored)
