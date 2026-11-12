import unittest
from isc112_v3.guarded import still_accepted,attributed_B_guard


class GuardedTests(unittest.TestCase):
    def test_acceptance_backup_respects_abstention(self):
        item={'holder':'B','scope':'profile','status':'active','support':'explicit','duplicate_of':'b2'}
        self.assertTrue(still_accepted(item))
        self.assertFalse(still_accepted({**item,'support':'unknown'}))
        self.assertFalse(still_accepted({**item,'holder':'A'}))

    def test_observer_and_target_guard_is_source_bound(self):
        old={'claim':"B's condition is described by A as relaxed",'evidence_turns':[1]}
        revised={**old,'holder':'A'}
        self.assertTrue(attributed_B_guard(old,revised,[{'turn':1,'text':'You seem relaxed.'}]))
        self.assertFalse(attributed_B_guard(old,revised,[{'turn':1,'text':'Do you seem relaxed?'}]))
        self.assertFalse(attributed_B_guard(old,revised,[{'turn':1,'text':'You seem relaxed.'},{'turn':3,'text':'You seem upset now.'}]))
        self.assertFalse(attributed_B_guard(old,{**revised,'claim':'A is relaxed'},[{'turn':1,'text':'You seem relaxed.'}]))


if __name__=='__main__':unittest.main()
