import evaluator_io as e

def f(claim, level, slots, members):
    return (claim,level,[(f's{i}',n,v,c) for i,(n,v,c) in enumerate(slots,1)],[(i,[f's{j}' for j in ids]) for i,ids in members])
def simple(claim, level, indices):
    return f(claim,level,[('relation',claim,True)],[(i,[1]) for i in indices])
