class Error(Exception):
    """Base class for exceptions used in the AddBiomechanics engine."""
    def __init__(self, previous_message):
        self.previous_message = previous_message
        self.message = f"{self.get_message()} {self.previous_message}"

        super().__init__(self.message)

    def get_message(self):
        raise NotImplementedError("Subclasses must implement the 'get_message' method.")


class PathError(Error):
    """Raised when a path is invalid."""
    def get_message(self):
        return "DerivedException: This is a custom message."

