def drop_negative_decimal_patterns(result, generator, request, public):
    """Strip the leading minus from decimal patterns: none of ours go negative."""
    for schema in result.get("components", {}).get("schemas", {}).values():
        for prop in schema.get("properties", {}).values():
            pattern = prop.get("pattern")
            if prop.get("format") == "decimal" and pattern and pattern.startswith("^-?"):
                prop["pattern"] = "^" + pattern[3:]
    return result
