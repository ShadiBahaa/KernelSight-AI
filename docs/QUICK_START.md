# KernelSight AI - Quick Start Guide

## 🚀 One-Command Demo

Run the complete end-to-end demonstration:

```bash
bash scripts/run_complete_demo.sh
```

**What it does:**
1. ✅ Checks prerequisites (Python, packages, stress)
2. ✅ Runs 3-minute stress test (generates ~3,000+ signals)
3. ✅ Processes data into semantic signals
4. ✅ Launches live Gemini 3 autonomous agent demo
5. ✅ Optional: Records with asciinema

**Total runtime:** ~15 minutes

---

## 📋 Prerequisites

### Required
```bash
# Python 3.10+
python3 --version

# Install Gemini library
pip3 install google-genai

# Stress utility (for data generation)
sudo apt install stress
```

### Optional (for recording)
```bash
pip3 install asciinema
```

---

## 🎬 Manual Steps (if preferred)

### Step 1: Generate Data
```bash
bash scripts/semantic_stress_test.sh
# Wait 3 minutes for completion
```

### Step 2: Run Demo
```bash
python3 scripts/hackathon_demo.py --db data/semantic_stress_test.db
```

### Step 3: Record (optional)
```bash
asciinema rec demo.cast -c "python3 scripts/hackathon_demo.py"
```

---

## 🔍 Verify Setup

Check if you have signals:
```bash
sqlite3 data/semantic_stress_test.db "SELECT COUNT(*) FROM signal_metadata"
```

Check signal types:
```bash
sqlite3 data/semantic_stress_test.db \
  "SELECT signal_type, COUNT(*) FROM signal_metadata GROUP BY signal_type"
```

---

## ⚙️ Configuration

### API Key
Set in `scripts/hackathon_demo.py`:
```python
os.environ['GEMINI_API_KEY'] = 'your-key-here'
```

Or export as environment variable:
```bash
export GEMINI_API_KEY='your-key-here'
python3 scripts/hackathon_demo.py
```

### Stress Test Duration
Edit `scripts/run_complete_demo.sh`:
```bash
STRESS_DURATION=180  # seconds (default: 3 minutes)
```

---

## 📊 What to Expect

### Demo Output
- **Scenario 1:** Memory leak detection + prediction
- **Scenario 2:** Cascade failure analysis
- **Scenario 3:** Self-reflection + learning

### Live Gemini Calls
You'll see real-time API responses in formatted boxes:
```
💡 Gemini 3's Real-Time Response:
┌──────────────────────────────────────────────────────────────────┐
│ The gradual linear memory growth with high statistical          │
│ confidence suggests a memory leak in a long-running process...  │
└──────────────────────────────────────────────────────────────────┘
```

### Metrics Shown
- Detection time: ~5 seconds
- Reasoning time: ~10 seconds
- MTTR improvement: **360-720x faster** than human

---

## 🐛 Troubleshooting

### "No recent signals found"
**Solution:** Run stress test first
```bash
bash scripts/semantic_stress_test.sh
```

### "Quota exceeded"
**Solution:** Try different model or wait for quota reset
- Edit `src/agent/gemini_client.py` line 173
- Change to: `gemini-1.5-flash` or `gemini-1.5-pro`

### "Database not found"
**Solution:** Check path
```bash
ls -lh data/semantic_stress_test.db
```

### "stress command not found"
**Solution:** Install stress
```bash
sudo apt update
sudo apt install stress
```

---

## 📚 Documentation Index

- **For Judges:** [README_FOR_JUDGES.md](README_FOR_JUDGES.md)
- **Architecture:** [Architecture Overview](architecture/overview.md)

- **Inspiration:** [INSPIRATION.md](INSPIRATION.md)
- **Diagnostic Narratives:** [diagnostic_narratives/](diagnostic_narratives/)

---

## 🎯 Ready to Submit?

1. ✅ Run complete demo
2. ✅ Record with asciinema
3. ✅ Review all docs in `docs/`
4. ✅ Check `docs/README_FOR_JUDGES.md`
5. ✅ Submit! 🚀

---

**Questions?** Check the [full documentation](README_FOR_JUDGES.md) or review the [diagnostic narratives](diagnostic_narratives/README.md) for detailed examples.
