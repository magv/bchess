import math
import subprocess
import threading
import random

from collections import namedtuple

Evaluation = namedtuple("Evaluation", "score wdl depth nodes multipv pv")

Score_CentiPawn = namedtuple("CentiPawn", "value")
Score_Mate = namedtuple("Mate", "moves")
Score_CentiPawn.invert = lambda score: Score_CentiPawn(-score.value)
Score_Mate.invert = lambda score: Score_Mate(-score.moves)
Score_CentiPawn.__sub__ = lambda s1, s2: s1.value-s2.value
Score_Mate.__sub__ = lambda m1, m2: m1.moves-m2.moves

Request_Analyze = namedtuple("Analyze", "position white limit callback callback_args")
Request_Quit = namedtuple("Quit", "")

BestMove = namedtuple("BestMove", "uci")

def score_eval(score, depth=None):
    if isinstance(score, Score_CentiPawn):
        return f"{score.value/100:.2f}/{depth}" if depth is not None else f"{score.value/100:.2f}"
    elif isinstance(score, Score_Mate):
        return f"#{score.moves}/{depth}" if depth is not None else f"{score.moves}"
    else:
        raise ValueError("Not a valid score: {score}")

def score_winpercent(score):
    if isinstance(score, Score_CentiPawn):
        return 1/(1 + 10**(-score.value/400))
    elif isinstance(score, Score_Mate):
        return math.copysign(1.0, score.moves)
    else:
        raise ValueError(f"Not a valid score: {score}")

def uci_value_fmt(value):
    return ("true" if value else "false") if isinstance(value, bool) else str(value)

class Engine:
    def __init__(self, exepath, options={}, maxdepth=None, maxtime=None, maxnodes=None):
        self.maxdepth = maxdepth
        self.maxtime = maxtime
        self.maxnodes = maxnodes
        self.exepath = exepath
        self.ucioptions = options
        self.quit_requested = False
        self.request = None
        self.sent_requests = []
        self.writer_cond = threading.Condition()
        self.writer_thread = threading.Thread(target=self._writer, name="an-writer", daemon=True)
        self.reader_thread = threading.Thread(target=self._reader, name="an-reader", daemon=True)
        self.id = {}
        self.process = subprocess.Popen(
                exepath,
                encoding="utf-8",
                universal_newlines=True,
                bufsize=1,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL)
        self.writer_thread.start()
        self.reader_thread.start()

    def quit(self):
        with self.writer_cond:
            self.request = Request_Quit()
            self.writer_cond.notify()
        self.process.kill()
        self.writer_thread.join()
        self.reader_thread.join()

    def __del__(self):
        self.quit()

    def analyze(self, board, callback, *args):
        position = "startpos moves " + " ".join(move.uci() for move in board.move_stack)
        limit = f"nodes {self.maxnodes}" if self.maxnodes is not None else \
                f"movetime {int(self.maxtime*1000)}" if self.maxtime is not None else \
                f"depth {self.maxdepth}" if self.maxdepth is not None else \
                f"infinite"
        with self.writer_cond:
            self.request = Request_Analyze(position, board.turn, limit, callback, args)
            self.writer_cond.notify()

    def play(self, board, callback, *args):
        self.analyze(board, self._play_callback, callback, *args)

    def _play_callback(self, result, callback, *args):
        if isinstance(result, BestMove):
            callback(result.uci, *args)

    def _writer(self):
        f = self.process.stdin
        f.write("uci\n")
        for k, v in self.ucioptions.items():
            f.write(f"setoption name {k} value {uci_value_fmt(v)}\n")
        f.write("isready\n")
        while True:
            with self.writer_cond:
                while self.request is None:
                    self.writer_cond.wait()
                req = self.request
                self.request = None
                self.sent_requests.append(req)
            if isinstance(req, Request_Quit):
                f.close()
                #f.write("stop\nisready\nquit\n")
                break
            if isinstance(req, Request_Analyze):
                f.write(f"stop\nposition {req.position}\ngo {req.limit}\n")

    def _reader(self):
        for line in self.process.stdout:
            if isinstance(self.request, Request_Quit):
                break
            words = line.split()
            if len(words) == 0:
                continue
            elif words[0] == "info":
                try:
                    i = words.index("score") + 1
                    if words[i] == "cp":
                        score = Score_CentiPawn(int(words[i + 1]))
                    elif words[i] == "mate":
                        score = Score_Mate(int(words[i + 1]))
                    else:
                        raise ValueError
                    depth = int(words[words.index("depth") + 1])
                    nodes = int(words[words.index("nodes") + 1])
                    pv = words[words.index("pv") + 1:]
                    try:
                        multipv = int(words[words.index("multipv") + 1])
                    except ValueError:
                        multipv = 1
                    req = self.sent_requests[0]
                    try:
                        i = words.index("wdl")
                        if req.white:
                            wdl = (int(words[i + 1]), int(words[i + 2]), int(words[i + 3]))
                        else:
                            wdl = (int(words[i + 3]), int(words[i + 2]), int(words[i + 1]))
                    except ValueError:
                        wdl = None
                    req.callback(Evaluation(
                            score if req.white else score.invert(),
                            wdl, depth, nodes, multipv, pv),
                        *req.callback_args)
                except ValueError as e:
                    # No "score", "depth", or "nodes".
                    pass
            elif words[0] == "bestmove":
                req = self.sent_requests[0]
                req.callback(BestMove(words[1]), *req.callback_args)
                # Mutation of self.sent_requests is not guarded
                # by a lock here because Python threads are not
                # real.
                self.sent_requests.pop(0)
            elif words[0] == "readyok":
                pass
            elif words[0] == "id":
                self.id[words[1]] = " ".join(words[2:])
            if isinstance(self.request, Request_Quit):
                break

