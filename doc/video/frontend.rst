.. highlight:: javascript
   :linenothreshold: 5

.. _video-frontend:

Video Component Frontend - Web Application
==========================================

The video component features a comprehensive Vue.js web application for virtual events, live streaming, and interactive online experiences.

.. note::
  This documentation covers the video frontend (``app/eventyay/webapp/video/``).
   
   For talk component frontend apps (schedule editor, global nav), see :doc:`/talk/developer/frontend`.

Overview
--------

The video frontend is a full-featured virtual event platform built with Vue 3, providing:

- **Live Video Streaming**: HLS/RTMP streams and WebRTC calls
- **Interactive Chat**: Real-time messaging with channels and DMs
- **Audience Engagement**: Polls, Q&A, emoji reactions
- **Networking**: Speed networking (roulette) and direct messaging
- **Exhibition**: Virtual exhibition halls with exhibitor booths
- **Posters**: Academic poster sessions with Q&A
- **Recordings**: On-demand video playback

**Location**: ``app/eventyay/webapp/video/``

**Framework**: Vue 3

**State Management**: Vuex

**Build System**: Vite

**Styling**: Stylus

Architecture
------------

Technology Stack
~~~~~~~~~~~~~~~~

**Frontend Framework**
  - Vue 3 (Composition API)
  - Vue Router for routing
  - Vuex for state management

**Build Tools**
  - Vite for fast development and optimized builds
  - Babel for JavaScript transpilation
  - ESLint for code quality

**Styling**
  - Stylus preprocessor
  - Custom theme system
  - Responsive design with media queries

**Real-Time Communication**
  - WebSocket for bidirectional communication
  - WebRTC for peer-to-peer video
  - Janus Gateway integration
  - Server-Sent Events for notifications

**Internationalization**
  - vue-i18n
  - 8 languages supported
  - JSON translation files

Application Structure
~~~~~~~~~~~~~~~~~~~~~

**Entry Point**: ``src/main.js``

Initializes:
- Vue application
- Vuex store
- Vue Router
- i18n  
- WebSocket connections
- Global components

**Root Component**: ``src/App.vue``

Contains:
- AppBar (top navigation)
- RoomsSidebar (room list)
- Router view (dynamic content)
- Global modals and prompts
- Error boundaries

Core Components
---------------

Navigation & Layout
~~~~~~~~~~~~~~~~~~~

AppBar Component
^^^^^^^^^^^^^^^^

**File**: ``components/AppBar.vue``

Top navigation bar featuring:
- Event branding and logo
- Active room/view indicator
- User menu (profile, settings, logout)
- Notifications bell
- Language selector
- Theme toggle

RoomsSidebar Component
^^^^^^^^^^^^^^^^^^^^^^

**File**: ``components/RoomsSidebar.vue``

Collapsible sidebar showing:
- List of available rooms
- Unread message indicators
- Room categories
- Direct messages
- Pinned rooms
- Search functionality

Dashboard Layout
^^^^^^^^^^^^^^^^

**Files**: ``components/dashboard-layout/index.vue``, ``Panel.vue``

Flexible panel system for:
- Split-screen layouts
- Resizable panels
- Drag-and-drop arrangement
- Responsive breakpoints

Chat System
~~~~~~~~~~~

The video platform includes a comprehensive real-time chat system.

Chat Component
^^^^^^^^^^^^^^

**File**: ``components/Chat.vue``

Main chat container with:
- Message list
- Input area
- Member list toggle
- Channel settings
- Moderation tools

ChatContent Component
^^^^^^^^^^^^^^^^^^^^^

**File**: ``components/ChatContent.vue``

Message display area featuring:
- Infinite scroll
- Message grouping
- Timestamp display
- Read receipts
- Reaction support
- Media embeds

ChatInput Component
^^^^^^^^^^^^^^^^^^^

**File**: ``components/ChatInput.vue``

Message input with:
- Rich text formatting
- Emoji picker integration
- File upload
- @mentions autocomplete
- Message editing
- Draft persistence

ChatMessage Component
^^^^^^^^^^^^^^^^^^^^^

**File**: ``components/ChatMessage.vue``

Individual message display:
- User avatar and name
- Message content (markdown support)
- Timestamp
- Edit/delete actions (for own messages)
- Reply threading
- Reaction bar

