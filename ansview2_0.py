#!/usr/bin/env python3
import curses
import os
import re
import sys
import argparse

# ─── ANSI COLOR MAP ────────────────────────────────────────────────
ANSI_COLOR_MAP = {
    30: curses.COLOR_BLACK,
    31: curses.COLOR_RED,
    32: curses.COLOR_GREEN,
    33: curses.COLOR_YELLOW,
    34: curses.COLOR_BLUE,
    35: curses.COLOR_MAGENTA,
    36: curses.COLOR_CYAN,
    37: curses.COLOR_WHITE,
    90: curses.COLOR_BLACK,
    91: curses.COLOR_RED,
    92: curses.COLOR_GREEN,
    93: curses.COLOR_YELLOW,
    94: curses.COLOR_BLUE,
    95: curses.COLOR_MAGENTA,
    96: curses.COLOR_CYAN,
    97: curses.COLOR_WHITE,
}

# ─── SAUCE ───────────────────────────────────────────────────────
def read_sauce(data: bytes):
    """
    Reads the SAUCE record and comments from a bytes array.
    Returns None if no SAUCE found.
    """
    if len(data) < 128:
        return None

    trailer = data[-128:]
    if trailer[:5] != b"SAUCE":
        return None

    version = trailer[5:7].decode("ascii", errors="replace")
    title = trailer[7:42].rstrip(b'\x00').decode("cp437", errors="replace")
    author = trailer[42:62].rstrip(b'\x00').decode("cp437", errors="replace")
    group = trailer[62:82].rstrip(b'\x00').decode("cp437", errors="replace")
    date = trailer[82:90].decode("ascii", errors="replace")
    file_size = int.from_bytes(trailer[90:94], "little")
    data_type = trailer[94]
    file_type = trailer[95]
    tinfo1 = int.from_bytes(trailer[96:98], "little")
    tinfo2 = int.from_bytes(trailer[98:100], "little")
    tinfo3 = int.from_bytes(trailer[100:102], "little")
    tinfo4 = int.from_bytes(trailer[102:104], "little")
    comments_count = trailer[104]
    tflags = trailer[105]
    tinfos = trailer[106:128].rstrip(b'\x00').decode("cp437", errors="replace")

    comments = []
    if comments_count > 0:
        comment_block_size = comments_count * 64
        if len(data) < 128 + 5 + comment_block_size:
            return None
        comment_data = data[-(128 + 5 + comment_block_size):-128]
        for i in range(comments_count):
            line = comment_data[i*64:(i+1)*64].rstrip(b'\x00')
            comments.append(line.decode("cp437", errors="replace"))

    return {
        "version": version,
        "title": title,
        "author": author,
        "group": group,
        "date": date,
        "file_size": file_size,
        "data_type": data_type,
        "file_type": file_type,
        "tinfo1": tinfo1,
        "tinfo2": tinfo2,
        "tinfo3": tinfo3,
        "tinfo4": tinfo4,
        "tflags": tflags,
        "tinfos": tinfos,
        "comments": comments
    }

def print_sauce(sauce):
    """
    Print SAUCE metadata to console in a formatted way.
    """
    if not sauce:
        print("No SAUCE metadata found.")
        return
    print(f"Version : {sauce.get('version', '')}")
    print(f"Title   : {sauce.get('title', '')}")
    print(f"Author  : {sauce.get('author', '')}")
    print(f"Group   : {sauce.get('group', '')}")
    print(f"Date    : {sauce.get('date', '')}")
    print(f"DataType: {sauce.get('data_type', '')}")
    print(f"FileType: {sauce.get('file_type', '')}")
    print(f"TInfo1-4: {sauce.get('tinfo1', '')} {sauce.get('tinfo2', '')} {sauce.get('tinfo3', '')} {sauce.get('tinfo4', '')}")
    print(f"TFlags  : {sauce.get('tflags', '')}")
    print(f"TInfoS  : {sauce.get('tinfos', '')}")
    if sauce.get("comments"):
        print("Comments:")
        for comment in sauce.get("comments", []):
            print(f"  {comment}")

# ─── BOX DRAWING CHARACTERS ───────────────────────────────────────
UL_CORNER = "┏"
UR_CORNER = "┓"
LL_CORNER = "┗"
LR_CORNER = "┛"
H_LINE = "━"
V_LINE = "┃"

