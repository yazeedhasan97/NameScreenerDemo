import hashlib

from controllers.consts import Language


class NameHashHandler:
    def __init__(self, sep: str = ' ', language: Language = None):
        self._language = language if language else Language.ARABIC
        self._sep = sep

    def hash(self, name: str) -> int:
        names = name.strip().split()
        length = len(names)

        if not (2 <= length <= 30):
            raise ValueError("Full name must have between 2 and 30 names.")

        # Concatenate the first letter of each name in order.
        letters = ''.join(name[0] for name in names)

        # Create a composite string with language, number of names, and ordered first letters.
        composite = f"{self._language}{self._sep}{length}{self._sep}{letters}"

        # Generate the SHA-256 hash and convert it to an integer.
        return int(hashlib.sha256(composite.encode('utf-8')).hexdigest(), 16)


# Demo usage
if __name__ == "__main__":
    demo_examples = [
        ("John Doe", "English"),
        ("Jane Danald", "English"),
        ("Jane Janald", "English"),
        ("Jane Danald Serio", "English"),
        ("أحمد علي", "Arabic"),
        ("أحسن عمرو", "Arabic"),
        ("Marie Curie", "French")
    ]

    for full_name, language in demo_examples:
        hash_value = NameHashHandler().hash(full_name)
        print(f"Full Name: {full_name} | Language: {language} => Hash: {hash_value}")
