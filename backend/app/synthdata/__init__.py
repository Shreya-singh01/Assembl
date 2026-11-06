"""Synthetic platform data for building, demos and robustness testing.

EVERYTHING produced here is synthetic and labelled as such:
* every account e-mail ends in ``@demo.assembl.example`` (RFC 2606 reserved)
  and every display name ends in "(demo)";
* every project carries ``demo: true``;
* research scenarios are stored with ``provenance: "synthetic"`` and simulated
  ratings with ``judgment_provenance: "simulated"``.

None of it may be used as research evidence or to calibrate weights that are
then reported as results. Usage: ``python -m app.synthdata --help``.
"""

DEMO_DOMAIN = "demo.assembl.example"
DEMO_PASSWORD = "demo-password-123"
