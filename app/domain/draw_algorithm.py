import random
from collections.abc import Iterable, Sequence


def find_assignment(
    participant_ids: Sequence[int],
    exclusions: Iterable[tuple[int, int]],
    rng: random.Random | random.SystemRandom | None = None,
) -> dict[int, int] | None:
    """Find a complete derangement using randomized augmenting paths."""
    if len(set(participant_ids)) != len(participant_ids):
        raise ValueError("Participant IDs must be unique")

    participant_set = set(participant_ids)
    forbidden: set[tuple[int, int]] = set()
    for first, second in exclusions:
        if first == second:
            raise ValueError("An exclusion cannot contain the same participant twice")
        if first not in participant_set or second not in participant_set:
            raise ValueError("Exclusions must refer to participants in this draw")
        forbidden.add((first, second))
        forbidden.add((second, first))

    if len(participant_ids) < 2:
        return None

    randomizer = rng or random.SystemRandom()
    candidates: dict[int, list[int]] = {}
    for giver in participant_ids:
        allowed = [
            receiver
            for receiver in participant_ids
            if receiver != giver and (giver, receiver) not in forbidden
        ]
        randomizer.shuffle(allowed)
        candidates[giver] = allowed

    receiver_to_giver: dict[int, int] = {}

    def augment(giver: int, seen_receivers: set[int]) -> bool:
        for receiver in candidates[giver]:
            if receiver in seen_receivers:
                continue
            seen_receivers.add(receiver)
            previous_giver = receiver_to_giver.get(receiver)
            if previous_giver is None or augment(previous_giver, seen_receivers):
                receiver_to_giver[receiver] = giver
                return True
        return False

    giver_order = list(participant_ids)
    randomizer.shuffle(giver_order)
    for giver in giver_order:
        if not augment(giver, set()):
            return None

    assignment = {giver: receiver for receiver, giver in receiver_to_giver.items()}
    if len(assignment) != len(participant_ids):
        return None
    return assignment
