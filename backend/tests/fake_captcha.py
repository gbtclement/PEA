class FakeCaptcha:
    """Remplace Turnstile. Par défaut, pas de captcha (comme en local) ; `required = True` pour le tester."""

    def __init__(self) -> None:
        self.required = False
        self.calls: list[tuple[str | None, str | None]] = []

    def verify(self, token: str | None, ip: str | None) -> bool:
        self.calls.append((token, ip))
        return not self.required or token == "jeton-valide"
