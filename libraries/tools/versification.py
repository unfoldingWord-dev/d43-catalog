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
    def __init__(self, ref, c, v, delete=False, early=False, split=False, count=1, psalm_heading=0):
        self.early = early
        self.delete = delete
        self.ref = ref
        self.c = c
        self.v = v
        self.count = count
        self.psalm_heading = psalm_heading
        self.split = split


def hebrew_to_ufw(b, c, v, from_original=True):
    """
    Converts a hebrew reference to a ufw reference.
    :param b: book of the bible
    :param c: chapter number
    :param v: verse number
    :param from_original: indicates if we are converting the versification from the original language i.e. Hebrew.
    :return: the ufw reference. Or, if `from_original` is False, the hebrew reference
    """
    ref = Ref(b, c, v)
    if b == 'gen':
        # chapter break gen 31:55
        if c == 31 or c == 32:
            break_chapter(Opt(early=from_original is False, ref=ref, c=31, v=55))
    if b == 'exo':
        # chapter break exo 7:26
        if c == 7 or c == 8:
            break_chapter(Opt(early=from_original is True, ref=ref, c=7, v=26, count=4))
        # verse split exo 20:13
        if c == 20 or v == 13:
            split_verse(Opt(split=from_original is True, ref=ref, c=20, v=13, count=3))
        # chapter break exo 21:37
        if c == 21 or c == 22:
            break_chapter(Opt(early=from_original is True, ref=ref, c=21, v=37))
    if b == 'lev':
        # chapter break lev 5:20
        if c == 5 or c == 6:
            break_chapter(Opt(early=from_original is True, ref=ref, c=5, v=20, count=7))
    if b == 'num':
        # chapter break num 16:36
        if c == 16 or c == 17:
            break_chapter(Opt(early=from_original is False, ref=ref, c=16, v=36, count=15))
        # chapter break num 29:40
        if c == 29 or c == 30:
            break_chapter(Opt(early=from_original is False, ref=ref, c=29, v=40))
    if b == 'deu':
        # chapter break deu 12:32
        if c == 12 or c == 13:
            break_chapter(Opt(early=from_original is False, ref=ref, c=12, v=32))
        # chapter break deu 22:30
        if c == 22 or c == 23:
            break_chapter(Opt(early=from_original is False, ref=ref, c=22, v=30))
        # chapter break deu 28:69
        if c == 28 or c == 29:
            break_chapter(Opt(early=from_original is True, ref=ref, c=28, v=69))
    if b == '1sa':
        # verse split across a chapter break 1sa 20:42
        if c == 20 or c == 21:
            split_verse_across_chapters(Opt(split=from_original is False, ref=ref, c=20, v=42))
        # chapter break 1sa 23:29
        if c == 23 or c == 24:
            break_chapter(Opt(early=from_original is False, ref=ref, c=23, v=29))
    if b == '2sa':
        # chapter break 2sa 18:33
        if c == 18 or c == 19:
            break_chapter(Opt(early=from_original is False, ref=ref, c=18, v=33))
    if b == '1ki':
        # chapter break 1ki 4:21
        if c == 4 or c == 5:
            break_chapter(Opt(early=from_original is False, ref=ref, c=4, v=21, count=14))
        # verse split 1ki 22:43
        if c == 22:
            split_verse(Opt(split=from_original is False, ref=ref, c=22, v=43))
    if b == '2ki':
        # chapter break 2ki 11:21
        if c == 11 or c == 12:
            break_chapter(Opt(early=from_original is False, ref=ref, c=11, v=21))
    if b == '1ch':
        # chapter break 1ch 5:27
        if c == 5 or c == 6:
            break_chapter(Opt(early=from_original is True, ref=ref, c=5, v=27, count=15))
        # verse split 1ch 12:4
        if c == 12:
            split_verse(Opt(split=from_original is False, ref=ref, c=12, v=4))
    if b == '2ch':
        # chapter break 2ch 1:8
        if c == 1 or c == 2:
            break_chapter(Opt(early=from_original is True, ref=ref, c=1, v=18))
        # chapter break 2ch 13:23
        if c == 13 or c == 14:
            break_chapter(Opt(early=from_original is True, ref=ref, c=13, v=23))
    if b == 'neh':
        # chapter break neh 3:33
        if c == 3 or c == 4:
            break_chapter(Opt(early=from_original is True, ref=ref, c=3, v=33, count=6))
        # verse split neh 7:67
        if c == 7:
            # NOTE: we don't currently support splitting into ufw e.g. Neh.7.67-Neh.7.68
            # split_verse(Opt(split=True, ref=ref, c=7, v=67))
            pass
        # chapter break neh 9:38
        if c == 9 or c == 10:
            break_chapter(Opt(early=from_original is False, ref=ref, c=9, v=38))
    if b == 'job':
        # chapter break job 40:25
        if c == 40 or c == 41:
            break_chapter(Opt(early=from_original is True, ref=ref, c=40, v=25, count=8))
    if b == 'psa':
        # delete psa heading 1 verse
        chapters = [3, 4, 5, 6, 7, 8, 9, 12, 13, 18, 19, 20, 21, 22, 30, 31, 34, 36, 38, 39, 40, 41, 42, 44, 45, 46, 47,
                    48, 49, 53, 55, 56, 57, 58, 59, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 75, 76, 77, 80, 81, 83, 84,
                    85, 88, 89, 92, 102, 108, 140, 142]
        if c in chapters:
            delete_verse(Opt(delete=from_original is True, ref=ref, c=c, v=1))
        # delete psa heading 2 verses
        chapters = [51, 52, 54, 60]
        if c in chapters:
            delete_verse(Opt(delete=from_original is True, ref=ref, c=c, v=1, count=2))
        # verse split psa 13:6
        if c == 13:
            # NOTE: we don't currently support splitting into ufw e.g. Ps.13.5-Ps.13.6
            # split_verse(Opt(split=True, ref=ref, c=13, v=6, psalm_heading=1))
            pass
        # verse split psa 66:2
        if c == 66:
            # NOTE: we don't currently support splitting into ufw e.g. Ps.66.1-Ps.66.2
            # split_verse(Opt(split=True, ref=ref, c=66, v=2, psalm_heading=1))
            pass
    if b == 'ecc':
        # chapter break ecc 4:17
        if c == 4 or c == 5:
            break_chapter(Opt(early=from_original is True, ref=ref, c=4, v=17))
    if b == 'sng':
        # chapter break sng 6:13
        if c == 6 or c == 7:
            break_chapter(Opt(early=from_original is False, ref=ref, c=6, v=13))
    if b == 'isa':
        # chapter break isa 8:32
        if c == 8 or c == 9:
            break_chapter(Opt(early=from_original is True, ref=ref, c=8, v=23))
        # verse split across a chapter break isa 63:19
        if c == 63 or c == 64:
            # NOTE: we don't currently support splitting into ufw e.g. Isa.63.19-Isa.64.1
            # split_verse_across_chapters(Opt(split=True, ref=ref, c=63, v=19))
            pass
    if b == 'jer':
        # chapter break jer 8:23
        if c == 8 or c == 9:
            break_chapter(Opt(early=from_original is True, ref=ref, c=8, v=23))
    if b == 'ezk':
        # chapter break ezk 20:45
        if c == 20 or c == 21:
            break_chapter(Opt(early=from_original is False, ref=ref, c=20, v=45, count=5))
    if b == 'dan':
        # chapter break dan 3:31
        if c == 3 or c == 4:
            break_chapter(Opt(early=from_original is True, ref=ref, c=3, v=31, count=3))
        # chapter break dan 5:31
        if c == 5 or c == 6:
            break_chapter(Opt(early=from_original is False, ref=ref, c=5, v=31))
    if b == 'hos':
        # chapter break hos 1:10
        if c == 1 or c == 2:
            break_chapter(Opt(early=from_original is False, ref=ref, c=1, v=10, count=2))
        # chapter break hos 11:12
        if c == 11 or c == 12:
            break_chapter(Opt(early=from_original is False, ref=ref, c=11, v=12))
        # chapter break hos 13:16
        if c == 13 or c == 14:
            break_chapter(Opt(early=from_original is False, ref=ref, c=13, v=16))
    if b == 'jol':
        # chapter split jol 2:28
        if c >= 2:
            split_chapter(Opt(early=from_original is False, ref=ref, c=2, v=28))
    if b == 'jon':
        # chapter break jon 1:17
        if c == 1 or c == 2:
            break_chapter(Opt(early=from_original is False, ref=ref, c=1, v=17))
    if b == 'mic':
        # chapter break mic 4:14
        if c == 4 or c == 5:
            break_chapter(Opt(early=from_original is True, ref=ref, c=4, v=14))
    if b == 'nah':
        # chapter break nah 1:15
        if c == 1 or c == 2:
            break_chapter(Opt(early=from_original is False, ref=ref, c=1, v=15))
    if b == 'zec':
        # chapter break zec 1:18
        if c == 1 or c == 2:
            break_chapter(Opt(early=from_original is False, ref=ref, c=1, v=18, count=4))
    if b == 'mal':
        # chapter break mal 3:19
        if c >= 3:
            break_chapter(Opt(early=from_original is True, ref=ref, c=3, v=19))
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


def delete_verse(opt):
    """
    Handle verses which are completely deleted
    :return:
    """
    pass
