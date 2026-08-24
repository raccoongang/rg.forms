# Cascading dropdowns comparison

**Requirement:** country → region → city, where each level's options depend on
the selection above it, an invalid child selection resets when its parent
changes, and the parent/child relationship is validated authoritatively.

!!! note "Architectural comparison, not a LOC measurement"
    Unlike the [four measured slices](../comparison.md#3-results-overview), this
    page compares *what each architecture must build*, not counted source lines
    (no fixtures were generated for it). The structural difference is the point.

- **rg.forms (runnable):**
  [`forms/cascading.py`](https://github.com/raccoongang/rg.forms/blob/master/examples/examples/forms/cascading.py) ·
  [`views/cascading.py`](https://github.com/raccoongang/rg.forms/blob/master/examples/examples/views/cascading.py) ·
  [`_cascading_form_fragment.html`](https://github.com/raccoongang/rg.forms/blob/master/examples/examples/templates/examples/_cascading_form_fragment.html)

## What each side has to build

| Concern | Client stack (React + API) | rg.forms |
|---|---|---|
| Options for each level | client `useState`/query cache per level, invalidated on parent change | `choices_from=` callables, re-run server-side |
| Fetch on change | `useEffect`/query hook per dependent level → API call | one `data-on:change` that re-POSTs the form |
| Endpoints | an API route per level (regions?country=, cities?region=) | none — the same view re-renders the fragment |
| Invalid-child reset | manual: clear child state when the parent changes | server drops a now-invalid child on re-render |
| Loading state | per-request `isLoading` wired to each control | native `data-indicator` on a local signal |
| Stale responses | manual request-id / abort bookkeeping | server renders the current state; nothing to reconcile |
| Authoritative validation | re-declared on the server (belongs-to checks) | one `clean()` — the same code that drives choices |

## Why it disappears

The client version splits one concept — "the city list depends on the region,
which depends on the country" — across option state, cache invalidation, a
fetch-on-change effect per level, per-level API endpoints, loading flags, stale
handling, and a duplicated server rule. rg.forms declares the dependency once
(`depends_on=[...]` + `choices_from=...`); a parent change re-POSTs the form and
the server re-renders the fragment with the child options recomputed and any
invalid child reset. The dependency rule and the belongs-to validation are the
same server code.

## Trade-offs

Each parent change is a (small, fragment-sized) server round-trip rather than a
cached client transition; for option lists this is usually indistinguishable and
avoids the client-cache/staleness surface entirely. If a level's option set is
huge and must be filtered/searched entirely client-side, a client component may
still be warranted for that control.
