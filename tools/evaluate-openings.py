import sqlite3
import collections
import subprocess
import time
import chess

MAXDEPTH = 36
THREADS = 16
ENGINE = ["./bchess/data/stockfish"]
OPTIONS = {
    "UCI_AnalyseMode": "true",
    "Threads": str(THREADS),
    "Hash": "4096",
    "EvalFile": "bchess/data/default.nnue"
}

ENG = subprocess.Popen(ENGINE,
                encoding="utf-8",
                universal_newlines=True,
                bufsize=1,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL)
ENG.stdin.write("uci\n")
for line in ENG.stdout:
    #print(">", line)
    if line.strip() == "uciok": break
ENG.stdin.write("".join([
    f"setoption name {name} value {value}\n"
    for name, value in OPTIONS.items()
]))

def analyze_position(fen, flip):
    depth2eval = {}
    if 1:
        ENG.stdin.write("".join([
            f"position fen {fen}\n",
            f"go depth {MAXDEPTH}\n"
        ]))
        for line in ENG.stdout:
            #print(">", line.strip())
            if line.startswith("bestmove"):
                break
            words = line.split()
            if words[0] == "info":
                try:
                    depth = int(words[words.index("depth") + 1])
                    pv = words[words.index("pv") + 1:]
                    i = words.index("score") + 1
                    if words[i] == "cp":
                        score = int(words[i + 1])
                        score = str(score) if not flip else str(-score)
                        depth2eval[depth] = ("cp " + score, " ".join(pv))
                    elif words[i] == "mate":
                        score = int(words[i + 1])
                        score = str(score) if not flip else str(-score)
                        depth2eval[depth] = ("mate " + score, " ".join(pv))
                    else:
                        raise ValueError
                except ValueError as e:
                    # No "score", "depth", or "nodes".
                    pass
    return [(depth, score, pv) for depth, (score, pv) in depth2eval.items()]

db = sqlite3.connect(f"file:bchess/data/openings.sqlite?immutable=1", uri=True, check_same_thread=False)

print("* Sorting positions")
boardid2nmoves = collections.defaultdict(lambda: 0)
for boardid, movestring in db.execute("select boardid, moves from moves"):
    boardid2nmoves[boardid] += sum(int(mc.split(":")[1]) for mc in movestring.split())
print(f"Total positions: {len(boardid2nmoves)}")
print(f"Total moves: {sum(boardid2nmoves.values())}")

boardid2epd = {}
epd2boardid = {}
for boardid, epd in db.execute("select id, epd from boards"):
    boardid2epd[boardid] = epd
    epd2boardid[epd] = boardid

done = set()
nsum = 0
for boardid, in db.execute("select distinct boardid from evaluations"):
    done.add(boardid)
    nsum += boardid2nmoves[boardid]
print(f"Already done: {len(done)} of {len(boardid2nmoves)} boards")

db.close()

todo = sorted(boardid2nmoves.keys(), key=lambda bid: -boardid2nmoves[bid])
print(f"Highest move count: {boardid2nmoves[todo[0]]}")
print(f"Lowest move count: {boardid2nmoves[todo[-1]]}")
nmoves_total = sum(boardid2nmoves.values())
with open("new.evaluations.sql", "w", buffering=1) as f:
    f.write("""\
PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE evaluations(boardid integer, depth integer, score text, pv text, foreign key(boardid) references boards(id));
""")
    try:
        while True:
            bid = todo.pop(0)
            epd = boardid2epd[bid]
            if bid in done: continue
            done.add(bid)
            nsum += boardid2nmoves[bid]
            percentile = nsum/nmoves_total
            print(f"* Board #{len(done)}, id {bid} ({nsum/nmoves_total*100:.0f}% of moves so far)")
            board = chess.Board(epd)
            print(board.unicode())
            t1 = time.time()
            evaluation = analyze_position(epd, not board.turn)
            t2 = time.time()
            #f.write(f"INSERT INTO boards VALUES({bid},'{epd}');\n")
            for depth, score, pv in evaluation[-4:]:
                print(f" d{depth}, {score}, {pv[:5*10]}")
            print(f" t -> {t2-t1:.1f}s")
            for depth, score, pv in evaluation:
                f.write(f"INSERT INTO evaluations VALUES({bid},{depth},'{score}','{pv}');\n")
            f.flush()
            move = pv.split(" ")[0]
            board.push_uci(move)
            if board.epd() in epd2boardid:
                print("Will continue with", move)
                todo.insert(0, epd2boardid[board.epd()])
    finally:
        f.write("""\
COMMIT;
CREATE INDEX evaluations_boardid on evaluations(boardid);
PRAGMA foreign_keys=ON;
""")
