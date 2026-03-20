import DOMPurify from 'dompurify'

export function sanitizeHTML(dirty: string): string {
  return DOMPurify.sanitize(dirty, {
    ALLOWED_TAGS: [
      'h1', 'h2', 'h3', 'h4', 'p', 'ul', 'ol', 'li', 'strong', 'em',
      'a', 'code', 'pre', 'blockquote', 'table', 'thead', 'tbody', 'tr',
      'th', 'td', 'br', 'hr', 'div', 'span', 'img',
    ],
    ALLOWED_ATTR: ['href', 'target', 'rel', 'class', 'src', 'alt', 'width', 'height'],
    ADD_ATTR: ['target'],
  })
}
