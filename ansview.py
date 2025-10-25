#!/usr/bin/env python3
"""
ansview.py - CP437 ANSI (.ans) viewer with smooth ANSI rendering and SAUCE support.
Preserves ANSI colors, box-drawing characters, and interactive scrolling.
SAUCE comments are shown only with --sauce.
"""

import sys, argparse, io, os, shutil, termios, tty, select

ESC = '\x1b'
SAUCE_SIZE = 128

def parse_sauce(data: bytes):
    """Parse SAUCE metadata including comment lines (if present)."""
    if len(data) < SAUCE_SIZE or data[-SAUCE_SIZE:-SAUCE_SIZE+7] != b"SAUCE00":
        return None

    trailer = data[-SAUCE_SIZE:]
    title = trailer[7:42].rstrip(b'\x00').decode('latin1','ignore')
    author = trailer[42:62].rstrip(b'\x00').decode('latin1','ignore')
    group = trailer[62:82].rstrip(b'\x00').decode('latin1','ignore')
    date = trailer[82:90].decode('ascii','ignore')
    filesize = int.from_bytes(trailer[90:94],'little')
    n_comments = trailer[94]

    comments = []
    if n_comments > 0:
        comnt_pos = len(data) - SAUCE_SIZE - n_comments*64 - 5
        if comnt_pos >= 0 and data[comnt_pos:comnt_pos+5] == b"COMNT":
            comment_start = comnt_pos + 5
            for i in range(n_comments):
                line = data[comment_start + i*64 : comment_start + (i+1)*64]
                comments.append(line.rstrip(b'\x00').decode('latin1','ignore'))

    return {
        "Title": title,
        "Author": author,
        "Group": group,
        "Date": date,
        "FileSize": filesize,
        "Comments": comments
    }

def remove_sauce_bytes(data: bytes) -> bytes:
    """Remove SAUCE trailer and comment block if present."""
    if len(data) < SAUCE_SIZE or data[-SAUCE_SIZE:-SAUCE_SIZE+7] != b"SAUCE00":
        return data

    trailer = data[-SAUCE_SIZE:]
    n_comments = trailer[94]
    comnt_pos = len(data) - SAUCE_SIZE - n_comments*64 - 5

    if n_comments>0 and comnt_pos >= 0 and data[comnt_pos:comnt_pos+5] == b"COMNT":
        return data[:comnt_pos]
    else:
        return data[:-SAUCE_SIZE]

def cp437_to_unicode_preserve_ansi(s: str) -> str:
    """Preserve ANSI escape sequences and printable CP437 chars."""
    ESC = '\x1b'
    out = []
    i = 0
    while i < len(s):
        ch = s[i]
        code = ord(ch)
        if ch == ESC and i+1 < len(s) and s[i+1] == '[':
            # Copy entire ANSI sequence
            seq_end = i+2
            while seq_end < len(s) and not (0x40 <= ord(s[seq_end]) <= 0x7E):
                seq_end += 1
            seq_end = min(seq_end+1, len(s))
            out.append(s[i:seq_end])
            i = seq_end
            continue
        elif ch in '\r\n\t' or 0x20 <= code <= 0x7E or code >= 0xA0:
            out.append(ch)
        else:
            out.append(ch)
        i += 1
    return ''.join(out)

def get_term_size():
    return shutil.get_terminal_size((80,24))

def clear_screen():
    sys.stdout.write(ESC+'[2J'+ESC+'[H')
    sys.stdout.flush()

def read_key(timeout=None):
    fd = sys.stdin.fileno()
    rlist,_,_ = select.select([fd],[],[],timeout)
    if not rlist:
        return ''
    return os.read(fd,32).decode('latin1','ignore')

def interactive_view(lines):
    fd = sys.stdin.fileno()
    old_attrs = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    scroll = 0
    last_scroll = None
    term_cols, term_rows = get_term_size()
    max_scroll = max(0,len(lines)-term_rows)

    try:

        # Clear screen completely before first draw
        clear_screen()
        
        # Initial draw BEFORE any key is pressed
        last_scroll = scroll
        sys.stdout.write(ESC+'[H')
        visible = lines[scroll:scroll+term_rows]
        for l in visible:
            sys.stdout.write(l[:term_cols]+ESC+'[K\n')
        for _ in range(len(visible), term_rows):
            sys.stdout.write(ESC+'[K\n')
        sys.stdout.flush()

        # Enter key loop
        while True:
            key = read_key(timeout=None)
            redraw = False

            if key in ('\x1b','q'):
                break

            if max_scroll>0:
                if key.startswith('\x1b['):
                    seq = key[2:]
                    if seq.startswith('A'):
                        scroll = max(0, scroll-1)
                        redraw = True
                    elif seq.startswith('B'):
                        scroll = min(max_scroll, scroll+1)
                        redraw = True
                    elif seq.startswith('5'):
                        scroll = max(0, scroll-term_rows)
                        redraw = True
                    elif seq.startswith('6'):
                        scroll = min(max_scroll, scroll+term_rows)
                        redraw = True
                if key.lower()=='j':
                    scroll = min(max_scroll, scroll+1)
                    redraw = True
                if key.lower()=='k':
                    scroll = max(0, scroll-1)
                    redraw = True

            if redraw or scroll != last_scroll:
                last_scroll = scroll
                sys.stdout.write(ESC+'[H')
                visible = lines[scroll:scroll+term_rows]
                for l in visible:
                    sys.stdout.write(l[:term_cols]+ESC+'[K\n')
                for _ in range(len(visible), term_rows):
                    sys.stdout.write(ESC+'[K\n')
                sys.stdout.flush()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)
        clear_screen()



def main(argv=None):
    parser = argparse.ArgumentParser(description="""CP437 ANSI viewer with scrolling and SAUCE support | version 1.0 | (c) 2025 hollowone/oftenhide""")
    parser.add_argument('file', nargs='?', help="ANS file (or stdin with -)")
    parser.add_argument('--cat', action='store_true', help="Dump raw ANSI to stdout")
    parser.add_argument('--sauce', action='store_true', help="Show SAUCE metadata including comments")
    args = parser.parse_args(argv)

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    if not args.file or args.file=='-':
        data = sys.stdin.buffer.read()
    else:
        with open(args.file,'rb') as f:
            data = f.read()

    sauce = parse_sauce(data)
    core = remove_sauce_bytes(data)

    if args.sauce:
        if sauce:
            print(f"Title   : {sauce.get('Title','')}")
            print(f"Author  : {sauce.get('Author','')}")
            print(f"Group   : {sauce.get('Group','')}")
            print(f"Date    : {sauce.get('Date','')}")
            print(f"FileSize: {sauce.get('FileSize','')}")
            if sauce.get('Comments'):
                print("Comments:")
                for line in sauce['Comments']:
                    print(f"  {line}")
        else:
            print("No SAUCE metadata found.")
        return

    if args.cat:
        sys.stdout.buffer.write(core)
        sys.stdout.flush()
        return

    text = core.decode('cp437', errors='replace')
    lines = cp437_to_unicode_preserve_ansi(text).splitlines()
    interactive_view(lines)

if __name__=='__main__':
    main()

