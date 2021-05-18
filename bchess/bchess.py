#!/usr/bin/env python3

import os
os.environ.setdefault("ESCDELAY", "25")

import chess
import chess.pgn
import curses
import datetime
import json
import os.path
import random
import re
import sys
import time

# All of the following should be relative imports, but in Python 3
# the "main module" if forbidden from using them, so if one
# wants to import this file (as we do in the appimage) instead
# of running it directly, PYTHONPATH must be set so that all of
# these files are in it, and come first.

from . import engine
from . import imui
from . import ecodb
from . import book

### Configuration

progdir = os.path.dirname(__file__)
config_kwargs = {
    "bin": os.path.join(progdir, "data"),
    "data": os.path.join(progdir, "data"),
    "date": datetime.date.today().strftime("%Y-%m-%d")
}

def config_subs(value):
    """Recursively substitute {variables} in a config dict."""
    if isinstance(value, list):
        return [config_subs(x) for x in value]
    elif isinstance(value, dict):
        return {k:config_subs(v) for k,v in value.items()}
    elif isinstance(value, str):
        return value.format_map(config_kwargs)
    elif isinstance(value, int):
        return value
    else:
        raise ValueError(f"Can't substitute variables in {value!r}")

def dict_overlay(dst, src):
    """
    Recursively apply the source dict on top of the destination
    dict: merge dictionaries, overwrite non-dictionary values.
    """
    for key, value in src.items():
        if isinstance(value, dict):
            oldvalue = dst.get(key, None)
            if isinstance(oldvalue, dict):
                dict_overlay(oldvalue, value)
            else:
                dst[key] = value
        else:
            dst[key] = value

def load_config(*filenames):
    """
    Load configuration dict from several files, return overlayed
    result.
    """
    conf = {}
    for fn in filenames:
        try:
            with open(fn, "r") as f:
                o = json.load(f)
            dict_overlay(conf, o)
        except OSError:
            pass
    return conf

### MISC UI

def FormatText(text, attr=0):
    maxw = im.text_width
    for i, para in enumerate(text.split("\n")):
        if i > 0:
            im.VSpace(1)
        line = []
        linew = 0
        for word in para.split():
            if linew + 1 + len(word) > maxw:
                im.Text(" ".join(line), attr=attr)
                line = [word]
                linew = len(word)
            else:
                line.append(word)
                linew += 1 + len(word)
        if line:
            im.Text(" ".join(line), attr=attr)

UI_RENDERER = None
def set_scene(renderer):
    assert callable(renderer)
    global UI_RENDERER
    UI_RENDERER = renderer
    im.want_refresh = True

### CHESS UI

rx_move = re.compile("^([QKNRBqknrb])?(?:([a-h])([1-8])?)?([x:])?(?:([a-h])([1-8])?)?=?([QNRBqnrb])?[#+]?$")
def highlight_san_move(text, board=None):
    """
    Parse a move in SAN (or UCI) notation, and return a set of
    highlighted squares the move might be affecting.
    """
    # [QKNRB]?[a-h]?[1-8]?x?[a-h][1-8]=?[QNRB]
    def squareset(pc, f1, r1, x, f2, r2):
        hi1 = ~chess.SquareSet() if pc or f1 or r1 else chess.SquareSet()
        if pc is not None: hi1 &= board.pieces(chess.Piece.from_symbol(pc).piece_type, board.turn) 
        if x and not pc: hi1 &= board.pieces(chess.PAWN, board.turn)
        if f1 is not None: hi1 &= chess.BB_FILES[ord(f1) - ord("a")]
        if r1 is not None: hi1 &= chess.BB_RANKS[ord(r1) - ord("1")]
        hi2 = ~chess.SquareSet() if f2 or r2 else chess.SquareSet()
        if f2 is not None: hi2 &= chess.BB_FILES[ord(f2) - ord("a")]
        if r2 is not None: hi2 &= chess.BB_RANKS[ord(r2) - ord("1")]
        return hi1 | hi2
    match = rx_move.match(text)
    if not match: return chess.SquareSet()
    pc, f1, r1, x, f2, r2, pr = match.groups()
    ss = squareset(pc, f1, r1, x, f2, r2)
    if not x and not f2 and not r2: ss |= squareset(pc, None, None, None, f1, r1)
    return ss