def draw_sauce_popup(stdscr, sauce):
    if not sauce:
        return

    h, w = stdscr.getmaxyx()
    box_w = min(60, w - 4)
    box_h = min(9 + len(sauce.get("comments", [])), h - 4)
    start_y = (h - box_h) // 2
    start_x = (w - box_w) // 2

    for y in range(start_y + 1, start_y + box_h - 1):
        stdscr.addstr(y, start_x + 1, " " * (box_w - 2))

    for x in range(box_w):
        stdscr.addstr(start_y, start_x + x, H_LINE)
        stdscr.addstr(start_y + box_h - 1, start_x + x, H_LINE)

    for y in range(1, box_h - 1):
        stdscr.addstr(start_y + y, start_x, V_LINE)
        stdscr.addstr(start_y + y, start_x + box_w - 1, V_LINE)

    stdscr.addstr(start_y, start_x, UL_CORNER)
    stdscr.addstr(start_y, start_x + box_w - 1, UR_CORNER)
    stdscr.addstr(start_y + box_h - 1, start_x, LL_CORNER)
    stdscr.addstr(start_y + box_h - 1, start_x + box_w - 1, LR_CORNER)

    info_lines = [
        f"Title: {sauce.get('title','')}",
        f"Author: {sauce.get('author','')}",
        f"Group: {sauce.get('group','')}",
        f"Date: {sauce.get('date','')}",
        f"DataType: {sauce.get('data_type','')}",
        f"FileType: {sauce.get('file_type','')}",
        f"TInfo1-4: {sauce.get('tinfo1','')} {sauce.get('tinfo2','')} {sauce.get('tinfo3','')} {sauce.get('tinfo4','')}",
        f"TFlags: {sauce.get('tflags','')}",
        f"TInfoS: {sauce.get('tinfos','')}"
    ]

    full_lines = info_lines + sauce.get("comments", [])
    for i, line in enumerate(full_lines[:box_h - 2]):
        stdscr.addstr(start_y + 1 + i, start_x + 1, line[:box_w - 2])

def strip_sauce_and_comments(data: bytes) -> bytes:
    """
    Remove SAUCE metadata and preceding comment blocks from raw ANSI file bytes.
    Returns the clean bytes without SAUCE or COMNT sections.
    """
    clean_data = data
    if len(clean_data) >= 128 and clean_data[-128:-123] == b'SAUCE':
        sauce_trailer = clean_data[-128:]
        comment_lines = sauce_trailer[104]  # Fixed index to match read_sauce
        total_strip = 128 + comment_lines * 64
        if total_strip <= len(clean_data):
            clean_data = clean_data[:-total_strip]

    while True:
        idx = clean_data.rfind(b'COMNT')
        if idx == -1:
            break
        clean_data = clean_data[:idx]

    return clean_data

def strip_trailing_ctrlz(data: bytes) -> bytes:
    """Remove trailing DOS Ctrl-Z (^Z, 0x1A) bytes at end of file."""
    return data.rstrip(b'\x1A')

def sanitize_trailing_escapes(data: bytes) -> bytes:
    """
    Remove incomplete ANSI escape sequences at the end of the file.
    """
    pattern = re.compile(rb'\x1b\[[0-9;]*[A-Za-z]')
    matches = list(pattern.finditer(data))
    if not matches:
        return data
    last = matches[-1]
    end_pos = last.end()
    if end_pos > len(data):
        return data[:last.start()]
    return strip_trailing_ctrlz(data)

# ─── HELPERS ───────────────────────────────────────────────────────
def get_ansi_dimensions(sauce, default_width=80):
    """
    Return (cols, rows) from SAUCE if present; otherwise assume 80 columns.
    """
    if sauce and "tinfo1" in sauce and sauce["tinfo1"] > 0:
        cols = sauce["tinfo1"]
        rows = sauce["tinfo2"] if "tinfo2" in sauce else 0
        return cols, rows
    return default_width, 0

def cp437_to_unicode(b: bytes) -> str:
    """Convert CP437 bytes to Unicode string."""
    return b.decode("cp437", errors="replace")

def parse_ansi_to_lines(text, fixed_width=80):
    """
    Parse ANSI escape codes into (char, color_pair) grid lines.
    Returns:
        lines: dict {y: [(x, ch, color_pair), ...]}
        height: total number of lines
        width: max line width
    """
    text = text.replace("\x00", " ")  # remove null bytes
    pattern = re.compile(r"(\x1b\[[0-9;]*[A-Za-z])")
    parts = pattern.split(text)

    y, x = 0, 0
    current_fg, current_bg = curses.COLOR_WHITE, curses.COLOR_BLACK
    lines = {}
    pair_index = {}
    pair_count = 1

    for fg in ANSI_COLOR_MAP.values():
        for bg in ANSI_COLOR_MAP.values():
            if pair_count < curses.COLOR_PAIRS:
                curses.init_pair(pair_count, fg, bg)
                pair_index[(fg, bg)] = pair_count
                pair_count += 1

    color_pair = 0
    max_width = 0

    for part in parts:
        if not part:
            continue

        if part.startswith("\x1b["):
            m = re.match(r"\x1b\[([0-9;]*)([A-Za-z])", part)
            if not m:
                continue
            params, cmd = m.groups()
            nums = [int(n) for n in params.split(";") if n] if params else []

            if cmd == "m":
                for n in nums or [0]:
                    if 30 <= n <= 37 or 90 <= n <= 97:
                        current_fg = ANSI_COLOR_MAP.get(n, current_fg)
                    elif 40 <= n <= 47 or 100 <= n <= 107:
                        current_bg = ANSI_COLOR_MAP.get(n - 10, current_bg)
                    elif n == 0:
                        current_fg, current_bg = curses.COLOR_WHITE, curses.COLOR_BLACK
                color_pair = pair_index.get((current_fg, current_bg), 0)
            elif cmd == "H" and len(nums) >= 2:
                y, x = nums[0] - 1, nums[1] - 1
            elif cmd == "A":
                y = max(0, y - (nums[0] if nums else 1))
            elif cmd == "B":
                y += (nums[0] if nums else 1)
            elif cmd == "C":
                x += (nums[0] if nums else 1)
            elif cmd == "D":
                x = max(0, x - (nums[0] if nums else 1))
            continue

        for ch in part:
            if ch == "\n":
                y += 1
                x = 0
                continue
            if x >= fixed_width:
                y += 1
                x = 0

            if y not in lines:
                lines[y] = []
            lines[y].append((x, ch, color_pair))
            x += 1

    height = max(lines.keys()) + 1 if lines else 1
    for line in lines.values():
        if line:
            cur_width = max(pos[0] for pos in line) + 1
            max_width = max(max_width, cur_width)

    return lines, height, max_width


