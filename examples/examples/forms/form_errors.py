"""Additional example — form-level (non-field) errors.

Some rules span several fields and cannot attach to one field: a date range
must be ordered, and a budget split must total 100%. These surface as
**non-field** errors on submit (incremental validation shows only errors
attached to the triggering field — ADR-0004 §2).
"""

from __future__ import annotations

from rg.forms import ReactiveDateField, ReactiveForm, ReactiveIntegerField


class ProjectTimelineForm(ReactiveForm):
    start_date = ReactiveDateField(label="Start date")
    end_date = ReactiveDateField(label="End date")

    budget_design = ReactiveIntegerField(label="Design %", min_value=0, max_value=100, initial=30)
    budget_dev = ReactiveIntegerField(label="Development %", min_value=0, max_value=100, initial=50)
    budget_qa = ReactiveIntegerField(label="QA %", min_value=0, max_value=100, initial=20)

    # A live client-side preview of the split total (server re-checks on submit).
    total_pct = ReactiveIntegerField(
        label="Total % (must equal 100)",
        required=False,
        computed="$budget_design + $budget_dev + $budget_qa",
    )

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end < start:
            # Non-field error: belongs to neither date alone.
            self.add_error(None, "The end date must be on or after the start date.")

        parts = [cleaned.get("budget_design"), cleaned.get("budget_dev"), cleaned.get("budget_qa")]
        if all(p is not None for p in parts) and sum(parts) != 100:
            self.add_error(None, f"The budget split must total 100% (currently {sum(parts)}%).")
        return cleaned
