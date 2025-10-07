import streamlit as st
import pandas as pd
import mailbox, gzip, zipfile, tempfile, os
import xml.etree.ElementTree as ET
from datetime import datetime
from streamlit.components.v1 import html as st_html
from packaging import version

# ---------------------------
# Provider Map (generic only)
# ---------------------------
PROVIDER_MAP = {
    "sendgrid": "SendGrid",
    "amazonses.com": "Amazon SES",
    "salesforce.com": "Salesforce Marketing Cloud",
    "bnc.salesforce.com": "Salesforce Marketing Cloud",
    "front-mail": "Front",
    "onmicrosoft.com": "Microsoft 365 / Exchange Online",
    "outlook.com": "Microsoft Outlook",
    "gmail.com": "Gmail",
    "google.com": "Google Workspace",
    "comcast.net": "Comcast",
    "comcastmailservice.net": "Comcast",
    "activecampaign.com": "ActiveCampaign",
    "activehosted.com": "ActiveCampaign",
    "mailchimp.com": "Mailchimp",
    "yahoo.com": "Yahoo",
}

# ---------------------------
# Helpers
# ---------------------------
def convert_unix_to_date(ts: str) -> str:
    try:
        return datetime.utcfromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return ""

def format_date_short(date_str: str) -> str:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")
    except Exception:
        return date_str or ""

def safe_txt(x) -> str:
    return (x or "").strip()

def lower_or_empty(x) -> str:
    return safe_txt(x).lower()

def domain_part(addr_or_domain: str) -> str:
    s = lower_or_empty(addr_or_domain)
    if "@" in s:
        return s.split("@", 1)[-1]
    return s

# ---------------------------
# XML parsing
# ---------------------------
def parse_dmarc_xml(path: str):
    out = []
    try:
        root = ET.parse(path).getroot()

        report_metadata = root.find("report_metadata")
        org_name = safe_txt(report_metadata.findtext("org_name", default="")) if report_metadata is not None else ""
        report_id = safe_txt(report_metadata.findtext("report_id", default="")) if report_metadata is not None else ""

        date_range = report_metadata.find("date_range") if report_metadata is not None else None
        begin = safe_txt(date_range.findtext("begin", default="")) if date_range is not None else ""
        end   = safe_txt(date_range.findtext("end", default=""))   if date_range is not None else ""

        policy_published = root.find("policy_published")
        policy_domain = safe_txt(policy_published.findtext("domain", default="")) if policy_published is not None else ""

        for rec in root.findall("record"):
            r = rec.find("row")
            source_ip = safe_txt(r.findtext("source_ip", default="")) if r is not None else ""
            count     = int(safe_txt(r.findtext("count", default="0"))) if r is not None else 0
            pe        = r.find("policy_evaluated") if r is not None else None
            disposition = safe_txt(pe.findtext("disposition", default="")) if pe is not None else ""

            identifiers = rec.find("identifiers")
            header_from    = safe_txt(identifiers.findtext("header_from", default="")) if identifiers is not None else ""
            envelope_from  = safe_txt(identifiers.findtext("envelope_from", default="")) if identifiers is not None else ""

            ar = rec.find("auth_results")
            dkim_domain = ""
            spf_domain = ""
            if ar is not None:
                dkim_elem = ar.find("dkim")
                if dkim_elem is not None:
                    dkim_domain = safe_txt(dkim_elem.findtext("domain", default=""))
                spf_elem = ar.find("spf")
                if spf_elem is not None:
                    spf_domain = safe_txt(spf_elem.findtext("domain", default=""))

            out.append({
                "reporting_domain": org_name,
                "report_id": report_id,
                "date_begin": begin,
                "date_end": end,
                "domain": policy_domain,
                "source_ip": source_ip,
                "count": count,
                "disposition": disposition,
                "header_from": header_from,
                "envelope_from": envelope_from,
                "auth_dkim_domain": dkim_domain,
                "auth_spf_domain": spf_domain,
                "xml_path": path,
            })
    except Exception:
        pass
    return out