def draw_window(stdscr, lines, offset_y, cat_mode=False):
    """Draw visible window portion based on scroll offset."""

    stdscr.erase()
    h, w = stdscr.getmaxyx()
    visible_lines = range(offset_y, offset_y + h - 1)
    for y in visible_lines:
        if y in lines:
            for x, ch, color in lines[y]:
                if 0 <= x < w - 1:
                    try:
                        stdscr.addstr(y - offset_y, x, ch, curses.color_pair(color))
                    except curses.error:
                        pass
    stdscr.addstr(h - 1, 0, "ANSI VIEWER 2.0 (c) 2025 hollowone/oftenhide | ↑↓ scroll | TAB sauce | Q quit  ", curses.A_REVERSE)
    stdscr.refresh()

# ─── MAIN ──────────────────────────────────────────────────────────
def main(stdscr, data, cat_mode = False):
    curses.start_color()
    curses.use_default_colors()
    stdscr.keypad(True)
    curses.curs_set(0)

    sauce_data = read_sauce(data)
    show_sauce = False #show_sauce_flag

    data = strip_sauce_and_comments(data)
    data = sanitize_trailing_escapes(data)

    cols, _ = get_ansi_dimensions(sauce_data)
    text = cp437_to_unicode(data)
    lines, total_height, total_width = parse_ansi_to_lines(text, fixed_width=cols)

    if cat_mode:
        draw_window(stdscr,lines,0,True)
        sys.exit(0)

    offset_y = 0

    while True:
        if show_sauce:
            draw_sauce_popup(stdscr, sauce_data)
        else:
            draw_window(stdscr, lines, offset_y)

        key = stdscr.getch()
        if key in (ord('q'), 27):
            break
        elif key == 9:  # TAB
            show_sauce = not show_sauce
        elif not show_sauce:
            h, w = stdscr.getmaxyx()
            if key in (curses.KEY_DOWN, ord("j")):
                if offset_y < total_height - h:
                    offset_y += 1
            elif key in (curses.KEY_UP, ord("k")):
                if offset_y > 0:
                    offset_y -= 1
            elif key == curses.KEY_NPAGE:
                offset_y = min(total_height - h, offset_y + h - 2)
            elif key == curses.KEY_PPAGE:
                offset_y = max(0, offset_y - h + 2)
            elif key == curses.KEY_RESIZE:
                pass

# ─── ENTRY POINT ───────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CP437 ANSI viewer with scrolling and SAUCE support | version 2.0 | (c) 2025 hollowone/oftenhide")
    parser.add_argument('file', nargs='?', help="ANS file (or stdin with -)")
#    parser.add_argument('--cat', action='store_true', help="Dump raw ANSI to stdout")
    parser.add_argument('--sauce', action='store_true', help="Show SAUCE metadata including comments")
    args = parser.parse_args()

    if not args.file:
        parser.print_help()
        sys.exit(1)

    cat_mode = False
    
#    if args.cat:
#        cat_mode=True
           
# Handle --sauce flag
    if args.sauce:
        if args.file == '-':
            data = sys.stdin.buffer.read()
        else:
            if not os.path.exists(args.file):
                print(f"File not found: {args.file}", file=sys.stderr)
                sys.exit(1)
            if not os.path.isfile(args.file):
                print(f"Not a file: {args.file}", file=sys.stderr)
                sys.exit(1)
            with open(args.file, 'rb') as f:
                data = f.read()
        
        sauce_data = read_sauce(data)
        print_sauce(sauce_data)
        sys.exit(0)

    if args.file == '-':
        data = sys.stdin.buffer.read()
    else:
        if not os.path.exists(args.file):
            print(f"File not found: {args.file}", file=sys.stderr)
            sys.exit(1)
        if not os.path.isfile(args.file):
            print(f"Not a file: {args.file}", file=sys.stderr)
            sys.exit(1)
        with open(args.file, 'rb') as f:
            data = f.read()

    curses.wrapper(main, data, cat_mode)
