# TaskFlow Frontend

React + Vite single-page app for the TaskFlow API.

## Quick start

```bash
cd frontend
npm install
npm run dev
```

The frontend runs on **http://localhost:5173** and proxies API calls to the FastAPI backend on port 8000. Make sure the backend is running first:

```bash
# Terminal 1 — backend
cd ..
python scripts/seed_data.py   # first time only
python run.py

# Terminal 2 — frontend
cd frontend
npm install
npm run dev
```

## Features

- **Login / Register** — JWT auth stored in localStorage
- **Tasks** — full CRUD, search, status filter, stats
- **Users** — list, edit, delete
- **Profile** — update own account

## Structure

```
src/
├── api/client.js          # All API calls (fetch wrapper)
├── context/AuthContext.jsx # Global auth state
├── pages/
│   ├── Login.jsx
│   ├── Register.jsx
│   ├── Tasks.jsx          # Task CRUD
│   ├── Users.jsx          # User CRUD
│   └── Profile.jsx
├── components/
│   └── TaskModal.jsx      # Create / edit task form
├── App.jsx                # Router + layout
└── index.css              # All styles
```
