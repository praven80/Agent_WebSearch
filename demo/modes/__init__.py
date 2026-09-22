"""The two options the demo compares.

Web search goes through the AWS-managed Web Search tool on an AgentCore Gateway.
No third-party search provider is used anywhere.
"""

from .agentcore_search import MODE as AGENTCORE_SEARCH
from .no_search import MODE as NO_SEARCH

# Ordered as they are presented to the customer.
MODES = (NO_SEARCH, AGENTCORE_SEARCH)
MODES_BY_KEY = {mode.key: mode for mode in MODES}

__all__ = ["AGENTCORE_SEARCH", "MODES", "MODES_BY_KEY", "NO_SEARCH"]
