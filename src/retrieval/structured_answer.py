def build_structured_answer(results, parsed_query):
    intent = parsed_query.get("intent")
    date = parsed_query.get("date")
    environment = parsed_query.get("environment")
    status = parsed_query.get("status")

    env_label = environment.upper() if environment else None
    status_label = {
        "executed": "executed",
        "not_executed": "not executed",
    }.get(status, status)

    if intent == "count":
        if date and environment and status:
            return (
                f"{len(results)} files under {date} are shown as "
                f"{status_label} in {env_label}."
            )
        return f"{len(results)} matching records were found."

    if not results:
        filters = []
        if date:
            filters.append(f"date {date}")
        if environment:
            filters.append(env_label)
        if status:
            filters.append(status_label)

        detail = ", ".join(filters)

        if detail:
            return (
                f"No files matching {detail} were found in "
                "the uploaded deployment report."
            )

        return "No matching records were found."

    if date and environment and status:
        heading = (
            f"Files under {date} shown as {status_label} "
            f"in {env_label}:"
        )
    else:
        heading = "Matching files:"

    lines = [heading, ""]

    for index, chunk in enumerate(results, start=1):
        script = chunk["metadata"].get(
            "git_script",
            "Unknown script",
        )
        lines.append(f"{index}. {script}")

    return "\n".join(lines)