ChatUserCard Component
^^^^^^^^^^^^^^^^^^^^^^

**File**: ``components/ChatUserCard.vue``

User profile card in chat:
- Avatar and name
- Bio/description
- Social links
- Direct message button
- Block/report options (for moderators)

CreateChatPrompt & CreateDmPrompt
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Files**: ``components/CreateChatPrompt.vue``, ``CreateDmPrompt.vue``

Modals for:
- Creating new channels
- Starting direct messages
- Setting channel permissions
- Inviting users

Video & Streaming
~~~~~~~~~~~~~~~~~

Livestream Component
^^^^^^^^^^^^^^^^^^^^

**File**: ``components/Livestream.vue``

HLS/RTMP stream viewer with:
- Adaptive bitrate streaming
- Full-screen mode
- Volume controls
- Quality selector
- Picture-in-picture
- Stream status indicators

JanusCall Component
^^^^^^^^^^^^^^^^^^^

**File**: ``components/JanusCall.vue``

WebRTC video conferencing via Janus Gateway:
- Multi-party video calls
- Screen sharing
- Audio/video controls
- Layout options (grid, speaker view)
- Connection quality indicators

JanusChannelCall Component
^^^^^^^^^^^^^^^^^^^^^^^^^^

**File**: ``components/JanusChannelCall.vue``

Channel-integrated video calls:
- Room-specific video
- Automatic participant joining
- Moderator controls
- Recording capabilities

MediaSource & MediaSourcePlaceholder
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Files**: ``components/MediaSource.vue``, ``MediaSourcePlaceholder.vue``

Media source selection and display:
- Choose between stream types
- Switch between stage and call
- Handle loading states
- Error recovery

AVDevicePrompt Component
^^^^^^^^^^^^^^^^^^^^^^^^

**File**: ``components/AVDevicePrompt.vue``

Audio/video device setup:
- Camera selection
- Microphone selection
- Device permissions
- Preview before joining
- Settings persistence

Interactive Features
~~~~~~~~~~~~~~~~~~~~

Poll & Polls Components
^^^^^^^^^^^^^^^^^^^^^^^

**Files**: ``components/Poll.vue``, ``components/Polls.vue``

Live polling system:
- Single poll display and voting
- Poll listing with results
- Real-time vote updates
- Anonymous/identified voting
- Result visualization (charts)
- Admin controls (create, close, delete)

Question & Questions Components
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Files**: ``components/Question.vue``, ``components/Questions.vue``

Q&A system:
- Question submission
- Upvoting questions
- Moderator review queue
- Answer posting
- Mark as answered
- Pin important questions

Roulette Component
^^^^^^^^^^^^^^^^^^

**File**: ``components/Roulette.vue``

Speed networking/roulette matching:
- Join networking queue
- Automatic random matching
- Video call integration
- Match history
- Availability status
- Time limits per match

ReactionsBar & ReactionsOverlay
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Files**: ``components/ReactionsBar.vue``, ``ReactionsOverlay.vue``

Live reactions system:
- Emoji reactions (👏, ❤️, 😂, +1, etc.)
- Floating reaction animations
- Reaction counts
- Real-time synchronization
- Custom reaction sets per event

Exhibition & Posters
~~~~~~~~~~~~~~~~~~~~

Exhibition Component
^^^^^^^^^^^^^^^^^^^^

**File**: ``components/Exhibition.vue``

Virtual exhibition hall:
- Exhibitor booth grid
- Booth details modal
- Contact forms
- Resource downloads
- Live chat with exhibitors
- Booth visit tracking

PosterHall Component
^^^^^^^^^^^^^^^^^^^^

**File**: ``components/PosterHall.vue``

Academic poster sessions:
- Poster grid display
- Poster detail view
- Author chat
- File downloads
- Voting/feedback
- Session scheduling

ContactExhibitorPrompt Component
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**File**: ``components/ContactExhibitorPrompt.vue``

Exhibitor contact form:
- Send messages to exhibitors
- Request meetings
- Download materials
- Track inquiries

User Interface Components
~~~~~~~~~~~~~~~~~~~~~~~~~

Avatar & Identicon
^^^^^^^^^^^^^^^^^^

**Files**: ``components/Avatar.vue``, ``components/Identicon.vue``

User image display:
- Gravatar integration
- Generated identicons (when no avatar)
- Size variants
- Loading states
- Fallback handling

