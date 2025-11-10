# SynthAI Setup & Run Instructions

Complete guide to set up and run the SynthAI Literature Discovery system.

---

## Prerequisites

- **Python 3.11+**
- **Node.js 18+** and npm
- **Git**
- **API Keys**:
  - Anthropic API key (required)
  - NCBI E-utilities API key (recommended for better rate limits)

---

## 🔑 Step 1: Get API Keys

### 1.1 Anthropic API Key (Required)
1. Go to https://console.anthropic.com/
2. Sign up / Log in
3. Navigate to API Keys
4. Create a new key
5. Copy your key (starts with `sk-ant-api03-`)

### 1.2 NCBI E-utilities API Key (Recommended)
1. Create an NCBI account at https://www.ncbi.nlm.nih.gov/account/
2. Go to https://www.ncbi.nlm.nih.gov/account/settings/
3. Scroll to "API Key Management"
4. Click "Create an API Key"
5. Copy your key

**Why?** NCBI API key increases rate limit from 3 req/s to 10 req/s, preventing 429 errors.

---

## ⚙️ Step 2: Configure Environment

1. **Navigate to project root**:
   ```bash
   cd /Users/namithrao/projects/SynthAI
   ```

2. **Edit `.env` file** and add your keys:
   ```bash
   nano .env
   ```

   Update these lines:
   ```env
   ANTHROPIC_API_KEY=your_anthropic_key_here
   NCBI_API_KEY=your_ncbi_key_here
   ```

   Save and exit (Ctrl+X, then Y, then Enter).

---

## 🔧 Step 3: Backend Setup

### 3.1 Create Virtual Environment
```bash
cd apps/backend
python3 -m venv venv
```

### 3.2 Activate Virtual Environment

**macOS/Linux**:
```bash
source venv/bin/activate
```

**Windows**:
```bash
venv\Scripts\activate
```

Your terminal should now show `(venv)` prefix.

### 3.3 Install Dependencies
```bash
pip install -r requirements.txt
```

This will install:
- FastAPI & Uvicorn (web framework)
- Anthropic SDK (Claude AI)
- httpx (HTTP client)
- transformers & torch (BlueBERT)
- pandas, numpy, scipy (data processing)
- And more...

**Note**: Installation may take 5-10 minutes due to PyTorch.

### 3.4 Verify Installation
```bash
python -c "import anthropic; import httpx; import fastapi; print('✅ All dependencies installed')"
```

---

## 🎨 Step 4: Frontend Setup

### 4.1 Navigate to Frontend
```bash
# Open a NEW terminal window/tab
cd /Users/namithrao/projects/SynthAI/apps/frontend
```

### 4.2 Install Dependencies
```bash
npm install
```

This will install:
- React & TypeScript
- Vite (dev server)
- Tailwind CSS (styling)
- Axios (HTTP client)
- Lucide React (icons)

### 4.3 Verify Installation
```bash
npm list react
```

Should show React version ~18.2.0.

---

## 🚀 Step 5: Run the Application

You need **TWO terminal windows** running simultaneously.

### Terminal 1: Backend Server

```bash
cd /Users/namithrao/projects/SynthAI/apps/backend
source venv/bin/activate  # Or venv\Scripts\activate on Windows
uvicorn synthai_backend.main:app --reload --host 0.0.0.0 --port 8000
```

**Expected output**:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Initializing SynthAI MCP Orchestrator...
INFO:     Application startup complete.
```

✅ Backend running at http://localhost:8000

### Terminal 2: Frontend Dev Server

```bash
cd /Users/namithrao/projects/SynthAI/apps/frontend
npm run dev
```

**Expected output**:
```
  VITE v5.1.0  ready in 500 ms

  ➜  Local:   http://localhost:5173/
  ➜  Network: use --host to expose
  ➜  press h + enter to show help
```

✅ Frontend running at http://localhost:5173

---

## 🌐 Step 6: Access the Application

Open your browser and go to:

**http://localhost:5173**

You should see the SynthAI interface with two tabs:
1. **NHANES Data Research** (uses MCP for NHANES data)
2. **Literature Discovery** (PubMed/PMC search with Claude analysis)

---

## 📚 Step 7: Test Literature Discovery

### Test via Web Interface

1. Go to http://localhost:5173
2. Click **Literature Discovery** tab
3. Enter a hypothesis, for example:
   ```
   Does elevated C-reactive protein predict cardiovascular events in adults with type 2 diabetes?
   ```
4. Click **Discover from PubMed**
5. Wait 30-60 seconds for results

You should see:
- ✅ Summary statistics (papers analyzed, variables found)
- ✅ Synthesis insights
- ✅ Variables table (for generator)
- ✅ Paper cards (expandable with abstracts/full text)

### Test via Python Script

```bash
cd /Users/namithrao/projects/SynthAI/apps/backend
source venv/bin/activate
python test_literature_discovery.py
```

**Expected output**:
```
================================================================================
TESTING LITERATURE DISCOVERY AGENT V2
================================================================================

