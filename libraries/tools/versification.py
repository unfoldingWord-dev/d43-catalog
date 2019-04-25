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
        pass
    if b == 'jos':
        pass
    if b == '1sa':
        pass
    if b == '2sa':
        # chapter break 2sa 18:33
        if c == 18 or c == 19:
            break_chapter(Opt(early=False, ref=ref, c=18, v=33))
    if b == '1ki':
        pass
    if b == '2ki':
        # chapter break 2ki 11:21
        if c == 11 or c == 12:
            break_chapter(Opt(early=False, ref=ref, c=11, v=21))
    if b == '1ch':
        pass
    if b == '2ch':
        pass
    if b == 'neh':
        pass
    if b == 'job':
        pass
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

