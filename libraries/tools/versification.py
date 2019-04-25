# This was inspired by https://github.com/curiousdannii/reversify


class Ref:
    def __init__(self, b, c, v):
        self.b = b
        self.c = c
        self.v = v

    def to_dict(self):
        return {
            'book': self.b,
            'chapter': self.c,
            'verse': self.v
        }


class Opt:
    def __init__(self, early, ref, c, v, count=1, psalm_heading=0, split=False):
        self.early = early
        self.ref = ref
        self.c = c
        self.v = v
        self.count = count
        self.psalm_heading = psalm_heading
        self.split = split


def hebrew_to_ufw(b, c, v, from_original=True):
    """
    Converts hebrew versification to ufw versification.
    :param b: book string
    :param c: chapter number
    :param v: verse number
    :param from_original: indicates if we are converting the versification from the original language.
    :return: the ufw version of the reference. Or, if `from_original` is False, the hebrew version
    """
    ref = Ref(b, c, v)
    if b == 'gen':
        # chapter break gen 31:55
        if c == 31 or c == 32:
            break_chapter(Opt(early=False, ref=ref, c=31, v=55))
    if b == 'exo':
        # chapter break exo 7:26
        if c == 7 or c == 8:
            break_chapter(Opt(early=True, ref=ref, c=7, v=26, count=4))
        # verse split exo 20:13
        if c == 20 or v == 13:
            split_verse(Opt(early=False, split=True, ref=ref, c=20, v=13, count=3))
        # chapter break exo 21:37
        if c == 21 or c == 22:
            break_chapter(Opt(early=True, ref=ref, c=21, v=37))
    if b == 'lev':
        # chapter break lev 5:20
        if c == 5 or c == 6:
            break_chapter(Opt(early=True, ref=ref, c=5, v=20, count=7))
    if b == 'num':
        # chapter break num 16:36
        if c == 16 or c == 17:
            break_chapter(Opt(early=False, ref=ref, c=16, v=36, count=15))
        # chapter break num 29:40
        if c == 29 or c == 30:
            break_chapter(Opt(early=False, ref=ref, c=29, v=40))
    if b == 'deu':
        # chapter break deu 12:32
        if c == 12 or c == 13:
            break_chapter(Opt(early=False, ref=ref, c=12, v=32))
        # chapter break deu 22:30
        if c == 22 or c == 23:
            break_chapter(Opt(early=False, ref=ref, c=22, v=30))
        # chapter break deu 28:69
        if c == 28 or c == 29:
            break_chapter(Opt(early=True, ref=ref, c=28, v=69))
    if b == '1sa':
        # verse split across a chapter break 1sa 20:42
        if c == 20 or c == 21:
            split_verse_across_chapters(Opt(early=False, split=False, ref=ref, c=20, v=42))
        # chapter break 1sa 23:29
        if c == 23 or c == 24:
            break_chapter(Opt(early=False, ref=ref, c=23, v=29))
    if b == '2sa':
        # chapter break 2sa 18:33
        if c == 18 or c == 19:
            break_chapter(Opt(early=False, ref=ref, c=18, v=33))
    if b == '1ki':
        # chapter break 1ki 4:21
        if c == 4 or c == 5:
            break_chapter(Opt(early=False, ref=ref, c=4, v=21, count=14))
        # verse split 1ki 22:43
        if c == 22:
            split_verse(Opt(early=False, split=False, ref=ref, c=22, v=43))
    if b == '2ki':
        # chapter break 2ki 11:21
        if c == 11 or c == 12:
            break_chapter(Opt(early=False, ref=ref, c=11, v=21))
    if b == '1ch':
        # chapter break 1ch 5:27
        if c == 5 or c == 6:
            break_chapter(Opt(early=True, ref=ref, c=5, v=27, count=15))
        # verse split 1ch 12:4
        if c == 12:
            split_verse(Opt(early=False, split=False, ref=ref, c=12, v=4))
    if b == '2ch':
        # chapter break 2ch 1:8
        if c == 1 or c == 2:
            break_chapter(Opt(early=True, ref=ref, c=1, v=18))
        # chapter break 2ch 13:23
        if c == 13 or c == 14:
            break_chapter(Opt(early=True, ref=ref, c=13, v=23))
    if b == 'neh':
        # chapter break neh 3:33
        if c == 3 or c == 4:
            break_chapter(Opt(early=True, ref=ref, c=3, v=33, count=6))
        # verse split neh 7:67
        if c == 7:
            # NOTE: we don't currently support splitting into ufw e.g. Neh.7.67-Neh.7.68
            # split_verse(Opt(early=False, split=True, ref=ref, c=7, v=67))
            pass
        # chapter break neh 9:38
        if c == 9 or c == 10:
            break_chapter(Opt(early=False, ref=ref, c=9, v=38))
    if b == 'job':
        # chapter break job 40:25
        if c == 40 or c == 41:
            break_chapter(Opt(early=True, ref=ref, c=40, v=25, count=8))
    if b == 'psa':
        pass
    if b == 'ecc':
        pass
    if b == 'sng':
        pass
    if b == 'isa':
        pass
    if b == 'jer':
        pass
    if b == 'ezk':
        pass
    if b == 'dan':
        pass
    if b == 'hos':
        pass
    if b == 'jol':
        # chapter split jol 2:28
        if c >= 2:
            split_chapter(Opt(early=False, ref=ref, c=2, v=28))
    if b == 'jon':
        pass
    if b == 'mic':
        pass
    if b == 'nah':
        pass
    if b == 'zec':
        pass
    if b == 'mal':
        pass
    return ref