class LossyEngine:
    def __init__(self, engine, maxloss=90):
        self.engine = engine
        self.maxloss = maxloss
        self.multipv = {}

    def play(self, board, callback, *args):
        self.engine.analyze(board, self._engine_callback, board.fen(), board.turn, callback, *args)

    def quit(self):
        self.engine.quit()

    def _engine_callback(self, x, fen, turn, callback, *args):
        if isinstance(x, BestMove):
            #print(f"LossyEngine: choosing from {self.multipv.values()}")
            moves = [move
                for score, move in self.multipv.values()
                if isinstance(score, Score_Mate) and score.moves >= 0]
            if moves:
                move = random.choice(moves)
                #print(f"LossyEngine: {moves} => {move}")
                self.multipv.clear()
                callback(move, *args)
                return
            moves = [(score.value, move)
                for score, move in self.multipv.values()
                if isinstance(score, Score_CentiPawn)]
            if moves:
                bestv = max(scorev for scorev, move in moves)
                moves = [move
                    for scorev, move in moves
                    if scorev >= bestv - self.maxloss]
                move = random.choice(moves)
                #print(f"LossyEngine: {moves} => {move}")
                self.multipv.clear()
                callback(move, *args)
                return
            #print(f"LossyEngine: => {x.uci}")
            self.multipv.clear()
            callback(x.uci, *args)
        elif isinstance(x, Evaluation):
            #print(f"Eval[{fen}, {turn}] = {x}")
            move = x.pv[0]
            self.multipv[x.multipv] = (x.score if turn else x.score.invert(), move)

def of_spec(spec):
    eng = Engine(exepath=spec["bin"],
            options=spec["options"],
            maxnodes=spec["limit"].get("maxnodes", None),
            maxdepth=spec["limit"].get("maxdepth", None),
            maxtime=spec["limit"].get("maxtime", None))
    if "maxloss" in spec:
        eng = LossyEngine(eng, spec["maxloss"])
    return eng
