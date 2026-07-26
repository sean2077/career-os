from __future__ import annotations

import os

# Rich styles an option name as a separate `-` plus `-name` run when color is
# enabled, so `"--apply" in result.stdout` is false under a colored environment
# even though the help text is correct. CI runners commonly export FORCE_COLOR,
# which no NO_COLOR setting overrides. Pin the test process to a plain terminal
# so CLI output assertions do not depend on who runs the suite.
os.environ["TERM"] = "dumb"
os.environ.pop("FORCE_COLOR", None)
os.environ.pop("CLICOLOR_FORCE", None)