def parse_mbox_to_dataframe(mbox_file_or_bytes):
    raw = mbox_file_or_bytes.read() if hasattr(mbox_file_or_bytes, "read") else mbox_file_or_bytes
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(raw)
        mbox_path = tmp.name

    extract_dir = tempfile.mkdtemp()
    xml_files = []

    mbox = mailbox.mbox(mbox_path)
    for i, msg in enumerate(mbox):
        if not msg.is_multipart():
            continue
        for part in msg.walk():
            fname = part.get_filename()
            if not fname:
                continue
            payload = part.get_payload(decode=True)
            lf = fname.lower()

            if lf.endswith(".xml"):
                p = os.path.join(extract_dir, f"msg{i}_{fname}")
                with open(p, "wb") as f:
                    f.write(payload)
                xml_files.append(p)

            elif lf.endswith((".gz", ".gzip")):
                gz_path = os.path.join(extract_dir, f"msg{i}_{fname}")
                with open(gz_path, "wb") as f:
                    f.write(payload)
                try:
                    with gzip.open(gz_path, "rb") as gz:
                        xml_content = gz.read()
                    outpath = gz_path.rsplit(".", 1)[0]
                    with open(outpath, "wb") as f:
                        f.write(xml_content)
                    xml_files.append(outpath)
                except Exception:
                    pass

            elif lf.endswith(".zip"):
                zp = os.path.join(extract_dir, f"msg{i}_{fname}")
                with open(zp, "wb") as f:
                    f.write(payload)
                try:
                    with zipfile.ZipFile(zp, "r") as z:
                        z.extractall(extract_dir)
                        for name in z.namelist():
                            if name.lower().endswith(".xml"):
                                xml_files.append(os.path.join(extract_dir, name))
                except Exception:
                    pass

    records = []
    for p in xml_files:
        records.extend(parse_dmarc_xml(p))

    df = pd.DataFrame(records)
    if not df.empty:
        df["date_begin"] = df["date_begin"].apply(convert_unix_to_date)
        df["date_end"]   = df["date_end"].apply(convert_unix_to_date)
        df["date_begin_dt"] = pd.to_datetime(df["date_begin"], errors="coerce", utc=True)
        df["date_end_dt"]   = pd.to_datetime(df["date_end"], errors="coerce", utc=True)
    return df

# ---------------------------
# Provider inference
# ---------------------------
def detect_provider_and_domain(row):
    candidates = [
        row.get("auth_dkim_domain", ""),
        row.get("auth_spf_domain", ""),
        row.get("envelope_from", ""),
        row.get("header_from", ""),
    ]
    cand_domains = [domain_part(c) for c in candidates if c]

    for cd in cand_domains:
        for key, name in PROVIDER_MAP.items():
            if key in cd:
                return name, cd

    for cd in cand_domains:
        if cd and cd != domain_part(row.get("domain", "")):
            return None, cd

    return None, domain_part(row.get("domain", ""))

def compute_provider_tables(df_filtered: pd.DataFrame):
    if df_filtered.empty:
        return pd.DataFrame(columns=["provider","matched_domain","count"]), pd.DataFrame(columns=["domain","count"])

    prov = df_filtered.apply(detect_provider_and_domain, axis=1, result_type="expand")
    prov.columns = ["provider", "matched_domain"]
    enriched = pd.concat([df_filtered.reset_index(drop=True), prov], axis=1)

    failures = enriched[enriched["disposition"] != "none"].copy()

    known = (
        failures[failures["provider"].notna()]
        .groupby(["provider", "matched_domain"], as_index=False)["count"]
        .sum()
        .sort_values("count", ascending=False)
        .head(5)
        .reset_index(drop=True)
    )

    own_domains = set(enriched["domain"].dropna().map(domain_part))
    unknown = (
        failures[(failures["provider"].isna()) & (~failures["matched_domain"].isin(own_domains))]
        .groupby("matched_domain", as_index=False)["count"]
        .sum()
        .rename(columns={"matched_domain": "domain"})
        .sort_values("count", ascending=False)
        .head(5)
        .reset_index(drop=True)
    )

    return known, unknown

