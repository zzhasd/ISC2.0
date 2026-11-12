"""Usage: python -m isc112 [all|prepare|analyze|plot|report|check]. Never calls an API."""
import argparse
import json
from . import data, analysis, plots

def main():
    parser = argparse.ArgumentParser(description='112段完整自然对话的统一离线统计与论文绘图；不调用模型API。')
    parser.add_argument('action', nargs='?', default='all', choices=['all', 'prepare', 'analyze', 'plot', 'report', 'check'])
    action = parser.parse_args().action
    result = {}
    if action in ['all', 'prepare']:
        result['prepare'] = data.prepare()
    if action in ['all', 'analyze']:
        result['analyze'] = analysis.analyze()
    if action in ['all', 'plot']:
        result['plot'] = plots.plot()
    if action in ['all', 'report']:
        from .report import report
        result['report'] = report()
    if action in ['all', 'check']:
        from .validation import validate
        result['check'] = validate()
    print(json.dumps(result, ensure_ascii=True, indent=2))

if __name__ == '__main__':
    main()
