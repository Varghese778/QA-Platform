# QA Platform - Frontend Dashboard

Modern, responsive React dashboard for the QA Platform. Enables QA engineers to submit user stories, monitor test generation pipelines in real-time, and review execution reports.

## Features

- **Story Submission**: Submit user stories with validation, priority, tags, and environment targeting
- **Real-Time Pipeline Status**: WebSocket-powered live updates on test generation progress
- **Test Suite Viewer**: Browse and filter generated test cases with collapsible details
- **Execution Reports**: View pass/fail metrics, coverage charts, and detailed failure analysis
- **Export Functionality**: Download reports as PDF or CSV
- **Responsive Design**: Optimized for 1280px-2560px viewports

## Tech Stack

- **Framework**: React 18 with TypeScript
- **Build Tool**: Vite
- **Styling**: Tailwind CSS
- **State Management**: React Context API + Zustand
- **HTTP Client**: Axios
- **WebSockets**: Native browser WebSocket API with auto-reconnect
- **Routing**: React Router v6

## Prerequisites

- Node.js 18+ and npm/yarn/pnpm
- Running API Gateway on `localhost:8080`
- Running Auth Service on `localhost:8000`

## Installation

```bash
# Install dependencies
npm install

# or with yarn
yarn install

# or with pnpm
pnpm install
```

## Configuration

Copy `.env.example` to `.env` and update the values:

```env
VITE_API_BASE_URL=http://localhost:8080/api/v1
VITE_WS_BASE_URL=ws://localhost:8080/ws/v1
VITE_AUTH_SERVICE_URL=http://localhost:8000
```

## Development

```bash
# Start development server
npm run dev

# Access at: http://localhost:3000
```

The development server features:
- Hot Module Replacement (HMR)
- Fast refresh
- Auto-open browser

## Build for Production

```bash
# Type check
npm run type-check

# Build optimized bundle
npm run build

# Preview production build
npm run preview
```

Build output will be in the `dist/` directory.

## Project Structure

```
src/
├── components/
│   ├── Common/           # Reusable UI components (Spinner, Toast, etc.)
│   ├── Layout/           # Layout components (Header, DashboardLayout)
│   ├── StorySubmission/  # Story submission form
│   ├── PipelineStatus/   # Real-time pipeline status panel
│   ├── TestSuite/        # Test suite viewer and cards
│   └── ExecutionReport/  # Execution report components
├── context/              # React Context providers (Auth, Job, WebSocket)
├── hooks/                # Custom React hooks
├── pages/                # Route pages (Login, Dashboard, JobDetail, etc.)
├── services/             # API clients (Axios, WebSocket manager)
├── types/                # TypeScript type definitions
├── utils/                # Utility functions (validation, formatting, errors)
├── App.tsx               # Root app component with routing
├── main.tsx              # App entry point
└── index.css             # Global styles (Tailwind directives)
```

## Key Components

### StorySubmissionForm
Validates and submits user stories to the API Gateway.

**Props:**
- `projectId: string` - Project context
- `onSuccessSubmit?: (jobId: string) => void` - Callback on successful submission

**Validation:**
- Title: 1-120 chars
- Story: 20-5000 chars
- Tags: Max 10, each max 32 chars
- Files: Max 5 files, each ≤10MB (`.pdf`, `.md`, `.txt`, `.png`, `.jpg`)

### PipelineStatusPanel
Displays real-time pipeline stage progress via WebSocket.

**Props:**
- `jobId: string`
- `jobRecord: JobRecord`

**Features:**
- Auto-connects to WebSocket on mount
- Shows per-stage status, timing, agent info, log snippets
- Timeout warning if job > 15 minutes

### TestSuiteViewer
Renders test cases with filtering and collapsible details.

**Props:**
- `jobId: string`
- `testCases: TestCase[]`
- `onFilterChange?: (filter: string | null) => void`

**Filters:**
- By status (ALL, PASS, FAIL, SKIP, PENDING)
- By tag

### ExecutionReportViewer
Shows execution summary, pass/fail charts, and failures.

**Props:**
- `jobId: string`
- `report: ExecutionReport`

**Features:**
- Export as PDF or CSV
- Coverage metrics
- Detailed failure stack traces

## WebSocket Integration

The WebSocket manager (`src/services/wsManager.ts`) handles:
- Connection lifecycle (connect, disconnect, reconnect)
- Exponential backoff reconnection (max 5 attempts, 30s cap)
- Heartbeat (ping/pong every 30s)
- Message subscription per job ID

**Usage:**
```typescript
import { wsManager } from './services/wsManager'

// Subscribe to job updates
const unsubscribe = wsManager.subscribe(jobId, (message) => {
  console.log('Status update:', message)
})

// Cleanup
unsubscribe()
```

## Authentication

JWT tokens are stored in `localStorage` and automatically injected into API requests via Axios interceptors.

**Demo Login:**
The login page includes a "Quick Demo Login" button that bypasses authentication for testing. In production, remove this or gate it behind a feature flag.

## API Error Handling

All API errors are parsed into structured `ApiError` objects with:
- `code`: Machine-readable error code (e.g., `VALIDATION_ERROR`, `UNAUTHORIZED`)
- `message`: Human-readable description
- `details`: Field-level errors (for validation failures)
- `requestId`: Correlation ID for debugging

Errors are displayed via Toast notifications.

## State Management

### AuthContext
Manages user authentication state and JWT lifecycle.

**Methods:**
- `login(email, password)`
- `logout()`
- `setAuthToken(token)`

### JobContext
Manages job data and API interactions.

**Methods:**
- `submitJob(payload)` - Submit new job
- `fetchJobs(projectId)` - List jobs
- `fetchJobDetail(jobId)` - Get job details
- `fetchJobTests(jobId)` - Get test cases
- `fetchJobReport(jobId)` - Get execution report
- `cancelJob(jobId)` - Cancel job

### WebSocketContext
Manages WebSocket connections for real-time updates.

**Methods:**
- `subscribe(jobId, callback)` - Subscribe to job updates
- `unsubscribe(jobId)` - Disconnect from job
- `reconnect()` - Manual reconnect

## Troubleshooting

### WebSocket Connection Fails
- Ensure API Gateway is running on `localhost:8080`
- Check JWT token is valid
- Verify CORS settings allow WebSocket upgrades

### API Requests Return 401
- Check JWT token in localStorage
- Verify token hasn't expired
- Ensure API Gateway JWKS is accessible

### Build Size Too Large
- Run `npm run build` and check bundle size
- Ensure tree-shaking is enabled (Vite default)
- Lazy-load heavy components with React.lazy()

## Performance Optimizations

- Code splitting by route (React Router)
- Manual chunks for vendor libraries (vite.config.ts)
- Lazy loading for non-critical components
- WebSocket connection pooling (singleton wsManager)
- Tailwind CSS purging (automatic in production)

## Browser Support

- Chrome 110+
- Firefox 110+
- Safari 16+
- Edge 110+

## License

Proprietary - QA Platform Internal Use Only
