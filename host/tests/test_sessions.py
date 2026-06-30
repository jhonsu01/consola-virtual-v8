"""Pruebas del gestor de sesiones y PINs (sin red ni audio)."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from consola_v8.sessions import SessionManager  # noqa: E402


def test_starts_with_one_pin():
    sm = SessionManager()
    assert len(sm.pins()) == 1
    assert sm.primary_pin() == sm.pins()[0]


def test_add_unique_pins():
    sm = SessionManager()
    p2 = sm.add_pin()
    assert p2 in sm.pins()
    assert len(set(sm.pins())) == len(sm.pins())  # todos unicos


def test_validate():
    sm = SessionManager()
    good = sm.pins()[0]
    assert sm.validate(good) is True
    assert sm.validate("0000" if good != "0000" else "1111") is False


def test_cannot_remove_last_pin():
    sm = SessionManager()
    only = sm.pins()[0]
    sm.remove_pin(only)
    assert len(sm.pins()) == 1  # no se quedo sin ninguno


def test_open_and_close_sessions():
    sm = SessionManager()
    sid = sm.open("Tel-A", "192.168.1.10", sm.primary_pin())
    assert sm.count() == 1
    assert sm.sessions()[sid]["device"] == "Tel-A"
    sm.close(sid)
    assert sm.count() == 0


def test_multiple_concurrent_sessions():
    sm = SessionManager()
    p2 = sm.add_pin()
    s1 = sm.open("A", "ip1", sm.primary_pin())
    s2 = sm.open("B", "ip2", sm.primary_pin())
    s3 = sm.open("C", "ip3", p2)
    assert sm.count() == 3
    assert len({s1, s2, s3}) == 3
