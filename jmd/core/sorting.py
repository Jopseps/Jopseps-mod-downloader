# Copyright (C) 2025-2026 Yusuf Mert Turan
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Load-order auto-sort: stable topological sort over loadAfter / loadBefore / dependencies."""
import heapq


def _edges(order, entries, tier):
    """{uid: set(uids that must come after it)} among the active mods only. Rules that would pull a mod
    ahead of a lower tier (e.g. something 'loadBefore' Core) are dropped: pinned tiers always win."""
    present = set(order)
    after = {u: set() for u in order}

    def add(first, then):
        if first in present and then in present and first != then and tier(first) <= tier(then):
            after[first].add(then)

    for uid in order:
        e = entries.get(uid)
        if not e:
            continue
        for other in e.load_after:
            add(other, uid)
        for dep in e.deps:
            add(dep.uid, uid)
        for other in e.load_before:
            add(uid, other)
    return after


def _cycles(nodes, after):
    """Strongly connected components with more than one mod (Tarjan, iterative)."""
    index, low, on, stack, out = {}, {}, set(), [], []
    counter = [0]
    for root in nodes:
        if root in index:
            continue
        work = [(root, iter(sorted(after[root])))]
        index[root] = low[root] = counter[0]
        counter[0] += 1
        stack.append(root)
        on.add(root)
        while work:
            node, it = work[-1]
            nxt = next(it, None)
            if nxt is not None:
                if nxt not in index:
                    index[nxt] = low[nxt] = counter[0]
                    counter[0] += 1
                    stack.append(nxt)
                    on.add(nxt)
                    work.append((nxt, iter(sorted(after[nxt]))))
                elif nxt in on:
                    low[node] = min(low[node], index[nxt])
                continue
            work.pop()
            if work:
                low[work[-1][0]] = min(low[work[-1][0]], low[node])
            if low[node] == index[node]:
                comp = []
                while True:
                    w = stack.pop()
                    on.discard(w)
                    comp.append(w)
                    if w == node:
                        break
                if len(comp) > 1:
                    out.append(comp)
    return out


def topo_sort(order, entries, tier=lambda uid: 0):
    """Sort active uids so every rule holds, moving as little as possible: among mods that are free to go,
    the lower tier and then the earlier current position wins. Cycles keep the user's order.
    → (new order, [[uids in a cycle], …])"""
    order = list(dict.fromkeys(order))
    pos = {u: i for i, u in enumerate(order)}
    after = _edges(order, entries, tier)
    cycles = _cycles(order, after)
    for comp in cycles:
        members = set(comp)
        for u in comp:
            after[u] -= members
        comp.sort(key=pos.get)
        for first, then in zip(comp, comp[1:]):
            after[first].add(then)  # the loop's mods stay in the user's order

    indeg = {u: 0 for u in order}
    for u in order:
        for v in after[u]:
            indeg[v] += 1
    heap = [(tier(u), pos[u], u) for u in order if indeg[u] == 0]
    heapq.heapify(heap)
    out = []
    while heap:
        _, _, u = heapq.heappop(heap)
        out.append(u)
        for v in after[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                heapq.heappush(heap, (tier(v), pos[v], v))
    return out, cycles
