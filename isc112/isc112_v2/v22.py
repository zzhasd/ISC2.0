"""Current repair release, using the shared versioned replay/evaluation implementation."""
import sys
from . import v21
from . import core_v22
from .runner import ROOT


def main():
    v21.OUT = ROOT / 'results/isc112_v22'
    v21.DATA = ROOT / 'data/isc112_v22'
    v21.ARM = 'evidence_dual_on_v22'
    v21.VERSION = '2.2'
    v21.PROTOCOL = 'ISC112_V22_PROTOCOL.md'
    v21.RENDER = core_v22.render
    v21.EXTRA_CODE = ['isc112_v2/core_v22.py', 'isc112_v2/v22.py']
    v21.main()


if __name__ == '__main__': main()
