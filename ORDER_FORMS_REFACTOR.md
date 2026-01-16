# Order Forms UI Refactoring

## Overview
This branch refactors the order forms configuration UI in the tickets component to use a table-based layout, aligning it with the form options UI used in the talk component.

## Changes Made

### 1. Template Refactoring
**File:** `app/eventyay/control/templates/pretixcontrol/items/orderforms.html`

- Replaced traditional form layout with table-based layout
- Added two separate tables for Customer Data and Attendee Data sections
- Implemented columns: Field, Active, Required, Settings
- Integrated toggle switches for Active/Inactive state
- Added dropdown selectors for Required/Optional state
- Preserved all existing functionality and field logic

### 2. JavaScript Component
**File:** `app/eventyay/static/pretixcontrol/js/ui/orderforms.js`

- Created toggle interaction handlers
- Manages Active/Inactive state via toggle switches
- Handles Required/Optional state via dropdowns
- Syncs UI state with hidden form fields
- Supports both tri-state fields (do_not_ask/optional/required) and boolean fields

### 3. CSS Styling
**File:** `app/eventyay/static/pretixcontrol/css/orderforms.css`

- Table-specific styling for order forms
- Responsive design adjustments
- Extends existing toggle switch styles from `orga/css/question-toggles.css`
- Maintains visual consistency with talk component

### 4. Backup
**File:** `app/eventyay/control/templates/pretixcontrol/items/orderforms.html.backup`

- Original template preserved for reference
- Can be used for rollback if needed

## Features

### Customer Data Section
- **Email Address**: Toggle active/inactive, set required/optional
- **Email Confirmation**: Toggle to ask users to confirm email
- **Phone Number**: Toggle active/inactive, set required/optional
- **Name and Address**: Link to invoice settings

### Attendee Data Section
- **Attendee Name**: Toggle active/inactive, set required/optional
- **Attendee Email**: Toggle active/inactive, set required/optional
- **Company**: Toggle active/inactive, set required/optional
- **Postal Address**: Toggle active/inactive, set required/optional
- **Explanation Text**: Rich text field for attendee data explanation

### Form Settings
- All existing form settings preserved (not in table format)
- Login requirements
- Name scheme configuration
- Copy answers button settings

## Technical Details

### Form Field States
The implementation handles three states for each field:
- `do_not_ask`: Field is disabled/hidden
- `optional`: Field is shown but not required
- `required`: Field is shown and required

### Toggle Behavior
- **Active Toggle**: Controls whether field is shown at all
- **Required Dropdown**: Controls whether field is optional or required (only when active)
- When toggle is off: Field state saved to `do_not_ask`
- When toggle is on: Restores previous optional/required state

### Compatibility
- Maintains backward compatibility with existing form data structure
- Uses same field names and validation logic
- No database schema changes required

## Testing Checklist

- [ ] Order forms page loads without errors
- [ ] All toggle switches work correctly
- [ ] Required/Optional dropdowns update properly
- [ ] Form submission saves all settings correctly
- [ ] Settings persist after page reload
- [ ] Table is responsive on mobile devices
- [ ] Keyboard navigation works properly
- [ ] Screen readers can navigate the table

## Benefits

1. **Improved Overview**: All fields visible in one clean table
2. **Faster Configuration**: Quick toggle switches vs. checkbox + nested checkbox
3. **UI Consistency**: Matches talk component patterns
4. **Better UX**: Clear visual hierarchy and field states
5. **Accessibility**: Proper ARIA labels and keyboard navigation
6. **Maintainability**: Reusable components for future features

## Future Enhancements

- Add inline help tooltips for each field
- Implement drag-and-drop field reordering
- Add bulk enable/disable actions
- Create field templates/presets
- Add field usage analytics

## Related Files

- Form definition: `app/eventyay/control/forms/event.py`
- Settings configuration: `app/eventyay/base/configurations/default_setting.py`
- Toggle styles (reused): `app/eventyay/static/orga/css/question-toggles.css`
- Toggle logic (reference): `app/eventyay/static/orga/js/questionToggles.js`

## Rollback Instructions

If needed, restore the original template:
```bash
cd /home/yashraj/YASHRAJ/eventyay
cp app/eventyay/control/templates/pretixcontrol/items/orderforms.html.backup \
   app/eventyay/control/templates/pretixcontrol/items/orderforms.html
```

## Author Notes

This implementation follows the existing patterns from the talk component's form options UI, ensuring consistency across the application. The refactoring maintains all existing functionality while significantly improving the user experience for event organizers managing order forms.
