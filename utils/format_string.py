from phrases import PHRASES_RU


def clear_string(text: str):
    if not text:
        return PHRASES_RU.icon.not_text
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def project_link(title: str | None, url: str | None = None) -> str:
    if not title:
        return ''
    safe_title = clear_string(title)
    if url:
        return f'<a href="{url.replace(chr(34), "%22")}">{safe_title}</a>'
    return safe_title


def get_query_count_emoji(count: int) -> str:
    for emoji, threshold in PHRASES_RU.icon.query.thresholds.__dict__.items():
        if count > threshold:
            return emoji
    return PHRASES_RU.icon.query.default
