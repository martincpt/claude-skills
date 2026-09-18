# Call-Site Style

How a single call, append, or loop header gets built — when to name an intermediate value instead of
folding it in, when a value earns a walrus instead of its own statement, and when an argument should
be positional versus keyword.

## Naming Intermediate Values

Naming an intermediate value pays for itself in three situations: **accumulating** it into a
collection (`.append()`/`.extend()`), **iterating** over it (`for`/`async for`), or **chaining
several calls that each do independent work** — I/O, a lookup, a transformation — so a failure or a
debugger breakpoint lands on the step that actually caused it, not on one line doing three jobs.

```python
# Bad — the appended value's shape is buried inside .append(...):
results.append(TaskResult(key=key, outcome=outcome, detail=detail))

# Good — named first, so the construction and the append each read as one step:
result = TaskResult(key=key, outcome=outcome, detail=detail)
results.append(result)

# Bad — a for loop over a literal tuple hides the iterable inside the loop header:
for stage in (Pipeline.validate, Pipeline.upsert, Pipeline.publish):
    run(stage)

# Good — the tuple is a value with its own name, reusable and inspectable:
stages = (Pipeline.validate, Pipeline.upsert, Pipeline.publish)

for stage in stages:
    run(stage)

# Bad — three calls chained inline, each doing real work (a lookup, then I/O, then a
# blocking run); a failure gives one confusing traceback frame instead of three clear ones:
rows = run(load_rows(get_channel(channel_name)))

# Good — each step is named, so a debugger or a traceback lands on the right line:
channel = get_channel(channel_name)
coro = load_rows(channel)
rows = run(coro)

# Bad — the query is built and iterated in the same statement:
async for snapshot in Snapshot.find(
    Snapshot.status == Status.pending,
    Snapshot.source == Source.channel,
):
    handle(snapshot)

# Good — the query is a named value; the loop header just says "iterate this":
query = Snapshot.find(
    Snapshot.status == Status.pending,
    Snapshot.source == Source.channel,
)

async for snapshot in query:
    handle(snapshot)

# Bad — a repository is constructed and called on in the same expression; the object
# that owns the call is invisible, and there's nothing to hold a breakpoint on:
category = await CategoryRepository().by_slug(slug)

# Good — the instance is named, so "which object" and "which call" are two separate facts:
repository = CategoryRepository()
category = await repository.by_slug(slug)
```

A constructed **object** — a repository, a service, a client, anything whose `__init__` sets up
state — gets the same treatment as any other chained call, even though the constructor call itself
looks trivial: name the instance, then call the method on it. This is different from constructing a
**value** (see below) — an object has identity and behavior; a value doesn't.

**What doesn't need naming:** a single expression whose only job is to *build* a value that goes
straight into the one call or `return` that consumes it — a model constructor, a query-operator tree.
That's already one job, not two; a name would only restate what the expression already says. Don't
confuse this with the chained-calls case above — the difference is whether a *second, independent*
piece of work (another lookup, another round trip) is nested inside the first.

```python
# Fine — pure construction, handed straight to the one call that consumes it; nothing here
# does independent work, so there's no second step for a name to separate out:
products = Product.find(
    Or(
        RegEx(Product.name, pattern, "i"),
        RegEx(Product.sku, pattern, "i"),
    ),
)

# Fine — same reasoning on return: constructing the value *is* the return:
def get_user(user_id: int) -> User:
    """Load a user by id."""
    return User(id=user_id, name="Ada")

# Fine — a trivial, self-evident one-off, such as a single test assertion. Naming it would
# add a line without adding clarity:
assert ProductRepository().document is Product
```

### Walrus operator

`:=` fuses naming and use into one line. Reach for it exactly when the named value is consumed
**only** by the expression it's declared in — nowhere else in the surrounding block. The moment the
value is needed again later, fall back to a plain statement; a walrus whose name leaks into later use
hides a value the rest of the function still depends on.

```python
# Good — rows is used only inside this if, nowhere else in the loop body:
for task in TASK_ORDER:
    if rows := rows_by_task.get(task):
        render_section(task, rows)

    log_progress(task)

# Bad — rows is walrus-assigned but then reused below; the second use is easy to miss:
for task in TASK_ORDER:
    if rows := rows_by_task.get(task):
        render_section(task, rows)

    log_progress(task, rows)  # ← silently depends on the walrus from the `if`

# Good — reused later, so it's a plain statement instead:
for task in TASK_ORDER:
    rows = rows_by_task.get(task)

    if rows:
        render_section(task, rows)

    log_progress(task, rows)
```

## Argument-Passing Style

Positional vs. keyword is decided by whether the parameter's meaning is obvious at the call site and
whether the call fits on one line — never by whether the call happens to wrap.

- **Positional** when the meaning is obvious and the call fits on one line.
- **Keyword** when the meaning isn't obvious, even if it fits on one line.
- **Keyword** once the call needs to wrap across multiple lines — every argument should read without
  checking the signature.
- A call whose arguments are **already self-describing on their own** (a `*args`-style spread of
  named comparison expressions, say) doesn't need per-item keywords invented just because it wraps —
  bundling them into a fake `args=(...)` keyword adds a layer that says nothing a keyword wouldn't
  already say if the arguments actually needed one.

```python
# Bad — user_id's meaning is obvious; the keyword adds nothing:
repository.get_user(user_id=user_id)

# Good:
repository.get_user(user_id)

# Bad — "John" and the email string give no clue which is which:
repository.create_user("John", "john.doe@example.com")

# Good — keyword even though it fits on one line, because the meaning isn't obvious:
repository.create_user(username="John", email="john.doe@example.com")

# Bad — wrapped, but still positional; every line needs a trip to the signature:
image_set = ImageBundle.extract(
    product.description_html,
    base_url,
    self.source,
    product.source_id,
    product.images,
)

# Good — keyword once it wraps, so every argument is self-describing:
image_set = ImageBundle.extract(
    description_html=product.description_html,
    base_url=base_url,
    source=self.source,
    source_id=product.source_id,
    images=product.images,
)

# Bad — repository.query(*expressions) takes comparison expressions that already read on
# their own; wrapping them in a fake args= keyword adds nothing:
repository.query(
    args=(
        Snapshot.status == Status.pending,
        Snapshot.source == Source.channel,
    ),
)

# Good — positional, wrapped, and still self-describing without a keyword:
repository.query(
    Snapshot.status == Status.pending,
    Snapshot.source == Source.channel,
)
```