EmojiPicker & EmojiPickerButton
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Files**: ``components/EmojiPicker.vue``, ``components/EmojiPickerButton.vue``

Emoji selection:
- Categorized emoji list
- Search functionality
- Recent emojis
- Skin tone selector
- Keyboard navigation

ColorPicker Component
^^^^^^^^^^^^^^^^^^^^^

**File**: ``components/ColorPicker.vue``

Color selection tool:
- Hex color input
- Visual color picker
- Preset colors
- Validation

Scrollbars Component
^^^^^^^^^^^^^^^^^^^^

**File**: ``components/Scrollbars.vue``

Custom scrollbar styling:
- Consistent appearance across browsers
- Smooth scrolling
- Hover effects
- Mobile-friendly

InfiniteScroll Component
^^^^^^^^^^^^^^^^^^^^^^^^

**File**: ``components/InfiniteScroll.vue``

Infinite scroll loader:
- Load more on scroll
- Loading indicators
- End-of-list detection
- Performance optimized

Content Components
~~~~~~~~~~~~~~~~~~

RichTextEditor & RichTextContent
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Files**: ``components/RichTextEditor.vue``, ``components/RichTextContent.vue``

Rich text editing with TinyMCE:
- Bold, italic, underline
- Lists and headings
- Links and images
- Code blocks
- Mentions support
- Sanitized output

MarkdownContent & MarkdownPage
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Files**: ``components/MarkdownContent.js``, ``components/MarkdownPage.vue``

Markdown rendering:
- GitHub-flavored markdown
- Syntax highlighting
- Link handling
- Image loading
- Safe HTML output

StaticPage & IframePage
^^^^^^^^^^^^^^^^^^^^^^^

**Files**: ``components/StaticPage.vue``, ``components/IframePage.vue``

Static content display:
- Custom HTML pages
- Embedded iframes
- Responsive containers
- Security considerations

Utility Components
~~~~~~~~~~~~~~~~~~

Prompt Component
^^^^^^^^^^^^^^^^

**File**: ``components/Prompt.vue``

Base modal dialog:
- Customizable content
- Confirm/cancel actions
- Keyboard shortcuts (ESC to close)
- Click-outside to close
- Accessibility (focus trap)

UserActionPrompt Component
^^^^^^^^^^^^^^^^^^^^^^^^^^

**File**: ``components/UserActionPrompt.vue``

User action confirmation:
- Block/report users
- Kick from rooms
- Ban users
- Moderator actions

FeedbackPrompt Component
^^^^^^^^^^^^^^^^^^^^^^^^

**File**: ``components/FeedbackPrompt.vue``

User feedback collection:
- Rating systems
- Text feedback
- Categories
- Anonymous option

RecordingsPrompt Component
^^^^^^^^^^^^^^^^^^^^^^^^^^

**File**: ``components/RecordingsPrompt.vue``

Recording access:
- List available recordings
- Playback controls
- Download options
- Access permissions

QRCodePrompt Component
^^^^^^^^^^^^^^^^^^^^^^

**File**: ``components/QRCodePrompt.vue``

QR code display:
- Generate QR codes
- Share room links
- Mobile app integration

UploadButton & UploadUrlInput
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Files**: ``components/UploadButton.vue``, ``components/UploadUrlInput.vue``

File upload utilities:
- Drag-and-drop file upload
- URL input option
- File type validation
- Size limits
- Progress indicators

UserSearch & UserSelect
^^^^^^^^^^^^^^^^^^^^^^^

**Files**: ``components/UserSearch.vue``, ``components/UserSelect.vue``

User selection:
- Search users by name
- Autocomplete
- Multi-select support
- Selected user chips

CopyableText Component
^^^^^^^^^^^^^^^^^^^^^^

**File**: ``components/CopyableText.vue``

Click-to-copy text:
- One-click copy
- Visual feedback
- Fallback for old browsers

ErrorBoundary Component
^^^^^^^^^^^^^^^^^^^^^^^

**File**: ``components/ErrorBoundary.vue``

Error handling:
- Catch rendering errors
- Display error messages
- Prevent app crashes
- Development mode details

Views (70+ Pages)
-----------------

The application includes comprehensive views in ``src/views/``:

Room Views
~~~~~~~~~~

