class FakeMailer:
    """Remplace le serveur SMTP : garde les mails envoyés, peut simuler des pannes."""

    def __init__(self) -> None:
        self.sent: list[dict] = []
        self.fail_next = 0

    def send(self, **mail) -> None:
        if self.fail_next:
            self.fail_next -= 1
            raise OSError("SMTP indisponible")
        self.sent.append(mail)
