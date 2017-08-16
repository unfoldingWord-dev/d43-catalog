#!/usr/bin/env python2
# -*- coding: utf-8 -*-

"""
This script allows you to run a compatible tool in the tools/ dir.

Usage: python execute.py csvtousfm3
"""

from __future__ import unicode_literals
import sys

if __name__ == '__main__':
    args = sys.argv
    args.pop(0)

    if len(args) > 0:
        cmd = args[0]
        if cmd[-3:] != '.py':
            cmd += '.py'

        with open('tools/' + cmd) as f:
            code = compile(f.read(), cmd, 'exec')
            exec(code)
