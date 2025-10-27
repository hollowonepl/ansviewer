#!/usr/bin/env python3

# Simple Console ANSI (CP437) Viewer in UTF-8 modern terminal
# (C) 2025 hollowone/oftenhide
# 
# Allowed to distribute under BSD-2 license (full clause below)
#
# Feedback:
#      contact me via https://github.com/hollowonepl/ansviewer
# 
# Changelog:
#      1.0 - initial version, using termios, far from perfect
#      2.0 - improved, fully compliant with ANSI art format, based on curses
#      2.1 - --cat mode to drop the ansi art directly to terminal without navigation added 
#          - Added autoplay feature triggered by SPACE key with configurable speed
#
# -----------------------------------------------------------------------------------------
#
# BSD 2-Clause License:
#     Copyright (c) 2025, hollowone / oftenhide
# 
#     Redistribution and use in source and binary forms, with or without
#     modification, are permitted provided that the following conditions are met:
# 
#     1. Redistributions of source code must retain the above copyright notice, this
#        list of conditions and the following disclaimer.
# 
#     2. Redistributions in binary form must reproduce the above copyright notice,
#        this list of conditions and the following disclaimer in the documentation
#        and/or other materials provided with the distribution.
# 
#     THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
#     AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
#     IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
#     DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
#     FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
#     DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#     SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
#     CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
#     OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
#     OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# 
# -----------------------------------------------------------------------------------------

import curses
import os
import re
import sys
import argparse
import time

# ─── ANSI COLOR MAP ────────────────────────────────────────────────
ANSI_COLOR_MAP = {
    30: 0,  # curses.COLOR_BLACK
    31: 1,  # curses.COLOR_RED
    32: 2,  # curses.COLOR_GREEN
    33: 3,  # curses.COLOR_YELLOW
    34: 4,  # curses.COLOR_BLUE
    35: 5,  # curses.COLOR_MAGENTA
    36: 6,  # curses.COLOR_CYAN
    37: 7,  # curses.COLOR_WHITE
    90: 0,  # Bright black
    91: 1,  # Bright red
    92: 2,  # Bright green
    93: 3,  # Bright yellow
    94: 4,  # Bright blue
    95: 5,  # Bright magenta
    96: 6,  # Bright cyan
    97: 7,  # Bright white
}

