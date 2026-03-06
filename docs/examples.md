# Examples

The `examples/` directory in the repository contains a full Django project demonstrating all rg.forms features.

## Running the example project

```bash
git clone https://github.com/raccoongang/rg.forms.git
cd rg.forms/examples

uv venv
source .venv/bin/activate
uv pip install -e "..[all]"

python manage.py migrate
python manage.py runserver
```

Visit [http://localhost:8000/](http://localhost:8000/) to see all examples.

## Included examples

### Order Form
Demonstrates `visible_when` for conditional field visibility. Fields appear and disappear based on order type selection.

### Price Calculator
Demonstrates `computed` fields. The total updates in real time as quantity and price change.

### Contact Form
Demonstrates `required_when` for dynamic requirements. Email or phone becomes required based on contact method.

### Backend Validation
Shows how the backend evaluates all reactive expressions during validation:

- Hidden fields are skipped (even if `required=True`)
- Dynamic requirements are enforced
- Computed values are recalculated (client value ignored)

### Conditional Attributes
Demonstrates `disabled_when`, `read_only_when`, and `help_text_when` for dynamic field states.

### Cascading Dropdowns
Dependent dropdowns with server-side re-rendering via Datastar SSE. Category selection updates available products.

### Field Groups
Fields organized into sections with shared `visible_when` rules. Business fields appear only for business accounts.

### SSE Validation
Backend-heavy validation without full page reloads. Demonstrates `reactive_form_response()` with:

- Username uniqueness check (simulated database lookup)
- Coupon code verification (server-side lookup)
- VAT number format validation (would call external API in production)
- Cross-field business rules (business accounts require company email)

On validation errors, only the form HTML is patched via SSE — the rest of the page stays untouched.

## Source code

- **Forms**: `examples/examples/forms.py`
- **Views**: `examples/examples/views.py`
- **Templates**: `examples/examples/templates/examples/`
- **Base template**: `examples/templates/base.html`
