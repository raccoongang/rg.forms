# ADR 0005 — Multi-form reactive submission (`reactive_forms_response`)

- Status: Accepted (2026-08-25) — revised after review (rev. 2); implemented
- Date: 2026-08-25
- Deciders: Oleksii Koval (author of rg.forms)
- Relates to: reuses the SSE machinery of `reactive_form_response`
  (`src/rg/forms/views.py`); composes with
  [ADR-0003](0003-scoped-signals-and-reactive-formsets.md) (scoped signals so a formset renders inside the shared
  fragment) and [ADR-0004](0004-declarative-incremental-server-validation.md) (per-field validation, orthogonal).
- Motivating consumer: a downstream Django project's staff user create/edit page (a user form + a profile form +
  a work-experience formset submitted together).

## Revision 2 — decisions resolved after review

- **The error branch reuses an extracted `_sse_patch(html)` helper**, not a nonexistent `_patch_events` (D6). With the
  D8 delegation implemented, `reactive_form_response` routes its error path through `_sse_patch` directly, so the old
  `_sse_patch_form` was removed as dead code.
- **An empty `forms` sequence is a programming error and raises `ValueError`** — `all([])` is `True`, so silently
  treating "no forms" as valid would run `on_success`/redirect without validating anything (D1a).
- **Cross-form validation contract is explicit**: the caller attaches aggregate errors to a member *before* calling the
  helper; `on_success` is not a validation hook (D5). A `validate_forms` callback was considered and rejected to keep
  the surface minimal.
- **`context` is required** (keyword-only, no default) — there is no canonical single-form context to inject (D4).
- **Public export is part of the decision**: `reactive_forms_response` is added to `src/rg/forms/__init__.py`
  imports and `__all__` (D7).
- **The `on_success` return is typed `HttpResponseBase | None`** and its short-circuit/fall-through contract is stated
  (D3). Because that result is returned as-is, the helper's own return type is `HttpResponseBase | None` (the concrete
  results are still `HttpResponseRedirect` / `DatastarResponse`).

## Context

`reactive_form_response(request, form, fragment_template, *, success_url, on_success, context)` **validates and handles
the response for exactly one caller-bound form** (it does not construct or bind the form — the caller does). On a
Datastar request it patches the form's fragment on error or SSE-redirects on success; on a native request it redirects
or returns `None` so the view renders the full page. It is the reason a single-form page can go reactive with one view
call.

Real applications routinely submit **several forms and/or a formset together** on one page, persisted atomically: a
create/edit screen for an aggregate root and its related rows. The canonical shape — the Django docs' own "using
multiple forms" pattern — is:

```python
if a_form.is_valid() & b_form.is_valid() & formset.is_valid():   # non-short-circuit: collect all errors
    with transaction.atomic():
        ... persist all three ...
    return redirect(success_url)
```

Such a view **cannot** use the reactive path: `reactive_form_response` is single-form by signature. A multi-form page
therefore either stays a full-page reload (the regression the library exists to remove) or hand-rolls its own SSE
(`is_datastar_request` + `render_to_string` + `ServerSentEventGenerator` + `DatastarResponse`), re-deriving — per page
— plumbing the library already encapsulates.

The aggregate save itself is small; what is missing is a **reusable contract** for it, so its absence reads as "the
framework can't do multi-form." This ADR fixes the contract at the library level, independently of whether any
particular multi-form page *should* be converted (see Non-goals).

## Problems

### P1 — No reusable N-form submission contract

`reactive_form_response` is single-form by signature. Nothing in rg.forms expresses "validate this ordered set of
forms/formsets, patch the shared fragment on any error, redirect on all-valid." Every multi-form page re-derives it.

### P2 — Hand-rolled multi-form SSE drifts from the single-form contract

A page that hand-writes the multi-form SSE diverges from `reactive_form_response`: different native-vs-Datastar
branching, different redirect encoding, or (a real bug) short-circuit validation that hides later forms' errors.

### P3 — The single-form `on_success(form)` shape does not generalize

`reactive_form_response` passes the validated `form` to `on_success`. With N forms there is no single form to pass, and
the library cannot know how to persist a heterogeneous set atomically (transaction boundaries, write ordering,
cross-form invariants, audit consolidation). That is irreducibly the caller's domain.

## Decision

Add a sibling helper, **`reactive_forms_response`** (plural), that owns only the request/response plumbing for the
N-form case and leaves validation-of-aggregates and persistence to the caller.

```python
def reactive_forms_response(
    request: HttpRequest,
    forms: Sequence[Any],                                  # non-empty; members already bound, each with is_valid()
    fragment_template: str,
    *,
    context: Mapping[str, Any],                            # required — no canonical single-form default (D4)
    success_url: str | None = None,
    on_success: Callable[[], HttpResponseBase | None] | None = None,   # no form arg (D3)
) -> HttpResponseBase | None:                              # HttpResponseRedirect / DatastarResponse / on_success result
    ...
```

