import random
try:
    from game29 import Game29
except Exception:
    Game29 = None


SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["7", "8", "9", "10", "J", "Q", "K", "A"]


def build_intro():
    return {
        "title": "Twenty-Nine",
        "subtitle": "PyScript demo — initializing game engine"
    }


# Expose a simple API for the browser to get the human player's hand.
_game = None


def _ensure_game():
    global _game
    if _game is None:
        if Game29 is None:
            return None
        _game = Game29()
        # start_round is already called in Game29.__init__, but ensure a fresh round
        try:
            _game.start_round()
        except Exception:
            pass
    return _game


def shuffle_cards(count=4):
    """Return `count` cards from the human player's (South) hand as strings.

    This uses the real `Game29` engine when available in the environment.
    """
    g = _ensure_game()
    if g is None:
        # fallback to a simple random deck if the full engine isn't importable
        deck = [f"{rank}{suit}" for suit in SUITS for rank in RANKS]
        random.shuffle(deck)
        return deck[:count]
    human = g.players[0]
    # Ensure stable ordering for display
    try:
        hand = sorted(human.hand, key=lambda c: (c.suit, c.rank))
    except Exception:
        hand = list(human.hand)
    return [str(c) for c in hand[:count]]
