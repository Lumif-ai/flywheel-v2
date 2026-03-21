"""Tool JSON schema definitions in Anthropic input_schema format.

Each tool has a description (shown to Claude) and an input_schema
(JSON Schema for parameter validation).
"""

TOOL_SCHEMAS: dict[str, dict] = {
    "web_search": {
        "description": (
            "Search the web for current information. Returns up to 5 results "
            "with title, URL, and snippet. Use for finding recent data, news, "
            "company information, or any factual lookup."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query string.",
                },
            },
            "required": ["query"],
        },
    },
    "web_fetch": {
        "description": (
            "Fetch and extract readable text content from a URL. Returns the "
            "main article/page content as plain text, stripped of navigation "
            "and boilerplate. Use after web_search to read full page content."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch content from.",
                },
            },
            "required": ["url"],
        },
    },
    "context_read": {
        "description": (
            "Read all entries from a context file. Context files store "
            "accumulated knowledge about topics like company-intel, "
            "competitive-landscape, meeting-history, etc."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file": {
                    "type": "string",
                    "description": "Context file name (e.g., 'company-intel', 'competitive-landscape').",
                },
            },
            "required": ["file"],
        },
    },
    "context_write": {
        "description": (
            "Write a new entry to a context file. Entries are deduplicated "
            "by detail -- if an entry with the same detail already exists, "
            "its evidence count is incremented instead of creating a duplicate."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file": {
                    "type": "string",
                    "description": "Context file name to write to.",
                },
                "content": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of content lines for the entry.",
                },
                "detail": {
                    "type": "string",
                    "description": "Brief description of what this entry is about.",
                },
                "confidence": {
                    "type": "string",
                    "enum": ["low", "medium", "high"],
                    "description": "Confidence level for this entry. Defaults to 'medium'.",
                },
            },
            "required": ["file", "content", "detail"],
        },
    },
    "context_query": {
        "description": (
            "Search context entries using full-text search. Optionally filter "
            "by context file. Returns matching entries ranked by relevance."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "search": {
                    "type": "string",
                    "description": "Full-text search query.",
                },
                "file": {
                    "type": "string",
                    "description": "Optional: limit search to a specific context file.",
                },
            },
            "required": ["search"],
        },
    },
    "file_read": {
        "description": (
            "Read a previously generated file by its ID. Use to review "
            "outputs from previous skill runs."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "file_id": {
                    "type": "string",
                    "description": "The file ID to read.",
                },
            },
            "required": ["file_id"],
        },
    },
    "file_write": {
        "description": (
            "Write a file as output from the current skill run. Use for "
            "generating reports, dashboards, documents, or any file output."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "Output filename (e.g., 'report.html', 'analysis.md').",
                },
                "content": {
                    "type": "string",
                    "description": "The file content to write.",
                },
                "mimetype": {
                    "type": "string",
                    "description": "MIME type of the file. Defaults to 'text/html'.",
                },
            },
            "required": ["filename", "content"],
        },
    },
    "python_execute": {
        "description": (
            "Execute Python code in a sandboxed environment. Use for data "
            "processing, calculations, or generating structured output. "
            "The code runs in an isolated subprocess with limited permissions."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute.",
                },
            },
            "required": ["code"],
        },
    },
    # Browser tools (require local agent connection)
    "browser_navigate": {
        "description": (
            "Navigate to a URL using the local browser agent. Returns page "
            "text content (truncated to 50KB). (Requires local agent)"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to navigate to.",
                },
            },
            "required": ["url"],
        },
    },
    "browser_click": {
        "description": (
            "Click an element by CSS selector in the local browser. "
            "(Requires local agent)"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector of the element to click.",
                },
            },
            "required": ["selector"],
        },
    },
    "browser_type": {
        "description": (
            "Type text into a form field by CSS selector in the local browser. "
            "(Requires local agent)"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector of the input field.",
                },
                "text": {
                    "type": "string",
                    "description": "The text to type into the field.",
                },
            },
            "required": ["selector", "text"],
        },
    },
    "browser_extract": {
        "description": (
            "Extract text content from a specific element by CSS selector "
            "in the local browser. (Requires local agent)"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {
                    "type": "string",
                    "description": "CSS selector of the element to extract text from.",
                },
            },
            "required": ["selector"],
        },
    },
    "browser_screenshot": {
        "description": (
            "Take a screenshot of the current page in the local browser. "
            "Returns base64-encoded JPEG. (Requires local agent)"
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
}
