.. highlight:: javascript
   :linenothreshold: 5

Frontend Applications Overview
==============================

The unified eventyay system includes several frontend applications built with modern web technologies.

This page provides an overview of all frontend applications. For component-specific details:

- **Video Frontend**: See :doc:`/video/frontend` 
- **Talk Frontend Apps**: See :doc:`/talk/developer/frontend`

Video Web Application
---------------------

The main video/virtual event interface is a comprehensive Vue 3 application.

**Location**: ``app/eventyay/webapp/video/``

For complete documentation, see :doc:`/video/frontend`.

Architecture
~~~~~~~~~~~~

**Framework**: Vue 3 with Vuex for state management

**Build System**: Vite

**Routing**: Vue Router

**Styling**: Stylus with custom theming

**i18n**: vue-i18n for internationalization

Core Application Structure
~~~~~~~~~~~~~~~~~~~~~~~~~~

Main Entry Point
^^^^^^^^^^^^^^^^

**File**: ``src/main.js``

Initializes the Vue application, sets up:
- Store (Vuex)
- Router
- i18n
- Global components
- WebSocket connections

Root Component
^^^^^^^^^^^^^^

**File**: ``src/App.vue``

The root component that contains:
- AppBar (top navigation)
- Router view (dynamic content)
- Global error boundaries
- Theme provider

Key Components
~~~~~~~~~~~~~~

Navigation & Layout
^^^^^^^^^^^^^^^^^^^

- ``components/AppBar.vue`` - Top navigation bar with user menu
- ``components/RoomsSidebar.vue`` - Room listing sidebar
- ``components/dashboard-layout/`` - Dashboard panel layout system
- ``components/MenuDropdown.vue`` - Dropdown menu component

Chat System
^^^^^^^^^^^

- ``components/Chat.vue`` - Main chat container
- ``components/ChatContent.vue`` - Message display area
- ``components/ChatInput.vue`` - Message input with emoji support
- ``components/ChatMessage.vue`` - Individual message component
- ``components/ChatUserCard.vue`` - User profile card in chat
- ``components/CreateChatPrompt.vue`` - New channel creation
- ``components/CreateDmPrompt.vue`` - Direct message creation

Video & Streaming
^^^^^^^^^^^^^^^^^

- ``components/Livestream.vue`` - HLS/RTMP stream viewer
- ``components/MediaSource.vue`` - Media source selector
- ``components/JanusCall.vue`` - Janus WebRTC video call
- ``components/JanusChannelCall.vue`` - Channel-based video calls
- ``components/janus/`` - Janus-specific components

Interactive Features
^^^^^^^^^^^^^^^^^^^^

- ``components/Poll.vue`` - Single poll display and voting
- ``components/Polls.vue`` - Polls listing
- ``components/Question.vue`` - Single Q&A question
- ``components/Questions.vue`` - Q&A question list
- ``components/Roulette.vue`` - Speed networking roulette

Exhibition
^^^^^^^^^^

- ``components/Exhibition.vue`` - Exhibition hall view
- ``components/ContactExhibitorPrompt.vue`` - Exhibitor contact form
- ``components/PosterHall.vue`` - Poster session hall

User Interface
^^^^^^^^^^^^^^

- ``components/Avatar.vue`` - User avatar display
- ``components/Identicon.vue`` - Generated user identicons
- ``components/EmojiPicker.vue`` - Emoji selection
- ``components/ColorPicker.vue`` - Color selection
- ``components/ReactionsBar.vue`` - Reaction emoji bar
- ``components/ReactionsOverlay.vue`` - Floating reaction overlays
- ``components/Scrollbars.vue`` - Custom scrollbar styling

Content Display
^^^^^^^^^^^^^^^

- ``components/MarkdownContent.js`` - Markdown renderer
- ``components/MarkdownPage.vue`` - Full markdown page
- ``components/RichTextContent.vue`` - Rich text display
- ``components/RichTextEditor.vue`` - TinyMCE-based rich text editor
- ``components/StaticPage.vue`` - Static content pages
- ``components/IframePage.vue`` - Embedded iframe pages

