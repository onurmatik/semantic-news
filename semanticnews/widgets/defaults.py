"""Seed definitions for the built-in widget catalog."""

DEFAULT_WIDGETS = (
    {
        "name": "Topic Overview",
        "type": "text",
        "prompt": (
            "Summarise the topic's key points in two short paragraphs focusing on recency, "
            "impact, and unresolved questions."
        ),
        "response_format": {"type": "markdown", "sections": ["summary"]},
        "tools": [],
        "template": "{{ summary }}",
    },
    {
        "name": "Key Images",
        "type": "images",
        "prompt": "Suggest up to four compelling image concepts that illustrate the topic.",
        "response_format": {"type": "image_list", "max_items": 4},
        "tools": ["image_search"],
        "template": "{% for image in images %}<figure>{{ image.caption }}</figure>{% endfor %}",
    },
    {
        "name": "Data Highlights",
        "type": "data",
        "prompt": (
            "Surface the three most insightful quantitative facts about the topic and "
            "explain why they matter."
        ),
        "response_format": {"type": "bulleted_metrics", "max_items": 3},
        "tools": ["data_catalog"],
        "template": "{% for metric in metrics %}- {{ metric.label }}: {{ metric.value }}{% endfor %}",
    },
    {
        "name": "Timeline",
        "type": "timeline",
        "prompt": "Outline the five most important moments related to the topic in chronological order.",
        "response_format": {"type": "timeline", "max_items": 5},
        "tools": [],
        "template": "{% for event in events %}<p>{{ event.date }} — {{ event.summary }}</p>{% endfor %}",
    },
    {
        "name": "Related Coverage",
        "type": "webcontents",
        "prompt": "Curate notable external articles or resources that deepen understanding of the topic.",
        "response_format": {"type": "link_list", "max_items": 5},
        "tools": ["web_search"],
        "template": "{% for link in links %}<li><a href=\"{{ link.url }}\">{{ link.title }}</a></li>{% endfor %}",
    },
)
