"""ISC113: the frozen DailyDialog A-to-B experiment."""
import argparse

def main():
    p=argparse.ArgumentParser()
    p.add_argument('action',choices=['prepare','export','match','analyze','reproduce','check'])
    p.add_argument('--run-id',help='New run only; omit for the frozen historical experiment')
    a=p.parse_args()
    if a.run_id is not None and a.action not in ['export','match','analyze']:p.error('--run-id applies to export, match and analyze')
    if a.action=='prepare':
        from .run import prepare_inputs
        print({'primary_inputs':len(prepare_inputs()),'frozen_inputs':len(prepare_inputs(scope='all300'))})
    elif a.action=='export':
        from .export import export
        print(export('dailydialog',a.run_id))
    elif a.action=='match':
        from .evaluation import match_dataset
        print(match_dataset('dailydialog',run_id=a.run_id))
    elif a.action=='analyze':
        from .evaluation import analyze
        print(analyze('dailydialog',run_id=a.run_id))
    elif a.action=='reproduce':
        from .reproduction import reproduce
        print(reproduce())
    else:
        import unittest
        from . import test_science,test_reference_adapter,test_interfaces
        suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromModule(m)
                                  for m in [test_science,test_reference_adapter,test_interfaces])
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        from .common import BASE,save
        save(BASE/'results/interface_test_report.json',{'tests_run':result.testsRun,
            'passed':result.wasSuccessful(),'failures':len(result.failures),'errors':len(result.errors),
            'transport':'mocked HTTP contract tests plus recorded provider response replay',
            'live_provider_called':False})
        if not result.wasSuccessful():raise SystemExit(1)
        from .reproduction import reproduce
        print(reproduce())

if __name__=='__main__':main()