### D1 — Validate every member, non-short-circuit, in order

`all_valid = all([f.is_valid() for f in forms])` — a **list**, not a generator, so every member is validated even when
an earlier one fails, and in the supplied order. This guarantees the single error patch shows all errors at once.
Formsets qualify: `FormSet.is_valid()` is part of the same contract, and their fields render in the shared fragment via
ADR-0003 scoped signals.

### D1a — An empty `forms` sequence raises

`all([])` is `True`. Passing `[]` would run `on_success`/redirect without validating anything — a silent footgun. The
helper guards explicitly:

```python
if not forms:
    raise ValueError("forms must contain at least one bound form or formset")
```

### D2 — Response branching mirrors `reactive_form_response`

- **all valid** → call `on_success()` if given; if it returns non-`None`, return that; else redirect to `success_url`
  (`sse_redirect` under Datastar, `HttpResponseRedirect` otherwise). If neither is set, return `None`.
- **any invalid** → Datastar: patch `fragment_template` (rendered with `context`); native: return `None` so the view
  renders the full page with bound errors.

This is the **same response branching** as the singular helper; the context handling (D4) and callback signature (D3)
deliberately differ.

### D3 — `on_success` takes no argument; the caller owns atomicity

`on_success()` receives nothing and closes over the forms it already holds. The caller runs its own
`transaction.atomic()` (and any service/audit logic) inside it. Return contract: **returning a Django response
(`HttpResponseBase`) short-circuits** normal redirect handling and is returned as-is; **returning `None` falls
through** to the `success_url` redirect. Rationale: the helper must not own persistence — multi-model atomic writes,
write ordering, and audit consolidation are application concerns. This is the load-bearing boundary of the ADR: the
helper is submission *plumbing*, never a save engine.

### D4 — The caller supplies the fragment context; it is required

The singular helper injects `{"form": form}` before rendering. With N forms there is no canonical name, so
`reactive_forms_response` renders the fragment with the **caller's `context`** (e.g.
`{"user_form": ..., "profile_form": ..., "formset": ...}`, matching the template). Because a wrong/empty context would
render a broken fragment on the error path, `context` is **keyword-only and required** (no default).

### D5 — Cross-form validation is the caller's, attached *before* the call