piece_starting_count = [None, 8, 2, 2, 2, 1, 1]
piece_material = [None, 1, 3, 3, 5, 9, 100]

def ChessBoard(self, board, hi_squares, mv_squares, flip=False, evalbar=None, pv=()):
    white = ""
    black = ""
    material = 0
    marks = {}
    for i, uci in reversed(list(enumerate(pv[:3]))):
        marks[ord(uci[0]) - ord("a"), ord(uci[1]) - ord("1")] = chr(ord("1") + i)
        marks[ord(uci[2]) - ord("a"), ord(uci[3]) - ord("1")] = chr(ord("1") + i)
    for p in reversed(chess.PIECE_TYPES):
        n = len(board.pieces(p, True)) - len(board.pieces(p, False))
        material += piece_material[p] * n
        for i in range(n): white += self.piece_symbols[p]
        for i in range(-n): black += self.piece_symbols[p]
    if material > 0: white = f"{white} +{material}"
    if material < 0: black = f"+{-material} {black}"
    with im.Table(2, (1,1), (1,1), 2):
        whitename = self.aispec[1]["name"] if self.aispec[1] else self.user_name
        blackname = self.aispec[0]["name"] if self.aispec[0] else self.user_name
        with im.Row():
            with im.Cell(): pass
            with im.Cell(): im.Text(whitename, attr=self.attr_title)
            with im.Cell(): im.Text(blackname, attr=self.attr_title, align=2)
            with im.Cell(): pass
    with im.Table(2, (1,1), (1,1), 2):
        with im.Row():
            with im.Cell(): pass
            with im.Cell(): im.Text(white, attr=self.attr_subtitle)
            with im.Cell(): im.Text(black, attr=self.attr_subtitle, align=2)
            with im.Cell(): pass
    if evalbar:
        win, loss = evalbar
        bar_white = min(max(int(8*3*win), 1), 8*3 - 1)
        bar_black = 8*3 - min(max(int(8*3*loss), 1), 8*3 - 1)
    with im.Table(2,6,6,6,6,6,6,6,6,2):
        # Top frame
        with im.Row():
            with im.Cell(): im.Text("  ", attr=self.attr_border)
            for file in range(7, -1, -1) if flip else range(8):
                with im.Cell():
                    name = ord("a") + file
                    im.Text(f"   {name:c}  " if flip else "      ", attr=self.attr_border)
            with im.Cell(): im.Text("  ", attr=self.attr_border)
        # The board
        for rank in range(8) if flip else range(7, -1, -1):
            with im.Row():
                # Left frame
                with im.Cell():
                    if flip:
                        if evalbar:
                            aw = 3*rank + 0 < bar_white
                            al = 3*rank + 0 >= bar_black
                            bw = 3*rank + 1 < bar_white
                            bl = 3*rank + 1 >= bar_black
                            cw = 3*rank + 2 < bar_white
                            cl = 3*rank + 2 >= bar_black
                            a = self.attr_eval_w if aw else self.attr_eval_l if al else self.attr_eval_w
                            b = self.attr_eval_w if bw else self.attr_eval_l if bl else self.attr_eval_w
                            c = self.attr_eval_w if cw else self.attr_eval_l if cl else self.attr_eval_w
                            im.Text("█ " if aw or al else "░ ", attr=a)
                            im.Text("█ " if bw or bl else "░ ", attr=b)
                            im.Text("█ " if cw or cl else "░ ", attr=c)
                    else:
                        name = ord("1") + rank
                        im.Text("  ", attr=self.attr_border)
                        im.Text(f" {name:c}", attr=self.attr_border)
                        im.Text("  ", attr=self.attr_border)
                # Pieces
                for file in range(7, -1, -1) if flip else range(8):
                    white = (rank ^ file) & 1
                    with im.Cell():
                        if self.ai[self.board.turn] is None and \
                                not self.board.is_game_over(claim_draw=self.draw) and \
                                im.MouseClick(im.curx, im.cury, 6, 3):
                            square = chr(ord("a") + file) + chr(ord("1") + rank)
                            self.move = \
                                    self.move[:-2] if self.move.endswith(square) else \
                                    self.move + square + "\n"
                            self.try_user_move()
                            im.want_refresh = True
                        hi = chess.square(file, rank) in hi_squares
                        mv = chess.square(file, rank) in mv_squares
                        p = self.board.piece_at(chess.square(file, rank))
                        attr = (self.attr_hi_piece if hi else \
                                self.attr_mv_piece if mv else \
                                self.attr_piece)[white + 2*(p.color if p else white)]
                        for i, line in enumerate(self.piece_art[p.piece_type if p else 0]):
                            if i == 2 and (file,rank) in marks:
                                im.Text(marks[file,rank] + line[1:], attr=attr)
                            else:
                                im.Text(line, attr=attr)
                # Right frame
                with im.Cell():
                    if flip:
                        name = ord("1") + rank
                        im.Text("  ", attr=self.attr_border)
                        im.Text(f"{name:c} ", attr=self.attr_border)
                        im.Text("  ", attr=self.attr_border)
                    else:
                        if evalbar:
                            aw = 3*rank + 0 < bar_white
                            al = 3*rank + 0 >= bar_black
                            bw = 3*rank + 1 < bar_white
                            bl = 3*rank + 1 >= bar_black
                            cw = 3*rank + 2 < bar_white
                            cl = 3*rank + 2 >= bar_black
                            a = self.attr_eval_w if aw else self.attr_eval_l if al else self.attr_eval_w
                            b = self.attr_eval_w if bw else self.attr_eval_l if bl else self.attr_eval_w
                            c = self.attr_eval_w if cw else self.attr_eval_l if cl else self.attr_eval_w
                            im.Text(" █" if cw or cl else " ░", attr=c)
                            im.Text(" █" if bw or bl else " ░", attr=b)
                            im.Text(" █" if aw or al else " ░", attr=a)
        # Bottom frame
        with im.Row():
            with im.Cell(): im.Text("  ", attr=self.attr_border)
            for file in range(7, -1, -1) if flip else range(8):
                with im.Cell():
                    name = ord("a") + file
                    im.Text("      " if flip else f"  {name:c}   ", attr=self.attr_border)
            with im.Cell(): im.Text("  ", attr=self.attr_border)

