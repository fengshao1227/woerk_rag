# Admin Frontend

> [Home](../CLAUDE.md) > Admin Frontend

## Overview

React 19 + Vite management dashboard with Ant Design components.

## Tech Stack

| Tech | Version |
|------|---------|
| React | 19.2.0 |
| Vite | 7.2.4 |
| Ant Design | 6.0.1 |
| React Router | 7.10.1 |
| Axios | 1.13.2 |

## Directory Structure

```
admin_frontend/
├── src/
│   ├── App.jsx          # Main app with routing
│   ├── main.jsx         # Entry point
│   ├── index.css        # Global styles (TailwindCSS)
│   ├── pages/           # Page components
│   ├── components/      # Reusable components
│   ├── services/        # API service layer
│   └── hooks/           # Custom React hooks
├── dist/                # Production build output
├── package.json
└── vite.config.js
```

## Pages

| Page | Description |
|------|-------------|
| Login | Authentication |
| Dashboard | Statistics overview |
| Providers | LLM provider management |
| Models | LLM model management |
| Knowledge | Knowledge base CRUD |
| Groups | Knowledge grouping |
| ApiKeys | MCP API key management |
| Users | User management |
| Settings | System settings |

## Key Components

- **Layout**: Main layout with sidebar navigation
- **AuthGuard**: Protected route wrapper
- **DataTable**: Reusable table with pagination

## API Service

Located in `src/services/api.js`:

```javascript
// Base configuration
const api = axios.create({
  baseURL: '/admin/api',
  headers: { 'Content-Type': 'application/json' }
});

// Request interceptor adds JWT token
// Response interceptor handles 401 redirect
```

## Development

```bash
# Install dependencies
npm install

# Start dev server (port 5173)
npm run dev

# Build for production
npm run build

# Preview build
npm run preview
```

## Build Output

Production build goes to `dist/` and is served by FastAPI as static files at `/admin`.

## Styling

- TailwindCSS classes in `index.css`
- Ant Design components for UI
- Custom CSS in `App.css`

## Environment

Development server proxies API requests to backend (configured in `vite.config.js`).
