

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


def hebrew_to_ufw(b, c, v):
    """

    :param b: book string
    :param c: chapter number
    :param v: verse number
    :return: the ufw version of the reference
    """
    ref = Ref(b, c, v)
    if b == 'gen':
        pass
    if b == 'exo':
        pass
    if b == 'lev':
        pass
    if b == 'num':
        pass
    if b == 'deu':
        pass
    if b == 'jos':
        pass
    if b == '1sa':
        pass
    if b == '2sa':
        pass
    if b == '1ki':
        pass
    if b == '2ki':
        pass
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

