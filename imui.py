import curses

from contextlib import contextmanager
from collections import namedtuple

EventMousePress = namedtuple("EventMousePress", "button x y")

class Ref:
    """
    Mutable cell with one value.

    One can get the value by calling this object with no parameters,
    and set it by calling it with one.

    See also: class RefOfAttribute and RefOfItem.
    """
    __slots__ = ("value",)
    def __init__(self, value):
        self.value = value
    def __call__(self, value=None):
        if value is not None: self.value = value
        return self.value

class RefOfAttribute:
    """
    Mutable cell referencing an attribute of an object.

    See also: class Ref and RefOfItem.
    """
    __slots__ = ("container", "key")
    def __init__(self, obj, key):
        self.obj = obj
        self.key = key
    def __call__(self, value=None):
        if value is not None: setattr(self.obj, key, value)
        return getattr(self.obj, self.key)

class RefOfItem:
    """
    Mutable cell referencing a keyed item of a container.

    See also: class Ref and RefOfAttribute.
    """
    __slots__ = ("container", "key")
    def __init__(self, container, key):
        self.container = container
        self.key = key
    def __call__(self, value=None):
        if value is not None: self.container[key] = value
        return self.container[self.key]

class IM_EndOfScreen(Exception):
    """
    Throw this exception when the bottom of the screen (or the
    current column) is reached, and further rendering will only
    go below it, so it can be safely skipped.
    """
    pass

