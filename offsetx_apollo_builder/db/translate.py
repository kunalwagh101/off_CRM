"""SQL translation between the two backends.

Stores write ``?`` placeholders because that is what SQLite takes and what the
whole codebase already contains — 449 of them in ``outreach/store.py`` alone.
Rewriting every query to ``%s`` would be a large diff that breaks SQLite, so the
translation happens here instead, once.

**Why this is not a regex.** ``?`` and ``%`` both occur inside string literals,
and a blind replace corrupts them:

    SELECT * FROM t WHERE note LIKE '50%' AND q = ?

A regex turns the ``%`` in the literal into ``%%`` visible to the user, or
leaves it as a stray format specifier that psycopg then chokes on. So the
translator walks the string and tracks whether it is inside a quoted literal,
which is a dozen lines and cannot be wrong in the way a pattern can.
"""

from __future__ import annotations


def translate_params(sql: str) -> str:
    """Rewrite ``?`` placeholders to ``%s`` for psycopg.

    Also doubles every literal ``%`` — psycopg treats ``%`` as the start of a
    placeholder whenever parameters are passed, so a percent sign that was
    meant literally has to be escaped. Both substitutions respect quoting:
    text inside ``'...'`` or ``"..."`` is data or an identifier, never syntax.

    SQL comments are not special-cased. A ``?`` inside ``-- a comment`` would
    be rewritten, which is harmless: it is a comment either way.
    """
    out: list[str] = []
    quote: str | None = None
    index = 0
    length = len(sql)

    while index < length:
        char = sql[index]

        if quote is not None:
            out.append(char)
            if char == quote:
                # Doubled quote is an escaped quote, not the end of the literal:
                # 'it''s' is one string. Consume both and stay inside.
                if index + 1 < length and sql[index + 1] == quote:
                    out.append(sql[index + 1])
                    index += 2
                    continue
                quote = None
            elif char == "%":
                # Inside a literal, % is still special to psycopg's parser.
                out.append("%")
            index += 1
            continue

        if char in ("'", '"'):
            quote = char
            out.append(char)
        elif char == "?":
            out.append("%s")
        elif char == "%":
            out.append("%%")
        else:
            out.append(char)
        index += 1

    return "".join(out)
