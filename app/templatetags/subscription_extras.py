from django import template

register = template.Library()

@register.filter(name='splitlines')
def splitlines(value):
    """
    Takes a string of text, splits it into a list at each newline,
    and removes any extra whitespace from each line.
    """
    if value:
        # .splitlines() handles different types of newlines (\n, \r\n)
        # and we filter out any blank lines that might be in the text.
        return [line.strip() for line in value.splitlines() if line.strip()]
    return []