Forms & Prompts
^^^^^^^^^^^^^^^

- ``components/Prompt.vue`` - Base modal prompt
- ``components/UserActionPrompt.vue`` - User action confirmation
- ``components/FeedbackPrompt.vue`` - Feedback submission
- ``components/RecordingsPrompt.vue`` - Recording access
- ``components/QRCodePrompt.vue`` - QR code display
- ``components/AVDevicePrompt.vue`` - Audio/video device selection

Utility Components
^^^^^^^^^^^^^^^^^^

- ``components/UploadButton.vue`` - File upload button
- ``components/UploadUrlInput.vue`` - URL or file upload
- ``components/UserSearch.vue`` - User search
- ``components/UserSelect.vue`` - User selection dropdown
- ``components/InfiniteScroll.vue`` - Infinite scroll loader
- ``components/CopyableText.vue`` - Click-to-copy text
- ``components/ErrorBoundary.vue`` - Error boundary component

Views
~~~~~

The application includes 70+ views in ``src/views/`` organized by feature:

Room Views
^^^^^^^^^^

- Room layout and configuration
- Room settings
- Room permissions
- Stage management

Event Views
^^^^^^^^^^^

- Event home page
- Schedule display
- Session details
- Speaker profiles

User Views
^^^^^^^^^^

- User profile
- Settings
- Notifications
- Direct messages

Admin Views
^^^^^^^^^^^

- Event configuration
- Room management
- User moderation
- Analytics dashboard

State Management
~~~~~~~~~~~~~~~~

Vuex Store Modules (``src/store/``)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**announcement.js**
  - Global announcements
  - Notification banners

**chat.js**
  - Chat messages and channels
  - Unread counts
  - Message history

**exhibition.js**
  - Exhibitor data
  - Contact requests
  - Booth interactions

**poll.js**
  - Poll data and votes
  - Real-time results

**question.js**
  - Q&A questions
  - Voting and moderation

**roulette.js**
  - Networking queue
  - Match history

**schedule.js**
  - Event schedule
  - Session bookmarks

**notifications.js**
  - In-app notifications
  - Browser notifications
  - Push subscriptions

Utility Libraries
~~~~~~~~~~~~~~~~~

API Client (``src/lib/api.js``)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Provides methods for:
- Authentication
- Room operations
- Chat operations
- User management
- Event data fetching

WebSocket Client (``src/lib/WebSocketClient.js``)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Handles:
- Real-time bidirectional communication
- Automatic reconnection
- Message queuing
- Channel subscriptions

Other Utilities
^^^^^^^^^^^^^^^

- ``src/lib/emoji.js`` - Emoji utilities and rendering
- ``src/lib/gravatar.js`` - Gravatar image URLs
- ``src/lib/identicon.js`` - Generated identicon images
- ``src/lib/validators.js`` - Form validation
- ``src/lib/profile.js`` - User profile helpers
- ``src/lib/janus.js`` - Janus WebRTC integration
- ``src/lib/search.js`` - Search utilities
- ``src/lib/filetypes.js`` - File type detection
- ``src/lib/ApiError.js`` - API error handling

Internationalization
~~~~~~~~~~~~~~~~~~~~

**Supported Languages** (``src/locales/``):
- English (en)
- German (de)
- Spanish (es)
- French (fr)
- Portuguese (pt_BR)
- Russian (ru)
- Ukrainian (uk)
- Arabic (ar)

**Implementation**: vue-i18n with JSON translation files

**Usage**:

.. code-block:: javascript

   // In components
   this.$t('key.path')
   
   // In templates
   {{ $t('key.path') }}

Styling & Theming
~~~~~~~~~~~~~~~~~

**Base System**: Stylus preprocessor

**Files** (``src/styles/``):
- ``global.styl`` - Global styles
- ``variables.styl`` - CSS variables and colors
- ``typography.styl`` - Font definitions
- ``common-ui.styl`` - Common UI components
- ``themed-buntpapier.styl`` - Themed component library
- ``media-queries.styl`` - Responsive breakpoints

