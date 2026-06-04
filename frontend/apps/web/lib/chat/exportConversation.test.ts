/**
 * Markdown -> HTML transform used by the PDF export. Locks in the behaviours
 * we care about: assistant markdown stops looking like source code in the
 * exported PDF, AND injected HTML in user content / model content cannot
 * reach the print iframe as live markup.
 */
import { describe, expect, it } from 'vitest';

import { renderMarkdownToHtml } from './exportConversation';

describe('renderMarkdownToHtml', () => {
  it('renders headings as h1/h2/h3', () => {
    const out = renderMarkdownToHtml('# A\n\n## B\n\n### C');
    expect(out).toContain('<h1>A</h1>');
    expect(out).toContain('<h2>B</h2>');
    expect(out).toContain('<h3>C</h3>');
  });

  it('renders bold and italic spans', () => {
    const out = renderMarkdownToHtml('Plain **bold** and *ital* and __also bold__.');
    expect(out).toContain('<strong>bold</strong>');
    expect(out).toContain('<em>ital</em>');
    expect(out).toContain('<strong>also bold</strong>');
  });

  it('renders bullet and numbered lists', () => {
    const bullets = renderMarkdownToHtml('- One\n- Two\n- Three');
    expect(bullets).toContain('<ul><li>One</li><li>Two</li><li>Three</li></ul>');
    const numbered = renderMarkdownToHtml('1. First\n2. Second');
    expect(numbered).toContain('<ol><li>First</li><li>Second</li></ol>');
  });

  it('renders fenced code blocks with the language class', () => {
    const out = renderMarkdownToHtml('```python\nprint("hi")\n```');
    expect(out).toContain('<pre><code class="language-python">print(&quot;hi&quot;)\n</code></pre>');
  });

  it('renders inline code', () => {
    const out = renderMarkdownToHtml('Use `WHP` carefully.');
    expect(out).toContain('<code>WHP</code>');
  });

  it('renders links with href attribute', () => {
    const out = renderMarkdownToHtml('[label](https://example.com)');
    expect(out).toContain('<a href="https://example.com">label</a>');
  });

  it('paragraph-wraps prose without markdown markers', () => {
    const out = renderMarkdownToHtml('First paragraph.\n\nSecond paragraph.');
    expect(out).toContain('<p>First paragraph.</p>');
    expect(out).toContain('<p>Second paragraph.</p>');
  });

  it('preserves single line breaks inside a paragraph as <br />', () => {
    const out = renderMarkdownToHtml('Line one\nLine two');
    expect(out).toContain('Line one<br />Line two');
  });

  it('html in source content is escaped, not executed', () => {
    const out = renderMarkdownToHtml('Watch out: <script>alert(1)</script>');
    expect(out).not.toContain('<script>');
    expect(out).toContain('&lt;script&gt;');
  });

  it('html inside a fenced code block is also escaped', () => {
    const out = renderMarkdownToHtml('```\n<script>x</script>\n```');
    expect(out).toContain('&lt;script&gt;x&lt;/script&gt;');
    expect(out).not.toContain('<script>x</script>');
  });

  it('returns empty string for empty input', () => {
    expect(renderMarkdownToHtml('')).toBe('');
  });
});
