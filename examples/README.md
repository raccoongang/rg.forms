# rg.forms example project

Example Django project demonstrating rg.forms - Reactive Django Forms with Datastar integration.

## Setup

```bash
cd examples
uv venv
source .venv/bin/activate

# Install rg.forms in editable mode from the parent directory
uv pip install -e "..[all]"

python manage.py migrate
python manage.py runserver
```

## Examples

Visit http://localhost:8000/ to see the examples:

1. **Order Form** - Demonstrates `visible_when` for conditional field visibility
2. **Price Calculator** - Demonstrates `computed` for automatic calculations
3. **Contact Form** - Demonstrates `required_when` for dynamic field requirements

## Project Structure

```
examples/               # This directory (inside rg.forms repo)
├── manage.py
├── testsite/
│   ├── settings.py    # Adds ../../src to sys.path for local rg.forms
│   └── urls.py
├── examples/
│   ├── forms.py       # Example reactive forms
│   ├── views.py       # FBV views
│   └── templates/
└── templates/
    └── base.html      # Base template with Datastar & Bulma
```