class IM:
    """
    This is an "immediate mode" terminal UI library.

    IM is a bit specialized and not 100% general, but the approach
    adopted here is the best way to construct UIs, terminal or
    not.
    """

    def __init__(self):
        self.win = None
        self.key_events = []
        self.mouse_events = []
        self.want_refresh = False
        self.minx = 0
        self.miny = 0
        self.maxx = 0
        self.maxy = 0
        self.curx = 0
        self.cury = 0
        self.active_id = None
        self.active_index = None
        self.current_index = 0
        self.runqueue = []
        self.table_rowy, self.table_maxy, self.table_col_minx, self.table_col_maxx, self.table_idx = None, None, None, None, None

    def gather_input(self, win):
        """
        Read and process a part of the available input from stdin, 
        possibly pausing a few ms to wait for additional input.
        Execute all functions enqueued by run_soon() at the end.
        You should call this in a loop.
        """
        curses.halfdelay(7)
        win.nodelay(1)
        while True:
            try:
                key = win.get_wch()
            except curses.error:
                break
            curses.cbreak()
            if key == curses.KEY_MOUSE:
                try:
                    self.input_mouse(*curses.getmouse())
                except curses.error:
                    pass
            else:
                self.input_key(key)
        if self.runqueue:
            rq = self.runqueue
            self.runqueue = []
            for f in rq: f()
        return self.key_events != [] or self.mouse_events != []

    def run_soon(self, f):
        """Enqueue a function to be run after the next gather_input()."""
        self.runqueue.append(f)

    def input_mouse(self, mid, x, y, z, state):
        """Add a mouse event to the input queue."""
        if state & curses.BUTTON1_PRESSED:
            self.mouse_events.append(EventMousePress(1, x, y))
        if state & curses.BUTTON2_PRESSED:
            self.mouse_events.append(EventMousePress(2, x, y))
        if state & curses.BUTTON3_PRESSED:
            self.mouse_events.append(EventMousePress(3, x, y))
        if state & curses.BUTTON4_PRESSED:
            self.mouse_events.append(EventMousePress(4, x, y))
        if state & getattr(curses, "BUTTON5_PRESSED", 134217728):
            self.mouse_events.append(EventMousePress(5, x, y))

    def input_key(self, key):
        """Add a keyboard event to the input queue."""
        self.key_events.append(key)

    @property
    def text_width(self):
        """The width of the current column (or the screen)."""
        return self.maxx + 1 - self.minx

    @property
    def text_height(self):
        """The height of the current column (or the screen)."""
        return self.maxy + 1 - self.miny

    @contextmanager
    def Frame(self, screen):
        """
        Reset the screen state and prepare for a new frame. Call
        this each frame.
        """
        self.win = screen
        self.win.erase()
        self.want_refresh = False
        self._focus_begin()
        try:
            with self.Screen(): yield
        finally:
            self.win.refresh()
            self.win = None
            self.key_events = []
            self.mouse_events = []
            self._focus_end()

    @contextmanager
    def Screen(self):
        """
        Begin the layout of the whole screen (from the top left).
        Call only if an overlay over the previous layout needed,
        otherwise Frame() will call this automatically.
        """
        save = self.minx, self.miny, self.maxy, self.maxx, self.curx, self.cury
        self.minx, self.miny = 0, 0
        self.maxy, self.maxx = self.win.getmaxyx()
        self.maxy -= 1
        self.maxx -= 1
        self.curx, self.cury = 0, 0
        try:
            yield
        except IM_EndOfScreen:
            pass
        finally:
            self.minx, self.miny, self.maxy, self.maxx, self.curx, self.cury = save

    def Key(self, key, id=None):
        """
        An invisible key accelerator. Returns the number of times
        the key was pressed. If id is given, only consumes keys
        when the specified element is active.
        """
        if id is None or self.active_id == id:
            n = len(self.key_events)
            self.key_events = [e for e in self.key_events if e != key]
            return n - len(self.key_events)
        else:
            return 0

    def _focus_begin(self):
        """Call at the start of Frame() to update focus data."""
        if self.active_id is None:
            # Nothing is active yet, searching for active_index.
            n = self.Key("\t") - self.Key(curses.KEY_BTAB)
            if n:
                if self.active_index is None:
                    self.active_index = n - 1 if n > 0 else n
                else:
                    self.active_index += n
        if self.active_index is not None:
            if self.current_index > 0:
                self.active_index %= self.current_index
            else:
                self.active_index = None
        self.current_index = 0
        self.active_exists = False

    def _focus_end(self):
        """Call at the end of Frame() to update focus data."""
        if self.active_index is not None:
            # This might be off if the new active element was
            # not found during the frame. If so, try again.
            self.want_refresh = True
        if self.active_id is not None and not self.active_exists:
            self.active_id = None

    def cycle_focus(self, id):
        """
        Detect if Tab was pressed, and if so, change the focus
        to the next element. Every focusable element should call
        this exactly once, before determining focus.
        Return True if the current element is focused.
        """
        assert self.active_id is None or self.active_index is None
        if id is None:
            # This element is not even focusable.
            return False
        if self.active_id == id:
            # This element is active, unless Tab was pressed...
            n = self.Key("\t") - self.Key(curses.KEY_BTAB)
            if n:
                # ... in which case unfocus and search for the
                # next focused element.
                self.active_id = None
                self.active_index = self.current_index + n
            if self.Key("\x1b") != 0:
                # Or maybe just unfocus all.
                self.active_id = None
                self.active_index = None
        elif self.active_id is None:
            # No element is active.
            if self.active_index == self.current_index:
                self.active_id = id
                self.active_index = None
        else:
            # Some other element is active.
            pass
        self.current_index += 1
        if self.active_id == id:
            self.active_exists = True
            return True
        else:
            return False

    def focus(self, id):
        if id is None:
            return False
        if self.active_id is not None:
            self.want_refresh = True
        self.active_id = id
        self.active_index = None
        return True

    def AllKeys(self, id=None):
        if id is None or self.active_id == id:
            for k in self.key_events: yield k
            self.key_events = []
        else:
            return 0

    def Input(self, text, id=None, prefix="", attr=0, align=0):
        change = False
        if self.active_id == id:
            while self.key_events:
                key = self.key_events.pop(0)
                if key == curses.KEY_BACKSPACE:
                    if text == "":
                        pass
                    else:
                        text = text[:-1]
                        change = True
                elif type(key) == str:
                    text = text + key
                    change = True
            self.Text(prefix + text + "▒", attr=attr, align=align)
        else:
            self.Text(prefix + text + " ", attr=attr, align=align)
        return text, change

    def MouseClick(self, x, y, w, h):
        """
        An invisible mouse region. Returns the number of times
        it was clicked.
        """
        n = len(self.mouse_events)
        self.mouse_events = [
            e for e in self.mouse_events
            if not((x <= e.x < x + w) and (y <= e.y < y + h))
        ]
        return n - len(self.mouse_events)

    def TextAt(self, x, y, text, attr=0):
        """A text label at fixed coordinates."""
        w = len(text)
        if y <= self.maxy and x <= self.maxx:
            if x + w <= self.maxx:
                self.win.addstr(y, x, text, attr)
            else:
                try:
                    ll = self.maxx - x + 1
                    self.win.addstr(y, x, text[:ll], attr)
                except curses.error:
                    # Lower right corner always fails, no matter
                    # what. Stupid.
                    pass

    def Text(self, text, attr=0, align=0):
        """A text label (at the current layout position)."""
        text = str(text).strip("\"\'")
        if "\n" in text: _, text = text.rsplit("\n", 1)
        if align == 0:
            self.TextAt(self.curx, self.cury, text, attr=attr)
        elif align == 1:
            self.TextAt((self.curx + self.maxx - len(text) + 2)//2, self.cury, text, attr=attr)
        elif align == 2:
            self.TextAt(self.maxx - len(text) + 1, self.cury, text, attr=attr)
        self.cury += 1

    def VSpace(self, rows):
        """A number of empty rows."""
        self.cury += max(rows, 0)

    def HSpace(self, columns):
        """A number of empty columns"""
        self.curx += max(columns, 0)

    def HR(self, fill="-"):
        """A horizontal ruler, filling the whole line."""
        return self.Text(fill * (self.maxx - self.minx + 1))

    def Button(self, text, attr=0, hiattr=None, id=None, key=None):
        """
        A clickable and maybe pressable label. Returns the number
        of times it was clicked or pressed.
        """
        focus = self.cycle_focus(id)
        lines = text.splitlines()
        x, y, w, h = self.curx, self.cury, max(len(line) for line in lines), len(lines)
        hit = self.Key(key, id=id) + self.MouseClick(x, y, w, h)
        if hit: focus = self.focus(id)
        for line in lines:
            self.Text(line, (hiattr if hiattr is not None else attr | curses.A_REVERSE) if focus else attr)
        return hit

    @contextmanager
    def Table(self, *widths, margin=0):
        save = self.table_rowy, self.table_maxy, self.table_col_minx, self.table_col_maxx, self.table_idx
        minx, maxx = self.minx, self.maxx
        colw = [w if type(w) is int else w[0] for w in widths]
        colf = [0 if type(w) is int else w[1] for w in widths]
        self.table_rowy = self.cury
        self.table_maxy = self.cury
        self.table_col_minx = []
        self.table_col_maxx = []
        extraw = 1 + maxx - minx - sum(colw) - margin*(len(colw)-1)
        x = minx
        for i in range(len(colw)):
            flex = 0 if colf[i] == 0 else (extraw * colf[i] // sum(colf))
            self.table_col_minx.append(x)
            self.table_col_maxx.append(min(x + colw[i] + flex - 1, maxx))
            x += colw[i] + flex + margin
        yield
        self.minx, self.maxx = minx, maxx
        self.curx = minx
        self.cury = self.table_maxy
        self.table_rowy, self.table_maxy, self.table_col_minx, self.table_col_maxx, self.table_idx = save

    @contextmanager
    def Row(self):
        if self.table_rowy > self.maxy: raise IM_EndOfScreen()
        self.table_idx = 0
        self.table_maxy = 0
        yield True
        self.table_rowy = self.table_maxy

    @contextmanager
    def Cell(self, colspan=1):
        self.minx = self.table_col_minx[self.table_idx]
        self.maxx = self.table_col_maxx[self.table_idx + colspan - 1]
        self.curx = self.minx
        self.cury = self.table_rowy
        yield
        self.table_maxy = max(self.table_maxy, self.cury)
        self.table_idx += colspan

    def RowSeparator(self, fill="-"):
        with self.Row():
            for i in range(len(self.table_col_minx)):
                with self.Cell():
                    self.HR(fill)

    @contextmanager
    def TableRow(self, *widths, margin=0):
        with self.Table(*widths, margin=margin):
            with self.Row():
                yield

    @contextmanager
    def Center(self, width=None, height=None):
        if width is not None:
            with self.Table((0,1), width, (0,1), margin=0):
                with self.Row():
                    with self.Cell(): pass
                    with self.Cell():
                        if height is not None:
                            self.VSpace((self.text_height - height)//2)
                        yield
                    #with self.Cell(): pass
        else:
            if height is not None:
                self.VSpace((self.text_height - height)//2)
            yield

    @contextmanager
    def TabBar(self, *widths, index=None):
        self.tab_count = len(widths)
        self.tab_active = index() if index is not None else 0
        self.tab_current = 0
        hit = self.Key("\t") + self.Key(curses.KEY_RIGHT) - self.Key(curses.KEY_BTAB) - self.Key(curses.KEY_LEFT)
        self.tab_active = (self.tab_active + hit) % self.tab_count
        with self.Table(*widths):
            with self.Row():
                yield
        if index is not None:
            index(self.tab_active)

    @contextmanager
    def Tab(self, text, attr=0, key=None):
        with self.Cell():
            a = curses.A_REVERSE if self.tab_active == self.tab_current else attr
            if self.Button(text, attr=a, key=key):
                self.tab_active = self.tab_current
            self.tab_current += 1

    @contextmanager
    def ListView(self, index, id=None):
        self.lv_id = id
        self.lv_active = index() if index is not None else 0
        self.lv_current = 0
        if self.cycle_focus(id):
            hit = self.Key(curses.KEY_DOWN) - self.Key(curses.KEY_UP)
            self.lv_active += hit
        yield
        if not (0 <= self.lv_active < self.lv_current):
            self.lv_active %= self.lv_current
            self.want_refresh = True
        if index() != self.lv_active:
            index(self.lv_active)
            # This is only needed if some UI before the list
            # view depended on the index value.
            self.want_refresh = True

    def ListItem(self, text, attr=0, key=None):
        if self.Key(key):
            self.lv_active = self.lv_current
        if self.lv_active == self.lv_current:
            attr |= curses.A_REVERSE if self.active_id == self.lv_id else curses.A_UNDERLINE
        if self.Button(text, attr=attr):
            self.active_id = self.lv_id
            self.lv_active = self.lv_current
            self.want_refresh = True
        self.lv_current += 1

