"""v1.39.0: RFC 7950 (YANG 1.1) statement reference — bundled short excerpts.

Cisco YANG Suite shows the relevant RFC section text when you click a node.
We bundle a curated map of YANG statement keywords -> (RFC 7950 section,
title, short excerpt, anchor URL). Excerpts are brief, factual summaries of
each statement's purpose (not full RFC reproductions); a link to the exact
section on datatracker.ietf.org is provided for the complete normative text.

RFC 7950 supersedes RFC 6020 (which YANG Suite references); section numbers
for these core statements are identical between the two, so the anchors line
up with either. We link to 7950 as the current standard.
"""
from __future__ import annotations

_BASE = "https://datatracker.ietf.org/doc/html/rfc7950"

# keyword -> {section, title, text, url}
_RFC: dict[str, dict] = {
    "module": {
        "section": "7.1",
        "title": "The 'module' Statement",
        "text": ("The 'module' statement defines a YANG module. It groups a set "
                 "of related nodes, type definitions, groupings, and other "
                 "statements into a single self-contained unit identified by a "
                 "namespace and a prefix."),
    },
    "submodule": {
        "section": "7.2",
        "title": "The 'submodule' Statement",
        "text": ("A submodule contributes definitions to a module via the "
                 "'belongs-to' statement. Submodules let a large module be split "
                 "across multiple files while sharing one namespace."),
    },
    "container": {
        "section": "7.5",
        "title": "The 'container' Statement",
        "text": ("The 'container' statement groups related nodes in the schema "
                 "tree. A container has no value; it exists to hold child nodes. "
                 "A 'presence' container's mere existence carries configuration "
                 "meaning, whereas a non-presence container is just for "
                 "organizing its children."),
    },
    "leaf": {
        "section": "7.6",
        "title": "The 'leaf' Statement",
        "text": ("A 'leaf' holds a single value of a particular type and has no "
                 "child nodes. It is the basic unit of data in a YANG schema."),
    },
    "leaf-list": {
        "section": "7.7",
        "title": "The 'leaf-list' Statement",
        "text": ("A 'leaf-list' is a sequence of leaf nodes with exactly one "
                 "value of a particular type per entry — effectively an array of "
                 "leaves."),
    },
    "list": {
        "section": "7.8",
        "title": "The 'list' Statement",
        "text": ("The 'list' statement defines an interior data node that may "
                 "exist in multiple instances. Each instance (list entry) is "
                 "uniquely identified by the values of its 'key' leaf(s)."),
    },
    "choice": {
        "section": "7.9",
        "title": "The 'choice' Statement",
        "text": ("A 'choice' allows exactly one of its 'case' branches to exist "
                 "at a time. Only the nodes from a single selected case may be "
                 "present in the data tree."),
    },
    "case": {
        "section": "7.9.2",
        "title": "The 'case' Statement",
        "text": ("A 'case' groups the nodes that belong to one alternative of a "
                 "'choice'. Selecting a case makes its nodes valid and implicitly "
                 "removes the nodes of any other case."),
    },
    "anydata": {
        "section": "7.10",
        "title": "The 'anydata' Statement",
        "text": ("'anydata' represents a node that can hold an unknown set of "
                 "nodes modellable in YANG, without the schema constraining their "
                 "structure."),
    },
    "anyxml": {
        "section": "7.11",
        "title": "The 'anyxml' Statement",
        "text": ("'anyxml' represents a node holding an unknown chunk of XML "
                 "data. Unlike 'anydata', its content need not be representable "
                 "in the YANG data model."),
    },
    "grouping": {
        "section": "7.12",
        "title": "The 'grouping' Statement",
        "text": ("A 'grouping' is a reusable collection of nodes. It is not part "
                 "of the schema tree itself; its contents are instantiated where "
                 "a 'uses' statement references it."),
    },
    "uses": {
        "section": "7.13",
        "title": "The 'uses' Statement",
        "text": ("The 'uses' statement instantiates the contents of a named "
                 "'grouping' at the current location in the schema tree, "
                 "optionally refining or augmenting them."),
    },
    "rpc": {
        "section": "7.14",
        "title": "The 'rpc' Statement",
        "text": ("An 'rpc' defines a Remote Procedure Call, with optional 'input' "
                 "and 'output' sub-statements describing its request and "
                 "response parameters."),
    },
    "action": {
        "section": "7.15",
        "title": "The 'action' Statement",
        "text": ("An 'action' is an operation tied to a specific data node "
                 "(unlike an 'rpc', which is defined at module top level). It "
                 "also has optional 'input' and 'output'."),
    },
    "input": {
        "section": "7.14.2",
        "title": "The 'input' Statement",
        "text": ("'input' defines the parameters (child nodes) supplied when an "
                 "rpc or action is invoked."),
    },
    "output": {
        "section": "7.14.3",
        "title": "The 'output' Statement",
        "text": ("'output' defines the nodes returned in the response to an rpc "
                 "or action."),
    },
    "notification": {
        "section": "7.16",
        "title": "The 'notification' Statement",
        "text": ("A 'notification' defines the contents of an event that the "
                 "server may send to subscribed clients."),
    },
    "augment": {
        "section": "7.17",
        "title": "The 'augment' Statement",
        "text": ("The 'augment' statement adds nodes into the schema tree of "
                 "another module or a different location in the same module. This "
                 "is how, e.g., Cisco-IOS-XE-bgp adds 'bgp' under "
                 "/native/router."),
    },
    "identity": {
        "section": "7.18",
        "title": "The 'identity' Statement",
        "text": ("An 'identity' defines a globally unique, abstract value that "
                 "can be derived from and referenced (via 'identityref') to model "
                 "extensible enumerations."),
    },
    "typedef": {
        "section": "7.3",
        "title": "The 'typedef' Statement",
        "text": ("A 'typedef' defines a new named type derived from an existing "
                 "base type, optionally adding restrictions."),
    },
}

# fall-through for leaf-like value nodes
_ALIASES = {"leafref": "leaf", "identityref": "leaf"}


def rfc_for(keyword: str) -> dict | None:
    """Return {section, title, text, url} for a YANG statement keyword, or None."""
    kw = _ALIASES.get(keyword, keyword)
    entry = _RFC.get(kw)
    if not entry:
        return None
    return {**entry, "url": f"{_BASE}#section-{entry['section']}"}
