# Files Safe to Delete - DCLM Project

**Purpose:** This document lists files that can be safely deleted from the project without affecting functionality.

---

## Temporary Test/Verification Scripts

These were created during development for testing and can be removed:

### Root Directory Scripts
```
✗ check_db_simple.py          # Database connection test
✗ check_dependencies.py        # Dependency verification
✗ check_rls.py                 # RLS verification script
✗ check_idempotency.py         # Idempotency testing
✗ check_media.py               # Media module testing
✗ check_public.py              # Public API testing
✗ count_routes.py              # Route counting utility
```

**Reason:** These were one-time verification scripts. The features they tested are now confirmed working.

**Action:** Delete all `check_*.py` and `count_routes.py` files from root.

---

## Duplicate/Old CRUD Files

The `app/crud/` directory may contain old/duplicate files:

### Check for These Patterns
```
✗ *_crud.py (if corresponding crud_*.py exists)
  Examples:
  - count_crud.py (if crud_counts.py exists)
  - location_crud.py (if crud_location.py exists)
  - offering_crud.py (if crud_offerings.py exists)
  - program_crud.py (if crud_programs.py exists)
  - user_crud.py (if crud_user.py exists)
  - worker_crud.py (if crud_worker.py exists)
  - newcomer_crud.py (if crud_records.py exists)
  - convert_crud.py (if crud_records.py exists)
```

**Reason:** Naming convention was standardized to `crud_*.py`. Old `*_crud.py` files are duplicates.

**Action:** 
1. Verify the `crud_*.py` version exists and is being used
2. Delete the `*_crud.py` version
3. Check imports in route files to ensure they use the correct version

---

## Development/Example Files

### Potential Development Artifacts
```
✗ test.py                      # Generic test file
✗ example.py                   # Example code
✗ temp.py                      # Temporary scripts
✗ scratch.py                   # Scratch work
✗ debug.py                     # Debug helpers
```

**Action:** Search for and remove any such files.

---

## Old Migration Files (If Applicable)

### Alembic Migrations
**Keep:** All migration files in `alembic/versions/`  
**Review:** Check if any migrations are marked as "test" or "temp"

**Action:** Generally keep all migrations, but review for any obviously temporary ones.

---

## Documentation Duplicates

### Artifact Directory
The `.gemini/antigravity/brain/` directory contains documentation artifacts.

**Keep:** All files in this directory (they're documentation)  
**Move:** Consider moving final docs to `dclm/docs/` for production

---

## Node.js Related Files (Not Needed)

Since you confirmed all apps will be Python-based:

```
✗ package.json                 # Node.js dependencies
✗ package-lock.json            # Node.js lock file
✗ node_modules/                # Node.js packages
✗ .npmrc                       # NPM configuration
✗ yarn.lock                    # Yarn lock file
```

**Action:** If any of these exist, delete them.

---

## IDE/Editor Specific Files (Optional Cleanup)

### VS Code
```
? .vscode/settings.json        # Personal settings (keep if useful)
? .vscode/launch.json          # Debug configs (keep if useful)
```

### PyCharm
```
? .idea/                       # PyCharm project files
```

**Action:** These are personal preference. Delete if not using that IDE.

---

## Python Cache Files (Auto-Generated)

These are safe to delete (will be regenerated):

```
✗ __pycache__/                 # Python bytecode cache
✗ *.pyc                        # Compiled Python files
✗ *.pyo                        # Optimized Python files
✗ .pytest_cache/               # Pytest cache
✗ .mypy_cache/                 # MyPy cache
✗ .ruff_cache/                 # Ruff cache
```

**Action:** Delete all cache directories. Add to `.gitignore` if not already there.

---

## Environment Files (Keep But Review)

```
✓ .env                         # Keep (contains secrets)
✓ .env.example                 # Keep (template for others)
? .env.local                   # Delete if duplicate of .env
? .env.development             # Delete if not using multiple envs
? .env.production              # Keep if using for deployment
```

**Action:** Keep `.env` and `.env.example`. Remove duplicates.

---

## Log Files

```
✗ *.log                        # Application logs
✗ logs/                        # Log directory
```

**Action:** Delete old logs. Ensure logs/ is in `.gitignore`.

---

## Database Files (If Using SQLite for Testing)

```
✗ *.db                         # SQLite database files
✗ *.sqlite                     # SQLite database files
✗ *.sqlite3                    # SQLite database files
```

**Action:** Delete if using PostgreSQL (Supabase) in production.

---

## Recommended Cleanup Commands

### Windows (PowerShell)
```powershell
# Navigate to project root
cd C:\Users\Meshell\Desktop\Backends\dclm

# Remove test scripts
Remove-Item check_*.py
Remove-Item count_routes.py

# Remove Python cache
Get-ChildItem -Recurse -Directory __pycache__ | Remove-Item -Recurse -Force
Get-ChildItem -Recurse -Filter *.pyc | Remove-Item -Force

# Remove Node.js files (if they exist)
Remove-Item package.json -ErrorAction SilentlyContinue
Remove-Item package-lock.json -ErrorAction SilentlyContinue
Remove-Item -Recurse node_modules -ErrorAction SilentlyContinue

# Review and remove duplicate CRUD files
# (Manual step - check each one)
```

### Linux/Mac (Bash)
```bash
# Navigate to project root
cd ~/path/to/dclm

# Remove test scripts
rm -f check_*.py count_routes.py

# Remove Python cache
find . -type d -name __pycache__ -exec rm -rf {} +
find . -type f -name "*.pyc" -delete

# Remove Node.js files (if they exist)
rm -f package.json package-lock.json
rm -rf node_modules/
```

---

## Files to KEEP

### Essential Project Files
```
✓ app/                         # Main application code
✓ alembic/                     # Database migrations
✓ requirements.txt             # Python dependencies
✓ requirements-dev.txt         # Dev dependencies
✓ .env.example                 # Environment template
✓ .gitignore                   # Git ignore rules
✓ README.md                    # Project readme
✓ alembic.ini                  # Alembic configuration
✓ pyproject.toml               # Project metadata (if exists)
✓ setup.py                     # Setup script (if exists)
```

### Documentation
```
✓ docs/                        # Documentation directory
✓ COMPREHENSIVE_PROJECT_REVIEW.md
✓ planning_chat.txt
```

---

## Summary

### Safe to Delete (Confirmed)
1. All `check_*.py` scripts (7 files)
2. `count_routes.py`
3. All `__pycache__/` directories
4. Any Node.js related files
5. Old log files

### Review Before Deleting
1. Duplicate CRUD files (`*_crud.py` vs `crud_*.py`)
2. IDE-specific directories
3. Multiple `.env` files

### Never Delete
1. `app/` directory
2. `alembic/` directory
3. `requirements.txt`
4. `.env` (your secrets)
5. `.gitignore`

---

**Estimated Space Savings:** 10-50 MB (mostly from cache files)  
**Risk Level:** Low (all listed files are non-essential)  
**Recommendation:** Start with test scripts and cache files, then review duplicates manually.
