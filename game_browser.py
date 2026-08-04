import random

SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["7", "8", "9", "10", "J", "Q", "K", "A"]


def build_intro():
    return {
        "title": "Twenty-Nine",
        "subtitle": "Python running in the browser via PyScript"
    }


def shuffle_cards(count=4):
    deck = [f"{rank}{suit}" for suit in SUITS for rank in RANKS]
    random.shuffle(deck)
    return deck[:count]
