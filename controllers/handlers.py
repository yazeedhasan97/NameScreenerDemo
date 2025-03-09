import hashlib

from controllers.consts import SupportedLanguage, RecoType


class NameHandler:
    def __init__(self, sep: str = ' '):
        self._sep = sep

    def hash(self, name: str, type: int = None, ) -> int:
        # language = language if language else SupportedLanguage.ENGLISH.value
        type = type if type else RecoType.ENTITY.value

        names = self.clean(name).split()
        length = len(names)

        # if not (2 <= length <= 30):
        #     raise ValueError("Full name must have between 2 and 30 names.")

        # Concatenate the first letter of each name in order.
        letters = ''.join(name[0] for name in names)

        # Create a composite string with language, number of names, and ordered first letters.
        composite = f"{type}{length}{letters}"

        # Generate the SHA-256 hash and convert it to an integer.
        return int(hashlib.sha256(composite.encode('utf-8')).hexdigest(), 16)

    def detect_language(self, name: str) -> str:
        """Detects whether the name is in Arabic or English."""
        from langdetect import detect

        try:
            return detect(name)
        except Exception:
            return "unknown"

    def clean(self, name: str):
        # name =
        return name.strip(' ",|-=#$%&*').upper()
