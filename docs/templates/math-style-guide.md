# Mathematical Notation Style Guide & Cross-Platform Math Specification

This guide defines the syntax standards and compatibility rules for writing mathematical expressions across Markdown documentation in this repository. Adhering to these standards ensures formulas render reliably and identically across both the GitHub web interface (cmark-gfm + MathJax) and local VS Code Markdown Preview (markdown-it + KaTeX).

---

## 1. The Rendering Discrepancy (Root Cause)

GitHub and VS Code process Markdown mathematics using different parsing pipelines:

1. **GitHub Pipeline (CommonMark / `cmark-gfm` + MathJax):**
   - GitHub parses Markdown paragraphs and inline text using CommonMark *before* MathJax renders math expressions.
   - Under Section 2.4 of the CommonMark specification, any ASCII punctuation character immediately preceded by a backslash is treated as an escape sequence. The backslash is stripped and replaced with the literal character.
   - When LaTeX math is enclosed in `$...$` or `$$...$$` within a Markdown paragraph, CommonMark strips backslashes before ASCII punctuation:
     - `\big\{` becomes `\big{`
     - `\left\{` becomes `\left{`
     - `\{0, 1\}` becomes `{0, 1}`
     - `, \,` becomes `, ,`
     - `\|` becomes `|`
     - `\%` becomes `%`
   - MathJax then attempts to parse the stripped LaTeX. Because `{` is not a valid delimiter in TeX (it denotes a macro argument group, whereas `\{` or `\lbrace` is the delimiter), MathJax halts with:

     ```text
     Missing or unrecognized delimiter for \big
     ```

     or

     ```text
     Missing or unrecognized delimiter for \left
     ```

   - Furthermore, bare `{0, 1}` in TeX is invisible grouping, causing set braces to vanish entirely from rendered output, while bare `%` is treated as a TeX comment, discarding the remainder of the formula.

2. **VS Code Pipeline (`markdown-it` + KaTeX):**
   - VS Code's `markdown-math` extension registers rules that extract math blocks and inline expressions directly from raw document text *before* inline CommonMark escape resolution.
   - KaTeX receives `\big\{` and renders it without error, masking the breaking syntax during local preview.

---

## 2. Universal Cross-Platform Rules

To ensure equations render consistently in both GitHub and VS Code, adhere to the following conventions:

### Rule 1: Use `\lbrace` and `\rbrace` for Curly Braces and Delimiters

CommonMark only unescapes ASCII punctuation characters. It **never** strips backslashes before ASCII letters (`l`, `r`). Both KaTeX and MathJax treat `\lbrace` and `\rbrace` as standard curly brace delimiters.

| Syntax Context | ❌ Avoid (Fails on GitHub) | ✅ Recommended (Works in Both) | Rendered Meaning |
| :--- | :--- | :--- | :--- |
| **Sized Delimiters** | `\big\{ ... \big\}` | `\big\lbrace ... \big\rbrace` | Scaled curly brackets |
| **Large Delimiters** | `\Big\{ ... \Big\}` | `\Big\lbrace ... \Big\rbrace` | Larger scaled brackets |
| **Auto Delimiters** | `\left\{ ... \right\}` | `\left\lbrace ... \right\rbrace` | Content-scaled brackets |
| **Set Notation** | `\{0, 1, \dots, N\}` | `\lbrace 0, 1, \dots, N \rbrace` | Literal set braces $\lbrace 0, 1, \dots, N \rbrace$ |

### Rule 2: Use `\lVert` and `\rVert` for Norms

CommonMark strips the backslash in `\|`, leaving a single bar `|` and degrading vector norms to absolute value bars.

| Syntax Context | ❌ Avoid (Degrades on GitHub) | ✅ Recommended (Works in Both) | Rendered Meaning |
| :--- | :--- | :--- | :--- |
| **Vector Norm** | `\|\mathbf{x}\|_2` | `\lVert \mathbf{x} \rVert_2` | $L_2$ norm $\lVert \mathbf{x} \rVert_2$ |
| **Matrix Norm** | `\|\mathbf{W}\|_F` | `\lVert \mathbf{W} \rVert_F` | Frobenius norm |

### Rule 3: Avoid Redundant Comma Spacing (`, \,`)

In LaTeX math mode, commas automatically include standard mathematical punctuation spacing (`\mathpunct`). Adding `\,` after a comma produces `, ,` on GitHub because `\,` is unescaped to `,`.

- ❌ **Avoid:** `((x+1)\bmod 4, y), \, ((x-1)\bmod 4, y)`
- ✅ **Recommended:** `((x+1)\bmod 4, y), ((x-1)\bmod 4, y)`
- If explicit spacing is required between math elements, use named alphabetical commands: `\thinspace`, `\enspace`, `\quad`, or `\text{, }`.

### Rule 4: Keep Percentages Outside Math Mode

CommonMark unescapes `\%` to `%` inside math spans, which MathJax interprets as a TeX comment that comments out the rest of the equation or closing `$`.

- ❌ **Avoid:** `$73.9\%$`, `$95.0\%$`, `$\Delta K = +80\%$`
- ✅ **Recommended in prose/tables:** `73.9%`, `95.0%`, `$\Delta K = +80$%`
- ✅ **Recommended in formal equations:** `\text{95.0%}` or `\text{\%}`

### Rule 5: Avoid Underscores Inside `\text{...}`

In math mode, `\_` inside `\text{...}` unescapes to `_`, which triggers a KaTeX/MathJax syntax error (`Expected 'EOF', got '_'`).

- ❌ **Avoid:** `W_{\text{sum\_max}}`, `\text{active\_metaplastic}`
- ✅ **Recommended:** `W_{\text{sum-max}}` or `W_{\text{sum},\text{max}}`, `\text{active-metaplastic}`

---

## 3. Display Math Options

Both GitHub and VS Code support two methods for standalone display blocks:

### Option A: Standard `$$...$$` Blocks (with Control Words)

Place `$$` on separate lines and use control-word delimiters:

```markdown
$$
\mathcal{V} = \big\lbrace (x, y) \mid x, y \in \mathbb{Z}_4 \big\rbrace \cong \lbrace 0, 1, \dots, 15 \rbrace
$$
```

### Option B: Fenced `math` Code Blocks

For complex multi-line derivations, piecewise functions (`cases`), or matrices where multiple TeX control symbols appear, fenced ```` ```math ```` blocks completely bypass CommonMark inline parsing on both GitHub and VS Code:

````markdown
```math
s_i(t) = \begin{cases} 1 & \text{if } V_i(t) \ge \theta_i(t) \\ 0 & \text{otherwise} \end{cases}
```
````

---

## 4. Quick Verification Checklist

Before committing Markdown files containing mathematics:

1. [ ] Check that no `\big\{`, `\Big\{`, or `\left\{` constructs exist (use `\lbrace`).
2. [ ] Check that set notation uses `\lbrace ... \rbrace` so brackets render.
3. [ ] Check that norm operators use `\lVert ... \rVert` rather than `\|`.
4. [ ] Check that no `, \,` sequences exist.
5. [ ] Check that percentage symbols are written outside math mode or inside `\text{}`.
6. [ ] Run `markdownlint-cli2 "**/*.md"` to verify markdown structural conformance.
