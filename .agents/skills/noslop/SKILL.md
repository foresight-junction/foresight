---
name: noslop
description: Strip AI slop from code and user-facing text before committing. Use after writing or changing any code, UI copy, README or pitch text, and whenever asked to "clean up", "de-slop" or "tidy" something.
---

# noslop

AI-written code has recognisable failure patterns. Find and fix them in **your own changes** (`git diff` plus untracked files you created). Don't rewrite code you didn't touch.

## 1. Check the code for these, and fix every one you find

**Fake or wrong**
- [ ] Calls to functions, methods, params or endpoints that may not exist. Verify each unfamiliar one against the installed package (`node_modules/<pkg>`, `uv run python -c "import x; help(x.y)"`) or official docs. Delete or fix anything you can't verify.
- [ ] Fake data, stubbed calls or hardcoded responses without a `MOCK:` comment and the `USE_MOCKS` flag.
- [ ] `TODO`, `pass`, `...` or "implement later" in code that is presented as finished.
- [ ] Code that returns success when it actually failed.

**Defensive noise**
- [ ] `try/except` or `try/catch` that swallows errors, or logs them and carries on. Let errors raise unless there's a real recovery.
- [ ] Checks for things that can't happen (null checks on values that are never null, type checks the type system already guarantees).
- [ ] Fallback values that hide bugs (`|| []`, `or {}`, `?? "Unknown"`) where missing data is actually a bug.

**Over-engineering**
- [ ] Base classes, factories, interfaces, managers or config options with only one use. Inline them.
- [ ] New helper functions that duplicate one already in the codebase. Search first (`grep -rn "def <name>\|function <name>"`).
- [ ] Wrappers that just pass arguments through.
- [ ] Files or functions over ~150 lines that could be split along obvious seams.

**Noise**
- [ ] Comments that restate the code (`# increment counter`), section banners, and "This function..." docstrings on obvious functions.
- [ ] Commented-out code, unused imports, variables and parameters.
- [ ] Leftover `console.log` / `print` debugging.
- [ ] Magic strings or numbers that belong in `docs/CONTRACTS.md` or a constant.
- [ ] Inconsistent naming against the surrounding code.

## 2. Check user-facing text (UI copy, README, pitch, error messages)

- [ ] Cut hype words: seamless, revolutionary, unleash, empower, cutting-edge, robust, leverage, elevate, "in today's fast-paced world".
- [ ] No emoji in buttons, headings or error messages unless the design asks for it.
- [ ] Error messages say what went wrong and what to do next, in plain words.
- [ ] Headlines say what the product does, concretely. "Find a free study room in 10 seconds" beats "Revolutionising campus spaces".
- [ ] No em dashes in UI copy. Use a full stop or comma.

## 3. Finish

- Re-run the app or tests after your fixes. Removing "defensive" code sometimes exposes a real bug, which is the point.
- Report one line per fix: `file:line: what was removed or changed`. If nothing needed fixing, say "noslop: clean".
