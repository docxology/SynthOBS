# LaTeX Preamble

This file contains LaTeX packages and commands that are automatically injected into the document compilation process.

> **Infrastructure Note**: This file is parsed by `infrastructure/rendering/latex_utils.py` and combined with the configuration output by `infrastructure/rendering/pdf_renderer.py` before final Pandoc execution to generate the physical PDF holding this text.

```latex
% Core mathematics
\usepackage{amsmath}
\usepackage{amssymb}
\usepackage{amsfonts}
\usepackage{amsthm}
% The renderer's breakable-code helper is also used inside inline equations.
% Keep code readable there without switching \ttfamily directly in math mode.
\protected\def\breaktt#1{\ifmmode\text{\ttfamily\seqsplit{#1}}\else\begingroup\ttfamily\seqsplit{#1}\endgroup\fi}
\newtheorem{theorem}{Theorem}
\newtheorem{remark}[theorem]{Remark}
\newtheorem{example}[theorem]{Example}

% Document layout
\usepackage{geometry}
\geometry{margin=0.25in}
\usepackage{float}
\usepackage{graphicx}

% Tables
\usepackage{booktabs}
\usepackage{longtable}
\usepackage{array}

% Code listings
\usepackage{listings}

% Typography and formatting
\usepackage{microtype}
\usepackage{xcolor}

% Cross-references and citations
\usepackage{hyperref}
\hypersetup{
    colorlinks=true,
    allcolors=red
}
\usepackage[capitalise,noabbrev]{cleveref}
\usepackage{natbib}

% Prefer a Unicode-capable monospaced font without a machine-specific path.
\usepackage{fontspec}
\IfFontExistsTF{JuliaMono}{\setmonofont{JuliaMono}}{
  \IfFontExistsTF{DejaVu Sans Mono}{\setmonofont{DejaVu Sans Mono}}{}
}

% Math font for unicode-math: Latin Modern Math (TeX Live) has full BMP
% coverage including U+2223 (\mid), U+226A/226B (\ll/\gg), and the Greek/
% blackboard letters used in equations. Without an explicit \setmathfont,
% unicode-math falls back to lmroman text font which lacks several glyphs
% and emits "Missing character" warnings on every \mid in math mode.
\setmathfont{latinmodern-math.otf}
```
