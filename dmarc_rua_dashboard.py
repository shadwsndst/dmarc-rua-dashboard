import streamlit as st
import pandas as pd
import mailbox, gzip, zipfile, tempfile, os
import xml.etree.ElementTree as ET
from datetime import datetime
from streamlit.components.v1 import html as st_html

# --- Helpers ---
def convert_unix_to_date(ts):
    try:
        return datetime.utcfromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except:
        return ""

def format_date_short(date_str):
    """Convert full timestamp string to YYYY-MM-DD if possible."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")
    except:
        return date_str

def parse_dmarc_xml(path):
    records = []
    try:
        tree = ET.parse(path)
        root = tree.getroot()

        report_metadata = root.find("report_metadata")
        reporting_domain = report_metadata.findtext("org_name", default="")
        report_id = report_metadata.findtext("report_id", default="")

        date_range = report_metadata.find("date_range")
        begin = date_range.findtext("begin", default="") if date_range is not None else ""
        end = date_range.findtext("end", default="") if date_range is not None else ""

        policy_published = root.find("policy_published")
        domain = policy_published.findtext("domain", default="") if policy_published is not None else ""

        for record in root.findall("record"):
            row = {
                "reporting_domain": reporting_domain,
                "report_id": report_id,
                "date_begin": begin,
                "date_end": end,
                "domain": domain,
                "source_ip": record.findtext("row/source_ip", default=""),
                "count": int(record.findtext("row/count", default="0")),
                "disposition": record.findtext("row/policy_evaluated/disposition", default=""),
                "dkim": record.findtext("row/policy_evaluated/dkim", default=""),
                "spf": record.findtext("row/policy_evaluated/spf", default=""),
                "header_from": record.findtext("identifiers/header_from", default=""),
                "xml_path": path,
            }
            records.append(row)
    except Exception:
        pass
    return records

def parse_mbox_to_dataframe(mbox_file_or_bytes):
    data = (
        mbox_file_or_bytes.read()
        if hasattr(mbox_file_or_bytes, "read")
        else mbox_file_or_bytes
    )
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(data)
        mbox_path = tmp.name

    extract_dir = tempfile.mkdtemp()
    xml_files = []

    mbox = mailbox.mbox(mbox_path)
    for i, message in enumerate(mbox):
        if message.is_multipart():
            for part in message.walk():
                filename = part.get_filename()
                if not filename:
                    continue
                payload = part.get_payload(decode=True)
                fn = filename.lower()
                if fn.endswith(".xml"):
                    path = os.path.join(extract_dir, f"msg{i}_{filename}")
                    with open(path, "wb") as f:
                        f.write(payload)
                    xml_files.append(path)
                elif fn.endswith((".gz", ".gzip")):
                    gz_path = os.path.join(extract_dir, f"msg{i}_{filename}")
                    with open(gz_path, "wb") as f:
                        f.write(payload)
                    try:
                        import gzip as _gzip
                        with _gzip.open(gz_path, "rb") as gz:
                            xml_content = gz.read()
                        outpath = gz_path.rsplit(".", 1)[0]
                        with open(outpath, "wb") as f:
                            f.write(xml_content)
                        xml_files.append(outpath)
                    except Exception:
                        pass
                elif fn.endswith(".zip"):
                    zip_path = os.path.join(extract_dir, f"msg{i}_{filename}")
                    with open(zip_path, "wb") as f:
                        f.write(payload)
                    try:
                        with zipfile.ZipFile(zip_path, "r") as z:
                            z.extractall(extract_dir)
                            for name in z.namelist():
                                if name.lower().endswith(".xml"):
                                    xml_files.append(os.path.join(extract_dir, name))
                    except Exception:
                        pass

    all_records = []
    for f in xml_files:
        all_records.extend(parse_dmarc_xml(f))

    df = pd.DataFrame(all_records)
    if not df.empty:
        df["date_begin"] = df["date_begin"].apply(convert_unix_to_date)
        df["date_end"] = df["date_end"].apply(convert_unix_to_date)
    return df

def package_xml_files(df_subset, filename="dmarc_xml_export.zip"):
    tmpdir = tempfile.mkdtemp()
    zip_path = os.path.join(tmpdir, filename)
    with zipfile.ZipFile(zip_path, "w") as zf:
        for path in df_subset["xml_path"].dropna().unique():
            if os.path.exists(path):
                zf.write(path, os.path.basename(path))
    return zip_path

def stat_box(title, value, color="#ccc"):
    st.markdown(
        f"""
        <div style="border:2px solid {color}; border-radius:10px; padding:15px; text-align:center; margin-bottom:10px;">
            <h4 style="margin:0;">{title}</h4>
            <p style="font-size:24px; font-weight:bold; margin:5px 0; color:{color};">{value}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ---------- APP ----------
