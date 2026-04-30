"""Domain-to-agent identity map.

Maps each domain command to the expected agent identity.
Commands with a None value accept any registered agent.
The map is consulted before executing every command.
"""

DOMAIN_AGENT_MAP: dict[str, str | None] = {
    # tickets
    "tickets.create": "surgeon",
    "tickets.show": None,
    "tickets.list": None,
    "tickets.comment": "surgeon",
    "tickets.update": "surgeon",
    "tickets.resolve": "architect",
    # articles
    "articles.show": None,
    "articles.list": None,
    "articles.create": "scribe",
    "articles.update": "scribe",
    # milestones
    "milestones.list": None,
    "milestones.show": None,
    "milestones.update": None,
    "milestones.complete": "architect",
    # invoices
    "invoices.show": "oracle",
    "invoices.list": "oracle",
    "invoices.pay": "oracle",
    "invoices.send_receipt": "oracle",
    # search
    "search.search": None,
    # projects
    "projects.list": None,
    "projects.show": None,
    "projects.overview": None,
    "projects.create": None,
    "projects.update": None,
    "projects.complete": None,
    # templates
    "templates.list": None,
    "templates.show": None,
    "templates.apply": None,
    # products
    "products.list": None,
    # rate_cards
    "rate_cards.list": None,
    "rate_cards.lookup": None,
    # workbench
    "workbench.list": None,
    "workbench.pin": None,
    "workbench.unpin": None,
    # time_entries
    "time_entries.create": "surgeon",
    "time_entries.update": "surgeon",
    # artefacts
    "artefacts.show": None,
    "artefacts.list": None,
    "artefacts.create": "surgeon",
    # notify
    "notify.list": "scribe",
    # mockups
    "mockups.list": None,
    "mockups.show": None,
    "mockups.create": "surgeon",
    "mockups.update": "surgeon",
    "mockups.delete": "surgeon",
    "mockups.lint": "surgeon",
    "mockups.publish": "surgeon",
    # forms
    "forms.templates.create": None,
    "forms.templates.deploy": None,
    "forms.submissions.delete": None,
    "forms.submissions.update": None,
    "forms.submissions.share-token": None,
    # capture_execute
    "capture_execute.capture": None,
    "capture_execute.execute": None,
    # contacts
    "contacts.enable-portal": "surgeon",
    "contacts.invite": "surgeon",
}


def check_agent_for(domain: str, command: str, current_agent: str | None) -> str | None:
    """Check if the current agent is appropriate for the given domain command.

    Returns None if OK, or an error message string if the agent should not be used.
    """
    key = f"{domain}.{command}"
    expected = DOMAIN_AGENT_MAP.get(key)

    if expected and current_agent and current_agent != expected:
        return (
            f"{domain} {command} typically uses --agent {expected}. "
            f"Current agent is '{current_agent}'. Continue? "
        )

    return None


def suggest_agent_for(domain: str, command: str) -> str | None:
    """Return the expected agent name for a domain command, or None."""
    key = f"{domain}.{command}"
    expected = DOMAIN_AGENT_MAP.get(key)
    return expected if expected else None