**Theme System** (``src/theme.js``):
- Dynamic color themes
- Custom branding support
- Dark mode support

Building & Development
~~~~~~~~~~~~~~~~~~~~~~

**Development Server**:

.. code-block:: bash

  cd app/eventyay/webapp/video
   npm install
   npm run dev

**Production Build**:

.. code-block:: bash

   npm run build

**Output**: ``dist/`` directory with optimized assets

Configuration
~~~~~~~~~~~~~

**vite.config.js** - Vite build configuration

**vue.config.js** - Vue-specific configuration

**babel.config.js** - Babel transpilation

**eslint.config.js** - ESLint code quality

Talk Component Frontend Applications
------------------------------------

The talk component includes two specialized frontend applications:

**Schedule Editor**

A TypeScript/Vue 3 application for visual schedule editing.

**Location**: ``app/eventyay/webapp/schedule-editor/``

For complete documentation, see :doc:`/talk/developer/frontend`.

Development Setup
-----------------

Prerequisites
~~~~~~~~~~~~~

- Node.js 18+ and npm
- Python 3.11+ (for backend API)
- Modern web browser

Full Stack Development
~~~~~~~~~~~~~~~~~~~~~~

1. **Start Backend**:

.. code-block:: bash

   cd app
   make run

2. **Start Video Frontend**:

.. code-block:: bash

  cd app/eventyay/webapp/video
   npm install
   npm run dev

3. **Access**:
   - Frontend: http://localhost:8880
   - Backend API: http://localhost:8000

Frontend-Only Development
~~~~~~~~~~~~~~~~~~~~~~~~~

For frontend-only changes, you can use the production backend:

.. code-block:: bash

  cd app/eventyay/webapp/video
   # Edit config.js to point to production API
   npm run dev

Testing
~~~~~~~

.. code-block:: bash

   # Run linting
   npm run lint
   
   # Run unit tests (when available)
   npm run test

Best Practices
--------------

Component Development
~~~~~~~~~~~~~~~~~~~~~

1. **Single Responsibility**: Each component should do one thing well
2. **Props vs Events**: Use props down, events up pattern
3. **Composition**: Prefer composition over inheritance
4. **Async/Await**: Use async/await for API calls
5. **Error Handling**: Always handle errors gracefully

State Management
~~~~~~~~~~~~~~~~

1. **Local vs Global**: Use component state for local UI, Vuex for shared state
2. **Immutability**: Never mutate Vuex state directly
3. **Actions**: Use actions for async operations
4. **Getters**: Use getters for computed state

Performance
~~~~~~~~~~~

1. **Lazy Loading**: Use dynamic imports for route-based code splitting
2. **Virtual Scrolling**: Use for long lists (implemented in InfiniteScroll)
3. **Memoization**: Cache expensive computations
4. **Debouncing**: Debounce user input handlers

Accessibility
~~~~~~~~~~~~~

1. **Semantic HTML**: Use proper HTML elements
2. **ARIA Labels**: Add labels for screen readers
3. **Keyboard Navigation**: Ensure keyboard accessibility
4. **Color Contrast**: Maintain WCAG AA standards

Troubleshooting
---------------

Common Issues
~~~~~~~~~~~~~

**WebSocket Connection Fails**
  - Check CORS configuration
  - Verify WebSocket URL in config
  - Check browser console for errors

**Build Errors**
  - Clear node_modules and reinstall
  - Check Node.js version (18+)
  - Verify all dependencies installed

**Hot Reload Not Working**
  - Restart dev server
  - Clear browser cache
  - Check file watcher limits

**API Calls Failing**
  - Verify backend is running
  - Check API URL configuration
  - Inspect network tab for errors

Further Reading
---------------

- Vue 3 Documentation: https://vuejs.org
- Vuex Documentation: https://vuex.vuejs.org
- Vite Documentation: https://vitejs.dev
- TypeScript: https://www.typescriptlang.org