st.set_page_config(page_title="DMARC RUA Dashboard", layout="wide")
st.title("DMARC RUA Dashboard")

uploaded_file = st.file_uploader("📂 Drag & drop your MBOX file here", type="mbox")

if uploaded_file:
    with st.spinner("Parsing MBOX and extracting DMARC XML reports..."):
        df_all = parse_mbox_to_dataframe(uploaded_file)

    if df_all.empty:
        st.warning("No DMARC XML records were found in the uploaded MBOX.")
    else:
        # Summary stats
        total_reports = df_all["report_id"].nunique()
        total_records = len(df_all)
        date_min = df_all["date_begin"].min()
        date_max = df_all["date_end"].max()
        unique_ips = df_all["source_ip"].nunique()

        passes = df_all[df_all["disposition"] == "none"]["count"].sum()
        fails = df_all[df_all["disposition"] != "none"]["count"].sum()
        total_msgs = passes + fails
        pass_pct = round(passes / total_msgs * 100, 1) if total_msgs else 0
        fail_pct = round(fails / total_msgs * 100, 1) if total_msgs else 0

        top_fail_ips = (
            df_all[df_all["disposition"] != "none"]
            .groupby(["source_ip", "domain"])["count"]
            .sum()
            .sort_values(ascending=False)
            .head(5)
            .reset_index()
        )
        top_reporting_domains = (
            df_all.groupby(["reporting_domain"])["count"]
            .sum()
            .sort_values(ascending=False)
            .head(5)
            .reset_index()
        )

        # Shorten dates for Slack
        date_min_short = format_date_short(date_min)
        date_max_short = format_date_short(date_max)

        # Slack message builder with bolded numbers and short date range under title
        slack_message = (
            f"*DMARC RUA Scorecard*\n"
            f"_Date Range: {date_min_short} → {date_max_short}_\n\n"
            f"📊 *Summary*\n"
            f"Reports: *{total_reports}*\n"
            f"Records: *{total_records}*\n"
            f"Unique IPs: *{unique_ips}*\n"
            f"Passed: *{passes}* ({pass_pct}%)\n"
            f"Failed: *{fails}* ({fail_pct}%)\n\n"
            f"🔥 *Top 5 Failing IPs w/ Domains*\n"
            + "\n".join([f"{row.source_ip} ({row.domain}) → *{row['count']}*" for _, row in top_fail_ips.iterrows()])
            + "\n\n"
            f"🏢 *Top 5 Reporting Domains*\n"
            + "\n".join([f"{row.reporting_domain} → *{row['count']}*" for _, row in top_reporting_domains.iterrows()])
        )

        # Top bar: copy-to-clipboard button
        col1, col2 = st.columns([6, 1])
        with col2:
            st_html(
                f"""
                <div style="text-align:right;">
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

        # Summary boxes
        st.subheader("Summary")
        c1, c2, c3 = st.columns(3)
        with c1: stat_box("Total Reports", total_reports, color="#007acc")
        with c2: stat_box("Total Records", total_records, color="#007acc")
        with c3: stat_box("Unique Sending IPs", unique_ips, color="#007acc")

        c4, c5 = st.columns(2)
        with c4: stat_box("Date Range Start", date_min_short, color="#888")
        with c5: stat_box("Date Range End", date_max_short, color="#888")

        c6, c7 = st.columns(2)
        with c6: stat_box("Messages Passed DMARC", f"{passes} ({pass_pct}%)", color="green")
        with c7: stat_box("Messages Failed DMARC", f"{fails} ({fail_pct}%)", color="red")

        # Top tables
        st.subheader("Top 5 Failing IPs with Domains")
        st.dataframe(top_fail_ips, use_container_width=True)

        st.subheader("Top 5 Reporting Domains")
        st.dataframe(top_reporting_domains, use_container_width=True)
