import type { Conversation } from './conversations';
import type { AssistantMessage, Message, UserMessage } from './types';

const ISO = (n: number) => new Date(n).toISOString();
const SAFE_FILENAME_RE = /[^a-z0-9-_]+/gi;

export function conversationToMarkdown(conv: Conversation): string {
  const lines: string[] = [];
  lines.push(`# ${conv.title}`);
  lines.push('');
  lines.push(`> Exported from PetroBrain - ${new Date().toISOString()}`);
  lines.push(`> Created: ${ISO(conv.createdAt)} - Updated: ${ISO(conv.updatedAt)}`);
  if (conv.messages.length === 0) {
    lines.push('');
    lines.push('_(empty conversation)_');
    return lines.join('\n');
  }
  lines.push('');
  lines.push('---');
  for (const m of conv.messages) {
    lines.push('');
    if (m.role === 'user') {
      lines.push(...renderUser(m));
    } else {
      lines.push(...renderAssistant(m));
    }
  }
  lines.push('');
  lines.push('---');
  lines.push('');
  lines.push(
    'PetroBrain is decision support - verify safety-critical numbers with the competent person before acting.',
  );
  return lines.join('\n');
}

function renderUser(m: UserMessage): string[] {
  const out: string[] = [`## You - ${ISO(m.createdAt)}`, ''];
  if (m.module && m.module !== 'general') {
    out.push(`_Module: ${m.module}${m.assetContext ? ` - Asset: ${m.assetContext}` : ''}_`);
    out.push('');
  } else if (m.assetContext) {
    out.push(`_Asset: ${m.assetContext}_`);
    out.push('');
  }
  if (m.text.trim()) {
    out.push(m.text.trim());
  }
  if (m.attachments && m.attachments.length > 0) {
    out.push('');
    out.push('**Attachments:**');
    for (const a of m.attachments) {
      out.push(`- ${a.name} (${a.kind}, ${formatBytes(a.sizeBytes)})`);
    }
  }
  return out;
}

