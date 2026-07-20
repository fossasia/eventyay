import { Node, mergeAttributes } from '@tiptap/core'

/**
 * A non-editable inline node that represents an email template placeholder,
 * e.g. {attendee_name}. Serialises as {variable} (single braces, no spaces)
 * so the back-end email renderer can expand it via Python's str.format_map().
 * Double-brace notation {{ var }} is NOT used because Python format_map treats
 * {{ and }} as escapes for literal braces, not a substitution.
 */
export const PlaceholderVariable = Node.create({
  name: 'placeholderVariable',
  group: 'inline',
  inline: true,
  atom: true,

  addAttributes() {
    return {
      variable: {
        default: null,
        parseHTML: (element) => element.getAttribute('data-variable'),
        renderHTML: (attributes) => ({ 'data-variable': attributes.variable }),
      },
    }
  },

  parseHTML() {
    return [{ tag: 'span[data-variable]' }]
  },

  renderHTML({ HTMLAttributes }) {
    const attrs = mergeAttributes(HTMLAttributes, {
      class: 'tiptap-placeholder-chip',
      contenteditable: 'false',
    })
    // Text content uses single braces so Python format_map() expands it.
    return ['span', attrs, `{${HTMLAttributes['data-variable']}}`]
  },

  renderText({ node }) {
    return `{${node.attrs.variable}}`
  },

  addCommands() {
    return {
      insertPlaceholder:
        (variable) =>
        ({ commands }) => {
          return commands.insertContent({
            type: this.name,
            attrs: { variable },
          })
        },
    }
  },
})
