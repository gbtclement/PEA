"""Commandes d'exploitation : python -m app.cli <commande> (dans le conteneur api)."""
import argparse
from datetime import UTC, datetime

from app.core.brand import APP_NAME
from app.core.config import get_settings
from app.core.db import get_session_factory
from app.services.auth.bootstrap import bootstrap_admin, ensure_user


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("bootstrap-admin", help="Donne le rôle admin à ADMIN_EMAIL (lancé au démarrage de l'API)")
    user = commands.add_parser("ensure-user", help="Crée ou met à jour un compte validé (tests, dépannage)")
    user.add_argument("--email", required=True)
    user.add_argument("--password", required=True)
    user.add_argument("--first-name", default="Test")
    user.add_argument("--last-name", default=APP_NAME)
    user.add_argument("--admin", action="store_true")
    args = parser.parse_args(argv)

    now = datetime.now(UTC)
    with get_session_factory()() as db:
        if args.command == "bootstrap-admin":
            print(bootstrap_admin(db, get_settings().admin_email, now))
        else:
            account = ensure_user(db, email=args.email, password=args.password, first_name=args.first_name,
                                  last_name=args.last_name, admin=args.admin, now=now)
            print(f"Compte {account.email} prêt ({account.role}).")
        db.commit()


if __name__ == "__main__":
    main()
