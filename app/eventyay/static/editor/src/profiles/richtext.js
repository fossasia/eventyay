import StarterKit from '@tiptap/starter-kit'
import Underline from '@tiptap/extension-underline'
import Link from '@tiptap/extension-link'

/**
 * Returns Tiptap extensions for the simple rich text profile.
 * Supports: bold, italic, underline, headings (H1–H6), bullet list, ordered list,
 * link, blockquote, undo/redo.
 */
export function getRichTextExtensions() {
  return [
    StarterKit.configure({
      heading: { levels: [1, 2, 3, 4, 5, 6] },
      codeBlock: false,
      code: false,
      horizontalRule: false,
    }),
    Underline,
    Link.configure({
      openOnClick: false,
      autolink: false,
      HTMLAttributes: {
        rel: 'noopener noreferrer',
        target: '_blank',
      },
    }),
  ]
}
