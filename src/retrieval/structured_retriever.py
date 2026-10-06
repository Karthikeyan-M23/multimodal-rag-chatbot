def _normalize(value) -> str:
    return "" if value is None else str(value).strip().lower()


def _matches_date(metadata, requested_date):
    if not requested_date:
        return True

    # Dashboard questions use the date-group, not the date embedded
    # in the SQL filename.
    actual_date = metadata.get("deployment_group_date")

    return _normalize(actual_date) == _normalize(requested_date)


def _matches_environment(metadata, environment):
    if not environment:
        return True

    return f"{environment}_status" in metadata


def _matches_status(metadata, environment, status):
    if not environment or not status:
        return True

    return _normalize(
        metadata.get(f"{environment}_status")
    ) == _normalize(status)


def filter_structured_chunks(chunks, parsed_query):
    results = []

    for chunk in chunks:
        metadata = chunk.get("metadata", {})

        if metadata.get("record_type") != "html_table_row":
            continue

        if not _matches_date(metadata, parsed_query.get("date")):
            continue

        if not _matches_environment(
            metadata,
            parsed_query.get("environment"),
        ):
            continue

        if not _matches_status(
            metadata,
            parsed_query.get("environment"),
            parsed_query.get("status"),
        ):
            continue

        results.append(chunk)

    return results


def sort_structured_chunks(chunks):
    return sorted(
        chunks,
        key=lambda chunk: (
            chunk["metadata"].get("deployment_group_date") or "",
            chunk["metadata"].get("git_script") or "",
        ),
    )


def retrieve_structured_chunks(chunks, parsed_query):
    return sort_structured_chunks(
        filter_structured_chunks(chunks, parsed_query)
    )
