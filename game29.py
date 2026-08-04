import random
import math
import struct
import subprocess
import tempfile
import os
import time
import wave
try:
    import tkinter as tk
    from tkinter import messagebox
    GUI_AVAILABLE = True
except Exception:
    tk = None
    messagebox = None
    GUI_AVAILABLE = False

SUITS = ['♠', '♥', '♦', '♣']
SUIT_NAMES = {'♠': 'Spades', '♥': 'Hearts', '♦': 'Diamonds', '♣': 'Clubs'}
SUIT_COLORS = {'♠': '#1a1510', '♣': '#1a1510', '♥': '#b42318', '♦': '#b42318'}
RANKS = ['7', '8', '9', '10', 'J', 'Q', 'K', 'A']
CARD_POINTS = {'J': 3, '9': 2, 'A': 1, '10': 1, 'K': 0, 'Q': 0, '8': 0, '7': 0}
RANK_ORDER = {'7': 0, '8': 1, 'Q': 2, 'K': 3, '10': 4, 'A': 5, '9': 6, 'J': 7}

# =============================================================
# 1) Game Configuration and Visual Theme
# =============================================================
# এই বিভাগে গেমের মৌলিক সেটিং রাখা হয়েছে:
# - কার্ডের স্যুট, র‍্যাঙ্ক, পয়েন্ট
# - UI-এর রং, ফন্ট, এবং থিম
# - অ্যানিমেশন-এর সময়সূচী
# এগুলো পুরো গেম জুড়ে একসাথে ব্যবহার করা হয়।

# Midnight Casino theme: premium felt-table appearance with
# deep navy background, emerald table surface, and gold accents.
COL_NAVY = "#0B1220"
COL_NAVY_DEEP = "#070A12"
COL_FELT_DEEP = "#0C3B31"
COL_FELT = "#0E4D3C"
COL_FELT_MID = "#127A56"
COL_FELT_LIT = "#145A4A"
COL_WOOD = "#1A120C"
COL_WOOD_MID = "#2E2118"
COL_WOOD_EDGE = "#4A3424"
COL_GOLD = "#F59E0B"
COL_GOLD_SOFT = "#FBBF24"
COL_GOLD_DARK = "#D97706"
COL_IVORY = "#FFFBF2"
COL_IVORY_DIM = "#D4CFC3"
COL_INK = "#0F172A"
COL_CRIMSON = "#E63946"
COL_PANEL = "#0A1628"
COL_PANEL_HI = "#132338"
COL_TEXT = "#F8FAFC"
COL_MUTED = "#94A3B8"
COL_ACCENT = "#F59E0B"
COL_GLOW = "#FBBF24"
COL_ACTIVE = "#FCD34D"
COL_WIN = "#1ED760"
BACK_BG = "#162840"
BACK_INNER = "#1E3A5F"
BACK_PATTERN = "#2A4A73"

FONT_DISPLAY = "Georgia"
FONT_UI = "Cambria"
FONT_SUIT = "Georgia"

PLAYER_INITIALS = {0: "YO", 1: "WE", 2: "NO", 3: "EA"}
PLAYER_LABELS = {0: "You", 1: "West", 2: "North", 3: "East"}

# Animation timing (ms) — tuned for ~60fps feel
ANIM_FRAME = 12
ANIM_CARD_MS = 560
ANIM_COLLECT_MS = 520
ANIM_DEAL_MS = 480
ANIM_SHUFFLE_MS = 800
ANIM_DEAL_STAGGER = 95
ANIM_REVEAL_MS = 420


def ease_out_cubic(t):
    return 1 - (1 - t) ** 3


def ease_in_out_cubic(t):
    return 4 * t * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_out_back(t):
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def ease_out_quart(t):
    return 1 - (1 - t) ** 4


def lerp(a, b, t):
    return a + (b - a) * t