# Map curses color numbers to ANSI codes for cat_ansi_line
CURSES_TO_ANSI = {
    0: 30,  # COLOR_BLACK
    1: 31,  # COLOR_RED
    2: 32,  # COLOR_GREEN
    3: 33,  # COLOR_YELLOW
    4: 34,  # COLOR_BLUE
    5: 35,  # COLOR_MAGENTA
    6: 36,  # COLOR_CYAN
    7: 37,  # COLOR_WHITE
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
        comment_lines = sauce_trailer[104]
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
        cols = min(sauce["tinfo1"], 80)  # Cap at 80 to avoid excessive width
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
        pair_index: dict mapping (fg, bg) to color_pair
    """
    text = text.replace("\x00", " ")  # remove null bytes
    pattern = re.compile(r"(\x1b\[[0-9;]*[A-Za-z])")
    parts = pattern.split(text)

    y, x = 0, 0
    current_fg, current_bg = 7, 0  # Default to white on black
    lines = {}
    pair_index = {}
    pair_count = 1

    # Create color pairs (8 fg x 8 bg = 64 pairs)
    for fg in range(8):  # 0-7 for black, red, green, yellow, blue, magenta, cyan, white
        for bg in range(8):
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
                        current_fg, current_bg = 7, 0  # Reset to white on black
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
    
    return lines, height, max_width, pair_index

def cat_ansi_output(lines, pair_index):
    """
    Generate ANSI-escaped string output from parsed lines dictionary.
    Uses absolute cursor positioning (CSI row;colH) for accurate placement.
    """
    output = []
    reverse_pair_index = {v: k for k, v in pair_index.items()}
    last_color = None

    for y in sorted(lines.keys()):
        for x, ch, color_pair in sorted(lines[y], key=lambda t: t[0]):
            if color_pair != last_color:
                fg, bg = reverse_pair_index.get(color_pair, (7, 0))
                fg_ansi = 30 + fg
                bg_ansi = 40 + bg
                output.append(f"\x1b[{fg_ansi};{bg_ansi}m")
                last_color = color_pair
            output.append(f"\x1b[{y+1};{x+1}H{ch}")
    output.append("\x1b[0m\n")
    return "".join(output)

def cat_ansi_line(line, pair_index, fixed_width=80):
    """
    Convert a line of (x, ch, color_pair) tuples to a string with ANSI escape codes,
    wrapping at fixed_width if necessary.
    Args:
        line: List of (x, ch, color_pair) tuples for a single y-coordinate.
        pair_index: Dict mapping (fg, bg) to color_pair number.
        fixed_width: Maximum columns before wrapping (default 80).
    Returns:
        List of strings, each representing a wrapped line with ANSI escape codes.
    """
    if not line:
        return ["\x1b[0m\n"]
    
    # Reverse map color_pair to (fg, bg) for ANSI codes
    reverse_pair_index = {v: k for k, v in pair_index.items()}
    
    # Sort by x to ensure correct order
    sorted_line = sorted(line, key=lambda t: t[0])
    
    # Build line content, tracking x position and color changes
    current_x = 0
    current_color = 0
    result_lines = [[]]  # List of lists to handle wrapped lines
    for x, ch, color_pair in sorted_line:
        # Handle cursor movement if x is beyond current position
        if x > current_x:
            result_lines[-1].append(f"\x1b[{x + 1}G")
            current_x = x
        
        # Set color if changed
        if color_pair != current_color:
            fg, bg = reverse_pair_index.get(color_pair, (7, 0))  # Default to white on black
            fg_ansi = CURSES_TO_ANSI.get(fg, 37)
            bg_ansi = CURSES_TO_ANSI.get(bg, 40)
            result_lines[-1].append(f"\x1b[{fg_ansi};{bg_ansi}m")
            current_color = color_pair
        
        # Add character and update position
        result_lines[-1].append(ch)
        current_x += 1
        
        # Wrap if exceeding fixed_width
        if current_x >= fixed_width:
            result_lines.append([f"\x1b[{current_color}m" if current_color else "\x1b[0m"])
            current_x = 0

    # Finalize each line with reset and newline
    result = ["".join(line) + "\x1b[0m\n" for line in result_lines]
    
    return result

def draw_window(stdscr, lines, offset_y, autoplay=False):
    """
    Draw visible window portion based on scroll offset.
    Args:
        stdscr: Curses window object.
        lines: Dict {y: [(x, ch, color_pair), ...]} from parse_ansi_to_lines.
        offset_y: Vertical scroll offset.
        autoplay: Boolean indicating if autoplay is active.
    """
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
    status = "ANSI VIEWER 2.1 (c) 2025 hollowone/oftenhide | ↑↓ scroll | SPACE autoplay | TAB sauce | Q quit"
    if autoplay:
        status += " | AUTOPLAY ON"
    stdscr.addstr(h - 1, 0, status, curses.A_REVERSE)
    stdscr.refresh()

# ─── MAIN ──────────────────────────────────────────────────────────
def main(stdscr, data, autoplay_delay):
    curses.start_color()
    curses.use_default_colors()
    stdscr.keypad(True)
    curses.curs_set(0)
    stdscr.timeout(50)  # Set timeout for non-blocking key check during autoplay

    # Initialize color pairs for curses
    pair_index = {}
    pair_count = 1
    for fg in range(8):
        for bg in range(8):
            if pair_count < curses.COLOR_PAIRS:
                curses.init_pair(pair_count, fg, bg)
                pair_index[(fg, bg)] = pair_count
                pair_count += 1

    sauce_data = read_sauce(data)
    show_sauce = False
    autoplay = False
    last_autoplay_time = time.time()

    data = strip_sauce_and_comments(data)
    data = sanitize_trailing_escapes(data)

    cols, _ = get_ansi_dimensions(sauce_data)
    
    text = cp437_to_unicode(data)    
    lines, total_height, total_width, _ = parse_ansi_to_lines(text, fixed_width=cols)    

    offset_y = 0

    while True:
        if show_sauce:
            draw_sauce_popup(stdscr, sauce_data)
        else:
            draw_window(stdscr, lines, offset_y, autoplay)

        # Handle autoplay scrolling
        if autoplay and not show_sauce:
            current_time = time.time()
            if current_time - last_autoplay_time >= autoplay_delay:
                h, _ = stdscr.getmaxyx()
                if offset_y < total_height - h:
                    offset_y += 1
                else:
                    autoplay = False  # Stop autoplay at the bottom
                last_autoplay_time = current_time

        try:
            key = stdscr.getch()
            if key == -1:  # No key pressed
                continue
            if key in (ord('q'), 27):
                break
            elif key == 9:  # TAB
                show_sauce = not show_sauce
                autoplay = False  # Stop autoplay when toggling SAUCE
            elif not show_sauce:
                h, w = stdscr.getmaxyx()
                if key == ord(' '):  # SPACE to toggle autoplay
                    autoplay = not autoplay
                    last_autoplay_time = time.time()
                elif key in (curses.KEY_DOWN, ord("j")):
                    autoplay = False  # Stop autoplay on manual navigation
                    if offset_y < total_height - h:
                        offset_y += 1
                elif key in (curses.KEY_UP, ord("k")):
                    autoplay = False  # Stop autoplay on manual navigation
                    if offset_y > 0:
                        offset_y -= 1
                elif key == curses.KEY_NPAGE:
                    autoplay = False  # Stop autoplay on manual navigation
                    offset_y = min(total_height - h, offset_y + h - 2)
                elif key == curses.KEY_PPAGE:
                    autoplay = False  # Stop autoplay on manual navigation
                    offset_y = max(0, offset_y - h + 2)
                elif key == curses.KEY_RESIZE:
                    pass
        except curses.error:
            pass

# ─── ENTRY POINT ───────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CP437 ANSI viewer with scrolling, autoplay, and SAUCE support | version 2.1 | (c) 2025 hollowone/oftenhide")
    parser.add_argument('file', nargs='?', help="ANS file (or stdin with -)")
    parser.add_argument('--cat', action='store_true', help="Dump raw ANSI to stdout with colors and formatting")
    parser.add_argument('--sauce', action='store_true', help="Show SAUCE metadata including comments")
    parser.add_argument('--autoplay-delay', type=float, default=0.1, help="Delay between lines in autoplay mode (seconds, default: 0.1)")
    args = parser.parse_args()

    if not args.file:
        parser.print_help()
        sys.exit(1)

    # Read input data
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

    # Handle --sauce flag
    if args.sauce:
        sauce_data = read_sauce(data)
        print_sauce(sauce_data)
        sys.exit(0)

    # Handle --cat flag outside curses
    if args.cat:
        sauce_data = read_sauce(data)
        data = strip_sauce_and_comments(data)
        data = sanitize_trailing_escapes(data)
        cols, _ = get_ansi_dimensions(sauce_data)
        text = cp437_to_unicode(data)        
        lines, total_height, total_width, pair_index = parse_ansi_to_lines(text, fixed_width=cols)        
        ansi_out = cat_ansi_output(lines, pair_index)
        print(ansi_out, end="")
        sys.exit(0)

    # Run curses viewer for non-cat mode
    curses.wrapper(main, data, args.autoplay_delay)
