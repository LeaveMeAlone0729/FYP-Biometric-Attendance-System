"""Existing development entry point; recovery uses production_app explicitly."""
from application_factory import create_app

app = create_app()
