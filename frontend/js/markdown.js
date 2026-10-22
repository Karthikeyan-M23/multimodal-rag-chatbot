/*
 * Minimal, safe Markdown renderer for model answers.
 * All input is HTML-escaped first; only the constructs below are
 * turned into markup. Citations like [1] or [1, 2] become buttons.
 */

const Markdown = (() => {

    function escapeHtml(text) {
        return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function citations(html, maxCitation) {

        return html.replace(/\[(\d+(?:\s*,\s*\d+)*)\]/g, (match, list) => {

            const numbers = list.split(",").map(n => Number(n.trim()));

            if (numbers.some(n => n < 1 || n > maxCitation)) {
                return match;
            }

            return numbers
                .map(n => `<button type="button" class="cite" data-cite="${n}" aria-label="Source ${n}">${n}</button>`)
                .join("");
        });
    }

    function inline(text, maxCitation) {

        const codes = [];

        let html = text.replace(/`([^`]+)`/g, (match, code) => {
            codes.push(`<code>${code}</code>`);
            return `\u0000${codes.length - 1}\u0000`;
        });

        html = html
            .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
            .replace(/__([^_]+)__/g, "<strong>$1</strong>")
            .replace(/(^|[^*])\*([^*\s][^*]*)\*/g, "$1<em>$2</em>")
            .replace(
                /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
                '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
            );

        html = citations(html, maxCitation);

        return html.replace(/\u0000(\d+)\u0000/g, (match, index) => codes[Number(index)]);
    }

    function isTableDivider(line) {
        return /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(line);
    }

    function tableCells(line) {
        return line
            .trim()
            .replace(/^\|/, "")
            .replace(/\|$/, "")
            .split("|")
            .map(cell => cell.trim());
    }

    function render(source, maxCitation = 99) {

        const blocks = [];
        const text = escapeHtml(source || "").replace(/\r\n/g, "\n");

        // Fenced code blocks first, so their content is left alone.
        const withoutFences = text.replace(/```[\w-]*\n?([\s\S]*?)(```|$)/g, (match, code) => {
            blocks.push(`<pre><code>${code.replace(/\n$/, "")}</code></pre>`);
            return `\n\u0001${blocks.length - 1}\u0001\n`;
        });

        const lines = withoutFences.split("\n");
        const out = [];
        let paragraph = [];
        let list = null;

        const flushParagraph = () => {
            if (paragraph.length) {
                out.push(`<p>${inline(paragraph.join("<br>"), maxCitation)}</p>`);
                paragraph = [];
            }
        };

        const flushList = () => {
            if (list) {
                out.push(
                    `<${list.type}>` +
                    list.items.map(item => `<li>${inline(item, maxCitation)}</li>`).join("") +
                    `</${list.type}>`
                );
                list = null;
            }
        };

        for (let i = 0; i < lines.length; i++) {

            const line = lines[i];
            const fence = line.match(/^\u0001(\d+)\u0001$/);

            if (fence) {
                flushParagraph();
                flushList();
                out.push(blocks[Number(fence[1])]);
                continue;
            }

            if (!line.trim()) {
                flushParagraph();
                flushList();
                continue;
            }

            const heading = line.match(/^(#{1,4})\s+(.*)$/);

            if (heading) {
                flushParagraph();
                flushList();
                const level = Math.min(heading[1].length + 2, 4);
                out.push(`<h${level}>${inline(heading[2], maxCitation)}</h${level}>`);
                continue;
            }

            if (line.includes("|") && i + 1 < lines.length && isTableDivider(lines[i + 1])) {

                flushParagraph();
                flushList();

                const header = tableCells(line);
                const rows = [];
                i += 2;

                while (i < lines.length && lines[i].includes("|") && lines[i].trim()) {
                    rows.push(tableCells(lines[i]));
                    i++;
                }

                i--;

                out.push(
                    '<div class="table-wrap"><table><thead><tr>' +
                    header.map(cell => `<th>${inline(cell, maxCitation)}</th>`).join("") +
                    "</tr></thead><tbody>" +
                    rows.map(row =>
                        "<tr>" + row.map(cell => `<td>${inline(cell, maxCitation)}</td>`).join("") + "</tr>"
                    ).join("") +
                    "</tbody></table></div>"
                );
                continue;
            }

            const bullet = line.match(/^\s*[-*•]\s+(.*)$/);
            const numbered = line.match(/^\s*\d+[.)]\s+(.*)$/);

            if (bullet || numbered) {
                flushParagraph();
                const type = bullet ? "ul" : "ol";

                if (!list || list.type !== type) {
                    flushList();
                    list = { type, items: [] };
                }

                list.items.push((bullet || numbered)[1]);
                continue;
            }

            // Continuation of a list item.
            if (list && /^\s{2,}\S/.test(line)) {
                list.items[list.items.length - 1] += " " + line.trim();
                continue;
            }

            flushList();
            paragraph.push(line);
        }

        flushParagraph();
        flushList();

        return out.join("");
    }

    return { render, escapeHtml };

})();
