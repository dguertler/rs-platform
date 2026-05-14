"""Admin setzen. Aufruf: python set_admin.py email@example.com"""
import sys
from auth import init_db, set_admin, get_user

if len(sys.argv) != 2:
    print("Verwendung: python set_admin.py <email>")
    sys.exit(1)

email = sys.argv[1]
init_db()
if not get_user(email):
    print(f"User '{email}' nicht gefunden.")
    sys.exit(1)
set_admin(email, True)
print(f"User '{email}' ist jetzt Admin.")