class UI0:
    def __init__(self, config):
        self.config = config
        art = config["piece_art"]
        self.piece_art = [[art[0][i:i+6], art[1][i:i+6], art[2][i:i+6]] for i in range(0,8*6,6)]
        self.attr_piece = [
            # piece w/b -- square l/d
            config["style"]["square_wl"],  # 0b00
            config["style"]["square_wd"],  # 0b01
            config["style"]["square_bl"],  # 0b10
            config["style"]["square_bd"]   # 0b11
        ]
        self.attr_hi_piece = [
            config["style"]["square_hi_wl"], # 0b00
            config["style"]["square_hi_wd"], # 0b01
            config["style"]["square_hi_bl"], # 0b10
            config["style"]["square_hi_bd"]  # 0b11
        ]
        self.title = "??"
        self.ai_index = imui.Ref(0)
        self.color_index = imui.Ref(1)
        self.ailist = list(config["ai"].values())

    def render(self):
        with im.Center(width=60, height=10 + len(self.ailist) + len(self.config["rating_classes"])):
            im.Text("┳┓ ╭─┐┐           ")
            im.Text("┃┃ │  │  ╭─╮╭─┐╭─┐")
            im.Text("┣┻┓│  ├─╮├─╯╰─╮╰─╮")
            im.Text("┻━┛╰─╴┴ ┴╰─╴└─╯└─╯")
            im.VSpace(1)
            allais = []
            with im.TableRow(40, 14):
                with im.Cell():
                    im.Text("Play against:", attr=curses.A_BOLD)
                    with im.ListView(index=self.ai_index, id="lv-ai"):
                        for name, rat in self.config["rating_classes"].items():
                            ailist = [ai for ai in self.ailist if rat["min"] <= ai["rating"] < rat["max"]]
                            ailist.sort(key=lambda ai: ai["rating"])
                            allais.extend(ailist)
                            im.Text(f"== {name} ==")
                            #for i, ai in enumerate(self.ailist):
                            for i, ai in enumerate(ailist):
                                letter = chr(ord("1") + i if i < 9 else ord("a") + i - 9)
                                #if im.ListItem(f"{letter}) {ai['name']}", key=letter):
                                if im.ListItem(f"{letter}) {ai['name']}"):
                                    self.title = ai
                with im.Cell():
                    im.Text("Play as:", attr=curses.A_BOLD)
                    with im.TableRow(7,(1,1)):
                        with im.Cell():
                            attr = self.attr_piece[3 if self.color_index() == 2 else 1]
                            if im.Button("\n".join(self.piece_art[6 if self.color_index() != 1 else 7]), attr=attr):
                                self.color_index((self.color_index() + 1) % 3)
                                im.want_refresh = True
                        with im.Cell():
                            with im.ListView(index=self.color_index, id="lv-col"):
                                im.ListItem(f"Black", key="B")
                                im.ListItem(f"Random", key="R")
                                im.ListItem(f"White", key="W")
                    im.VSpace(1)
                    if im.Button("Start", key="\n", id="b-go", attr=curses.A_BOLD) or im.Key("\n"):
                        usercolor = \
                            False if self.color_index() == 0 else \
                            True if self.color_index() == 2 else \
                            random.choice((True,False))
                        if usercolor:
                            set_scene(UI(None, allais[self.ai_index()], self.config).render)
                        else:
                            set_scene(UI(allais[self.ai_index()], None, self.config).render)
            im.VSpace(1)
            aispec = allais[self.ai_index()]
            im.Text(f"{aispec['name']}", attr=curses.A_BOLD)
            FormatText(aispec.get("description", ""))

