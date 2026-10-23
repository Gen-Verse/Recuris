"""The deterministic discipline layer: four gates, all of them code.

Nothing here consults a model, and nothing here can be talked round. A model
proposes; whether the proposal is kept is decided by arithmetic over held-out
outcomes. That asymmetry is the load-bearing part of the whole system, so it
lives in one small file that can be read end to end.

1. ``held_out_paired_gate`` -- paired significance on the held-out split. This
   is the only admission gate.
2. ``leakage_check`` -- the red line: a card may not contain test-set answers.
3. ``fingerprint_verify`` -- the prescribed mechanism must actually have fired,
   so that a change which merely captured the output format cannot claim the
   improvement it did not cause.
4. ``Ledger`` -- the do-not-repeat record.
"""
import math
import random
import statistics
from dataclasses import dataclass, field


@dataclass
class Verdict:
    accept: bool
    net: float
    ci: tuple
    n_improved: int
    n_regressed: int
    reason: str


def held_out_paired_gate(base, cand, alpha=0.05, reg_cap=0, eps=1e-9,
                         n_boot=3000, seed=0, material=0.0):
    """Paired held-out significance test. This is the admission gate.

    ``base`` and ``cand`` map an item id to the list of its per-seed scores.
    A binary benchmark gives 0/1, a dense-reward benchmark gives floats in
    [0, 1]; the estimator is continuous either way, so one implementation
    serves both.

    Per item, take the mean over seeds, then the difference ``d_i`` between the
    candidate and the base. Bootstrap over *items*, not over trials: trials
    within an item are not independent, and resampling them would report an
    interval far narrower than the evidence supports.

    ACCEPT iff the interval excludes zero on the improving side and the number
    of regressed items is at most ``reg_cap``.

    ``material`` is how large a per-item difference has to be before it counts
    as an improvement or a regression. The default 0.0 leaves the threshold at
    ``eps``, so binary callers are unaffected. Raise it for dense rewards:
    otherwise noise of the 0.97-to-0.95 kind lands in ``n_dn``, and since
    ``reg_cap`` is a hard rejection condition, counting noise there turns the
    gate into a coin flip.
    """
    # A paired admission test cannot drop missing items or admit invalid scores.
    # Both benchmark variants promise per-seed values in the unit interval.
    def valid(matrix):
        return isinstance(matrix, dict) and all(
            isinstance(scores, (list, tuple)) and scores
            and all(type(score) in (int, float) and math.isfinite(score)
                    and 0 <= score <= 1 for score in scores)
            for scores in matrix.values()
        )

    if not valid(base) or not valid(cand) or set(base) != set(cand):
        return Verdict(False, 0.0, (0.0, 0.0), 0, 0,
                       "invalid or unpaired held-out scores")
    items = sorted(base)
    diffs = [statistics.mean(cand[i]) - statistics.mean(base[i]) for i in items]
    if not diffs:
        return Verdict(False, 0.0, (0.0, 0.0), 0, 0, "no comparable items")
    net = statistics.mean(diffs)
    floor = max(eps, material)
    n_up = sum(1 for x in diffs if x > floor)
    n_dn = sum(1 for x in diffs if x < -floor)
    rng = random.Random(seed)
    boots = sorted(statistics.mean([diffs[rng.randrange(len(diffs))] for _ in diffs])
                   for _ in range(n_boot))
    lo = boots[int((alpha / 2) * n_boot)]
    hi = boots[int((1 - alpha / 2) * n_boot) - 1]
    accept = (lo > 0) and (n_dn <= reg_cap)
    if accept:
        reason = "net improvement, CI excludes 0"
    elif lo <= 0:
        reason = "CI includes 0: not significant"
    else:
        reason = f"{n_dn} regressed items exceeds the cap of {reg_cap}"
    return Verdict(accept, round(net, 4), (round(lo, 4), round(hi, 4)), n_up, n_dn, reason)


def leakage_check(card, test_gold_params):
    """False if the card body contains any test-set answer parameter.

    Syntactic and deliberately crude. It cannot catch a paraphrased answer, and
    it is not the only defence -- the held-out split is -- but it makes the
    obvious form of leakage impossible to commit by accident.
    """
    body = (card.get("body") or "").lower()
    return not any(str(g).lower() in body for g in test_gold_params)


def fingerprint_verify(cand_results, prescription):
    """False unless the prescribed carrier fired at least once.

    Without this, a change that improved the score for an unrelated reason --
    or by capturing the output format -- would be credited to the mechanism it
    claimed to fix, and the next round would build on a false diagnosis.
    """
    return cand_results.fingerprint.get(prescription.carrier.value, 0) > 0


@dataclass
class Ledger:
    accepted: list = field(default_factory=list)   # [key]
    rejected: list = field(default_factory=list)   # [(key, reason)]
    untreatable: set = field(default_factory=set)  # {cluster_id}

    @staticmethod
    def key(rx):
        return (rx.cluster_id, rx.carrier.value, rx.primitive)

    def is_repeat(self, rx):
        k = self.key(rx)
        return k in self.accepted or any(k == rk for rk, _ in self.rejected)

    def accept(self, rx, verdict):
        self.accepted.append(self.key(rx))

    def reject(self, rx, reason):
        self.rejected.append((self.key(rx), reason))

    def note_untreatable(self, cluster):
        self.untreatable.add(cluster.id)