- **RoomView**: Main room display with video/chat/polls
- **RoomSettings**: Room configuration for moderators
- **CreateRoom**: Room creation wizard
- **StageManagement**: Stage controls for presenters

Event Views
~~~~~~~~~~~

- **EventHome**: Event landing page
- **Schedule**: Event schedule display
- **SessionDetail**: Individual session pages
- **SpeakerProfile**: Speaker bio pages

User Views
~~~~~~~~~~

- **UserProfile**: User profile page
- **UserSettings**: Account settings
- **Notifications**: Notification center
- **DirectMessages**: DM inbox

Admin Views
~~~~~~~~~~~

- **EventConfig**: Event-wide settings
- **RoomManagement**: Room administration
- **UserModeration**: Moderation tools
- **Analytics**: Real-time analytics dashboard

State Management (Vuex)
-----------------------

Store Modules
~~~~~~~~~~~~~

The application uses Vuex for centralized state management.

**Location**: ``src/store/``

announcement.js
^^^^^^^^^^^^^^^

Global announcements and banners:
- Fetch announcements
- Mark as read
- Display timing
- Priority levels

chat.js
^^^^^^^

Chat state management:
- Messages and channels
- Unread counts
- User typing indicators
- Message history
- Channel subscriptions

exhibition.js
^^^^^^^^^^^^^

Exhibition data:
- Exhibitor information
- Booth state
- Contact requests
- Visit tracking

poll.js
^^^^^^^

Poll state and voting:
- Active polls
- User votes
- Real-time results
- Poll history

question.js
^^^^^^^^^^^

Q&A functionality:
- Questions queue
- Upvotes
- Answers
- Moderation status

roulette.js
^^^^^^^^^^^

Networking state:
- Queue status
- Current match
- Match history
- Availability

schedule.js
^^^^^^^^^^^

Event schedule:
- Sessions data
- Bookmarks
- Filters
- Calendar sync

notifications.js
^^^^^^^^^^^^^^^^

In-app notifications:
- Notification list
- Unread count
- Browser notifications
- Push subscriptions

Utility Libraries
-----------------

API Client
~~~~~~~~~~

**File**: ``src/lib/api.js``

Comprehensive API client providing methods for:

**Authentication**:

.. code-block:: javascript

   // Login/logout
   api.login(email, password)
   api.logout()
   
   // Token management
   api.refreshToken()
   api.validateToken()


**Room Operations**:

.. code-block:: javascript

   // Fetch rooms
   api.fetchRooms(eventId)
   api.fetchRoom(roomId)
   
   // Room actions
   api.joinRoom(roomId)
   api.leaveRoom(roomId)
   api.updateRoom(roomId, data)


**Chat Operations**:

.. code-block:: javascript

   // Send messages
   api.sendMessage(channelId, text)
   api.editMessage(messageId, text)
   api.deleteMessage(messageId)
   
   // Channels
   api.createChannel(name, description)
   api.joinChannel(channelId)


**User Management**:

.. code-block:: javascript

   // Profile
   api.updateProfile(data)
   api.uploadAvatar(file)
   
   // Moderation
   api.blockUser(userId)
   api.reportUser(userId, reason)


WebSocket Client
~~~~~~~~~~~~~~~~

**File**: ``src/lib/WebSocketClient.js``

Real-time communication handler:

**Features**:
- Automatic reconnection with exponential backoff
- Message queuing during disconnection
- Channel subscriptions
- Event handling
- Ping/pong for connection health

**Usage**:

.. code-block:: javascript

   import WebSocketClient from './lib/WebSocketClient'
   
   const ws = new WebSocketClient('wss://example.com/ws')
   
   // Subscribe to channels
   ws.subscribe('room:123', (message) => {
       console.log('Room update:', message)
   })
   
   // Send messages
   ws.send('chat.message', {
       channel: '123',
       text: 'Hello!'
   })


Additional Utilities
~~~~~~~~~~~~~~~~~~~~

**emoji.js**
  - Emoji parsing and rendering
  - Emoji data and categories
  - Custom emoji support
  - Shortcode conversion

**gravatar.js**
  - Gravatar URL generation
  - Size parameters
  - Default image options
  - Secure HTTPS URLs

**identicon.js**
  - Generate unique avatar images
  - Deterministic based on user ID
  - Multiple visual styles
  - SVG output

**janus.js**
  - Janus Gateway WebRTC integration
  - Session management
  - Plugin handles
  - SDP negotiation
  - ICE candidate handling

