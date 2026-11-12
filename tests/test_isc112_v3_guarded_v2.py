import unittest
from isc112_v3.guarded_v2 import normalize_observation
from isc112_v3.guarded import attributed_B_guard


class MorphologyTests(unittest.TestCase):
    def test_progressive_forms_preserve_observed_target(self):
        for text in ["You're sounding healthy.",'You are seeming relaxed.','You ’ re looking confident.']:
            normalized=normalize_observation(text)
            old={'claim':"B's condition is described by A as positive",'evidence_turns':[1]}
            self.assertTrue(attributed_B_guard(old,{**old,'holder':'A'},[{'turn':1,'text':normalized}]))

    def test_question_and_conditional_are_still_not_assertions(self):
        old={'claim':"B's condition is described by A as positive",'evidence_turns':[1]}
        for text in ['Are you looking relaxed?','If you are looking relaxed, stay that way.']:
            self.assertFalse(attributed_B_guard(old,{**old,'holder':'A'},[{'turn':1,'text':normalize_observation(text)}]))


if __name__=='__main__':unittest.main()
