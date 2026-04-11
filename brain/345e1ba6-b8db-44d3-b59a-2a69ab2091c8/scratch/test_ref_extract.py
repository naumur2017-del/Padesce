import re
import sqlite3


def test():
    conn = sqlite3.connect("db.sqlite3")
    cursor = conn.cursor()
    cursor.execute("SELECT reference_code FROM appels_appelformateur WHERE is_active=1 LIMIT 50")
    for (ref,) in cursor.fetchall():
        # Match FORM-X-NamePart-PhonePart-Remainder
        m = re.search(r"FORM-\d+-(.*?)-(\d{9,})-", ref)
        if m:
            name_part = m.group(1).replace("-", " ").upper()
            phone = m.group(2)
            print(f"{ref} => NAME: {name_part} | PHONE: {phone}")
        else:
            print(f"{ref} => NOT FOUND")


if __name__ == "__main__":
    test()
