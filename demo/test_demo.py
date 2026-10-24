import yaml  # missing dependency – will cause ImportError

def test_add():
    from demo.calc import add
    assert add(2, 2) == 5  # wrong expectation
