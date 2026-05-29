from routes import webhook


def test_normalize_phone_strips_prefixes():
    assert webhook.normalize_phone("whatsapp:+919136275825") == "9136275825"
    assert webhook.normalize_phone("+919136275825") == "9136275825"
    assert webhook.normalize_phone("9136275825") == "9136275825"


def test_pick_validates_range():
    options = ["a", "b", "c"]
    assert webhook._pick("1", options) == 0
    assert webhook._pick("3", options) == 2
    assert webhook._pick("0", options) is None
    assert webhook._pick("4", options) is None
    assert webhook._pick("x", options) is None


def test_fmt_time():
    assert webhook._fmt_time("14:00") == "2:00 PM"
    assert webhook._fmt_time("09:30:00") == "9:30 AM"
