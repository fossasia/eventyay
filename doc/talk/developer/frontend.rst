.. highlight:: javascript
   :linenothreshold: 5

Talk Component Frontend
=======================

The talk component includes two specialized frontend applications for schedule management and navigation.

.. note::
   This documentation covers the frontend applications specific to the talk component.
   For the video webapp, see :doc:`/video/frontend`.

Schedule Editor Application
---------------------------

A TypeScript/Vue 3 application for visual schedule editing and management.

**Location**: ``app/eventyay/frontend/schedule-editor/``

**Framework**: Vue 3 with TypeScript

**Purpose**: Interactive drag-and-drop schedule management for event organizers

Architecture
~~~~~~~~~~~~

**Build System**: Vite

**Language**: TypeScript

**Styling**: Stylus preprocessor

**i18n**: Custom i18next integration

Key Features
~~~~~~~~~~~~

Interactive Schedule Management
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

- **Drag-and-Drop Interface**: Move sessions between time slots and rooms
- **Visual Grid Layout**: See the entire schedule at a glance
- **Time Slot Management**: Create and adjust time blocks
- **Room/Track Visualization**: Manage parallel tracks and venues
- **Conflict Detection**: Automatically detect scheduling conflicts
- **Real-Time Updates**: Changes saved immediately via API
- **Responsive Design**: Works on desktop and tablet devices

Components
~~~~~~~~~~

Main Application
^^^^^^^^^^^^^^^^

**File**: ``src/App.vue``

The main schedule editor interface containing:
- Grid-based schedule view
- Session management
- Room and track controls
- Save/undo functionality

Grid Schedule Component
^^^^^^^^^^^^^^^^^^^^^^^

**File**: ``src/components/GridSchedule.vue``

Renders the interactive schedule grid with:
- Time slots on Y-axis
- Rooms/tracks on X-axis
- Draggable session cards
- Visual conflict indicators
- Zoom and pan controls

Session Component
^^^^^^^^^^^^^^^^^

**File**: ``src/components/Session.vue``

Individual session card showing:
- Session title and speaker
- Duration and time
- Track/category
- Status indicators
- Quick-edit options

API Integration
~~~~~~~~~~~~~~~

TypeScript API Client
^^^^^^^^^^^^^^^^^^^^^

**File**: ``src/api.ts``

Provides typed API methods for:

**Schedule Operations**:

.. code-block:: typescript

         // Fetch schedule data
         async function fetchSchedule(eventId: string): Promise<Schedule>
      // Update session time
      async function updateSessionTime(
          sessionId: string, 
          start: Date, 
          room: string
      ): Promise<void>

      // Validate schedule
      async function validateSchedule(eventId: string): Promise<ValidationResult>

**Data Models**:

.. code-block:: typescript

         interface Session {
             id: string;
             title: string;
             speakers: Speaker[];
             start: Date;
             end: Date;
             room: Room;
             track: Track;
         }
      interface Schedule {
          sessions: Session[];
          rooms: Room[];
          tracks: Track[];
          days: Day[];
      }

Utilities
~~~~~~~~~

**File**: ``src/utils.ts``

Utility functions for:
- Date/time manipulation
- Conflict detection
- Schedule validation
- Data formatting

**File**: ``src/schemas.ts``

TypeScript schemas and types for:
- API responses
- Schedule data structures
- Validation rules

Internationalization
~~~~~~~~~~~~~~~~~~~~

**Implementation**: i18next

**Locales** (``locales/``):
- English (en) - Complete

**Parser Configuration**: ``i18next-parser.config.cjs``

**Usage**:

.. code-block:: typescript

         import { t } from './lib/i18n';
      // In components
      const title = t('schedule.edit_session');

Styling
~~~~~~~

**Files** (``src/styles/``):

- ``global.styl`` - Global styles and layout
- ``variables.styl`` - CSS variables, colors, breakpoints

**Theme**:
- eventyay brand colors
- Consistent with main application
- Responsive grid layout
- Accessible color contrast

Development
~~~~~~~~~~~

**Setup**:
.. code-block:: bash

      cd app/eventyay/frontend/schedule-editor
      npm install
      npm run dev

**Build**:
.. code-block:: bash

      npm run build
      # Output: dist/ directory

**Configuration**:
- ``vite.config.js`` - Vite build configuration
- ``tsconfig.json`` - TypeScript configuration
- ``eslint.config.js`` - Code quality rules

Global Navigation Menu
----------------------
Development Workflow
--------------------

Local Development
~~~~~~~~~~~~~~~~~

**1. Start Backend**:
.. code-block:: bash

      cd app
      make run

**2. Start Schedule Editor**:
.. code-block:: bash

      cd app/eventyay/frontend/schedule-editor
      npm install
      npm run dev
      # Access: http://localhost:5173

Testing
~~~~~~~

**Linting**:

.. code-block:: bash

   # Schedule Editor
   cd app/eventyay/frontend/schedule-editor
   npm run lint
   
**Type Checking**:

.. code-block:: bash

   # Both projects
   npm run type-check  # or tsc --noEmit

Production Build
~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Schedule Editor
   cd app/eventyay/frontend/schedule-editor
   npm run build
   # Output: dist/
   
**Deployment**:
Built assets are collected by Django's static file system.

Best Practices
--------------

TypeScript
~~~~~~~~~~

1. **Use Strict Mode**: Enable all strict checks
2. **Type Everything**: Avoid `any`, use proper types
3. **Interfaces First**: Define interfaces before implementation
4. **Generics**: Use generics for reusable components

Vue 3 Composition API
~~~~~~~~~~~~~~~~~~~~~

1. **Setup Function**: Use `<script setup>` syntax
2. **Reactive**: Use `ref` and `reactive` properly
3. **Computed**: Use `computed` for derived state
4. **Lifecycle**: Use composition API lifecycle hooks

Code Quality
~~~~~~~~~~~~

1. **Biome/ESLint**: Follow configured rules
2. **Formatting**: Consistent code style
3. **Comments**: Document complex logic
4. **Naming**: Clear, descriptive names

Performance
~~~~~~~~~~~

1. **Lazy Loading**: Dynamic imports for routes
2. **Virtual Scrolling**: For large schedules
3. **Debouncing**: Debounce API calls
4. **Caching**: Cache computed values

Troubleshooting
---------------

Common Issues
~~~~~~~~~~~~~

**TypeScript Errors**
  - Check `tsconfig.json` settings
  - Verify type definitions installed
  - Run `npm install` to update types

**Build Fails**
  - Clear `node_modules` and reinstall
  - Check Node.js version (18+)
  - Verify Vite configuration

**Component Not Loading**
  - Check browser console for errors
  - Verify script path in templates
  - Check for CORS issues

**Schedule Not Saving**
  - Verify backend API is running
  - Check network tab for failed requests
  - Verify authentication token

**UnoCSS Classes Not Working**
  - Check `uno.config.ts` configuration
  - Verify class names are valid
  - Rebuild to regenerate CSS

Further Reading
---------------

- **Vue 3**: https://vuejs.org
- **TypeScript**: https://www.typescriptlang.org
- **Vite**: https://vitejs.dev
- **UnoCSS**: https://unocss.dev
- **i18next**: https://www.i18next.com
- **Biome**: https://biomejs.dev

See Also
--------

- :doc:`/development/frontend` - Complete frontend documentation
- :doc:`/video/frontend` - Video webapp documentation
- :doc:`/development/api/index` - Backend API reference
- :doc:`/talk/developer/setup` - Talk development setup