class UI:
    def __init__(self, white_ai, black_ai, config):
        self.attr_piece = [
            # piece w/b -- square l/d
            config["style"]["square_wl"], # 0b00
            config["style"]["square_wd"], # 0b01
            config["style"]["square_bl"], # 0b10
            config["style"]["square_bd"]  # 0b11
        ]
        self.attr_hi_piece = [
            config["style"]["square_hi_wl"], # 0b00
            config["style"]["square_hi_wd"], # 0b01
            config["style"]["square_hi_bl"], # 0b10
            config["style"]["square_hi_bd"]  # 0b11
        ]
        self.attr_mv_piece = [
            config["style"]["square_mv_wl"], # 0b00
            config["style"]["square_mv_wd"], # 0b01
            config["style"]["square_mv_bl"], # 0b10
            config["style"]["square_mv_bd"]  # 0b11
        ]
        self.attr_title = config["style"]["title"]
        self.attr_subtitle = config["style"]["subtitle"]
        self.attr_border = config["style"]["border"]
        self.attr_input = config["style"]["input"]
        self.attr_eval_w = config["style"]["eval_win"]
        self.attr_eval_d = config["style"]["eval_draw"]
        self.attr_eval_l = config["style"]["eval_loss"]
        art = config["piece_art"]
        self.piece_art = [[art[0][i:i+6], art[1][i:i+6], art[2][i:i+6]] for i in range(0,7*6,6)]
        self.piece_symbols = [None] + config["piece_symbols"]
        self.flip = False if white_ai is None else True
        self.help = False
        self.pgn_filename = config["pgn_filename"]
        self.user_name = os.environ.get("USER", "user")
        self.board = chess.Board()
        self.eval = {}
        self.aispec = (black_ai, white_ai)
        self.book = (
            book.of_spec(black_ai.get("book", None)) if black_ai else None,
            book.of_spec(white_ai.get("book", None)) if white_ai else None
        )
        self.ai = (engine.of_spec(black_ai) if black_ai else None, engine.of_spec(white_ai) if white_ai else None)
        self.eval_ai = engine.of_spec(config["eval_ai"])
        self.move = ""
        self.draw = False
        self.pgn_root = chess.pgn.Game()
        self.pgn = self.pgn_root
        self.prepare_ai_move()

    def save_pgn(self, filename):
        game = chess.pgn.Game()
        game.headers["White"] = self.aispec[1]["name"] if self.aispec[1] else self.user_name
        game.headers["Black"] = self.aispec[0]["name"] if self.aispec[0] else self.user_name
        game.headers["Date"] = datetime.date.today().strftime("%Y.%m.%d")
        game.headers["Event"] = "??"
        game.headers["Site"] = "??"
        game.headers["Round"] = "1"
        game.headers["Result"] = self.board.result(claim_draw=self.draw)
        if self.eval_ai:
            game.headers["Annotator"] = self.eval_ai.id.get("name", self.eval_ai.exepath)
        node = game
        board = chess.Board()
        opening = ""
        for move in self.board.move_stack:
            node = node.add_main_variation(move)
            board.push(move)
            ev = self.eval.get(board.fen(), None)
            if ev:
                ev = max(ev.items(), key=lambda kv: kv[0])[1]
                node.comment = f"[%eval {engine.score_eval(ev.score, ev.depth)}]"
            opening = ecodb.db.get(board.epd(), opening)
        eco, opening, variation = opening.split(":", 2)
        if eco: game.headers["ECO"] = eco
        if opening: game.headers["Opening"] = opening
        if variation: game.headers["Variation"] = variation
        with open(filename, "w") as f:
            f.write(str(game))
            f.write("\n\n\n")

    def apply_move(self, move):
        if move == "draw":
            if not self.board.can_claim_draw():
                raise ValueError("No basis to claim draw now.")
            self.draw = True
        elif move == "undo":
            if len(self.board.move_stack) < 2:
                raise ValueError("Undo what?")
            self.board.pop()
            self.board.pop()
        elif move == "flip":
            self.flip = not self.flip
        elif move in ("quit", "exit", "resign"):
            exit(0)
        elif move in "help":
            self.help = not self.help
        else:
            try:
                self.board.push_uci(move)
            except:
                self.board.push_san(move)
        if self.board.move_stack:
            self.save_pgn("/tmp/bchess.pgn")
        if not self.board.is_game_over(claim_draw=self.draw):
            if self.eval_ai:
                self.eval_ai.analyze(self.board, self.eval_ai_update, self.board.fen())
            self.prepare_ai_move()
        im.want_refresh = True

    def prepare_ai_move(self):
        ai = self.ai[self.board.turn]
        if ai:
            book = self.book[self.board.turn]
            bookmove = book(self.board) if book else None
            if bookmove:
                self.ai_update(bookmove)
            else:
                ai.play(self.board, self.ai_update)

    def try_user_move(self):
        if "\n" not in self.move: return
        # Extra logic for multi-line pasted moves.
        thismove, nextmove = self.move.split("\n", 1)
        try:
            self.apply_move(thismove)
            self.move = nextmove
            im.want_refresh = True
        except ValueError as e:
            self.move = thismove
            pass

    def render(self):
        hi_squares = highlight_san_move(self.move, self.board)
        mv_squares = chess.SquareSet()
        if self.board.move_stack:
            m = self.board.move_stack[-1]
            mv_squares.add(m.from_square)
            mv_squares.add(m.to_square)
        if self.board.is_check():
            mv_squares.add(self.board.king(self.board.turn))
        with im.Center(width=52, height=26+3-1):
            ev = self.eval.get(self.board.fen(), None)
            if self.help and ev:
                evalbar = [engine.score_winpercent(e.score) for d, e in sorted(ev.items())]
                evalbar = [min(evalbar[-4:]), 1-max(evalbar[-4:])]
                ev = max(ev.items(), key=lambda kv: kv[0])[1]
                ChessBoard(self, self.board, hi_squares, mv_squares, evalbar=evalbar, pv=ev.pv, flip=self.flip)
            else:
                ChessBoard(self, self.board, hi_squares, mv_squares, flip=self.flip)
            if self.board.is_game_over(claim_draw=self.draw):
                im.Text(self.board.result(claim_draw=self.draw), attr=self.attr_input, align=1)
            else:
                # Move input field
                if self.ai[self.board.turn] is None:
                    if self.board.can_claim_fifty_moves():
                        im.Text("You can now claim draw by the fifty-move rule.", align=1)
                    if self.board.can_claim_threefold_repetition():
                        im.Text("You can now claim draw by threefold repetition.", align=1)
                    im.VSpace(1)
                    prefix = f"Move {self.board.fullmove_number}. " if self.board.turn else \
                             f"Move {self.board.fullmove_number}... "
                    self.move, chg = im.Input(self.move, prefix=prefix, attr=self.attr_input, align=1)
                    if chg: im.want_refresh = True
                    if "\n" in self.move:
                        self.try_user_move()
                else:
                    im.VSpace(1)

    def ai_update(self, move):
        # The update here must be delayed because:
        # 1) ai_update might get called from an AI thread;
        # 2) ai_update might get called from apply_move itself.
        im.run_soon(lambda: self.apply_move(move))

    def eval_ai_update(self, result, fen):
        if isinstance(result, engine.Evaluation):
            if result.depth >= 2:
                self.eval.setdefault(fen, {})
                self.eval[fen][result.depth] = result
                im.want_refresh = True

