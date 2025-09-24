# 📊 DMARC RUA Dashboard  

A Streamlit-powered dashboard for parsing and visualizing **DMARC RUA aggregate reports** from `.mbox` files.  
The tool makes it easy to:  

- Upload raw DMARC aggregate reports (MBOX format).  
- Parse XML records inside attachments (including `.gz` / `.zip`).  
- Summarize authentication pass/fail rates.  
- Identify top failing IPs and reporting domains.  
- Detect sending providers (SendGrid, ActiveCampaign, Front, etc.) via a provider dictionary.  
- Export ready-to-paste Slack updates for quick stakeholder reporting.  

---

## 🚀 Features
- **Interactive Web App** built with [Streamlit](https://streamlit.io/).  
- **Slack Export Buttons** for one-click copy of scorecards.  
- **Provider Fingerprinting** – categorize failures by known providers.  
- **Unknown Provider Detection** – quickly identify new senders for dictionary expansion.  
- **Summary Stats** – reports, records, unique IPs, pass/fail percentages.  
- **Top Lists** – failing IPs, reporting domains, providers.  

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

Then open [http://localhost:8501](http://localhost:8501) in your browser.  

---

## 📂 Example Workflow  
1. Export MBOX file from your DMARC RUA inbox.  
2. Drag & drop the file into the app.  
3. Review stats, failing IPs, and providers.  
4. Copy the Slack export and paste into your channel.  
5. Track unknown providers for dictionary updates.  

---

## 📌 Roadmap  
- [ ] Add automated Slack posting (via webhook).  
- [ ] Expand provider fingerprint dictionary.  
- [ ] Export reports to CSV/Excel.  
- [ ] Multi-file batch processing.  

---

## 🤝 Contributing  
PRs welcome! If you’d like to add new provider fingerprints, please submit a pull request with dictionary updates.  