# =============================================================
# 2) Audio Support
# =============================================================
# এই ক্লাসটি গেমের বিভিন্ন ইভেন্টে অডিও ইফেক্ট দেয়:
# - button click
# - card action
# - bid / double / redouble
#
# এটি Tkinter/pygame/OS audio backend-এ কাজ করতে পারে।
class SoundPlayer:
    """Premium-feeling procedural audio for UI and card-table interactions."""

    def __init__(self):
        self.enabled = True
        self._backend = None
        self._tmp = os.path.join(tempfile.gettempdir(), "29sound.wav")
        self._last_play = {}

    def play(self, kind):
        if not self.enabled:
            return
        try:
            if kind == "button":
                self._play_sfx([760], 0.055, 0.025, waveform="square", attack=0.003, release=0.018)
            elif kind == "hover":
                self._play_sfx([1250, 1520], 0.042, 0.018, waveform="triangle", attack=0.002, release=0.018)
            elif kind == "card":
                self._play_sfx([690, 1120], 0.058, 0.032, waveform="sine", attack=0.004, release=0.012)
            elif kind == "drop":
                self._play_sfx([420, 680], 0.085, 0.045, waveform="triangle", attack=0.004, release=0.045)
            elif kind == "shuffle":
                self._play_sweep(720, 420, 0.13, 0.03, waveform="triangle")
            elif kind == "bid":
                self._play_sfx([520, 780, 940], 0.085, 0.038, waveform="sine", attack=0.007, release=0.04)
            elif kind == "double":
                self._play_sfx([780, 960, 1240], 0.11, 0.046, waveform="triangle", attack=0.008, release=0.05)
            else:
                self._play_sfx([700], 0.05, 0.03, waveform="sine", attack=0.003, release=0.02)
        except Exception:
            pass

    def _play_sfx(self, freqs, duration, volume, waveform="sine", attack=0.004, release=0.02):
        if self._backend is None:
            self._backend = self._detect_backend()
        if self._backend is None:
            return
        sample_rate = 22050
        frames = int(sample_rate * duration)
        if frames <= 0:
            return

        wave_bytes = bytearray()
        for i in range(frames):
            t = i / sample_rate
            env = self._adsr(i, frames, attack, release)
            total = 0.0
            for idx, freq in enumerate(freqs):
                f = freq * (1.0 + 0.008 * idx)
                value = self._waveform_value(waveform, f, t, bias=0.0)
                total += value * (0.8 / max(1, len(freqs)))
            if len(freqs) > 1:
                total += 0.18 * self._waveform_value(waveform, freqs[0] * 2.0, t, bias=0.0)
            sample = int(32767 * volume * env * max(-1.0, min(1.0, total)))
            wave_bytes.extend(struct.pack("<h", sample))

        self._build_wav(sample_rate, wave_bytes)
        if self._backend == "pygame":
            try:
                import pygame
                with open(self._tmp, "rb") as fh:
                    sound = pygame.mixer.Sound(buffer=fh.read())
                sound.play()
            except Exception:
                pass
            return

        if isinstance(self._backend, (list, tuple)):
            cmd = list(self._backend)
        else:
            cmd = [self._backend]

        try:
            if cmd and cmd[0] == "afplay":
                subprocess.Popen(["afplay", self._tmp], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elif cmd and cmd[0] in {"aplay", "paplay"}:
                with open(self._tmp, "rb") as fh:
                    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    proc.communicate(input=fh.read())
            else:
                with open(self._tmp, "rb") as fh:
                    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    proc.communicate(input=fh.read())
        except Exception:
            pass

    def _play_sweep(self, start_freq, end_freq, duration, volume, waveform="sine"):
        if self._backend is None:
            self._backend = self._detect_backend()
        if self._backend is None:
            return
        sample_rate = 22050
        frames = int(sample_rate * duration)
        wave_bytes = bytearray()
        for i in range(frames):
            t = i / sample_rate
            progress = i / max(1, frames - 1)
            freq = start_freq + (end_freq - start_freq) * progress
            env = self._adsr(i, frames, 0.008, 0.03)
            value = self._waveform_value(waveform, freq, t, bias=0.0)
            sample = int(32767 * volume * env * value)
            wave_bytes.extend(struct.pack("<h", sample))
        self._build_wav(sample_rate, wave_bytes)
        if self._backend == "pygame":
            try:
                import pygame
                with open(self._tmp, "rb") as fh:
                    sound = pygame.mixer.Sound(buffer=fh.read())
                sound.play()
            except Exception:
                pass
            return
        if isinstance(self._backend, (list, tuple)):
            cmd = list(self._backend)
        else:
            cmd = [self._backend]
        try:
            if cmd and cmd[0] == "afplay":
                subprocess.Popen(["afplay", self._tmp], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                with open(self._tmp, "rb") as fh:
                    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    proc.communicate(input=fh.read())
        except Exception:
            pass

    def _adsr(self, index, frames, attack, release):
        if frames <= 1:
            return 1.0
        attack_frames = max(1, int(frames * attack))
        release_frames = max(1, int(frames * release))
        if index < attack_frames:
            return index / attack_frames
        if index > frames - release_frames:
            return (frames - index) / release_frames
        return 1.0

    def _waveform_value(self, waveform, freq, t, bias=0.0):
        phase = 2 * math.pi * freq * t + bias
        if waveform == "square":
            return 1.0 if math.sin(phase) >= 0 else -1.0
        if waveform == "triangle":
            return 2.0 * abs(2.0 * (phase / (2.0 * math.pi) - math.floor(phase / (2.0 * math.pi) + 0.5))) - 1.0
        if waveform == "saw":
            return 2.0 * (phase / (2.0 * math.pi) - math.floor(phase / (2.0 * math.pi) + 0.5))
        return math.sin(phase)

    def _build_wav(self, sample_rate, pcm):
        with wave.open(self._tmp, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm)

    def _detect_backend(self):
        try:
            import pygame
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=256)
            return "pygame"
        except Exception:
            pass
        for cmd in (["afplay"], ["aplay", "-q", "-"], ["paplay", "-q", "-"], ["ffplay", "-nodisp", "-autoexit", "-f", "wav", "-i", "-"]):
            try:
                subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                continue
            return cmd
        return None


# =============================================================
# 3) Core Game Objects
# =============================================================
# এই বিভাগে গেমের মৌলিক অবজেক্টগুলো সংজ্ঞায়িত করা হয়েছে:
# - Card: একটি কার্ড
# - Player: একটি প্লেয়ার
# - Game29: গেমের লজিক
class Card:
    """Represents a single playing card with suit, rank, and point value."""

    def __init__(self, suit, rank):
        self.suit = suit
        self.rank = rank
        self.points = CARD_POINTS[rank]

    def __repr__(self):
        return f"{self.rank}{self.suit}"

    def __eq__(self, other):
        return isinstance(other, Card) and self.suit == other.suit and self.rank == other.rank

    def __hash__(self):
        return hash((self.suit, self.rank))


class Player:
    """Represents a player with name, seat, team, hand, and human/AI status."""

    def __init__(self, name, index, is_human=False):
        self.name = name
        self.index = index
        self.is_human = is_human
        self.hand = []
        self.team = index % 2

    def has_suit(self, suit):
        return any(c.suit == suit for c in self.hand)


class Game29:
    """Core game engine handling bidding, trump selection, play, tricks, and scoring."""

    def __init__(self):
        self.reset_game()

    def reset_game(self):
        self.game_scores = [0, 0]
        self.dealer = random.randint(0, 3)
        self.start_round()

    def start_round(self):
        self.deck = [Card(s, r) for s in SUITS for r in RANKS]
        random.shuffle(self.deck)
        for p in self.players:
            p.hand = []
        self.dealer = (self.dealer + 1) % 4
        self.bidder_start = (self.dealer + 1) % 4
        for _ in range(4):
            for i in range(4):
                self.players[(self.bidder_start + i) % 4].hand.append(self.deck.pop())
        self.bid_value = 15
        self.highest_bidder = None
        self.bid_winner = None
        self.bid_amount = 0
        self.trump_suit = None
        self.trump_revealed = False
        self.trump_card = None
        self.multiplier = 1
        self.doubled_by = None
        self.redoubled = False
        self.current_trick = []
        self.trick_leader = None
        self.tricks_won_points = [0, 0]
        self.tricks_count = 0
        self.last_trick_winner = None
        self.pair_claimed = [False, False]
        self.phase = "BIDDING"
        self.current_player = self.bidder_start
        self.passes = 0
        self.bid_history = []
        self.last_bid_label = {0: "", 1: "", 2: "", 3: ""}

    players = [
        Player("You (South)", 0, is_human=True),
        Player("West", 1),
        Player("North (Partner)", 2),
        Player("East", 3),
    ]

    def deal_remaining(self):
        for _ in range(4):
            for i in range(4):
                p = self.players[(self.bidder_start + i) % 4]
                if self.deck:
                    p.hand.append(self.deck.pop())

    def can_bid(self, amount):
        return 16 <= amount <= 28 and amount > self.bid_value

    def place_bid(self, player_index, amount):
        if amount == 0:
            self.bid_history.append((player_index, "Pass"))
            self.passes += 1
            self.last_bid_label[player_index] = "PASS"
        else:
            self.bid_value = amount
            self.highest_bidder = player_index
            self.bid_amount = amount
            self.bid_history.append((player_index, str(amount)))
            self.passes = 0
            self.last_bid_label[player_index] = str(amount)

    def bidding_complete(self):
        if self.highest_bidder is not None and self.passes >= 3:
            return True
        if self.highest_bidder is None and self.passes >= 4:
            return True
        return False

    def ai_bid_decision(self, player):
        hp = sum(c.points for c in player.hand)
        jacks = sum(1 for c in player.hand if c.rank == 'J')
        nines = sum(1 for c in player.hand if c.rank == '9')
        sc = {}
        for c in player.hand:
            sc[c.suit] = sc.get(c.suit, 0) + 1
        best_len = max(sc.values()) if sc else 0
        strength = hp + jacks * 2 + nines + best_len
        target = self.bid_value + 1
        if strength >= 9 and target <= 20:
            return target
        if strength >= 7 and target <= 18:
            return target
        if strength >= 5 and target <= 17 and self.highest_bidder is None:
            return 16
        return 0

    def ai_select_trump(self, player):
        sc, sp = {}, {}
        for c in player.hand:
            sc[c.suit] = sc.get(c.suit, 0) + 1
            sp[c.suit] = sp.get(c.suit, 0) + c.points
        return max(SUITS, key=lambda s: sc.get(s, 0) * 2 + sp.get(s, 0))

    def valid_moves(self, player):
        if not self.current_trick:
            return player.hand[:]
        lead = self.current_trick[0][1].suit
        same = [c for c in player.hand if c.suit == lead]
        return same if same else player.hand[:]

    def can_reveal_trump(self, player):
        if self.trump_revealed or not self.trump_suit:
            return False
        if not self.current_trick:
            return False
        lead = self.current_trick[0][1].suit
        return not player.has_suit(lead)

    def play_card(self, player_index, card):
        self.players[player_index].hand.remove(card)
        self.current_trick.append((player_index, card))

    def resolve_trick(self):
        lead = self.current_trick[0][1].suit
        trump = self.trump_suit if self.trump_revealed else None
        bi = self.current_trick[0][0]
        bc = self.current_trick[0][1]
        for (pidx, card) in self.current_trick[1:]:
            bc, bi = self._compare_cards(bc, bi, card, pidx, lead, trump)
        tp = sum(c.points for (_, c) in self.current_trick)
        wt = self.players[bi].team
        self.tricks_won_points[wt] += tp
        self.tricks_count += 1
        self.last_trick_winner = bi
        if self.tricks_count == 8:
            self.tricks_won_points[wt] += 1
        self.current_trick = []
        self.trick_leader = bi
        self.current_player = bi
        return bi

    def _compare_cards(self, c1, i1, c2, i2, lead, trump):
        t1 = (trump and c1.suit == trump)
        t2 = (trump and c2.suit == trump)
        if t1 and not t2:
            return c1, i1
        if t2 and not t1:
            return c2, i2
        if t1 and t2:
            return (c1, i1) if RANK_ORDER[c1.rank] > RANK_ORDER[c2.rank] else (c2, i2)
        l1 = c1.suit == lead
        l2 = c2.suit == lead
        if l1 and not l2:
            return c1, i1
        if l2 and not l1:
            return c2, i2
        if l1 and l2:
            return (c1, i1) if RANK_ORDER[c1.rank] > RANK_ORDER[c2.rank] else (c2, i2)
        return c1, i1

    def can_claim_pair(self, player):
        if not self.trump_suit:
            return False
        hk = any(c.rank == 'K' and c.suit == self.trump_suit for c in player.hand)
        hq = any(c.rank == 'Q' and c.suit == self.trump_suit for c in player.hand)
        return hk and hq

    def pair_bonus_value(self):
        return 4

    def claim_pair(self, player_index):
        team = self.players[player_index].team
        if not self.pair_claimed[team]:
            self.pair_claimed[team] = True
            self.tricks_won_points[team] += self.pair_bonus_value()
            return True
        return False

    def score_round(self):
        bt = self.players[self.bid_winner].team
        ot = 1 - bt
        bp = self.tricks_won_points[bt]
        made = bp >= self.bid_amount
        res = {'made': made, 'bidder_points': bp, 'bid_amount': self.bid_amount}
        change = 1 * self.multiplier
        if made:
            self.game_scores[bt] += change
            res['winner_team'] = bt
        else:
            self.game_scores[ot] += change
            res['winner_team'] = ot
        res['multiplier'] = self.multiplier
        return res


# =============================================================
# 4) Graphical User Interface
# =============================================================
# এই ক্লাসটি Tkinter GUI-এর পুরো ইন্টারফেস তৈরি করে।
# এতে টেবিল, কার্ড, বাটন, অ্যানিমেশন, এবং খেলোয়াড়দের অবস্থান দেখানো হয়।
class Game29GUI:
    """Tkinter-based graphical interface for the Twenty-Nine card game."""

    CARD_W = 76
    CARD_H = 108

    def __init__(self, root):
        self.root = root
        self.root.title("Twenty-Nine — AI Card Game")
        self.W, self.H = 1280, 860
        self.root.geometry(f"{self.W}x{self.H}")
        self.root.configure(bg=COL_NAVY_DEEP)
        self.root.resizable(False, False)

        self.game = Game29()
        self.game.start_round()
        self.anim_running = False
        self.in_menu = True
        self._menu_pulse = 0
        self._seat_pulse = 0
        self._pulse_job = None
        self.hover_card = None
        self.hover_lift = {}          # card -> current lift px
        self._hover_job = None
        self._hidden_trick = False    # hide static trick while animating collect
        self._hide_hand = False       # hide face-up hand until deal+reveal done
        self._hide_fans = False       # hide opponent piles until deal done
        self._opp_fan_total = None    # layout fan as N cards while drawing fewer (2nd deal)
        self._locked_hand = []        # first 4 cards — never reshuffled
        self._incoming_cards = []     # second 4 cards — dealt after bid only
        self._flying_play = None      # (pidx, card) in flight — not drawn on board yet
        self.message_text = ""
        self.sound = SoundPlayer()
        self.sound_toggle_active = True
        self._last_hover_play = 0.0

        self.canvas = tk.Canvas(self.root, width=self.W, height=self.H,
                                highlightthickness=0, bg=COL_NAVY_DEEP)
        self.canvas.pack(fill="both", expand=True)

        self.hand_hit = []
        self.button_hit = []
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<Motion>", self.on_motion)

        self.draw_static_bg()
        self.show_menu()

    # -------------------------------------------------------------
    # 4.1) Canvas Drawing Helpers
    # -------------------------------------------------------------
    # এই অংশে Canvas-এ rounded panel, button, card, এবং decorative
    # element আঁকার helper ফাংশন সংজ্ঞায়িত করা হয়েছে।

    def round_rect(self, x1, y1, x2, y2, r, **kw):
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return self.canvas.create_polygon(pts, smooth=True, **kw)

    def panel(self, x1, y1, x2, y2, r=14, fill=COL_PANEL, outline=COL_GOLD_DARK, width=1, tags="dyn"):
        self.round_rect(x1 + 3, y1 + 5, x2 + 3, y2 + 5, r, fill="#04080f", outline="", tags=tags)
        self.round_rect(x1, y1, x2, y2, r, fill=fill, outline=outline, width=width, tags=tags)
        self.round_rect(x1 + 5, y1 + 5, x2 - 5, y2 - 5, max(6, r - 4),
                        fill="", outline="#1e3348", width=1, tags=tags)

    def play_center(self):
        """True geometric center of the play oval / trick cross."""
        # Slightly raised so oval aligns with West/East seats and trick cards
        return self.W // 2, 418

    def table_center(self):
        """Top-left of a card centered on the play oval."""
        cx, cy = self.play_center()
        return cx - self.CARD_W // 2, cy - self.CARD_H // 2

    def trick_slots(self):
        """Card top-left positions around the play-center cross."""
        cx, cy = self.table_center()
        dx, dy = 96, 72
        return {
            0: (cx, cy + dy),       # South
            1: (cx - dx, cy),       # West
            2: (cx, cy - dy),       # North
            3: (cx + dx, cy),       # East
        }

    def seat_xy(self):
        # West/East profiles stay fixed; card fans center on these Y values
        side_y = 358
        return {
            0: (self.W // 2, 612),
            1: (108, side_y),
            2: (self.W // 2, 122),
            3: (self.W - 108, side_y),
        }

    def side_fan_geometry(self, n):
        """Vertical West/East fan: card size + step (must match draw_opp_fan)."""
        card_w, card_h, step = 54, 38, 18
        n = max(0, n)
        fan_h = card_h + max(0, n - 1) * step if n else 0
        return card_w, card_h, step, fan_h

    def side_fan_top(self, n, seat_y):
        """Top Y so the fan stack is vertically centered on the profile avatar."""
        _w, _h, _step, fan_h = self.side_fan_geometry(n)
        if n <= 0:
            return seat_y
        return int(seat_y - fan_h / 2)

    def seat_card_slot(self, pidx, index, total_n):
        """(x, y, w, h) for card slot `index` at seat — same geometry as final fans/hand."""
        if pidx == 0:
            gap, start_x, hand_y, _ = self.hand_layout(total_n)
            return start_x + index * (self.CARD_W + gap), hand_y, self.CARD_W, self.CARD_H
        seats = self.seat_xy()
        if pidx == 2:  # North — horizontal fan
            return self.W // 2 - 130 + index * 24, 202, 38, 54
        if pidx == 1:  # West — vertical fan
            y_top = self.side_fan_top(total_n, seats[1][1])
            return 175, y_top + index * 18, 54, 38
        # East — vertical fan
        y_top = self.side_fan_top(total_n, seats[3][1])
        return self.W - 240, y_top + index * 18, 54, 38

    def deal_job_order(self, count_per_player, start_slot=0):
        """Round-robin deal order matching Game29 dealing (from bidder_start)."""
        jobs = []
        bs = self.game.bidder_start
        for r in range(count_per_player):
            for i in range(4):
                jobs.append(((bs + i) % 4, start_slot + r))
        return jobs

    def draw_static_bg(self):
        """Midnight stage + radial emerald felt — premium casino layout."""
        # Deep navy stage
        self.canvas.create_rectangle(0, 0, self.W, self.H, fill=COL_NAVY_DEEP, outline="")
        for i in range(0, self.H, 3):
            t = i / self.H
            r = int(7 + 4 * t)
            g = int(10 + 8 * t)
            b = int(18 + 14 * (1 - t))
            self.canvas.create_line(0, i, self.W, i, fill=f"#{r:02x}{g:02x}{b:02x}", width=3)

        m = 26
        # Felt well
        self.round_rect(m, m, self.W - m, self.H - m, 32, fill=COL_FELT_DEEP, outline="", tags="bg")

        # Radial felt (bright center → deep rim) — same center as play oval
        cx, cy = self.W // 2, 418
        for rad in range(360, 30, -14):
            k = rad / 360
            r = int(12 + 8 * (1 - k))
            g = int(0x3B + 40 * (1 - k))
            b = int(0x31 + 20 * (1 - k))
            self.canvas.create_oval(
                cx - rad, cy - int(rad * 0.56),
                cx + rad, cy + int(rad * 0.56),
                outline="", fill=f"#{r:02x}{g:02x}{b:02x}", tags="bg")

        # Soft inset shadow ring (aligned with gold play oval)
        self.canvas.create_oval(cx - 210, cy - 128, cx + 210, cy + 128,
                                outline="#083028", width=10, tags="bg")
        self.canvas.create_oval(cx - 198, cy - 118, cx + 198, cy + 118,
                                outline=COL_GOLD_DARK, width=1, tags="bg")

        # Micro diamond texture
        for x in range(m + 50, self.W - m, 56):
            for y in range(m + 50, self.H - m, 56):
                if (x // 56 + y // 56) % 2 == 0:
                    self.canvas.create_text(x, y, text="·", font=(FONT_UI, 7),
                                            fill="#0a4a3a", tags="bg")

        # Navy rail + amber bead (premium frame)
        self.canvas.create_rectangle(6, 6, self.W - 6, self.H - 6,
                                     outline=COL_NAVY, width=14, tags="bg")
        self.canvas.create_rectangle(16, 16, self.W - 16, self.H - 16,
                                     outline=COL_GOLD_DARK, width=2, tags="bg")
        self.canvas.create_rectangle(20, 20, self.W - 20, self.H - 20,
                                     outline=COL_GOLD, width=1, tags="bg")
        self.canvas.create_rectangle(24, 24, self.W - 24, self.H - 24,
                                     outline="#1a2a40", width=3, tags="bg")

        for (ox, oy, sx, sy) in [(38, 38, 1, 1), (self.W - 38, 38, -1, 1),
                                  (38, self.H - 38, 1, -1), (self.W - 38, self.H - 38, -1, -1)]:
            self.canvas.create_line(ox, oy, ox + 32 * sx, oy, fill=COL_GOLD, width=2, tags="bg")
            self.canvas.create_line(ox, oy, ox, oy + 32 * sy, fill=COL_GOLD, width=2, tags="bg")
            self.canvas.create_oval(ox - 3, oy - 3, ox + 3, oy + 3, fill=COL_GOLD_SOFT, outline="", tags="bg")

    # -------------------------------------------------------------
    # 4.2) Main Menu
    # -------------------------------------------------------------
    # এই অংশে গেমের শুরুতে menu প্রদর্শন করা হয়।
    # Continue, New Game, এবং Exit বাটন দিয়ে ব্যবহারকারী গেম চালু বা বন্ধ করতে পারে।

    def show_menu(self):
        self.in_menu = True
        self._stop_seat_pulse()
        self.canvas.delete("all")
        self.draw_static_bg()
        self.button_hit = []
        self.hand_hit = []

        cx, cy = self.W // 2, self.H // 2 - 30
        # Dim overlay
        self.round_rect(40, 40, self.W - 40, self.H - 40, 28,
                        fill=COL_NAVY, outline="", tags="menu")
        # Soft translucent panel via layered navy
        self.round_rect(cx - 340, 100, cx + 340, self.H - 100, 24,
                        fill="#0D1B2A", outline=COL_GOLD_DARK, width=2, tags="menu")
        self.round_rect(cx - 328, 112, cx + 328, self.H - 112, 18,
                        fill="", outline="#1E3A5F", width=1, tags="menu")

        self.canvas.create_text(cx, 150, text="TWENTY-NINE",
                                font=(FONT_DISPLAY, 16), fill=COL_GOLD_SOFT, tags="menu")
        self.canvas.create_text(cx, 230, text="29",
                                font=(FONT_DISPLAY, 100, "bold"), fill=COL_GOLD, tags=("menu", "brand29"))
        self.canvas.create_text(cx, 300, text="Card Game with Artificial Intelligence",
                                font=(FONT_DISPLAY, 15, "italic"), fill=COL_TEXT, tags="menu")

        self.canvas.create_text(cx, 460, text="Four players  ·  Fixed partnerships  ·  Heuristic AI",
                                font=(FONT_UI, 12), fill=COL_MUTED, tags="menu")

        bw, bh = 300, 50
        bx = cx - bw // 2
        by = 500
        self.draw_button(bx, by, bw, bh, "CONTINUE", self.menu_continue,
                         bg=COL_GOLD, fg=COL_INK, size=15, style="primary")
        self.draw_button(bx, by + 64, bw, bh, "NEW GAME", self.menu_new_game,
                         bg=COL_PANEL_HI, fg=COL_GOLD_SOFT, size=15, style="ghost")
        self.draw_button(bx, by + 128, bw, bh, "EXIT", self.exit_game,
                         bg="#3B1520", fg="#FECACA", size=14, style="ghost")

        self.canvas.create_text(cx, self.H - 78, text="Bid  ·  Trump  ·  Trick  ·  Pair Claim",
                                font=(FONT_UI, 10), fill=COL_MUTED, tags="menu")
        self._menu_pulse = 0
        self._animate_menu_brand()

    def _animate_menu_brand(self):
        if not self.in_menu:
            return
        self._menu_pulse = (self._menu_pulse + 1) % 90
        t = self._menu_pulse / 90
        intensity = 0.5 + 0.5 * abs(math.sin(t * math.pi * 2))
        self.canvas.delete("pulse")
        w = int(50 + 90 * intensity)
        cx = self.W // 2
        self.canvas.create_line(cx - w, 272, cx + w, 272,
                                fill=COL_GOLD_SOFT if intensity > 0.65 else COL_GOLD_DARK,
                                width=2, tags=("menu", "pulse"))
        # Gentle bob on demo cards
        self.canvas.delete("menu_bob")
        demo = [Card('♠', 'J'), Card('♥', '9'), Card('♦', 'A'), Card('♣', '10')]
        for i, c in enumerate(demo):
            bob = 6 * math.sin(t * math.pi * 2 + i * 0.7)
            self.draw_card(cx - 180 + i * 95, 330 + bob, c, playable=True, tag=("menu", "menu_bob"))
        self.root.after(ANIM_FRAME + 8, self._animate_menu_brand)

    def menu_continue(self):
        self.in_menu = False
        self._enter_table_with_deal()

    def menu_new_game(self):
        self.in_menu = False
        self.game.reset_game()
        self.game.start_round()
        self._enter_table_with_deal()

    def _enter_table_with_deal(self):
        """Table appears; hand stays hidden until shuffle → deal → reveal finishes."""
        self.message_text = "Shuffling…"
        self._hide_hand = True
        self._hide_fans = True
        self.refresh_all()
        self._start_seat_pulse()
        self.animate_shuffle_deal(after=self._after_opening_deal)

    def _after_opening_deal(self):
        self.message_text = ""
        self._hide_hand = False
        self._hide_fans = False
        # Snapshot first 4 after opening deal (stable through bidding)
        human = self.game.players[0]
        human.hand = sorted(human.hand, key=lambda c: (c.suit, RANK_ORDER[c.rank]))
        self._locked_hand = list(human.hand)
        self._incoming_cards = []
        self.refresh_all()
        self.process_phase()

    # -------------------------------------------------------------
    # 4.3) Table Layout and Card Rendering
    # -------------------------------------------------------------
    # এই অংশে কার্ডের front/back rendering, hand layout,
    # opponent fan, seat positions, এবং table geometry তৈরি করা হয়।

    def draw_card_back(self, x, y, w, h, tag="t"):
        r = max(6, int(w * 0.14))
        self.round_rect(x + 2, y + 4, x + w + 2, y + h + 4, r, fill="#050a12", outline="", tags=tag)
        self.round_rect(x, y, x + w, y + h, r, fill=BACK_BG, outline=COL_GOLD, width=2, tags=tag)
        self.round_rect(x + w * 0.08, y + h * 0.07, x + w * 0.92, y + h * 0.93,
                        max(4, int(w * 0.10)), fill=BACK_INNER,
                        outline=COL_GOLD_DARK, width=1, tags=tag)
        step = max(8, int(w * 0.18))
        ix1, iy1 = x + w * 0.12, y + h * 0.10
        ix2, iy2 = x + w * 0.88, y + h * 0.90
        for i in range(int(ix1), int(ix2), step):
            self.canvas.create_line(i, iy1, i, iy2, fill=BACK_PATTERN, width=1, tags=tag)
        for j in range(int(iy1), int(iy2), step):
            self.canvas.create_line(ix1, j, ix2, j, fill=BACK_PATTERN, width=1, tags=tag)
        mx, my = x + w / 2, y + h / 2
        ds = w * 0.20
        self.canvas.create_polygon(mx, my - ds, mx + ds, my, mx, my + ds, mx - ds, my,
                                   outline=COL_GOLD, fill=BACK_BG, width=1, tags=tag)
        self.canvas.create_text(mx, my, text="29",
                                font=(FONT_DISPLAY, max(8, int(w * 0.22)), "bold"),
                                fill=COL_GOLD, tags=tag)

    def draw_card(self, x, y, card, playable=True, glow=False, face=True, tag="t",
                  scale_x=1.0, lift=0):
        """scale_x < 1 simulates a 3D flip squash; lift raises the card."""
        w0, h = self.CARD_W, self.CARD_H
        y = y - lift
        scale_x = max(0.06, min(1.0, abs(scale_x)))
        w = w0 * scale_x
        x = x + (w0 - w) / 2

        if glow and scale_x > 0.5:
            self.round_rect(x - 6, y - 6, x + w + 6, y + h + 6, 14,
                            fill="#0a2e24", outline=COL_GOLD, width=1, tags=tag)
            self.round_rect(x - 2, y - 2, x + w + 2, y + h + 2, 12,
                            fill="", outline=COL_GOLD_SOFT, width=1, tags=tag)

        self.round_rect(x + 2, y + 4, x + w + 2, y + h + 4, 12, fill="#050a12", outline="", tags=tag)

        # Edge-on / flip midpoint → show back
        show_face = face and scale_x > 0.42
        if not show_face:
            self.draw_card_back(x, y, w, h, tag)
            return

        body = COL_IVORY if playable else COL_IVORY_DIM
        edge = COL_GOLD_DARK if playable else "#8a8578"
        self.round_rect(x, y, x + w, y + h, 12, fill=body, outline=edge, width=2, tags=tag)
        self.round_rect(x + 5, y + 5, x + w - 5, y + h - 5, 8,
                        fill="", outline="#E8DFC8", width=1, tags=tag)
        if card is None:
            return
        col = SUIT_COLORS[card.suit] if playable else "#777066"
        fs = max(9, int(13 * scale_x))
        cs = max(10, int(34 * scale_x))
        self.canvas.create_text(x + 12 * scale_x + 4, y + 16, text=card.rank,
                                font=(FONT_DISPLAY, fs, "bold"), fill=col, tags=tag, anchor="center")
        self.canvas.create_text(x + 12 * scale_x + 4, y + 32, text=card.suit,
                                font=(FONT_SUIT, max(9, fs - 1)), fill=col, tags=tag, anchor="center")
        self.canvas.create_text(x + w / 2, y + h / 2 + 2, text=card.suit,
                                font=(FONT_SUIT, cs, "bold"), fill=col, tags=tag)
        if card.points > 0 and playable and scale_x > 0.7:
            self.canvas.create_oval(x + w / 2 - 10, y + h - 28, x + w / 2 + 10, y + h - 8,
                                    fill="#F5EBD4", outline="#D4C9A8", width=1, tags=tag)
            self.canvas.create_text(x + w / 2, y + h - 18, text=str(card.points),
                                    font=(FONT_UI, 9, "bold"), fill=COL_GOLD_DARK, tags=tag)
        self.canvas.create_text(x + w - 12 * scale_x - 4, y + h - 32, text=card.suit,
                                font=(FONT_SUIT, max(9, fs - 1)), fill=col, tags=tag, anchor="center")
        self.canvas.create_text(x + w - 12 * scale_x - 4, y + h - 16, text=card.rank,
                                font=(FONT_DISPLAY, fs, "bold"), fill=col, tags=tag, anchor="center")

    def draw_button(self, x, y, w, h, text, callback, bg=COL_GOLD, fg=COL_INK, size=11, style="primary"):
        # Shadow
        self.round_rect(x + 2, y + 3, x + w + 2, y + h + 3, 8, fill="#04120c", outline="", tags="ui")
        if style == "ghost":
            self.round_rect(x, y, x + w, y + h, 8, fill=bg, outline=COL_GOLD_DARK, width=1, tags="ui")
        else:
            self.round_rect(x, y, x + w, y + h, 8, fill=bg, outline=COL_GOLD_DARK, width=2, tags="ui")
            # Top highlight strip
            self.round_rect(x + 3, y + 2, x + w - 3, y + max(8, h // 3), 6,
                            fill="", outline=COL_GOLD_SOFT, width=1, tags="ui")
        self.canvas.create_text(x + w / 2, y + h / 2, text=text,
                                font=(FONT_UI, size, "bold"), fill=fg, tags="ui")
        self.button_hit.append((x, y, x + w, y + h, callback))

    # -------------------------------------------------------------
    # 4.4) Refresh and Redraw Logic
    # -------------------------------------------------------------
    # এই অংশে প্রতিবার কোনো game state পরিবর্তন হলে পুরো UI yeniden draw করা হয়।
    # score, trump, hand, trick, message—সবকিছু refresh_all() দিয়ে আপডেট হয়।

    def refresh_all(self):
        if self.in_menu:
            return
        self.canvas.delete("dyn")
        self.canvas.delete("ui")
        self.canvas.delete("menu")
        self.canvas.delete("hand")
        if not self.anim_running:
            self.canvas.delete("anim")
        self.canvas.delete("seatpulse")
        self.hand_hit = []
        self.button_hit = []

        self.draw_table_center()
        self.draw_scoreboard()
        self.draw_trump_panel()
        self.draw_players_and_trick()
        self.draw_left_panel()
        if not self._hide_hand:
            self.draw_hand()
        else:
            # Empty tray placeholder so layout stays premium while hidden
            self._draw_empty_hand_tray()
        self.draw_message()
        self.draw_sound_toggle()

    def draw_table_center(self):
        """Gold play oval — centered on the same point as trick cards."""
        cx, cy = self.play_center()
        self.canvas.create_oval(cx - 200, cy - 122, cx + 200, cy + 122,
                                outline=COL_GOLD_DARK, width=2, tags="dyn")
        self.canvas.create_oval(cx - 188, cy - 112, cx + 188, cy + 112,
                                outline=COL_GOLD, width=1, tags="dyn")
        self.canvas.create_oval(cx - 176, cy - 102, cx + 176, cy + 102,
                                outline="#0A4034", width=1, tags="dyn")
        self.canvas.create_text(cx, cy, text="29",
                                font=(FONT_DISPLAY, 40, "bold"), fill="#0A4034", tags="dyn")

    def score_column_rect(self):
        """Right-top stacked team scoreboards — clear of North (center)."""
        track_w, track_h, gap = 236, 68, 8
        x = self.W - track_w - 40           # right top
        y0 = 72
        return x, y0, track_w, track_h, gap

    def draw_scoreboard(self):
        # Brand header center — North sits below, no board overlap
        self.canvas.create_text(self.W // 2, 40, text="TWENTY-NINE",
                                font=(FONT_DISPLAY, 11), fill=COL_GOLD_SOFT, tags="dyn")
        self.canvas.create_text(self.W // 2, 62, text="29",
                                font=(FONT_DISPLAY, 26, "bold"), fill=COL_GOLD, tags="dyn")

        # RIGHT TOP: OPPONENTS above YOUR TEAM
        sx, sy, tw, th, gap = self.score_column_rect()
        self.draw_score_track(sx, sy, "OPPONENTS", self.game.game_scores[1], COL_CRIMSON, tw, th)
        self.draw_score_track(sx, sy + th + gap, "YOUR TEAM", self.game.game_scores[0], "#2d8a5a", tw, th)

        # LEFT: ROUND POINTS only (under sound toggle)
        g = self.game
        rp_x, rp_y, rp_w, rp_h = self.round_points_rect()
        self.panel(rp_x, rp_y, rp_x + rp_w, rp_y + rp_h, r=10, tags="dyn")
        mid = rp_x + rp_w / 2
        self.canvas.create_text(mid, rp_y + 14, text="ROUND POINTS",
                                font=(FONT_UI, 8), fill=COL_MUTED, tags="dyn")
        self.canvas.create_text(mid - 40, rp_y + 36, text=str(g.tricks_won_points[0]),
                                font=(FONT_DISPLAY, 16, "bold"), fill=COL_GOLD, tags="dyn")
        self.canvas.create_text(mid, rp_y + 36, text="—",
                                font=(FONT_UI, 13), fill=COL_MUTED, tags="dyn")
        self.canvas.create_text(mid + 40, rp_y + 36, text=str(g.tricks_won_points[1]),
                                font=(FONT_DISPLAY, 16, "bold"), fill="#e8a090", tags="dyn")

    def round_points_rect(self):
        """Left ROUND POINTS board — x, y, w, h."""
        return 36, 72, 200, 56

    def status_banner_rect(self):
        """Popup/status strip directly under ROUND POINTS (same width, left-aligned)."""
        rp_x, rp_y, rp_w, rp_h = self.round_points_rect()
        y1 = rp_y + rp_h + 8
        return rp_x, y1, rp_x + rp_w, y1 + 40

    def draw_status_banner(self, text, tags="dyn"):
        """All game popups render here — under ROUND POINTS, never over North."""
        if not text:
            return
        x1, y1, x2, y2 = self.status_banner_rect()
        self.panel(x1, y1, x2, y2, r=10, tags=tags)
        self.canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=text,
                                font=(FONT_UI, 9, "bold"), fill=COL_GOLD_SOFT, tags=tags,
                                width=x2 - x1 - 18, justify="center")

    def draw_score_track(self, x, y, label, score, labelcol, w=248, h=72):
        self.panel(x, y, x + w, y + h, r=10, tags="dyn")
        self.canvas.create_text(x + w / 2, y + 14, text=label,
                                font=(FONT_UI, 10, "bold"), fill=labelcol, tags="dyn")
        slot_w, slot_h, slot_gap = 30, 30, 6
        total = 6 * slot_w + 5 * slot_gap
        start = x + (w - total) / 2
        for i in range(6):
            cx = start + i * (slot_w + slot_gap)
            cy = y + 32
            lit = i < score
            if lit:
                self.round_rect(cx, cy, cx + slot_w, cy + slot_h, 5,
                                fill=COL_CRIMSON, outline=COL_GOLD, width=1, tags="dyn")
                self.canvas.create_text(cx + slot_w / 2, cy + slot_h / 2, text="●",
                                        font=(FONT_UI, 10), fill=COL_GOLD_SOFT, tags="dyn")
            else:
                self.round_rect(cx, cy, cx + slot_w, cy + slot_h, 5,
                                fill="#12100e", outline="#3a3530", width=1, tags="dyn")
                self.canvas.create_text(cx + slot_w / 2, cy + slot_h / 2, text="○",
                                        font=(FONT_UI, 10), fill="#4a4540", tags="dyn")

    def draw_trump_panel(self):
        """Compact trump box — clear of East fan, score column, and hand tray."""
        pw, ph = 124, 158
        px = self.W - pw - 42
        # Sit below East cards (~490) and above hand tray (705)
        py = 528
        self.panel(px, py, px + pw, py + ph, r=10, tags="dyn")
        self.canvas.create_text(px + pw / 2, py + 16, text="TRUMP",
                                font=(FONT_DISPLAY, 10, "bold"), fill=COL_GOLD, tags="dyn")

        # Mini card so the panel stays short
        cw, ch = 48, 68
        cx = px + (pw - cw) / 2
        cy = py + 30
        g = self.game
        ow, oh = self.CARD_W, self.CARD_H
        self.CARD_W, self.CARD_H = cw, ch
        try:
            if g.trump_suit:
                if g.trump_revealed:
                    self.draw_card(cx, cy, Card(g.trump_suit, 'A'), playable=True, glow=False, tag="dyn")
                    self.canvas.create_text(px + pw / 2, py + 112, text=SUIT_NAMES[g.trump_suit].upper(),
                                            font=(FONT_UI, 9, "bold"), fill=COL_TEXT, tags="dyn")
                    self.canvas.create_text(px + pw / 2, py + 128, text="REVEALED",
                                            font=(FONT_UI, 8), fill="#7ec8a3", tags="dyn")
                else:
                    self.draw_card(cx, cy, None, face=False, tag="dyn")
                    self.canvas.create_text(px + pw / 2, py + 112, text="HIDDEN",
                                            font=(FONT_UI, 9, "bold"), fill=COL_ACTIVE, tags="dyn")
                    human = g.players[0]
                    if (g.phase == "PLAY" and not g.trump_revealed
                            and g.current_player == 0 and g.can_reveal_trump(human)):
                        self.draw_button(px + 10, py + ph - 34, pw - 20, 26, "Reveal",
                                         self.human_reveal_trump, bg="#a65d1a", fg=COL_IVORY, size=9)
            else:
                self.canvas.create_text(px + pw / 2, py + 78, text="Not set",
                                        font=(FONT_UI, 10), fill=COL_MUTED, tags="dyn")
        finally:
            self.CARD_W, self.CARD_H = ow, oh

    def draw_sound_toggle(self):
        x, y, w, h = 36, 36, 100, 30
        label = "Sound  ON" if self.sound_toggle_active else "Sound  OFF"
        self.round_rect(x, y, x + w, y + h, 8, fill=COL_PANEL, outline=COL_GOLD_DARK, width=1, tags="dyn")
        self.canvas.create_text(x + w // 2, y + h // 2, text=label,
                                font=(FONT_UI, 9, "bold"),
                                fill=COL_GOLD if self.sound_toggle_active else COL_MUTED, tags="dyn")
        self.button_hit.append((x, y, x + w, y + h, self.toggle_sound))

    def toggle_sound(self):
        self.sound_toggle_active = not self.sound_toggle_active
        self.sound.enabled = self.sound_toggle_active
        self.refresh_all()

    def draw_left_panel(self):
        g = self.game
        bx = 36
        if g.bid_winner is not None:
            bname = g.players[g.bid_winner].name.split(" (")[0]
            title = "CONTRACT"
            detail = f"{g.bid_amount}  ×{g.multiplier}"
            sub = f"by {bname}"
        elif g.highest_bidder is not None:
            title = "AUCTION"
            detail = str(g.bid_value)
            sub = "bidding…"
        else:
            title = "AUCTION"
            detail = "—"
            sub = "awaiting bids"

        info_y = self.H - 200
        self.panel(bx, info_y, bx + 168, info_y + 70, r=10, tags="dyn")
        self.canvas.create_text(bx + 84, info_y + 16, text=title,
                                font=(FONT_UI, 8), fill=COL_MUTED, tags="dyn")
        self.canvas.create_text(bx + 84, info_y + 38, text=detail,
                                font=(FONT_DISPLAY, 16, "bold"), fill=COL_GOLD, tags="dyn")
        self.canvas.create_text(bx + 84, info_y + 56, text=sub,
                                font=(FONT_UI, 9), fill=COL_TEXT, tags="dyn")

        by = info_y + 84
        self.draw_button(bx, by, 168, 34, "New Game", self.new_game,
                         bg=COL_PANEL_HI, fg=COL_GOLD_SOFT, size=11, style="ghost")
        self.draw_button(bx, by + 42, 168, 34, "Exit", self.exit_game,
                         bg="#3a1a14", fg="#e8c4b8", size=11, style="ghost")

    def new_game(self):
        if messagebox.askyesno("New Game", "Start a brand new game?"):
            self.anim_running = False
            self._hidden_trick = False
            self._hide_hand = False
            self._hide_fans = False
            self._opp_fan_total = None
            self._locked_hand = []
            self._incoming_cards = []
            self._flying_play = None
            self.hover_lift.clear()
            self.game.reset_game()
            self.game.start_round()
            self._enter_table_with_deal()

    def exit_game(self):
        if messagebox.askyesno("Exit", "Quit the game?"):
            self._stop_seat_pulse()
            self.root.quit()

    def draw_players_and_trick(self):
        g = self.game
        seats = self.seat_xy()
        if not self._hide_fans:
            # While second deal is pending, opponents still show only the first 4
            trim = 4 if self._incoming_cards else 0
            n_west = max(0, len(g.players[1].hand) - trim)
            n_east = max(0, len(g.players[3].hand) - trim)
            n_north = max(0, len(g.players[2].hand) - trim)
            # During 2nd deal anim, layout as full 8 so new cards land in correct slots
            layout = self._opp_fan_total
            lay_w = layout if layout else n_west
            lay_e = layout if layout else n_east
            # North cards below profile+name (profile y=122, name ~154) — no overlap
            self.draw_opp_fan(self.W // 2 - 130, 202, n_north, "h")
            # West/East cards move with count so avatar stays in the vertical middle
            west_y = self.side_fan_top(lay_w, seats[1][1])
            east_y = self.side_fan_top(lay_e, seats[3][1])
            self.draw_opp_fan(175, west_y, n_west, "v")
            self.draw_opp_fan(self.W - 240, east_y, n_east, "v")

        # Profiles drawn after fans so avatar/name stay on top and fixed in place
        for pidx, (sx, sy) in seats.items():
            self.player_profile(sx, sy, pidx, g.current_player == pidx)

        if not self._hidden_trick:
            slots = self.trick_slots()
            for (pidx, card) in g.current_trick:
                # While a play animation is flying, do NOT paint that card on the board
                if (self._flying_play is not None
                        and self._flying_play[0] == pidx
                        and self._flying_play[1] == card):
                    continue
                x, y = slots[pidx]
                self.draw_card(x, y, card, playable=True, tag="dyn")

    def _draw_empty_hand_tray(self):
        n = max(4, len(self.game.players[0].hand) or 4)
        gap, start_x, y, total_w = self.hand_layout(n)
        self.round_rect(start_x - 28, y - 18, start_x + total_w + 28, y + self.CARD_H + 22, 18,
                        fill="#050A14", outline="", tags="hand")
        self.round_rect(start_x - 24, y - 14, start_x + total_w + 24, y + self.CARD_H + 18, 16,
                        fill="#0A1628", outline=COL_GOLD_DARK, width=2, tags="hand")
        self.round_rect(start_x - 20, y - 10, start_x + total_w + 20, y + self.CARD_H + 14, 14,
                        fill="", outline=COL_GOLD, width=1, tags="hand")
        self.canvas.create_text(self.W // 2, y - 26, text="YOUR HAND",
                                font=(FONT_UI, 8, "bold"), fill=COL_MUTED, tags="hand")
        self.canvas.create_text(self.W // 2, y + self.CARD_H / 2,
                                text="Waiting for deal…",
                                font=(FONT_UI, 11, "italic"), fill=COL_MUTED, tags="hand")

    def draw_opp_fan(self, x, y, n, orient):
        for i in range(max(0, n)):
            if orient == "h":
                self.draw_card_back(x + i * 24, y, 38, 54, "dyn")
            else:
                # Keep in sync with side_fan_geometry()
                self.draw_card_back(x, y + i * 18, 54, 38, "dyn")

    def player_profile(self, x, y, pidx, active):
        g = self.game
        name = PLAYER_LABELS[pidx]
        initials = PLAYER_INITIALS[pidx]
        rr = 22
        ring = COL_GOLD if active else "#1a3a50"
        fill = "#2A2010" if active else "#0E1A28"
        self.canvas.create_oval(x - rr - 3, y - rr - 3, x + rr + 3, y + rr + 3,
                                fill="", outline=COL_GOLD_SOFT if active else "#122030",
                                width=1, tags=("dyn", f"seat{pidx}"))
        self.canvas.create_oval(x - rr, y - rr, x + rr, y + rr,
                                fill=fill, outline=ring, width=2, tags=("dyn", f"seat{pidx}"))
        self.canvas.create_text(x, y, text=initials,
                                font=(FONT_UI, 10, "bold"),
                                fill=COL_GOLD if active else COL_MUTED, tags="dyn")

        label = g.last_bid_label.get(pidx, "")
        if label:
            if pidx == 1:
                lx, by = x - 78, y + 4
            else:
                lx, by = x + 30, y + (0 if pidx != 0 else 0)
            self.round_rect(lx, by - 11, lx + 50, by + 11, 6,
                            fill=COL_IVORY, outline=COL_GOLD_DARK, width=1, tags="dyn")
            self.canvas.create_text(lx + 25, by, text=label,
                                    font=(FONT_UI, 9, "bold"),
                                    fill=COL_CRIMSON if label == "PASS" else "#1D4ED8", tags="dyn")

        w = 100
        ny = y + 32
        bg = COL_GOLD if active else COL_PANEL
        fg = COL_INK if active else COL_TEXT
        self.round_rect(x - w // 2, ny, x + w // 2, ny + 22, 8,
                        fill=bg, outline=COL_GOLD if active else "#243B55", width=1, tags="dyn")
        prefix = "● " if active else ""
        self.canvas.create_text(x, ny + 11, text=prefix + name,
                                font=(FONT_UI, 9, "bold"), fill=fg, tags="dyn")

    def hand_layout(self, n=None):
        """Return (gap, start_x, y, total_w) for the human hand tray."""
        if n is None:
            n = len(self.game.players[0].hand)
        gap = 14 if n <= 4 else 10
        total_w = max(0, n * (self.CARD_W + gap) - gap)
        start_x = (self.W - total_w) // 2
        return gap, start_x, 705, total_w

    def draw_hand(self):
        human = self.game.players[0]
        incoming = list(self._incoming_cards or [])
        valid = self.game.valid_moves(human) if self.game.phase == "PLAY" else []

        if incoming:
            # First 4 stay put face-up; second 4 are animated separately (not drawn here)
            locked = list(self._locked_hand) if self._locked_hand else [
                c for c in human.hand if c not in incoming
            ]
            visible = locked
            n_slots = len(locked) + len(incoming)
        else:
            visible = sorted(human.hand, key=lambda c: (c.suit, RANK_ORDER[c.rank]))
            human.hand = visible
            n_slots = len(visible)

        if not visible and not incoming:
            return

        gap, start_x, y, total_w = self.hand_layout(max(n_slots, 1))
        # Premium hand tray — layered navy + gold bead
        self.round_rect(start_x - 28, y - 18, start_x + total_w + 28, y + self.CARD_H + 22, 18,
                        fill="#050A14", outline="", tags="hand")
        self.round_rect(start_x - 24, y - 14, start_x + total_w + 24, y + self.CARD_H + 18, 16,
                        fill="#0A1628", outline=COL_GOLD_DARK, width=2, tags="hand")
        self.round_rect(start_x - 20, y - 10, start_x + total_w + 20, y + self.CARD_H + 14, 14,
                        fill="", outline=COL_GOLD, width=1, tags="hand")
        self.canvas.create_text(self.W // 2, y - 26, text="YOUR HAND",
                                font=(FONT_UI, 8, "bold"), fill=COL_MUTED, tags="hand")
        for i, card in enumerate(visible):
            playable = (self.game.phase == "PLAY" and self.game.current_player == 0
                        and not incoming and card in valid)
            lift = self.hover_lift.get(id(card), 0)
            if playable and self.hover_card is card and lift < 1:
                lift = 22
            xx = start_x + i * (self.CARD_W + gap)
            self.draw_card(xx, y, card, playable=playable or self.game.phase != "PLAY",
                           glow=playable, tag="hand", lift=lift)
            if not incoming:
                self.hand_hit.append((xx, y - lift, xx + self.CARD_W, y - lift + self.CARD_H,
                                      card, playable))

    def draw_message(self):
        # Always under ROUND POINTS — never above North profile
        self.draw_status_banner(self.message_text, tags="dyn")

    def set_message(self, text):
        self.message_text = text
        self.refresh_all()

    def on_click(self, e):
        for (x1, y1, x2, y2, cb) in self.button_hit:
            if x1 <= e.x <= x2 and y1 <= e.y <= y2:
                self.sound.play("button")
                cb()
                return
        if self.in_menu:
            return
        for (x1, y1, x2, y2, card, playable) in self.hand_hit:
            if playable and x1 <= e.x <= x2 and y1 <= e.y <= y2:
                self.human_play(card)
                return

    def on_motion(self, e):
        if self.in_menu or self.anim_running:
            return
        new = None
        for (x1, y1, x2, y2, card, playable) in self.hand_hit:
            if playable and x1 <= e.x <= x2 and y1 <= e.y <= y2:
                new = card
                break
        if new != self.hover_card:
            self.hover_card = new
            if new is not None and time.time() - self._last_hover_play > 0.06:
                self._last_hover_play = time.time()
                self.sound.play("hover")
            self._tick_hover_lift()

    def _tick_hover_lift(self):
        """Smooth interpolate card hover lift toward target."""
        if self.in_menu:
            return
        human = self.game.players[0]
        changed = False
        targets = {id(c): (22 if c is self.hover_card else 0) for c in human.hand}
        for key, target in targets.items():
            cur = self.hover_lift.get(key, 0)
            nxt = lerp(cur, target, 0.42)
            if abs(nxt - target) < 0.6:
                nxt = target
            if abs(nxt - cur) > 0.05:
                changed = True
            self.hover_lift[key] = nxt
        # Clean stale
        for key in list(self.hover_lift.keys()):
            if key not in targets:
                del self.hover_lift[key]
                changed = True
        if changed:
            self.canvas.delete("hand")
            self.hand_hit = []
            self.draw_hand()
            if self._hover_job:
                self.root.after_cancel(self._hover_job)
            self._hover_job = self.root.after(ANIM_FRAME, self._tick_hover_lift)

    def _start_seat_pulse(self):
        self._stop_seat_pulse()
        self._seat_pulse_loop()

    def _stop_seat_pulse(self):
        if self._pulse_job:
            try:
                self.root.after_cancel(self._pulse_job)
            except Exception:
                pass
            self._pulse_job = None
        self.canvas.delete("seatpulse")

    def _seat_pulse_loop(self):
        if self.in_menu:
            return
        self._seat_pulse = (self._seat_pulse + 1) % 80
        self.canvas.delete("seatpulse")
        if not self.anim_running:
            pidx = self.game.current_player
            sx, sy = self.seat_xy()[pidx]
            t = self._seat_pulse / 80
            rad = 26 + 5 * abs(math.sin(t * math.pi * 2))
            self.canvas.create_oval(sx - rad, sy - rad, sx + rad, sy + rad,
                                    outline=COL_GOLD_SOFT, width=2, tags="seatpulse")
            self.canvas.create_oval(sx - rad - 4, sy - rad - 4, sx + rad + 4, sy + rad + 4,
                                    outline=COL_GOLD_DARK, width=1, tags="seatpulse")
        self._pulse_job = self.root.after(ANIM_FRAME + 10, self._seat_pulse_loop)

    def animate_card(self, card, from_xy, to_xy, after, flip=True, pidx=None):
        """Fly card to board. Board slot stays empty until flight finishes."""
        steps = max(22, ANIM_CARD_MS // ANIM_FRAME)
        self.anim_running = True
        if pidx is not None:
            self._flying_play = (pidx, card)
        dist = math.hypot(to_xy[0] - from_xy[0], to_xy[1] - from_xy[1])
        arc = min(78, 32 + dist * 0.14)

        def step(i):
            if i > steps:
                self.canvas.delete("anim")
                # Soft land — still only the flying layer (board slot still empty)
                self.draw_card(to_xy[0], to_xy[1] - 3, card, playable=True, glow=True, tag="anim")
                self.root.after(ANIM_FRAME, lambda: self._finish_card_anim(card, to_xy, after))
                return
            raw = i / steps
            ease = ease_out_cubic(raw)
            if raw > 0.85:
                settle = ease_out_back(min(1.0, (raw - 0.85) / 0.15))
                ease = lerp(ease_out_cubic(0.85), 1.0, settle)
            x = lerp(from_xy[0], to_xy[0], ease)
            y = lerp(from_xy[1], to_xy[1], ease) - arc * math.sin(math.pi * ease)
            if flip:
                if raw < 0.42:
                    sx = 1.0 - ease_in_out_cubic(raw / 0.42) * 0.92
                else:
                    sx = 0.08 + ease_out_cubic((raw - 0.42) / 0.58) * 0.92
            else:
                sx = 1.0
            punch = 1.0 + 0.04 * math.sin(math.pi * ease)
            self.canvas.delete("anim")
            self.draw_card(x, y, card, playable=True, glow=True, tag="anim",
                           scale_x=sx * punch)
            self.root.after(ANIM_FRAME, lambda: step(i + 1))

        step(0)

    def _finish_card_anim(self, card, to_xy, after):
        self.canvas.delete("anim")
        # Now place on board: clear flying flag so static slot can paint
        self._flying_play = None
        self.anim_running = False
        after()

    def animate_trick_collect(self, trick, winner, after):
        """Slide all four trick cards toward the winner's seat (casino chip-fly feel)."""
        steps = max(16, ANIM_COLLECT_MS // ANIM_FRAME)
        self.anim_running = True
        self._hidden_trick = True
        slots = self.trick_slots()
        seats = self.seat_xy()
        tx, ty = seats[winner]
        tx -= self.CARD_W // 2
        ty -= 10
        starts = [(slots[p][0], slots[p][1], c) for p, c in trick]
        self.refresh_all()

        def step(i):
            if i > steps:
                self.canvas.delete("anim")
                self._hidden_trick = False
                self.anim_running = False
                after()
                return
            raw = i / steps
            ease = ease_in_out_cubic(raw)
            fade_scale = 1.0 - 0.35 * ease
            self.canvas.delete("anim")
            for (sx, sy, c) in starts:
                x = lerp(sx, tx, ease)
                y = lerp(sy, ty, ease) - 20 * math.sin(math.pi * ease)
                self.draw_card(x, y, c, playable=True, glow=raw < 0.5, tag="anim",
                               scale_x=fade_scale)
            self.root.after(ANIM_FRAME, lambda: step(i + 1))

        step(0)

    def animate_shuffle_deal(self, after=None):
        """Shuffle → deal face-down to ALL seats → reveal your hand. Opponents stay backs."""
        human = self.game.players[0]
        hand = sorted(human.hand, key=lambda c: (c.suit, RANK_ORDER[c.rank]))
        human.hand = hand
        if not hand:
            self._hide_hand = False
            self._hide_fans = False
            if after:
                after()
            return

        self.anim_running = True
        self._hide_hand = True
        self._hide_fans = True
        self._opp_fan_total = None
        self.canvas.delete("hand")
        self.canvas.delete("shuffle")
        self.canvas.delete("deal")
        self.canvas.delete("dealsouth")
        self.canvas.delete("dealopp")
        self.canvas.delete("dealtray")
        self.canvas.delete("reveal")

        n_each = len(hand)
        gap, start_x, hand_y, total_w = self.hand_layout(n_each)
        cx, cy = self.table_center()
        deck_x, deck_y = cx, cy - 10
        jobs = self.deal_job_order(n_each, start_slot=0)
        shuffle_steps = max(28, ANIM_SHUFFLE_MS // ANIM_FRAME)
        deal_steps = max(22, ANIM_DEAL_MS // ANIM_FRAME)
        reveal_steps = max(18, ANIM_REVEAL_MS // ANIM_FRAME)
        landed = [False] * len(jobs)
        stagger = max(55, ANIM_DEAL_STAGGER * 4 // max(1, len(jobs)))

        def draw_tray(status_text):
            self.canvas.delete("dealtray")
            self.canvas.delete("msgstatus")
            self.round_rect(start_x - 28, hand_y - 18, start_x + total_w + 28, hand_y + self.CARD_H + 22, 18,
                            fill="#050A14", outline="", tags="dealtray")
            self.round_rect(start_x - 24, hand_y - 14, start_x + total_w + 24, hand_y + self.CARD_H + 18, 16,
                            fill="#0A1628", outline=COL_GOLD_DARK, width=2, tags="dealtray")
            self.round_rect(start_x - 20, hand_y - 10, start_x + total_w + 20, hand_y + self.CARD_H + 14, 14,
                            fill="", outline=COL_GOLD, width=1, tags="dealtray")
            self.canvas.create_text(self.W // 2, hand_y - 26, text="YOUR HAND",
                                    font=(FONT_UI, 8, "bold"), fill=COL_MUTED, tags="dealtray")
            if status_text:
                self.draw_status_banner(status_text, tags=("dealtray", "msgstatus"))

        def finish_all():
            self.canvas.delete("shuffle")
            self.canvas.delete("deal")
            self.canvas.delete("dealsouth")
            self.canvas.delete("dealopp")
            self.canvas.delete("dealtray")
            self.canvas.delete("reveal")
            self.canvas.delete("msgstatus")
            self._hide_hand = False
            self._hide_fans = False
            self._opp_fan_total = None
            self.anim_running = False
            self.message_text = ""
            self.refresh_all()
            if after:
                after()

        def draw_deck_stack(riffle_t, spread=18):
            self.canvas.delete("shuffle")
            draw_tray("SHUFFLING")
            for i in range(7):
                packet = -1 if i % 2 == 0 else 1
                wobble = math.sin(riffle_t * math.pi * 5 + i * 0.5) * spread * packet
                lift = math.cos(riffle_t * math.pi * 3.2 + i * 0.8) * 5
                ox = deck_x + wobble + (i - 3) * 1.2
                oy = deck_y + i * 2.0 + lift
                self.draw_card_back(ox, oy, self.CARD_W, self.CARD_H, tag="shuffle")

        def shuffle_step(i):
            if i == 0:
                self.sound.play("shuffle")
            if i > shuffle_steps:
                self.sound.play("card")
                self.canvas.delete("shuffle")
                for k in range(5):
                    self.draw_card_back(deck_x + k * 1.1, deck_y + k * 1.6,
                                        self.CARD_W, self.CARD_H, tag="shuffle")
                self.root.after(140, start_dealing)
                return
            raw = i / shuffle_steps
            intensity = ease_in_out_cubic(min(1.0, raw * 1.15))
            draw_deck_stack(raw, spread=12 + 14 * math.sin(intensity * math.pi))
            if i % 7 == 0:
                self.sound.play("card")
            self.root.after(ANIM_FRAME, lambda: shuffle_step(i + 1))

        def start_dealing():
            self.canvas.delete("shuffle")
            self.message_text = ""
            draw_tray("DEALING")
            for jidx in range(len(jobs)):
                self.root.after(jidx * stagger, lambda j=jidx: deal_one(j))

        def maybe_start_reveal():
            if all(landed):
                self.root.after(160, reveal_all)

        def deal_one(jidx):
            pidx, slot = jobs[jidx]
            to_x, to_y, tw, th = self.seat_card_slot(pidx, slot, n_each)
            group = "dealsouth" if pidx == 0 else "dealopp"
            tag = f"deal{jidx}"
            tags = (tag, group)

            def step(i):
                if i > deal_steps:
                    landed[jidx] = True
                    self.canvas.delete(tag)
                    self.draw_card_back(to_x, to_y, tw, th, tag=tags)
                    self.sound.play("card")
                    maybe_start_reveal()
                    return
                raw = i / deal_steps
                ease = ease_out_quart(raw)
                swirl = math.sin(ease * math.pi) * (14 if jidx % 2 == 0 else -14)
                x = lerp(deck_x, to_x, ease) + swirl * (1 - ease)
                y = lerp(deck_y, to_y, ease) - 62 * math.sin(math.pi * ease)
                sx = 0.88 + 0.12 * math.sin(ease * math.pi)
                self.canvas.delete(tag)
                dw = tw * sx
                self.draw_card_back(x + (tw - dw) / 2, y, dw, th, tag=tags)
                self.root.after(ANIM_FRAME, lambda: step(i + 1))

            step(0)

        def reveal_all():
            """Flip YOUR hand face-up; opponent backs stay on their seats until finish."""
            draw_tray("REVEALING")
            self.sound.play("bid")

            def step(i):
                if i > reveal_steps:
                    finish_all()
                    return
                raw = i / reveal_steps
                self.canvas.delete("dealsouth")
                self.canvas.delete("reveal")
                for idx, card in enumerate(hand):
                    to_x, to_y, _tw, _th = self.seat_card_slot(0, idx, n_each)
                    local = min(1.0, max(0.0, (raw - idx * 0.04) / 0.72))
                    if local < 0.5:
                        sx = 1.0 - ease_in_out_cubic(local / 0.5) * 0.94
                        face = False
                    else:
                        sx = 0.06 + ease_out_back(min(1.0, (local - 0.5) / 0.5)) * 0.94
                        face = True
                    lift = 10 * math.sin(local * math.pi)
                    self.draw_card(to_x, to_y, card, playable=True, glow=face and local > 0.7,
                                   face=face, tag="reveal", scale_x=max(0.08, sx), lift=lift)
                self.root.after(ANIM_FRAME, lambda: step(i + 1))

            step(0)

        draw_tray("SHUFFLING")
        shuffle_step(0)

    def animate_deal_burst(self, after=None):
        """Alias — opening deal only (first 4)."""
        self.animate_shuffle_deal(after=after)

    def animate_deal_extra(self, new_cards, after=None):
        """After bid: deal next 4 to ALL seats. First 4 stay put (yours face-up)."""
        new_cards = list(new_cards or [])
        if not new_cards:
            self._incoming_cards = []
            self._locked_hand = []
            self._opp_fan_total = None
            if after:
                after()
            return

        locked = list(self._locked_hand) if self._locked_hand else [
            c for c in self.game.players[0].hand if c not in new_cards
        ]
        self._locked_hand = locked
        self._incoming_cards = new_cards
        self.anim_running = True
        # Keep first 4 visible; do not hide hand or reshuffle them
        self._hide_hand = False
        self._hide_fans = False
        n_locked = len(locked)
        n_new = len(new_cards)
        n_total = n_locked + n_new
        self._opp_fan_total = n_total  # position first 4 in full-8 fan slots
        self.canvas.delete("shuffle")
        self.canvas.delete("deal")
        self.canvas.delete("dealsouth")
        self.canvas.delete("dealopp")
        self.canvas.delete("dealtray")
        self.canvas.delete("reveal")
        self.refresh_all()

        cx, cy = self.table_center()
        deck_x, deck_y = cx, cy - 10
        jobs = self.deal_job_order(n_new, start_slot=n_locked)
        shuffle_steps = max(18, (ANIM_SHUFFLE_MS * 2 // 3) // ANIM_FRAME)
        deal_steps = max(20, ANIM_DEAL_MS // ANIM_FRAME)
        reveal_steps = max(16, ANIM_REVEAL_MS // ANIM_FRAME)
        landed = [False] * len(jobs)
        stagger = max(55, ANIM_DEAL_STAGGER * 4 // max(1, len(jobs)))

        def status(msg):
            self.canvas.delete("exstatus")
            self.canvas.delete("msgstatus")
            if msg:
                self.draw_status_banner(msg, tags=("exstatus", "msgstatus"))

        def finish_extra():
            self.canvas.delete("shuffle")
            self.canvas.delete("deal")
            self.canvas.delete("dealsouth")
            self.canvas.delete("dealopp")
            self.canvas.delete("reveal")
            self.canvas.delete("exstatus")
            self.canvas.delete("msgstatus")
            self._incoming_cards = []
            self._locked_hand = []
            self._opp_fan_total = None
            self.anim_running = False
            self.message_text = ""
            human = self.game.players[0]
            human.hand = sorted(human.hand, key=lambda c: (c.suit, RANK_ORDER[c.rank]))
            self.refresh_all()
            if after:
                after()

        def draw_packet(riffle_t, spread=14):
            self.canvas.delete("shuffle")
            status("SHUFFLING NEXT 4")
            for i in range(5):
                packet = -1 if i % 2 == 0 else 1
                wobble = math.sin(riffle_t * math.pi * 5 + i * 0.55) * spread * packet
                lift = math.cos(riffle_t * math.pi * 3 + i) * 4
                self.draw_card_back(deck_x + wobble + (i - 2) * 1.2,
                                    deck_y + i * 2.0 + lift,
                                    self.CARD_W, self.CARD_H, tag="shuffle")

        def shuffle_step(i):
            if i == 0:
                self.sound.play("shuffle")
            if i > shuffle_steps:
                self.sound.play("card")
                self.canvas.delete("shuffle")
                for k in range(3):
                    self.draw_card_back(deck_x + k, deck_y + k * 1.5,
                                        self.CARD_W, self.CARD_H, tag="shuffle")
                self.root.after(120, start_dealing)
                return
            raw = i / shuffle_steps
            draw_packet(raw, spread=10 + 12 * math.sin(ease_in_out_cubic(raw) * math.pi))
            if i % 6 == 0:
                self.sound.play("card")
            self.root.after(ANIM_FRAME, lambda: shuffle_step(i + 1))

        def start_dealing():
            self.canvas.delete("shuffle")
            status("DEALING NEXT 4")
            self.canvas.delete("hand")
            self.hand_hit = []
            self.draw_hand()
            for jidx in range(len(jobs)):
                self.root.after(jidx * stagger, lambda j=jidx: deal_one(j))

        def maybe_reveal():
            if all(landed):
                self.root.after(140, reveal_new)

        def deal_one(jidx):
            pidx, slot = jobs[jidx]
            to_x, to_y, tw, th = self.seat_card_slot(pidx, slot, n_total)
            group = "dealsouth" if pidx == 0 else "dealopp"
            tag = f"deal{jidx}"
            tags = (tag, group)

            def step(i):
                if i > deal_steps:
                    landed[jidx] = True
                    self.canvas.delete(tag)
                    self.draw_card_back(to_x, to_y, tw, th, tag=tags)
                    self.sound.play("card")
                    maybe_reveal()
                    return
                raw = i / deal_steps
                ease = ease_out_quart(raw)
                swirl = math.sin(ease * math.pi) * (12 if jidx % 2 == 0 else -12)
                x = lerp(deck_x, to_x, ease) + swirl * (1 - ease)
                y = lerp(deck_y, to_y, ease) - 58 * math.sin(math.pi * ease)
                sx = 0.88 + 0.12 * math.sin(ease * math.pi)
                self.canvas.delete(tag)
                dw = tw * sx
                self.draw_card_back(x + (tw - dw) / 2, y, dw, th, tag=tags)
                self.root.after(ANIM_FRAME, lambda: step(i + 1))

            step(0)

        def reveal_new():
            """Flip only YOUR new 4 — locked cards + opponent backs stay."""
            status("REVEALING")
            self.sound.play("bid")

            def step(i):
                if i > reveal_steps:
                    finish_extra()
                    return
                raw = i / reveal_steps
                self.canvas.delete("dealsouth")
                self.canvas.delete("reveal")
                self.canvas.delete("hand")
                self.hand_hit = []
                self.draw_hand()
                for idx, card in enumerate(new_cards):
                    to_x, to_y, _tw, _th = self.seat_card_slot(0, n_locked + idx, n_total)
                    local = min(1.0, max(0.0, (raw - idx * 0.05) / 0.75))
                    if local < 0.5:
                        sx = 1.0 - ease_in_out_cubic(local / 0.5) * 0.94
                        face = False
                    else:
                        sx = 0.06 + ease_out_back(min(1.0, (local - 0.5) / 0.5)) * 0.94
                        face = True
                    lift = 8 * math.sin(local * math.pi)
                    self.draw_card(to_x, to_y, card, playable=True, glow=face and local > 0.7,
                                   face=face, tag="reveal", scale_x=max(0.08, sx), lift=lift)
                self.root.after(ANIM_FRAME, lambda: step(i + 1))

            step(0)

        status("SHUFFLING NEXT 4")
        shuffle_step(0)

    def peek_trick_winner(self):
        g = self.game
        lead = g.current_trick[0][1].suit
        trump = g.trump_suit if g.trump_revealed else None
        bi = g.current_trick[0][0]
        bc = g.current_trick[0][1]
        for (pidx, card) in g.current_trick[1:]:
            bc, bi = g._compare_cards(bc, bi, card, pidx, lead, trump)
        return bi

    # -------------------------------------------------------------
    # 4.5) Game Flow and Turn Handling
    # -------------------------------------------------------------
    # এই অংশে বিডিং, ট্রাম্প নির্বাচন, ডাবল/রেডাবল, কার্ড খেলা,
    # trick resolution, এবং round-end scoring ধারাবাহিকভাবে নিয়ন্ত্রিত হয়।

    def process_phase(self):
        if self.in_menu:
            return
        ph = self.game.phase
        if ph == "BIDDING":
            self.process_bidding()
        elif ph == "TRUMP_SELECT":
            self.process_trump_select()
        elif ph == "PLAY":
            self.process_play()
        elif ph == "ROUND_END":
            self.process_round_end()

    def process_bidding(self):
        if self.game.bidding_complete():
            self.finish_bidding()
            return
        cur = self.game.current_player
        player = self.game.players[cur]
        if player.is_human:
            self.show_bidding_controls()
        else:
            amount = self.game.ai_bid_decision(player)
            if not self.game.can_bid(amount):
                amount = 0
            self.game.place_bid(cur, amount)
            self.sound.play("bid")
            self.refresh_all()
            self.game.current_player = (cur + 1) % 4
            self.root.after(950, self.process_bidding)

    def _action_banner(self, text, y=None):
        if y is None:
            y = self.play_center()[1]
        self.panel(self.W // 2 - 220, y - 44, self.W // 2 + 220, y - 8, r=10, tags="ui")
        self.canvas.create_text(self.W // 2, y - 26, text=text,
                                font=(FONT_UI, 13, "bold"), fill=COL_TEXT, tags="ui")

    def show_bidding_controls(self):
        self.refresh_all()
        y = self.play_center()[1]
        self._action_banner("Your bid", y)
        min_bid = max(16, self.game.bid_value + 1)
        x = self.W // 2 - 220
        for amt in range(min_bid, min(min_bid + 6, 29)):
            self.draw_button(x, y, 58, 40, str(amt), lambda a=amt: self.human_bid(a),
                             bg=COL_GOLD, fg=COL_INK, size=13)
            x += 66
        self.draw_button(x + 8, y, 88, 40, "PASS", lambda: self.human_bid(0),
                         bg="#6b2a22", fg="#f0d0c8", size=12)

    def human_bid(self, amount):
        self.game.place_bid(0, amount)
        self.sound.play("bid")
        self.game.current_player = (self.game.current_player + 1) % 4
        self.refresh_all()
        self.root.after(650, self.process_bidding)

    def finish_bidding(self):
        if self.game.highest_bidder is None:
            self.set_message("All passed. Redealing…")
            self.root.after(1500, self.redeal)
            return
        self.game.bid_winner = self.game.highest_bidder
        self.game.bid_amount = self.game.bid_value
        w = self.game.players[self.game.bid_winner]
        self.game.last_bid_label = {0: "", 1: "", 2: "", 3: ""}
        self.set_message(f"{w.name} won the bid at {self.game.bid_amount}!")
        self.game.phase = "TRUMP_SELECT"
        self.root.after(1200, self.process_trump_select)

    def redeal(self):
        self.game.start_round()
        self.message_text = "All passed — reshuffling…"
        self._hide_hand = True
        self._hide_fans = True
        self.refresh_all()
        self.animate_shuffle_deal(after=self._after_opening_deal)

    def process_trump_select(self):
        # Guard: never index players with a missing bid winner
        if self.game.bid_winner is None:
            if self.game.highest_bidder is not None:
                self.game.bid_winner = self.game.highest_bidder
                self.game.bid_amount = self.game.bid_value
            else:
                self.set_message("All passed. Redealing…")
                self.root.after(800, self.redeal)
                return
        w = self.game.players[self.game.bid_winner]
        if w.is_human:
            self.show_trump_controls()
        else:
            trump = self.game.ai_select_trump(w)
            self.game.trump_suit = trump
            self.game.trump_card = next((c for c in w.hand if c.suit == trump), None)
            self.set_message(f"{w.name} selected trump (hidden).")
            self.finalize_trump()

    def show_trump_controls(self):
        self.refresh_all()
        y = self.play_center()[1]
        self._action_banner("Select trump suit", y)
        x = self.W // 2 - 140
        for s in SUITS:
            self.draw_button(x, y, 60, 52, s, lambda su=s: self.human_select_trump(su),
                             bg=COL_IVORY, fg=SUIT_COLORS[s], size=22)
            x += 74

    def human_select_trump(self, suit):
        self.game.trump_suit = suit
        self.sound.play("bid")
        self.set_message(f"You set {SUIT_NAMES[suit]} {suit} as trump (hidden).")
        self.finalize_trump()

    def finalize_trump(self):
        human = self.game.players[0]
        # Freeze first 4 — these must NOT enter the second shuffle
        locked = list(human.hand)
        self.game.deal_remaining()
        self._locked_hand = locked
        self._incoming_cards = [c for c in human.hand if c not in locked]
        self.game.phase = "PLAY"
        self.game.current_player = self.game.bidder_start
        self.game.trick_leader = self.game.current_player
        # Hand still shows only locked 4 until start_play animates incoming
        self.refresh_all()
        self.offer_double()

    def offer_double(self):
        bt = self.game.players[self.game.bid_winner].team
        ht = self.game.players[0].team
        if ht != bt:
            self.refresh_all()
            y = self.play_center()[1]
            self._action_banner("Opponents bid — Double?", y)
            self.draw_button(self.W // 2 - 140, y + 8, 130, 40, "DOUBLE  ×2",
                             self.human_double, bg=COL_GOLD, fg=COL_INK)
            self.draw_button(self.W // 2 + 10, y + 8, 100, 40, "Pass",
                             self.skip_double, bg=COL_PANEL_HI, fg=COL_TEXT, style="ghost")
        else:
            opp = [p for p in self.game.players if p.team != bt]
            strong = any(sum(c.points for c in p.hand) >= 10 for p in opp)
            if strong and self.game.bid_amount >= 19:
                self.game.multiplier = 2
                self.game.doubled_by = opp[0].index
                self.set_message("Opponents DOUBLED! (×2)")
                self.root.after(1000, self.offer_redouble)
            else:
                self.start_play()

    def human_double(self):
        self.game.multiplier = 2
        self.sound.play("double")
        self.game.doubled_by = 0
        self.set_message("You DOUBLED! (×2)")
        self.root.after(800, self.offer_redouble)

    def skip_double(self):
        self.start_play()

    def offer_redouble(self):
        bt = self.game.players[self.game.bid_winner].team
        ht = self.game.players[0].team
        if ht == bt:
            self.refresh_all()
            y = self.play_center()[1]
            self._action_banner("You were doubled — Redouble?", y)
            self.draw_button(self.W // 2 - 150, y + 8, 150, 40, "REDOUBLE  ×4",
                             self.human_redouble, bg=COL_GOLD, fg=COL_INK)
            self.draw_button(self.W // 2 + 20, y + 8, 100, 40, "Pass",
                             self.skip_redouble, bg=COL_PANEL_HI, fg=COL_TEXT, style="ghost")
        else:
            bidder = self.game.players[self.game.bid_winner]
            if sum(c.points for c in bidder.hand) >= 14:
                self.game.multiplier = 4
                self.game.redoubled = True
                self.set_message("Bidding team REDOUBLED! (×4)")
                self.root.after(1000, self.start_play)
            else:
                self.start_play()

    def human_redouble(self):
        self.game.multiplier = 4
        self.sound.play("double")
        self.game.redoubled = True
        self.set_message("You REDOUBLED! (×4)")
        self.root.after(800, self.start_play)

    def skip_redouble(self):
        self.start_play()

    def start_play(self):
        new_cards = list(self._incoming_cards or [])
        self.message_text = "Dealing remaining 4 cards…"

        def after_deal():
            self.message_text = "Play begins — follow suit when you can"
            self._incoming_cards = []
            self._locked_hand = []
            self._hide_hand = False
            self._hide_fans = False
            self.refresh_all()
            self.process_play()

        if not new_cards:
            after_deal()
            return
        # ONLY the next 4 shuffle/deal — first 4 stay face-up as-is
        self.animate_deal_extra(new_cards, after=after_deal)

    def process_play(self):
        if self.game.tricks_count >= 8:
            self.game.phase = "ROUND_END"
            self.root.after(900, self.process_round_end)
            return
        self.refresh_all()
        cur = self.game.current_player
        player = self.game.players[cur]
        self.maybe_show_extra_buttons()
        if player.is_human:
            pass
        else:
            # Dramatic pause — “slow-roll” pacing from premium poker UIs
            self.root.after(780, lambda: self.ai_play(cur))

    def maybe_show_extra_buttons(self):
        human = self.game.players[0]
        g = self.game
        if (g.phase == "PLAY" and g.trump_revealed
                and not g.pair_claimed[human.team] and g.can_claim_pair(human)):
            self.draw_button(self.W // 2 - 160, 555, 320, 36,
                             "Claim Pair  (K + Q of Trump)  +4",
                             self.human_claim_pair, bg=COL_ACCENT, fg=COL_IVORY, size=11)

    def human_claim_pair(self):
        if self.game.claim_pair(0):
            self.set_message("Pair claimed (King + Queen of trump)! +4")
        self.refresh_all()
        self.maybe_show_extra_buttons()

    def human_reveal_trump(self):
        if not self.game.can_reveal_trump(self.game.players[0]):
            return
        self.game.trump_revealed = True
        self.set_message(f"Trump revealed: {SUIT_NAMES[self.game.trump_suit]} {self.game.trump_suit}")
        self.refresh_all()
        self.maybe_show_extra_buttons()

    def human_play(self, card):
        if self.game.current_player != 0 or self.anim_running:
            return
        if card not in self.game.valid_moves(self.game.players[0]):
            return
        # Mark in-flight BEFORE refresh so board slot stays empty
        self._flying_play = (0, card)
        self.game.play_card(0, card)
        self.sound.play("drop")
        self.hover_card = None
        self.hover_lift.clear()
        slots = self.trick_slots()
        # Capture start position from current hand layout if possible
        from_xy = (self.W // 2 - self.CARD_W // 2, 705)
        for (x1, y1, x2, y2, c, _p) in self.hand_hit:
            if c == card:
                from_xy = (x1, y1)
                break
        self.refresh_all()  # hand loses card; board does NOT show flying card yet
        self.animate_card(card, from_xy, slots[0], self.advance_after_play,
                          flip=True, pidx=0)

    def ai_play(self, pidx):
        if self.anim_running:
            self.root.after(120, lambda: self.ai_play(pidx))
            return
        player = self.game.players[pidx]
        g = self.game
        if (not g.trump_revealed and g.current_trick
                and not player.has_suit(g.current_trick[0][1].suit)):
            if player.has_suit(g.trump_suit):
                g.trump_revealed = True
                self.set_message(f"{player.name} revealed trump: {g.trump_suit}")
        if (g.trump_revealed and not g.pair_claimed[player.team]
                and g.can_claim_pair(player)):
            g.claim_pair(pidx)
        card = self.ai_choose_card(player)
        self._flying_play = (pidx, card)
        g.play_card(pidx, card)
        self.sound.play("drop")
        slots = self.trick_slots()
        seats = self.seat_xy()
        # Fly out from the middle of each opp fan
        froms = {
            1: (175, seats[1][1] - 19),
            2: (seats[2][0] - self.CARD_W // 2, 202),
            3: (self.W - 240, seats[3][1] - 19),
        }
        self.refresh_all()  # board slot empty until animation lands
        self.animate_card(card, froms[pidx], slots[pidx], self.advance_after_play,
                          flip=True, pidx=pidx)

    def ai_choose_card(self, player):
        g = self.game
        valid = g.valid_moves(player)
        trump = g.trump_suit if g.trump_revealed else None
        if not g.current_trick:
            nt = [c for c in valid if c.suit != trump]
            pool = nt if nt else valid
            return max(pool, key=lambda c: c.points * 2 + RANK_ORDER[c.rank])
        lead = g.current_trick[0][1].suit
        bc = g.current_trick[0][1]
        bi = g.current_trick[0][0]
        for (pi, c) in g.current_trick[1:]:
            bc, bi = g._compare_cards(bc, bi, c, pi, lead, trump)
        partner = (g.players[bi].team == player.team)
        if partner:
            return min(valid, key=lambda c: RANK_ORDER[c.rank])
        winners = []
        for c in valid:
            _, ti = g._compare_cards(bc, bi, c, player.index, lead, trump)
            if ti == player.index:
                winners.append(c)
        if winners:
            return min(winners, key=lambda c: RANK_ORDER[c.rank])
        return min(valid, key=lambda c: c.points * 2 + RANK_ORDER[c.rank])

    def advance_after_play(self):
        self.canvas.delete("anim")
        self._flying_play = None  # land: now paint card on the board
        self.refresh_all()
        if len(self.game.current_trick) == 4:
            # Brief beat so players can read the table, then collect
            self.root.after(700, self.finish_trick)
        else:
            self.game.current_player = (self.game.current_player + 1) % 4
            self.root.after(420, self.process_play)

    def finish_trick(self):
        trick = list(self.game.current_trick)
        winner = self.peek_trick_winner()

        def after_collect():
            self.game.resolve_trick()
            wname = self.game.players[winner].name
            self.set_message(
                f"{wname} wins the trick —  You {self.game.tricks_won_points[0]}  ·  "
                f"Opp {self.game.tricks_won_points[1]}")
            self.refresh_all()
            # Win flash on winner seat
            self._flash_winner(winner)
            self.root.after(900, self.process_play)

        self.animate_trick_collect(trick, winner, after_collect)

    def _flash_winner(self, winner):
        sx, sy = self.seat_xy()[winner]
        steps = 12

        def step(i):
            self.canvas.delete("winflash")
            if i > steps:
                return
            t = i / steps
            rad = 30 + 18 * (1 - t)
            col = COL_WIN if winner % 2 == 0 else COL_GOLD_SOFT
            self.canvas.create_oval(sx - rad, sy - rad, sx + rad, sy + rad,
                                    outline=col, width=3, tags="winflash")
            self.root.after(ANIM_FRAME + 4, lambda: step(i + 1))

        step(0)

    def process_round_end(self):
        self.game.trump_revealed = True
        result = self.game.score_round()
        self.refresh_all()
        bidder = self.game.players[self.game.bid_winner].name
        made = result['made']
        msg = (f"Round Over!\n\nBid: {result['bid_amount']} by {bidder}\n"
               f"Bidder team scored: {result['bidder_points']} points\n"
               f"Multiplier: ×{result['multiplier']}\n\n")
        if made:
            msg += f"Bid MADE — Team {result['winner_team']} +{result['multiplier']} (Black→Red)"
        else:
            msg += f"Bid FAILED — Team {result['winner_team']} +{result['multiplier']} (Black→Red)"

        if self.game.game_scores[0] >= 6 or self.game.game_scores[1] >= 6:
            champ = "YOUR TEAM" if self.game.game_scores[0] >= 6 else "OPPONENTS"
            messagebox.showinfo("Game Over", msg + f"\n\n{champ} WINS THE GAME")
            self.show_menu()
        else:
            messagebox.showinfo("Round Result", msg)
            self.game.start_round()
            self.refresh_all()
            self.process_phase()


# =============================================================
# 5) Application Entry Point
# =============================================================
# এই অংশে Tkinter window open করে GUI চালু হয়।

if __name__ == '__main__':
    if GUI_AVAILABLE:
        root = tk.Tk()
        app = Game29GUI(root)
        root.mainloop()
    else:
        print("Tkinter not available — install python3-tk for GUI.")
