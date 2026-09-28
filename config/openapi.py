def drop_negative_decimal_patterns(result, generator, request, public):
    """drf-spectacular gives every decimal a pattern that allows a leading
    minus sign, so Swagger UI makes up negative examples. No decimal in this
    API can be negative (hours, limits), so we drop that part of the pattern."""
    for schema in result.get("components", {}).get("schemas", {}).values():
        for prop in schema.get("properties", {}).values():
            pattern = prop.get("pattern")
            if prop.get("format") == "decimal" and pattern and pattern.startswith("^-?"):
                prop["pattern"] = "^" + pattern[3:]
    return result
