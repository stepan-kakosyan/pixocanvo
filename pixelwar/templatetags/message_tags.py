from django import template

register = template.Library()


@register.filter(name="has_tag")
def has_tag(message, tag_name: str) -> bool:
    tags = str(getattr(message, "tags", "") or "").split()
    return str(tag_name or "").strip() in tags
