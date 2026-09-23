"""The GTM engine: the product described once, and a strategy brain over it.

Design and work orders: ``docs/architecture/GTM_ENGINE.md``. Epic ``E-12``.

**This package owns no transport and imports nothing from ``ai/``.** Importing
any ``ai`` module runs ``ai/__init__.py``, which imports the broker and through
it every provider — so even a pure helper from there would give this package a
route to a model. Where the brain needs a model, ``ask`` is passed in by the API
layer, exactly as the video director's is. ``tests/test_gtm_products.py`` walks
every module here and fails the build on a forbidden import.
"""
