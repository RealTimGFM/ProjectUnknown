from ats_parser.rules import extract_contacts


def test_extract_contacts_happy_path():
    text = """
Tim Nguyen
Montreal, QC
tim@example.com
(514) 555-1234
https://github.com/RealTimGFM
https://www.linkedin.com/in/timnguyen
"""
    c = extract_contacts(text)
    assert c["email"] == "tim@example.com"
    assert c["phone"] and "+1" in c["phone"]
    assert "github.com" in " ".join(c["links"]).lower()
    assert c["name"] == "Tim Nguyen"


def test_extract_contacts_no_contacts_is_safe():
    text = "Just some text with no email and no phone."
    c = extract_contacts(text)
    assert c["email"] == ""
    assert c["phone"] == ""
    assert c["links"] == []
    assert c["name"] in ("",)
