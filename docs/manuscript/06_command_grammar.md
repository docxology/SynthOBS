# Command Line Grammar Structure {#sec:grammar}

A persistent terminal line is mounted at the base of the Vessel Console and holds
active focus at all times. At any instant the operator can bypass the button decks
entirely and speak directly to the wavefield through clean, deterministic syntax —
the same channel whether the system is in Observatory, Laboratory, or Expedition
trim. The grammar is implemented by the tested `synthobs.commands` parser, which
returns a typed, frozen command object and fails closed on any unknown verb or
out-of-range value. Nothing in this layer is interpreted as a "best guess": a line
either resolves to one exact intent or it resolves to nothing at all.

Formally, the parser is the total map

$$
\mathrm{parse} : \Sigma^{*} \longrightarrow \mathcal{C} \;\uplus\; \{\,\bot\,\},
$$ {#eq:command_grammar-1}

where $\Sigma^{*}$ is the set of all input lines, $\mathcal{C}$ is the closed set of
typed commands $\{\textsf{ModeCommand},\textsf{BindCommand},\textsf{CalibrateCommand},
\textsf{DashboardCommand}\}$, and $\bot$ is the fail-closed outcome — raised in code
as `CommandError`. Equation @eq:command_grammar-1 is the safety spine of the console:
the image of every line is either a fully-validated command or an explicit refusal,
never a silent no-op.

The fail-closed branch is reached precisely when the line is empty, the verb is
unknown, or any argument falls outside its admissible range:

$$
\mathrm{parse}(\ell) = \bot
\iff
\ell = \varepsilon
\;\lor\;
v(\ell) \notin V
\;\lor\;
\lnot\,\mathrm{valid}\bigl(\mathrm{args}(\ell)\bigr),
$$ {#eq:command_grammar-2}

with $\varepsilon$ the empty line, $v(\ell)$ the leading verb, and
$V = \{\,\texttt{/mode},\ \texttt{/transducer},\ \texttt{/swo},\ \texttt{/dashboard}\,\}$
the registered verb set. Equation @eq:command_grammar-2 is enforced verb-by-verb
below and rendered in Figure @fig:command-parser-pipeline.

The complete grammar, including dashboard planning/building and telemetry examples,
lives in [the parse-pipeline module](06b_command_telemetry_parse_pipeline_and_summary.md).
The macro/filter-routing material lives in
[the adjacent command module](06a_command_macros_and_filter_routing.md).
