def build_pagination_tokens(
    page_obj,
    *,
    leading_count: int = 4,
    trailing_count: int = 1,
    around_count: int = 1,
):
    if not page_obj or page_obj.paginator.num_pages <= 1:
        return []

    total_pages = page_obj.paginator.num_pages
    current_page = page_obj.number
    pages = set()

    pages.update(range(1, min(total_pages, leading_count) + 1))
    pages.update(
        range(
            max(1, current_page - around_count),
            min(total_pages, current_page + around_count) + 1,
        )
    )
    pages.update(range(max(1, total_pages - trailing_count + 1), total_pages + 1))

    tokens = []
    previous_page = None
    for page_number in sorted(pages):
        if previous_page is not None and page_number - previous_page > 1:
            tokens.append(None)
        tokens.append(page_number)
        previous_page = page_number
    return tokens