**validators.js**
  - Form validation rules
  - Email validation
  - URL validation
  - Custom validators

**profile.js**
  - User profile helpers
  - Display name formatting
  - Profile completeness
  - Avatar URL generation

**search.js**
  - Full-text search
  - Fuzzy matching
  - Result ranking
  - Highlighting

**filetypes.js**
  - File type detection
  - MIME type mapping
  - File icons
  - Upload validation

**ApiError.js**
  - API error handling
  - Error message extraction
  - Retry logic
  - User-friendly messages

Internationalization
--------------------

Supported Languages
~~~~~~~~~~~~~~~~~~~

**Location**: ``src/locales/``

- **English (en)** - Complete
- **German (de)** - Complete
- **Spanish (es)** - Complete
- **French (fr)** - Complete
- **Portuguese (pt_BR)** - Complete
- **Russian (ru)** - Complete
- **Ukrainian (uk)** - Complete
- **Arabic (ar)** - Complete

Implementation
~~~~~~~~~~~~~~

**Library**: vue-i18n

**Usage in Components**:

.. code-block:: vue

   <template>
     <div>{{ $t('room.join') }}</div>
     <button>{{ $t('chat.send_message') }}</button>
   </template>
   
   <script>
   export default {
     methods: {
       showMessage() {
         alert(this.$t('error.connection_lost'))
       }
     }
   }
   </script>

**Pluralization**:

.. code-block:: javascript

   $t('message.count', { count: 5 })
   // "5 messages" or "1 message"

**Date Formatting**:

.. code-block:: javascript

   $d(new Date(), 'short')
   // Locale-aware date formatting

Styling & Theming
-----------------

Stylus Files
~~~~~~~~~~~~

**Location**: ``src/styles/``

**global.styl**
  - Reset and base styles
  - Layout utilities
  - Global classes
  - z-index management

**variables.styl**
  - CSS custom properties
  - Color palette
  - Spacing scale
  - Typography scale
  - Breakpoints
  - Shadows and borders

**typography.styl**
  - Font families
  - Font sizes
  - Line heights
  - Font weights
  - Text utilities

**common-ui.styl**
  - Button styles
  - Input styles
  - Card styles
  - Badge styles
  - Common UI patterns

**themed-buntpapier.styl**
  - Themed component library
  - Custom eventyay colors
  - Component overrides

**media-queries.styl**
  - Responsive breakpoints
  - Mobile-first approach
  - Tablet and desktop rules

**browser-block.styl**
  - Unsupported browser warning
  - Modern browser recommendations

**preloader.styl**
  - Loading screen
  - Splash screen
  - Progress indicators

Theme System
~~~~~~~~~~~~

**File**: ``src/theme.js``

Dynamic theming support:
- Custom color schemes
- Dark mode (if configured)
- Brand customization
- Per-event theming

**Color Variables**:
.. code-block:: stylus

      --eventyay-primary: #2185d0
      --eventyay-secondary: #6435c9
      --eventyay-success: #21ba45
      --eventyay-warning: #f2c037
      --eventyay-error: #db2828

Routing
-------

**File**: ``src/router/index.js``

Vue Router configuration with:

**Routes**:
- `/` - Event landing page
- `/rooms/:roomId` - Individual rooms
- `/schedule` - Event schedule
- `/exhibition` - Exhibition hall
- `/posters` - Poster sessions
- `/profile` - User profile
- `/settings` - User settings

**Guards**:
- Authentication check
- Permission verification
- Redirect logic

**Meta**:
- Page titles
- Authentication requirements
- Navigation visibility

Development
-----------

Setup
~~~~~

**Prerequisites**:
- Node.js 18+ and npm
- Python 3.11+ (for backend)
- Modern web browser

**Installation**:
.. code-block:: bash

      cd app/eventyay/webapp/video
      npm install

**Environment**:

Create ``config.js`` with API endpoints:

.. code-block:: javascript

   export default {
     API_URL: 'http://localhost:8000',
     WS_URL: 'ws://localhost:8000/ws',
   }

Running Development Server
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Start backend first
   cd app
   make run
   
   # In another terminal, start frontend
  cd app/eventyay/webapp/video
   npm run dev
   
   # Access: http://localhost:8880


**Hot Reload**: Enabled - changes reflect instantly