# ---------------------------
# UI helpers
# ---------------------------
def stat_box(title, value, color="#ccc"):
    st.markdown(
        f"""
        <div style="border:2px solid {color}; border-radius:10px; padding:16px; text-align:center; margin-bottom:10px;">
            <h4 style="margin:0;">{title}</h4>
            <p style="font-size:24px; font-weight:bold; margin:6px 0; color:{color};">{value}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ---------------------------
# App
# ---------------------------
st.set_page_config(page_title="DMARC RUA Dashboard", layout="wide")
st.title("DMARC RUA Dashboard")

uploaded_file = st.file_uploader("📂 Drag & drop your MBOX file here", type="mbox")

if uploaded_file:
    with st.spinner("Parsing MBOX and extracting DMARC XML reports..."):
        df_all = parse_mbox_to_dataframe(uploaded_file)

    if df_all.empty:
        st.warning("No DMARC XML records were found in the uploaded MBOX.")
        st.stop()

    # --- Date filter ---
    st.subheader("Filter by Date Range")
    default_start = pd.to_datetime(df_all["date_begin_dt"].min()).date()
    default_end   = pd.to_datetime(df_all["date_end_dt"].max()).date()

    c1, c2 = st.columns([2,2])
    with c1:
        start_input = st.date_input("Start date", value=default_start)
    with c2:
        end_input   = st.date_input("End date",   value=default_end)

    c3, c4 = st.columns([1,1])
    with c3:
        apply_filter = st.button("Apply Filter", use_container_width=True)
    with c4:
        clear_filter = st.button("Clear Filter", type="secondary", use_container_width=True)

    if "active_range" not in st.session_state:
        st.session_state.active_range = (default_start, default_end)

    if apply_filter:
        st.session_state.active_range = (start_input, end_input)
    if clear_filter:
        st.session_state.active_range = (default_start, default_end)

    start_date, end_date = st.session_state.active_range
    start_ts = pd.Timestamp(start_date).tz_localize("UTC")
    end_ts   = pd.Timestamp(end_date).tz_localize("UTC")

    df_filtered = df_all[(df_all["date_begin_dt"] >= start_ts) & (df_all["date_end_dt"] <= end_ts)].copy()

    # --- Stats ---
    total_reports = df_filtered["report_id"].nunique()
    total_records = int(df_filtered["count"].sum()) if "count" in df_filtered else len(df_filtered)
    unique_ips    = df_filtered["source_ip"].nunique()

    passes = int(df_filtered[df_filtered["disposition"] == "none"]["count"].sum())
    fails  = int(df_filtered[df_filtered["disposition"] != "none"]["count"].sum())
    total_msgs = passes + fails
    pass_pct = round(passes / total_msgs * 100, 1) if total_msgs else 0.0
    fail_pct = round(fails / total_msgs * 100, 1) if total_msgs else 0.0

    # --- Simple Slack message ---
    start_short = start_date.isoformat()
    end_short   = end_date.isoformat()
    slack_message = (
        f"*DMARC RUA Scorecard*\n"
        f"_Date Range: {start_short} → {end_short}_\n\n"
        f"📊 *Summary*\n"
        f"Reports: *{total_reports}*\n"
        f"Records: *{total_records}*\n"
        f"Unique IPs: *{unique_ips}*\n"
        f"Passed: *{passes}* ({pass_pct}%)\n"
        f"Failed: *{fails}* ({fail_pct}%)\n"
    )
    st_html(
        f"""
        <div style="text-align:left; margin:8px 0 12px;">
          <textarea id="slackText" style="position:absolute; left:-10000px; top:-10000px;">{slack_message}</textarea>
          <button id="copyBtn" style="padding:8px 10px; border-radius:8px; border:1px solid #ccc; cursor:pointer;">
            📋 Copy Slack Update
          </button>
        </div>
        <script>
        const btn = document.getElementById('copyBtn');
        const ta  = document.getElementById('slackText');
        btn.addEventListener('click', async () => {{
          try {{
            await navigator.clipboard.writeText(ta.value);
            btn.textContent = '✅ Copied!';
            setTimeout(() => btn.textContent = '📋 Copy Slack Update', 1500);
          }} catch (e) {{
            ta.select(); ta.setSelectionRange(0, 999999);
            document.execCommand('copy');
            btn.textContent = '✅ Copied!';
            setTimeout(() => btn.textContent = '📋 Copy Slack Update', 1500);
          }}
        }});
        </script>
        """,
        height=60,
    )

    # --- UI: Summary boxes ---
    st.subheader("Summary")
    a,b,c = st.columns(3)
    with a: stat_box("Total Reports", total_reports, color="#007acc")
    with b: stat_box("Total Records", total_records, color="#007acc")
    with c: stat_box("Unique Sending IPs", unique_ips, color="#007acc")

    d,e = st.columns(2)
    with d: stat_box("Date Range Start", start_short, color="#888")
    with e: stat_box("Date Range End",   end_short,   color="#888")

    f,g = st.columns(2)
    with f: stat_box("Messages Passed DMARC", f"{passes} ({pass_pct}%)", color="green")
    with g: stat_box("Messages Failed DMARC", f"{fails} ({fail_pct}%)",  color="red")

    # --- Tables ---
    st.subheader("Top 5 Known Providers (by Failures)")
    known_providers, unknown_domains = compute_provider_tables(df_filtered)
    st.dataframe(known_providers.rename(columns={"matched_domain": "domain"}), use_container_width=True, hide_index=True)

    st.subheader("Top 5 Unknown Domains (by Failures)")
    st.dataframe(unknown_domains, use_container_width=True, hide_index=True)

    # --- Visualization: Top 5 Reporting Domains by Week ---
    import altair as alt

    st.subheader("Top 5 Reporting Domains by Week")

    if not df_filtered.empty:
        df_filtered["week"] = df_filtered["date_begin_dt"].dt.to_period("W").apply(lambda r: r.start_time)
        weekly_summary = (
            df_filtered.groupby(["reporting_domain", "week"])["count"]
            .sum()
            .reset_index()
        )

        top5_domains = (
            weekly_summary.groupby("reporting_domain")["count"]
            .sum()
            .nlargest(5)
            .index
        )

        top5_df = weekly_summary[weekly_summary["reporting_domain"].isin(top5_domains)]

        hover = alt.selection_single(fields=["reporting_domain"], nearest=True, on="mouseover", empty="none")

        chart = (
            alt.Chart(top5_df)
            .mark_line(point=True)
            .encode(
                x=alt.X("week:T", title="Week"),
                y=alt.Y("count:Q", title="Message Count"),
                color=alt.Color("reporting_domain:N", title="Reporting Domain", scale=alt.Scale(scheme="tableau10")),
                tooltip=[
                    alt.Tooltip("reporting_domain:N", title="Domain"),
                    alt.Tooltip("week:T", title="Week Start"),
                    alt.Tooltip("count:Q", title="Count")
                ],
                opacity=alt.condition(hover, alt.value(1.0), alt.value(0.25))
            )
            .add_selection(hover)
            .properties(height=400)
        )

        if version.parse(st.__version__) >= version.parse("1.50.0"):
            st.altair_chart(chart, width='stretch')
        else:
            st.altair_chart(chart, use_container_width=True)
    else:
        st.info("No data available for weekly reporting domain trends.")
