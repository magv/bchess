import random
import sqlite3

class BookDB:
    def __init__(self, filename):
        self.db = None
        self.db = sqlite3.connect(f"file:{filename}?immutable=1", uri=True, check_same_thread=False)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()

    def close(self):
        if self.db:
            self.db.close()

    def available_ratings(self):
        return [elo for elo, in self.db.execute("select distinct elo from moves")]

    def moves(self, epd, elo):
        movestring = None
        for row in self.db.execute("select moves from moves where elo=? and boardid=(select id from boards where epd=?)", (elo, epd)):
            movestring, = row
        if movestring is None:
            return [], []
        moves = []
        counts = []
        for mc in movestring.split():
            move, count = mc.split(":")
            moves.append(move)
            counts.append(int(count))
        return moves, counts

    def random_move(self, epd, elo):
        moves, counts = self.moves(epd, elo)
        if moves == []:
            return None
        return random.choices(moves, weights=counts)[0]

default = None

def of_spec(spec):
    if spec is None: return None
    assert spec["type"] == "builtin"
    assert default is not None
    rating = spec["rating"]
    return lambda board: default.random_move(board.epd(), rating)