def break_chapter(opt):
    """
    Insert an early chapter break
    :return:
    """
    if opt.early:
        if opt.ref.c == opt.c and opt.ref.v >= opt.v:
            opt.ref.c += 1
            opt.ref.v -= opt.v - 1
        elif opt.ref.c == opt.c + 1:
            opt.ref.v += opt.count
    else:
        if opt.ref.c == opt.c + 1:
            opt.ref.v -= opt.count
            if opt.ref.v < 1:
                opt.ref.c -= 1
                opt.ref.v += opt.v + opt.count - 1


def split_chapter(opt):
    """
    Split a chapter in two
    :return:
    """
    if opt.early:
        if opt.ref.c == opt.c and opt.ref.v >= opt.v:
            opt.ref.c += 1
            opt.ref.v -= opt.v - 1
        elif opt.ref.c > opt.c:
            opt.ref.c += 1
    else:
        if opt.ref.c > opt.c:
            opt.ref.c -= 1
            if opt.ref.c == opt.c:
                opt.ref.v += opt.v - 1


def split_verse(opt):
    """
    Split a verse in two
    :return:
    """
    if opt.split:
        # split the verse
        opt.v -= opt.psalm_heading
        if opt.ref.c == opt.c and opt.ref.v > opt.v:
            opt.ref.v += opt.count
    else:
        # join them back together
        if opt.ref.c == opt.c and opt.ref.v >= opt.v + 1:
            opt.ref.v -= opt.count


def split_verse_across_chapters(opt):
    """
    Split a verse in two across a chapter break
    :return:
    """
    if opt.split:
        # split the verse
        if opt.ref.c == opt.c and opt.ref.v > opt.v:
            opt.ref.c += 1
            opt.ref.v = 1
        elif opt.ref.c == opt.c + 1:
            opt.ref.v += 1
    else:
        # join them back together
        if opt.ref.c == opt.c + 1 and opt.ref.v == 1:
            opt.ref.c = opt.c
            opt.ref.v = opt.v
        if opt.ref.c == opt.c + 1:
            opt.ref.v -= 1


def delete_verse():
    """
    Handle verses which are completely deleted
    :return:
    """
    pass