Aggregate invariants that can only be checked by comparing multiple valid forms (e.g. "end date ≥ start date across
two forms") are the caller's responsibility, and must be attached **before** `reactive_forms_response` runs its success
branch — **not** inside `on_success` (which runs only when all members are individually valid, and whose added errors
would arrive after the redirect decision). The idiom relies on Django caching validation:

```python
forms = [user_form, profile_form, formset]
if all([f.is_valid() for f in forms]):          # populate cleaned_data + cache errors
    if profile_form.cleaned_data["birth_date"] > some_other:
        profile_form.add_error("birth_date", _("…"))   # form is now bound-and-invalid

# The helper re-checks is_valid() — cached, so no second full_clean; the attached error routes to the patch.
response = reactive_forms_response(request, forms, "…/_form.html", context={...}, ...)
```

`add_error` keeps a form bound-and-invalid and Django caches `full_clean`, so the helper's `all([...])` reflects the
attached errors without re-running validation. A dedicated `validate_forms` callback was considered but rejected: it
adds surface for something the caller can already express, and Option 1 keeps the helper minimal.

### D6 — Extract `_sse_patch(html)`

`_sse_patch_form` currently inlines the patch-events generator. Extract the generic part:

```python
def _sse_patch(html: str) -> DatastarResponse:
    def events() -> Generator[DatastarEvent, None, None]:
        yield ServerSentEventGenerator.patch_elements(html)
    return DatastarResponse(events())
```

`reactive_forms_response` uses `_sse_patch` directly. (This is the helper the previous draft mistakenly called
`_patch_events`.) In the shipped implementation, since `reactive_form_response` also delegates through
`reactive_forms_response` (D8), the intermediate `_sse_patch_form` is no longer referenced and was removed — both
helpers share `_sse_patch`.

### D7 — Public export

`reactive_forms_response` is imported in `src/rg/forms/__init__.py` and added to `__all__`, alongside
`reactive_form_response`. It must be importable as `from rg.forms import reactive_forms_response`, not only from
`rg.forms.views`.

### D8 — `reactive_form_response` is unchanged (refactored to delegate)

Purely additive. `reactive_form_response` keeps its signature and `on_success(form)` shape. **As implemented, it
delegates** to the plural form with a context shim that injects `{"form": form}` and an `on_success` adapter
(`lambda: on_success(form)`) — an internal cleanup, not a contract change. Because the delegation routes the single-form
error path through `_sse_patch` directly, the previous `_sse_patch_form` helper became dead code and was removed; the
generic `_sse_patch(html)` extraction of D6 is what both helpers now share.

## Input contract

- Every member of `forms` is **already bound** (constructed with `request.POST`/`request.FILES` by the caller). The
  helper never inspects `request.POST`/`request.FILES` itself.
- The sequence is **non-empty** (D1a).
- Each member exposes `is_valid()` (Django `Form`/`ModelForm`/`BaseFormSet` all do). Typed `Sequence[Any]` for now; a
  small `SupportsIsValid` protocol is a reasonable later refinement.
- **Order matters** for validation order (D1), even though all members are always validated.
- `context` is the exact template context for the error fragment (D4).

## Reference implementation

```python
def reactive_forms_response(request, forms, fragment_template, *, context, success_url=None, on_success=None):
    if not forms:
        raise ValueError("forms must contain at least one bound form or formset")

    datastar = is_datastar_request(request)
    all_valid = all([f.is_valid() for f in forms])          # list → validate every member, in order

    if all_valid:
        if on_success is not None:
            result = on_success()
            if result is not None:
                return result
        if success_url:
            return sse_redirect(success_url) if datastar else HttpResponseRedirect(success_url)
        return None

    if datastar:
        return _sse_patch(render_to_string(fragment_template, dict(context), request))
    return None
```

(`is_datastar_request`, `sse_redirect`, `render_to_string`, `HttpResponseRedirect`, and — after D6 — `_sse_patch`
already exist in `views.py`.)

## Usage

```python
def user_create(request):
    if request.method == "POST":
        user_form = StaffUserForm(request.POST)
        profile_form = UserProfileForm(request.POST)
        formset = WorkExperienceFormSet(request.POST)

        def _on_success():
            with transaction.atomic():          # caller owns atomicity + audit
                create_staff_user(user_form, profile_form, formset, actor=request.user)
            messages.success(request, _("User created."))
            return None                          # fall through to the redirect

        response = reactive_forms_response(
            request,
            [user_form, profile_form, formset],
            "management/users/_user_form.html",
            context={"form": user_form, "profile_form": profile_form, "formset": formset},
            success_url=reverse("user_list"),
            on_success=_on_success,
        )
        if response:
            return response
    else:
        user_form, profile_form, formset = StaffUserForm(), UserProfileForm(), WorkExperienceFormSet()
    return render(request, "management/users/user_form.html", {...})
```

## Non-goals / boundaries

This helper makes multi-form *submission plumbing* reusable. It explicitly does **not**:

- **Own persistence, transactions, or audit.** D3 — the caller's `on_success()` runs the atomic write.
- **Perform cross-form validation.** D5 — the caller attaches aggregate errors before the call.
- **Make every multi-form page convertible.** A page may still be correctly left bespoke for reasons this helper does
  not touch — e.g. a *deliberately consolidated single audit event* per aggregate write, or an *inherently atomic
  creation* with no valid partial state. (The motivating user form is exactly this: the helper removes the
  library-level objection, but the form stays combined for audit-atomicity reasons — the ADR removes a perceived
  blocker, not that team's design judgment.)
- **Solve error-path widget re-initialization.** Keeping JS-enhanced widgets (rich selects, date pickers, dynamic
  formsets) working across the error morph is the consumer's frontend concern — best solved by self-managing web
  components, not this helper.
- **Decompose a form into independently-saved sections**, or add per-field incremental validation across forms
  (ADR-0004 territory; composes but is separate).

## Backward compatibility

Additive only. No existing signature changes; `reactive_form_response` and all current consumers behave unchanged. The
D6 extraction of `_sse_patch` and D8 delegation are internal refactors with no observable contract change.

## Validation plan (acceptance)

Not a compatibility claim, but the intended sign-off: after implementation, run the library's own suite plus at least
one downstream consumer's full suite with **zero consumer edits required** for the additive change, then
convert one real multi-form page (a non-outlier one) as an end-to-end check.

## Testing

- Empty `forms` → `ValueError` (D1a).
- All-valid (Datastar) → SSE redirect to `success_url`; `on_success()` ran exactly once.
- Any-invalid (Datastar) → SSE `patch-elements` of the fragment; body carries **every** member's errors
  (non-short-circuit); `on_success()` not called; nothing persisted.
- Every member's `is_valid()` runs even when the first member is invalid; validation happens in supplied order.
- Caller-attached cross-form error (D5) renders in the patched fragment and prevents success.
- The supplied `context` is passed through unchanged and contains all expected objects.
- All-valid / any-invalid (native, no Datastar header) → `HttpResponseRedirect` / `None` (full-page fallback intact).
- `on_success()` returning a Django response short-circuits (both a native and a Datastar-context return); returning
  `None` falls through to `success_url`.
- All-valid call with neither `on_success` nor `success_url` returns `None`.
- A formset among `forms` is validated and its errors surface in the same patch (ADR-0003 scoped signals).
- Importable as `from rg.forms import reactive_forms_response` (D7), not only from `rg.forms.views`.
- `reactive_form_response` behavior remains unchanged after the D6/D8 refactor.
