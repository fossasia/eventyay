import { getRichTextExtensions } from './richtext.js'
import { PlaceholderVariable } from '../extensions/placeholder-variable.js'

/**
 * Returns Tiptap extensions for the email body editor profile.
 * Extends the richtext profile with placeholder variable insertion.
 */
export function getEmailExtensions() {
  return [
    ...getRichTextExtensions(),
    PlaceholderVariable,
  ]
}