Building for Production
~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

      npm run build

**Output**: ``dist/`` directory with:
- Optimized JavaScript bundles
- Minified CSS
- Compressed images
- Service worker
- Manifest file

**Static Files**: Collected by Django's `collectstatic` command

Configuration Files
~~~~~~~~~~~~~~~~~~~

**vite.config.js**
  - Vite build configuration
  - Dev server settings
  - Plugin configuration
  - Build optimizations

**vue.config.js**
  - Vue-specific settings
  - Webpack overrides (legacy)

**babel.config.js**
  - Babel transpilation rules
  - Browser targets
  - Polyfills

**eslint.config.js**
  - ESLint rules
  - Code style enforcement
  - Best practices

**i18next-parser.config.cjs**
  - Translation extraction
  - Locale management

Best Practices
--------------

Component Development
~~~~~~~~~~~~~~~~~~~~~

1. **Single Responsibility**: Each component does one thing
2. **Props Validation**: Always validate props with types
3. **Events**: Use descriptive event names
4. **Slots**: Provide slots for flexibility
5. **Scoped Styles**: Use `<style scoped>` for component styles

State Management
~~~~~~~~~~~~~~~~

1. **Local vs Global**: Use component state for UI, Vuex for shared data
2. **Actions**: Always use actions for async operations
3. **Mutations**: Keep mutations synchronous and simple
4. **Getters**: Use for computed/derived state
5. **Modules**: Keep store organized by feature

Performance
~~~~~~~~~~~

1. **Code Splitting**: Use dynamic imports for routes
2. **Virtual Scrolling**: Implemented in InfiniteScroll component
3. **Lazy Loading**: Load images and components on demand
4. **Debouncing**: Debounce search and input handlers
5. **Memoization**: Cache expensive computations

Accessibility
~~~~~~~~~~~~~

1. **Semantic HTML**: Use proper HTML elements
2. **ARIA Labels**: Add for screen readers
3. **Keyboard Navigation**: Support Tab, Enter, Escape
4. **Focus Management**: Manage focus in modals
5. **Color Contrast**: WCAG AA compliance

Security
~~~~~~~~

1. **XSS Prevention**: Sanitize user input
2. **CSRF Protection**: Use Django CSRF tokens
3. **Authentication**: Verify tokens
4. **Permissions**: Check user permissions
5. **Content Security**: Validate embedded content

Troubleshooting
---------------

Common Issues
~~~~~~~~~~~~~

**WebSocket Connection Fails**
  - Check WebSocket URL in config
  - Verify CORS settings on backend
  - Check browser console for specific errors
  - Ensure backend WebSocket server is running

**Build Errors**
  - Clear `node_modules`: `rm -rf node_modules && npm install`
  - Check Node.js version: `node --version` (need 18+)
  - Clear Vite cache: `rm -rf node_modules/.vite`

**Hot Reload Not Working**
  - Restart dev server
  - Clear browser cache
  - Check file watcher limits (Linux/Mac)
  - Verify file is in `src/` directory

**API Calls Failing**
  - Verify backend is running: `curl http://localhost:8000/api/`
  - Check API URL in `config.js`
  - Inspect browser Network tab
  - Check authentication token

**Video Not Playing**
  - Check stream URL and format (HLS/RTMP)
  - Verify CORS headers on video server
  - Check browser codec support
  - Test stream with external player

**WebRTC Issues**
  - Allow camera/microphone permissions
  - Check TURN server configuration
  - Verify firewall settings
  - Test with different browsers

**Styling Issues**
  - Rebuild CSS: `npm run build`
  - Check Stylus syntax
  - Verify variables are defined
  - Clear browser cache

Further Reading
---------------

- **Vue 3 Documentation**: https://vuejs.org
- **Vuex Documentation**: https://vuex.vuejs.org
- **Vite Documentation**: https://vitejs.dev
- **Janus Gateway**: https://janus.conf.meetecho.com/docs/
- **WebRTC**: https://webrtc.org
- **Stylus**: https://stylus-lang.com

Related Documentation
---------------------

- :doc:`/talk/developer/frontend` - Talk frontend (schedule editor, global nav)
- :doc:`/development/api/index` - Backend API reference
- :doc:`/video/developer/index` - Video backend development
- :doc:`/video/admin/index` - Video administration
- :doc:`/video/integration/index` - Integration guides
