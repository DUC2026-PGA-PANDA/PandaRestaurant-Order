# DUC2026-[Company-Name] — Panda Restaurant (adapted)

Project reorganized to follow the `src/` layout suggested by the team. This repo originally contained a `backend/` package and a `frontend/` folder; the runtime code continues to live in `backend/` but the `src/` wrapper provides a clear entrypoint and package layout for future refactor.

Layout
```
DUC2026-[Company-Name]
├── .github/
├── src/
│   ├── handlers/
│   ├── models/
│   ├── services/
│   ├── utils/
│   └── app.py
├── backend/ (existing implementation)
├── frontend/
├── tests/
├── .env.example
├── .gitignore
└── requirements.txt
```

Getting started

1. Copy `.env.example` to `.env` and fill in values.
2. Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

3. Run the app:

```powershell
python run.py
```

Notes
- This is a minimal reorganization to provide `src/` wrapper files while keeping the existing code base functional. I can further move modules into `src/handlers`, `src/models`, etc., and update imports if you want a full conversion.