function renderAssistant(m: AssistantMessage): string[] {
  const out: string[] = [`## PetroBrain - ${ISO(m.createdAt)}`, ''];
  if (m.error) {
    out.push(`> Error: ${m.error}`);
    out.push('');
  }
  if (m.text.trim()) {
    out.push(m.text.trim());
  }
  if (m.citations.length > 0) {
    out.push('');
    out.push('**Citations:**');
    for (const c of m.citations) {
      const parts = [c.title, c.revision, c.clause].filter(Boolean).join(' - ');
      out.push(`- ${parts}${c.url ? ` (${c.url})` : ''}`);
    }
  }
  if (m.flags.length > 0) {
    out.push('');
    out.push(`**Flags:** ${m.flags.join(', ')}`);
  }
  return out;
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export function downloadMarkdown(filename: string, content: string): void {
  const safe = (filename.replace(SAFE_FILENAME_RE, '-').replace(/-+/g, '-').slice(0, 80) || 'conversation') + '.md';
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
  downloadBlob(safe, blob);
}

function downloadBlob(filename: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function exportConversation(conv: Conversation): void {
  downloadMarkdown(conv.title, conversationToMarkdown(conv));
}

export function exportConversationPdf(conv: Conversation): void {
  const title = conv.title || 'PetroBrain conversation';
  const dateStamp = new Date().toISOString().slice(0, 10);
  const docTitle = `PetroBrain - ${title} - ${dateStamp}`;
  const html = renderConversationPrintHtml(conv, title, docTitle);
  printHtml(docTitle, html);
}

export function assistantMessageToMarkdown(
  message: AssistantMessage,
  title = 'PetroBrain answer',
): string {
  const lines: string[] = [];
  lines.push(`# ${title}`);
  lines.push('');
  lines.push(`> Exported from PetroBrain - ${new Date().toISOString()}`);
  lines.push('');
  lines.push(...renderAssistant(message));
  lines.push('');
  lines.push('---');
  lines.push('');
  lines.push(
    'PetroBrain is decision support - verify safety-critical numbers with the competent person before acting.',
  );
  return lines.join('\n');
}

export function exportAssistantMessageMarkdown(
  message: AssistantMessage,
  title = 'PetroBrain answer',
): void {
  downloadMarkdown(title, assistantMessageToMarkdown(message, title));
}

export function exportAssistantMessageText(
  message: AssistantMessage,
  title = 'PetroBrain answer',
): void {
  const safe = `${safeFileStem(title)}.txt`;
  downloadBlob(safe, new Blob([message.text.trim()], { type: 'text/plain;charset=utf-8' }));
}

export function exportAssistantMessageWord(
  message: AssistantMessage,
  title = 'PetroBrain answer',
): void {
  const dateStamp = new Date().toISOString().slice(0, 10);
  const docTitle = `PetroBrain - ${title} - ${dateStamp}`;
  const html = renderAssistantDocumentHtml(message, title, docTitle);
  const safe = `${safeFileStem(title)}.doc`;
  downloadBlob(
    safe,
    new Blob(['\ufeff', html], { type: 'application/msword;charset=utf-8' }),
  );
}

export function exportAssistantMessagePdf(
  message: AssistantMessage,
  title = 'PetroBrain answer',
): void {
  const dateStamp = new Date().toISOString().slice(0, 10);
  const docTitle = `PetroBrain - ${title} - ${dateStamp}`;
  const html = renderAssistantDocumentHtml(message, title, docTitle);
  printHtml(docTitle, html);
}

function safeFileStem(filename: string): string {
  return filename.replace(SAFE_FILENAME_RE, '-').replace(/-+/g, '-').slice(0, 80) || 'petrobrain-answer';
}

function printHtml(docTitle: string, html: string): void {
  // Hidden same-origin iframe avoids the popup blocker that
  // window.open trips, and prints just the conversation rather than the
  // whole React app the way window.print() on the host page would.
  const frame = document.createElement('iframe');
  frame.setAttribute('aria-hidden', 'true');
  frame.style.position = 'fixed';
  frame.style.right = '0';
  frame.style.bottom = '0';
  frame.style.width = '0';
  frame.style.height = '0';
  frame.style.border = '0';
  document.body.appendChild(frame);

  const doc = frame.contentDocument;
  const win = frame.contentWindow;
  if (!doc || !win) {
    // Last resort fallback: open a tab. Better than printing the host app
    // through window.print().
    const popup = window.open('', '_blank', 'noopener,noreferrer,width=960,height=1200');
    if (popup) {
      popup.document.title = docTitle;
      popup.document.write(html);
      popup.document.close();
      popup.focus();
      window.setTimeout(() => popup.print(), 250);
    }
    frame.remove();
    return;
  }
  doc.open();
  doc.write(html);
  doc.close();
  // The print dialog blocks until the user dismisses it; cleanup happens
  // afterward. Use a small delay so layout settles for the print engine.
  window.setTimeout(() => {
    try {
      win.focus();
      win.print();
    } finally {
      window.setTimeout(() => frame.remove(), 1000);
    }
  }, 200);
}

export function isExportable(messages: Message[]): boolean {
  return messages.length > 0 && messages.some((m) => m.text.trim().length > 0);
}

function renderAssistantDocumentHtml(
  message: AssistantMessage,
  title: string,
  docTitle: string,
): string {
  const body = renderMarkdownToHtml(message.text.trim() || 'No answer text available.');
  const sources =
    message.citations.length > 0
      ? `<section class="meta-block"><h2>Sources</h2><ul>${message.citations
          .map((c) => {
            const label = [c.title, c.revision, c.clause].filter(Boolean).join(' - ');
            return `<li>${escapeHtml(label || c.url || 'Source')}${
              c.url ? ` - ${escapeHtml(c.url)}` : ''
            }</li>`;
          })
          .join('')}</ul></section>`
      : '';
  const flags =
    message.flags.length > 0
      ? `<section class="meta-block"><h2>Notes</h2><p>${escapeHtml(message.flags.join(', '))}</p></section>`
      : '';

  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>${escapeHtml(docTitle)}</title>
  <style>
    @page { margin: 18mm; }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: #ffffff;
      color: #171717;
      font-family: Arial, Helvetica, sans-serif;
      font-size: 13px;
      line-height: 1.6;
    }
    header {
      border-bottom: 2px solid #ea580c;
      margin-bottom: 22px;
      padding-bottom: 14px;
    }
    h1 {
      margin: 0 0 6px;
      font-size: 24px;
      line-height: 1.2;
    }
    h2 {
      margin: 16px 0 8px;
      font-size: 15px;
      line-height: 1.3;
    }
    .meta {
      color: #666;
      font-size: 11px;
    }
    .answer {
      border: 1px solid #ddd;
      border-radius: 10px;
      padding: 14px;
    }
    .answer p { margin: 0 0 8px; }
    .answer p:last-child { margin-bottom: 0; }
    .answer h1, .answer h2, .answer h3 { margin: 12px 0 6px; line-height: 1.3; }
    .answer h1 { font-size: 18px; }
    .answer h2 { font-size: 16px; }
    .answer h3 { font-size: 14px; }
    .answer ul, .answer ol { margin: 4px 0 8px; padding-left: 22px; }
    .answer li { margin: 2px 0; }
    .answer code {
      background: #f3f4f6;
      border-radius: 3px;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 12px;
      padding: 1px 4px;
    }
    .answer pre {
      background: #f3f4f6;
      border-radius: 6px;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 12px;
      margin: 6px 0 10px;
      overflow-x: auto;
      padding: 8px 10px;
      white-space: pre-wrap;
    }
    .answer a { color: #c2410c; text-decoration: underline; }
    .meta-block {
      border-top: 1px solid #ddd;
      color: #555;
      font-size: 11px;
      margin-top: 18px;
      padding-top: 10px;
    }
    .meta-block ul { margin: 6px 0 0; padding-left: 18px; }
    footer {
      border-top: 1px solid #ddd;
      color: #666;
      font-size: 11px;
      margin-top: 24px;
      padding-top: 10px;
    }
    @media print {
      body { print-color-adjust: exact; -webkit-print-color-adjust: exact; }
    }
  </style>
</head>
<body>
  <header>
    <h1>${escapeHtml(title)}</h1>
    <div class="meta">Exported from PetroBrain on ${escapeHtml(new Date().toLocaleString())}</div>
  </header>
  <main>
    <section class="answer">${body}</section>
    ${sources}
    ${flags}
  </main>
  <footer>PetroBrain is decision support. Verify safety-critical numbers with the competent person before acting.</footer>
</body>
</html>`;
}

function renderConversationPrintHtml(
  conv: Conversation, title: string, docTitle?: string,
): string {
  const messages = conv.messages.map(renderPrintMessage).join('');
  return `<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>${escapeHtml(docTitle ?? title)}</title>
  <style>
    @page { margin: 18mm; }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: #ffffff;
      color: #171717;
      font-family: Arial, Helvetica, sans-serif;
      font-size: 13px;
      line-height: 1.55;
    }
    header {
      border-bottom: 2px solid #ea580c;
      margin-bottom: 22px;
      padding-bottom: 14px;
    }
    h1 {
      margin: 0 0 6px;
      font-size: 24px;
      line-height: 1.2;
    }
    .meta {
      color: #666;
      font-size: 11px;
    }
    .message {
      break-inside: avoid;
      border: 1px solid #ddd;
      border-radius: 10px;
      margin: 0 0 14px;
      overflow: hidden;
    }
    .role {
      align-items: center;
      background: #f7f7f7;
      border-bottom: 1px solid #ddd;
      display: flex;
      justify-content: space-between;
      gap: 16px;
      padding: 8px 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 10px;
      font-weight: 700;
      color: #555;
    }
    .message.user .role {
      background: #fff7ed;
      color: #9a3412;
    }
    .message.assistant .role {
      background: #f5f5f5;
      color: #262626;
    }
    .body {
      padding: 12px;
    }
    .body p { margin: 0 0 8px; }
    .body p:last-child { margin-bottom: 0; }
    .body h1, .body h2, .body h3 { margin: 12px 0 6px; line-height: 1.3; }
    .body h1 { font-size: 17px; }
    .body h2 { font-size: 15px; }
    .body h3 { font-size: 14px; }
    .body ul, .body ol { margin: 4px 0 8px; padding-left: 22px; }
    .body li { margin: 2px 0; }
    .body code {
      background: #f3f4f6;
      border-radius: 3px;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 12px;
      padding: 1px 4px;
    }
    .body pre {
      background: #f3f4f6;
      border-radius: 6px;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 12px;
      margin: 6px 0 10px;
      overflow-x: auto;
      padding: 8px 10px;
      white-space: pre-wrap;
    }
    .body a { color: #c2410c; text-decoration: underline; }
    .body strong { font-weight: 700; }
    .body em { font-style: italic; }
    .attachments, .sources, .flags {
      border-top: 1px solid #eee;
      color: #555;
      font-size: 11px;
      padding: 8px 12px;
    }
    footer {
      border-top: 1px solid #ddd;
      color: #666;
      font-size: 11px;
      margin-top: 24px;
      padding-top: 10px;
    }
    @media print {
      body { print-color-adjust: exact; -webkit-print-color-adjust: exact; }
    }
  </style>
</head>
<body>
  <header>
    <h1>${escapeHtml(title)}</h1>
    <div class="meta">
      Exported from PetroBrain on ${escapeHtml(new Date().toLocaleString())}<br />
      Created ${escapeHtml(new Date(conv.createdAt).toLocaleString())} · Updated ${escapeHtml(new Date(conv.updatedAt).toLocaleString())}
    </div>
  </header>
  <main>${messages || '<p>This conversation is empty.</p>'}</main>
  <footer>PetroBrain is decision support. Verify safety-critical numbers with the competent person before acting.</footer>
</body>
</html>`;
}

function renderPrintMessage(m: Message): string {
  const role = m.role === 'user' ? 'You' : 'PetroBrain';
  const created = new Date(m.createdAt).toLocaleString();
  const body = m.text.trim() || (m.role === 'assistant' && m.streaming ? 'Response in progress.' : '');
  const attachments =
    m.role === 'user' && m.attachments && m.attachments.length > 0
      ? `<div class="attachments"><strong>Attachments:</strong> ${m.attachments
          .map((a) => `${escapeHtml(a.name)} (${escapeHtml(a.kind)}, ${formatBytes(a.sizeBytes)})`)
          .join('; ')}</div>`
      : '';
  const sources =
    m.role === 'assistant' && m.citations.length > 0
      ? `<div class="sources"><strong>Sources:</strong> ${m.citations
          .map((c) => escapeHtml([c.title, c.revision, c.clause, c.url].filter(Boolean).join(' - ')))
          .join('; ')}</div>`
      : '';
  const flags =
    m.role === 'assistant' && m.flags.length > 0
      ? `<div class="flags"><strong>Flags:</strong> ${escapeHtml(m.flags.join(', '))}</div>`
      : '';
  // User messages are plain text - assistant messages may contain markdown
  // (the chat UI renders them with react-markdown). Apply the same
  // transformation here so the PDF doesn't show raw '##', '**', '- ' syntax.
  const rendered = m.role === 'assistant' ? renderMarkdownToHtml(body) : `<p>${escapeHtml(body)}</p>`;
  return `<section class="message ${m.role}">
    <div class="role"><span>${role}</span><span>${escapeHtml(created)}</span></div>
    <div class="body">${rendered}</div>
    ${attachments}${sources}${flags}
  </section>`;
}

/**
 * Tiny markdown -> HTML pass for the PDF export.
 *
 * Deliberately not a full CommonMark implementation - just the subset our
 * assistant actually emits in answers: headings, bold/italic, inline + fenced
 * code, lists, links, paragraphs. Everything is HTML-escaped first so an
 * injected tag in the source text cannot reach the print iframe as live HTML.
 *
 * If we ever need more coverage, swap this for `marked` or `markdown-it` -
 * but the current set covers ~95% of assistant output and keeps the export
 * dependency-free.
 */
export function renderMarkdownToHtml(source: string): string {
  if (!source) return '';
  // 1. Pull fenced code blocks out first so their contents survive the
  //    inline transformations below. Each block is replaced by a token we
  //    re-inject at the end.
  const codeBlocks: string[] = [];
  let text = source.replace(/```([\w-]*)\n([\s\S]*?)```/g, (_match, lang, body) => {
    const cls = lang ? ` class="language-${escapeHtml(String(lang))}"` : '';
    const idx = codeBlocks.length;
    codeBlocks.push(`<pre><code${cls}>${escapeHtml(String(body))}</code></pre>`);
    return ` CODEBLOCK_${idx} `;
  });

  // 2. Escape EVERYTHING else so user / model content cannot smuggle HTML.
  text = escapeHtml(text);

  // 3. Inline pieces (operate on escaped text - safe).
  // Inline code: `code`
  text = text.replace(/`([^`\n]+)`/g, '<code>$1</code>');
  // Bold: **text** or __text__
  text = text.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');
  text = text.replace(/__([^_\n]+)__/g, '<strong>$1</strong>');
  // Italic: *text* or _text_ (avoid eating list markers by requiring a
  // non-space adjacent to the marker).
  text = text.replace(/(^|[^*\w])\*(?!\s)([^*\n]+?)(?<!\s)\*(?!\w)/g, '$1<em>$2</em>');
  text = text.replace(/(^|[^_\w])_(?!\s)([^_\n]+?)(?<!\s)_(?!\w)/g, '$1<em>$2</em>');
  // Links: [label](url) - href value escaped because it's user-untrusted.
  text = text.replace(
    /\[([^\]\n]+)\]\(([^)\s]+)\)/g,
    (_m, label, href) => `<a href="${escapeHtmlAttr(String(href))}">${label}</a>`,
  );

  // 4. Block pieces. Split on blank lines into paragraphs, then upgrade
  //    each block that starts with a heading or list marker.
  const blocks = text.split(/\n{2,}/).map((block) => {
    const trimmed = block.trim();
    if (!trimmed) return '';
    // Skip code-block tokens; they re-inject at the end as full <pre>.
    if (/^ CODEBLOCK_\d+ $/.test(trimmed)) return trimmed;
    // Headings
    const h = /^(#{1,3})\s+(.+)$/.exec(trimmed);
    if (h) {
      const level = h[1]?.length ?? 1;
      const body = h[2] ?? '';
      return `<h${level}>${body}</h${level}>`;
    }
    // Lists - all lines must start with the same marker style.
    const lines = trimmed.split(/\n/);
    if (lines.every((l) => /^\s*[-*+]\s+/.test(l))) {
      const items = lines.map((l) => `<li>${l.replace(/^\s*[-*+]\s+/, '')}</li>`).join('');
      return `<ul>${items}</ul>`;
    }
    if (lines.every((l) => /^\s*\d+\.\s+/.test(l))) {
      const items = lines.map((l) => `<li>${l.replace(/^\s*\d+\.\s+/, '')}</li>`).join('');
      return `<ol>${items}</ol>`;
    }
    // Paragraph: preserve hard line breaks inside.
    const withBreaks = trimmed.replace(/\n/g, '<br />');
    return `<p>${withBreaks}</p>`;
  });

  text = blocks.filter(Boolean).join('\n');

  // 5. Re-inject the fenced code blocks we pulled out at the start.
  text = text.replace(/ CODEBLOCK_(\d+) /g, (_m, idx) => {
    const i = Number(idx);
    return codeBlocks[i] ?? '';
  });
  return text;
}

function escapeHtmlAttr(value: string): string {
  return escapeHtml(value);
}

function escapeHtml(value: string): string {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}