### MAIN

def config_implement_colors(conf):
    colors = {(-1, -1): 0}
    colorn = 1
    for a in conf.values():
        fg = a.get("fg", -1)
        bg = a.get("bg", -1)
        if (fg, bg) in colors: continue
        curses.init_pair(colorn, fg, bg)
        colors[fg, bg] = curses.color_pair(colorn)
        colorn += 1
    result = {}
    for key, a in list(conf.items()):
        attr = colors[a.get("fg", -1), a.get("bg", -1)]
        attrstr = a.get("attr", "")
        if "a" in attrstr: attr |= curses.A_ALTCHARSET
        if "B" in attrstr: attr |= curses.A_BLINK
        if "b" in attrstr: attr |= curses.A_BOLD
        if "d" in attrstr: attr |= curses.A_DIM
        if "I" in attrstr: attr |= curses.A_INVIS
        if "r" in attrstr: attr |= curses.A_REVERSE
        if "s" in attrstr: attr |= curses.A_STANDOUT
        if "u" in attrstr: attr |= curses.A_UNDERLINE
        result[key] = attr
    return result

def curses_main(win):
    config = config_subs(load_config(
        config_subs("{data}/bchess.conf"),
        os.path.expanduser("~/.config/bchess.conf"),
        os.path.expanduser("~/.bchess.conf")))
    curses.curs_set(False)
    curses.start_color()
    curses.use_default_colors()
    config["style"] = config_implement_colors(config["style"])
    set_scene(UI0(config).render)
    curses.cbreak()
    curses.mousemask(-1)
    curses.mouseinterval(0)
    while True:
        with im.Frame(win):
            UI_RENDERER()
            if im.Key("q"):
                break
        while not (im.want_refresh or im.gather_input(win)):
            pass

def main():
    global im
    im = imui.IM()
    book.default = book.BookDB(config_subs("{data}/openings.sqlite"))
    try:
        curses.wrapper(curses_main)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
