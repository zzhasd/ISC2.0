"""Utilities for explicit current-assistant decisions, never inference or automatic grading."""
from .evaluation import decision, record_batch
from .runner import OUT, read


class Batch:
    def __init__(self, number, folder='review_packets', output_dir=None):
        self.number = number
        self.folder = folder
        self.output_dir = output_dir or OUT
        self.rows = {r['index']: r for d in read(self.output_dir / f'{folder}/packet_{number:02d}.json') for r in d['review_rows']}
        self.decisions = {}

    def put(self, indices, kind, refs=(), reason='', ground=True, source='consistent', canonical=None, core=None):
        if isinstance(indices, int): indices = [indices]
        if isinstance(refs, str): refs = [refs]
        for i in indices:
            assert i in self.rows and i not in self.decisions, i
            did = self.rows[i]['dialogue_id']
            ids = [did + '_' + r for r in refs]
            self.decisions[i] = decision(kind, ids, reason, ground, source, did + '_' + canonical if canonical else None,
                [did + '_' + x for x in core] if core is not None else None)

    def m(self, indices, refs, reason='Same frozen information, value, participants and time/modality are expressed; visible A supports the claim.'):
        self.put(indices, 'match', refs, reason)

    def p(self, indices, refs, reason, ground=True, source='consistent'):
        self.put(indices, 'partial', refs, reason, ground, source)

    def u(self, indices, reason, source='unverified'):
        self.put(indices, 'unverified', reason=reason, ground=False, source=source)

    def s(self, indices, reason, ground=False, source='consistent'):
        self.put(indices, 'out_of_scope', reason=reason, ground=ground, source=source)

    def n(self, indices, canonical, reason):
        self.put(indices, 'supported_new', reason=reason, canonical=canonical)

    def finish(self): return record_batch(self.number, self.decisions, self.folder, self.output_dir)
