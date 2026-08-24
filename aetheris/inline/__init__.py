"""
Aetheris inline package — provides compatibility stubs for Hikka/Heroku inline modules.
"""
# Stub for modules that do: from ..inline import GeekInlineQuery, rand
class GeekInlineQuery:
    """Compatibility stub — not a real inline query handler."""
    pass


def rand(lst):
    """Compatibility stub — use random.choice instead."""
    import random
    return random.choice(lst)


# Add other commonly imported names as needed
__all__ = ["GeekInlineQuery", "rand"]
