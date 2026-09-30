class FakeBreach:
    """Remplace Have I Been Pwned : seuls les mots de passe de `pwned` sont « connus des fuites »."""

    def __init__(self) -> None:
        self.pwned: set[str] = set()

    def is_pwned(self, password: str) -> bool:
        return password in self.pwned
