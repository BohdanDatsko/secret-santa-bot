import itertools
import random

import pytest

from app.domain.draw_algorithm import find_assignment


def _brute_force_exists(participants: list[int], exclusions: set[tuple[int, int]]) -> bool:
    forbidden = exclusions | {(second, first) for first, second in exclusions}
    return any(
        all(
            giver != receiver and (giver, receiver) not in forbidden
            for giver, receiver in zip(participants, receivers)
        )
        for receivers in itertools.permutations(participants)
    )


def test_assignment_respects_all_invariants() -> None:
    participants = [11, 12, 13, 14, 15]
    exclusions = {(11, 12), (13, 15)}

    assignment = find_assignment(participants, exclusions, random.Random(12))

    assert assignment is not None
    assert set(assignment) == set(participants)
    assert set(assignment.values()) == set(participants)
    assert all(giver != receiver for giver, receiver in assignment.items())
    assert all(
        (giver, receiver) not in exclusions and (receiver, giver) not in exclusions
        for giver, receiver in assignment.items()
    )


def test_two_participant_exclusion_makes_draw_impossible() -> None:
    assert find_assignment([1, 2], {(1, 2)}, random.Random(1)) is None


def test_impossible_draw_returns_none() -> None:
    assert find_assignment([1], set(), random.Random(1)) is None


@pytest.mark.parametrize("participant_count", [2, 3, 4])
def test_matching_agrees_with_exhaustive_search(participant_count: int) -> None:
    participants = list(range(participant_count))
    possible_pairs = list(itertools.combinations(participants, 2))
    for mask in range(1 << len(possible_pairs)):
        exclusions = {pair for index, pair in enumerate(possible_pairs) if mask & (1 << index)}
        result = find_assignment(participants, exclusions, random.Random(mask))
        assert (result is not None) == _brute_force_exists(participants, exclusions)


def test_duplicate_ids_and_invalid_exclusions_are_rejected() -> None:
    with pytest.raises(ValueError, match="unique"):
        find_assignment([1, 1], set())
    with pytest.raises(ValueError, match="same participant"):
        find_assignment([1, 2], {(1, 1)})
    with pytest.raises(ValueError, match="refer to participants"):
        find_assignment([1, 2], {(1, 3)})
