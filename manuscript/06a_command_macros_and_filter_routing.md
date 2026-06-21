# Command Grammar: Macros and Filter Routing {#sec:grammar-macros-filter-routing}

## Mode Switching Macros

```text
/mode --observatory
/mode --lab
/mode --ship
```

Each macro resolves to exactly one of the three valid decks. Writing $M$ for the
deck set, the resolution is a lookup into the fixed flag table:

$$
\mathrm{mode}(\ell) =
\begin{cases}
\textsf{OBSERVATORY} & \text{if flag} \in \{\,\texttt{-{}-observatory}\,\},\\
\textsf{LABORATORY}  & \text{if flag} \in \{\,\texttt{-{}-lab},\ \texttt{-{}-laboratory}\,\},\\
\textsf{EXPEDITION}  & \text{if flag} \in \{\,\texttt{-{}-ship},\ \texttt{-{}-expedition}\,\},\\
\bot & \text{otherwise.}
\end{cases}
$$ {#eq:command_grammar-3}

An unrecognized target falls to the $\bot$ branch of @eq:command_grammar-3 and raises
a command error rather than leaving the console in an ambiguous trim. The aliases
(`--lab`/`--laboratory`, `--ship`/`--expedition`) are accepted so spoken shorthand
and full names land on the same deck.

## Dynamic Filter Routing via the EGS Fractal Constant

```text
/transducer bind source_cam_01 --ratio=1.618034
```

Binds a named source into the transducer matrix at the requested golden ratio. The
default operating point is $\varphi = 1.6180339887\ldots$ — El Gran Sol's Fractal
Constant for *layout* — but the operator may dial any strictly positive ratio. The
bind is admitted only when both the source name and a positive ratio are present:

$$
\mathrm{valid}_{\text{bind}}
\iff
(\,\text{positional}_0 = \texttt{bind}\,)
\;\land\;
(\,\text{source} \neq \varepsilon\,)
\;\land\;
(\,r > 0\,),
\qquad r \in \mathbb{R}.
$$ {#eq:command_grammar-4}

A missing source, a non-numeric ratio, or any $r \le 0$ violates
@eq:command_grammar-4 and routes to $\bot$ — the matrix never binds against a
degenerate or sign-flipped scale.