📋 Hypothesis: Does elevated C-reactive protein predict cardiovascular events in adults with type 2 diabetes?
🎯 Target: Find 10 variables
📚 Max papers: 5 (for testing)
🔄 Max iterations: 2

[NCBI ESearch] Found 25 PMIDs for query: ...
[NCBI ESummary] Retrieved 5 paper summaries
[NCBI EFetch] Fetching abstract for PMID:12345678
...

================================================================================
✅ DISCOVERY COMPLETED SUCCESSFULLY
================================================================================

📊 SYNTHESIS INPUT (for generator):
   Variables found: 12
   Correlations: 3
   ...
```

---

## 🔍 Step 8: Explore API Documentation

### Backend API Docs

Visit http://localhost:8000/docs

This shows interactive Swagger UI with all endpoints:
- `GET /` - Health check
- `POST /api/research` - NHANES research
- `POST /api/literature` - Literature discovery (NEW!)
- `GET /api/health` - Detailed health check

### Test Endpoints Directly

You can test the API using the Swagger UI or curl:

```bash
curl -X POST "http://localhost:8000/api/literature" \
  -H "Content-Type: application/json" \
  -d '{
    "hypothesis": "Does elevated CRP predict CVD in diabetics?",
    "min_variables": 10,
    "max_papers": 5,
    "max_iterations": 2
  }'
```

---

## 🐛 Troubleshooting

### Error: `ModuleNotFoundError: No module named 'anthropic'`

**Solution**: Activate virtual environment first
```bash
cd apps/backend
source venv/bin/activate  # macOS/Linux
# OR
venv\Scripts\activate  # Windows
```

### Error: `429 Too Many Requests` from NCBI

**Cause**: No NCBI API key or hitting rate limits

**Solutions**:
1. Add NCBI_API_KEY to `.env` file
2. Reduce `max_papers` in request
3. Wait a few minutes if you hit the limit

### Error: `ANTHROPIC_API_KEY not configured`

**Solution**: Check `.env` file has valid Anthropic API key
```bash
cat .env | grep ANTHROPIC_API_KEY
```

### Frontend shows "Network Error"

**Cause**: Backend not running

**Solution**:
1. Check backend is running on port 8000
2. Visit http://localhost:8000 - should show `{"status": "healthy"}`
3. Restart backend if needed

### Port Already in Use

**Backend (8000)**:
```bash
# macOS/Linux
lsof -ti:8000 | xargs kill -9

# Windows
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

**Frontend (5173)**:
```bash
# macOS/Linux
lsof -ti:5173 | xargs kill -9

# Windows
netstat -ano | findstr :5173
taskkill /PID <PID> /F
```

---

## 📁 Project Structure

```
SynthAI/
├── .env                          # Environment variables (API keys)
├── apps/
│   ├── backend/
│   │   ├── venv/                # Python virtual environment
│   │   ├── requirements.txt     # Python dependencies
│   │   ├── synthai_backend/
│   │   │   ├── main.py         # FastAPI app
│   │   │   ├── config.py       # Settings (loads .env)
│   │   │   ├── agents/
│   │   │   │   └── literature_discovery_agent_v2.py  # Literature agent
│   │   │   └── models/
│   │   │       └── literature_models.py              # Pydantic models
│   │   └── test_literature_discovery.py  # Test script
│   └── frontend/
│       ├── package.json         # Node dependencies
│       ├── vite.config.ts      # Vite config (proxy to backend)
│       └── src/
│           ├── App.tsx         # Main UI (tabs, forms)
│           └── components/
│               └── PaperCard.tsx  # Paper display component
└── SETUP_INSTRUCTIONS.md       # This file
```

---

## 🎯 Quick Start Summary

**One-time setup**:
```bash
# 1. Backend setup
cd apps/backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Frontend setup (new terminal)
cd apps/frontend
npm install

# 3. Configure .env
nano .env  # Add your API keys
```

**Every time you run**:
```bash
# Terminal 1: Backend
cd apps/backend
source venv/bin/activate
uvicorn synthai_backend.main:app --reload --port 8000

# Terminal 2: Frontend
cd apps/frontend
npm run dev

# Open browser: http://localhost:5173
```

---

## 📊 Testing Checklist

- [ ] Backend starts without errors
- [ ] Frontend starts without errors
- [ ] Can access http://localhost:5173
- [ ] Can access http://localhost:8000/docs
- [ ] NHANES tab works
- [ ] Literature Discovery tab works
- [ ] Can enter hypothesis and get results
- [ ] Papers show with abstracts
- [ ] Can expand paper cards
- [ ] Full text displays (when available)
- [ ] Variables table shows correct data

---

## 🆘 Need Help?

1. **Check logs**: Backend terminal shows detailed error messages
2. **Check API docs**: http://localhost:8000/docs
3. **Check .env**: Ensure all API keys are correct
4. **Restart everything**: Sometimes a clean restart fixes issues

---

**Happy researching! 🔬✨**
