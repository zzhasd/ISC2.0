"""Dialogue-clustered exploratory inference and duplicate-safe semantic matching."""
import random
import statistics

SEED = 20261101
REPLICATES = 3000

def maximum_match(edges):
    assigned = {}
    def add(i, seen):
        for fact in edges[i]:
            if fact in seen:
                continue
            seen.add(fact)
            if fact not in assigned or add(assigned[fact], seen):
                assigned[fact] = i
                return True
        return False
    for i in range(len(edges)):
        add(i, set())
    return set(assigned)

def bootstrap_mean(values, seed=SEED):
    if not values:
        return None
    rng = random.Random(seed); n = len(values)
    samples = sorted(statistics.mean(rng.choices(values, k=n)) for _ in range(REPLICATES))
    return {'mean': statistics.mean(values), 'low': samples[74], 'high': samples[2924], 'dialogues': n}

def bootstrap_ratio(numerators, denominators, seed=SEED):
    """Micro ratio of sums, resampling paired dialogue contributions together."""
    assert len(numerators) == len(denominators)
    n = len(numerators); den = sum(denominators)
    if not den:
        return None
    rng = random.Random(seed); pairs = list(zip(numerators, denominators)); samples = []
    for _ in range(REPLICATES):
        drawn = rng.choices(pairs, k=n); d = sum(p[1] for p in drawn)
        if d:
            samples.append(sum(p[0] for p in drawn) / d)
    samples.sort()
    return {'estimate': sum(numerators) / den, 'low': samples[int(.025 * len(samples))],
            'high': samples[min(len(samples) - 1, int(.975 * len(samples)))], 'dialogues': n,
            'numerator': sum(numerators), 'denominator': den}
