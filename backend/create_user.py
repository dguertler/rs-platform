"""User anlegen. Aufruf: python create_user.py email@example.com passwort"""
import sys
from auth import init_db, create_user, get_user

if len(sys.argv) != 3:
    print("Verwendung: python create_user.py <email> <passwort>")
    sys.exit(1)

email, password = sys.argv[1], sys.argv[2]
init_db()
if get_user(email):
    print(f"User '{email}' existiert bereits.")
    sys.exit(1)
create_user(email, password)
print(f"User '{email}' angelegt.")
