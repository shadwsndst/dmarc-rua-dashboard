# 📊 DMARC RUA Dashboard

A **Streamlit-powered dashboard** for parsing and visualizing DMARC RUA aggregate reports from `.mbox` files.

The tool makes it easy to:
- Upload raw DMARC aggregate reports (MBOX format)
- Parse XML records inside attachments (including `.gz` / `.zip`)
- Summarize authentication pass/fail rates
- Identify top failing IPs and reporting domains
- Detect sending providers via a safe provider dictionary
- Export ready-to-paste Slack updates for quick stakeholder reporting

---

## 🚀 Features

- **Interactive Web App** built with Streamlit  
- **Slack Export Button** for one-click copy of scorecards  
- **Provider Detection** – categorize failures by known providers  
- **Unknown Domain Detection** – quickly spot unrecognized senders for dictionary expansion  
- **Date Range Filtering** – focus on specific time periods with start/end controls  
- **Summary Stats** – reports, records, unique IPs, pass/fail percentages  
- **Top Lists** – failing IPs, reporting domains, *known providers*, *unknown domains*  

---

## 🛠️ Installation

1. Clone the repo:
```bash
git clone git@github.com:<your-username>/dmarc-rua-dashboard.git
cd dmarc-rua-dashboard
   ```

2. Create a virtual environment and install dependencies:  
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

---

## ▶️ Usage  

Run the dashboard locally with:  
```bash
streamlit run dmarc_rua_dashboard.py
```

### Alternate run method
You can also use the included helper script to start the app with one command:
```bash
./run.sh
```
This will automatically activate your virtual environment, install dependencies if needed, and launch the Streamlit dashboard.

---

## 📂 Example Workflow  
	1.	Export MBOX file from your DMARC RUA inbox.
	2.	Drag & drop the file into the app.
	3.	Apply date range filters if needed.
	4.	Review stats, failing IPs, and provider breakdowns (known vs. unknown).
	5.	Copy the Slack export and paste into your channel.
	6.	Track unknown domains for dictionary updates.

---

## 📌 Roadmap  
	•	Add automated Slack posting (via webhook).
	•	Expand provider fingerprint dictionary.
	•	Export reports to CSV/Excel.
	•	Multi-file batch processing.

---

## 🤝 Contributing  
PRs welcome! If you’d like to add new provider fingerprints, please submit a pull request with dictionary updates.  

---

This version only tweaks:  
- Features → mentions **date range filtering** and explicitly lists *known vs unknown domain split*.  
- Example Workflow → step 3 (date filters) + step 4 (provider breakdowns).  
- Everything else stays the same, no PII, no real domains.  
