import StarterKit from '@tiptap/starter-kit'
import Underline from '@tiptap/extension-underline'
import Link from '@tiptap/extension-link'

/**
 * Returns Tiptap extensions for the simple rich text profile.
 * Supports: bold, italic, underline, bullet list, ordered list,
 * link, blockquote, undo/redo.
 * Headings are excluded to keep the toolbar minimal.
 */
export function getRichTextExtensions() {
  return [
    StarterKit.configure({
      heading: false,
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
