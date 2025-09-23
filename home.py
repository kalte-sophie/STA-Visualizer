import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import io

st.title("STA Daten Visualisierung – mit Baseline-Korrektur & Onset/Peak Auswertung")

# Checkboxen für Signale
show_tg = st.checkbox("TG anzeigen", value=True)
show_dsc = st.checkbox("DSC anzeigen", value=True)
show_tangents = st.checkbox("Tangenten anzeigen", value=False)

# TG in mg oder %
weight_option = st.radio("TG anzeigen als:", ("mg", "%"))

# Dateien hochladen
uploaded_files = st.file_uploader("STA CSV Dateien hochladen", type=["csv"], accept_multiple_files=True)

# Sidebar: Achsenlimits
st.sidebar.header("Achsenlimits")
auto_x = st.sidebar.checkbox("X-Achse Auto", value=True)
auto_y1 = st.sidebar.checkbox("TG-Achse Auto", value=True)
auto_y2 = st.sidebar.checkbox("DSC-Achse Auto", value=True)

x_min = st.sidebar.number_input("X min", value=0.0) if not auto_x else None
x_max = st.sidebar.number_input("X max", value=1000.0) if not auto_x else None
y1_min = st.sidebar.number_input("TG min", value=0.0) if not auto_y1 else None
y1_max = st.sidebar.number_input("TG max", value=100.0) if not auto_y1 else None
y2_min = st.sidebar.number_input("DSC min", value=-10.0) if not auto_y2 else None
y2_max = st.sidebar.number_input("DSC max", value=10.0) if not auto_y2 else None

# Sidebar: Tasks für manuelle Auswertung
st.sidebar.header("Manuelle Auswertung")
if 'tasks' not in st.session_state:
    st.session_state.tasks = []

# Hinzufügen eines Tasks
if st.sidebar.button("➕ Hinzufügen"):
    st.session_state.tasks.append({})

# Benutzerdefinierte Tasks
remove_idx = None
for i, task in enumerate(st.session_state.tasks):
    with st.sidebar.expander(f"Task {i+1}"):
        task_type = st.selectbox("Signaltyp", ["Onset DSC", "Peak DSC", "Onset TG", "Delta TG"], key=f"type_{i}")
        task.update({"type": task_type})

        # Temperaturbereiche je Task
        if task_type in ["Onset DSC", "Onset TG"]:
            t1_start = st.number_input("Tangente 1 Start (°C)", value=0.0, key=f"t1s_{i}")
            t1_end = st.number_input("Tangente 1 Ende (°C)", value=100.0, key=f"t1e_{i}")
            t2_start = st.number_input("Tangente 2 Start (°C)", value=100.0, key=f"t2s_{i}")
            t2_end = st.number_input("Tangente 2 Ende (°C)", value=200.0, key=f"t2e_{i}")
            task.update({"t1_start": t1_start, "t1_end": t1_end, "t2_start": t2_start, "t2_end": t2_end})
        else:
            start_temp = st.number_input("Start (°C)", value=0.0, key=f"s_{i}")
            end_temp = st.number_input("Ende (°C)", value=100.0, key=f"e_{i}")
            task.update({"start": start_temp, "end": end_temp})

        if st.button("❌ Entfernen", key=f"remove_{i}"):
            remove_idx = i

# Task entfernen nach der Schleife
if remove_idx is not None:
    st.session_state.tasks.pop(remove_idx)

# Funktionen für Onset-Berechnung mit zwei Tangenten
def calculate_onset_two_tangents(temp, y, t1_start, t1_end, t2_start, t2_end):
    mask1 = (temp >= t1_start) & (temp <= t1_end)
    mask2 = (temp >= t2_start) & (temp <= t2_end)
    x1, y1 = temp[mask1], y[mask1]
    x2, y2 = temp[mask2], y[mask2]
    slope1, intercept1 = np.polyfit(x1, y1, 1)
    slope2, intercept2 = np.polyfit(x2, y2, 1)
    onset_temp = (intercept2 - intercept1) / (slope1 - slope2)
    return onset_temp, (slope1, intercept1, slope2, intercept2)

# Plot und Berechnung
if uploaded_files:
    fig, ax1 = plt.subplots(figsize=(8,5))
    tg_lines, tg_labels = [], []
    dsc_lines, dsc_labels = [], []
    colors = plt.cm.tab10.colors
    ax2 = None
    results = []

    for i, uploaded_file in enumerate(uploaded_files):
        df = pd.read_csv(uploaded_file)

        legend_name = st.text_input(f"Legendenname für {uploaded_file.name}",
                                    value=uploaded_file.name, key=f"legend_{i}")

        # TG in %
        if weight_option == "%":
            start_weight = df["Unsubtracted Weight"].iloc[0]
            df["Weight_plot"] = df["Unsubtracted Weight"] / start_weight * 100
        else:
            df["Weight_plot"] = df["Unsubtracted Weight"]

        color = colors[i % len(colors)]

        # TG plot
        if show_tg:
            line, = ax1.plot(df["Program Temperature"], df["Weight_plot"], color=color, linestyle="-")
            tg_lines.append(line)
            tg_labels.append(f"TG - {legend_name}")

        # DSC plot
        if show_dsc:
            if ax2 is None:
                ax2 = ax1.twinx()
            line, = ax2.plot(df["Program Temperature"], df["Unsubtracted Heat Flow"], color=color, linestyle="--")
            dsc_lines.append(line)
            dsc_labels.append(f"DSC - {legend_name}")

        # Tasks auswerten
        for task in st.session_state.tasks:
            if task["type"] == "Onset DSC" and show_dsc:
                mask = (df["Program Temperature"] >= task["t1_start"]) & (df["Program Temperature"] <= task["t2_end"])
                temp = df.loc[mask, "Program Temperature"].values
                dsc = df.loc[mask, "Unsubtracted Heat Flow"].values
                onset_temp, fits = calculate_onset_two_tangents(temp, dsc,
                                                              task["t1_start"], task["t1_end"],
                                                              task["t2_start"], task["t2_end"])
                if not np.isnan(onset_temp):
                    onset_dsc = np.interp(onset_temp, temp, dsc)
                    ax2.plot(onset_temp, onset_dsc, 'go', label=f"Onset {legend_name}")
                    results.append({"Datei": legend_name, "Signal": "Onset DSC", "Temperatur [°C]": onset_temp})
                    if show_tangents:
                        m1, b1, m2, b2 = fits
                        x_fit = np.linspace(task["t1_start"], task["t2_end"], 200)
                        ax2.plot(x_fit, m1*x_fit+b1, '--', color='grey', linewidth=1)
                        ax2.plot(x_fit, m2*x_fit+b2, '--', color='grey', linewidth=1)

            elif task["type"] == "Peak DSC" and show_dsc:
                mask = (df["Program Temperature"] >= task["start"]) & (df["Program Temperature"] <= task["end"])
                temp = df.loc[mask, "Program Temperature"].values
                dsc = df.loc[mask, "Unsubtracted Heat Flow"].values
                if len(dsc) > 0:
                    peak_idx = np.argmax(dsc)
                    peak_temp = temp[peak_idx]
                    ax2.plot(peak_temp, dsc[peak_idx], 'ro', label=f"Peak {legend_name}")
                    results.append({"Datei": legend_name, "Signal": "Peak DSC", "Temperatur [°C]": peak_temp})

            elif task["type"] == "Onset TG" and show_tg:
                mask = (df["Program Temperature"] >= task["t1_start"]) & (df["Program Temperature"] <= task["t2_end"])
                temp = df.loc[mask, "Program Temperature"].values
                tg = df.loc[mask, "Weight_plot"].values
                onset_temp, fits = calculate_onset_two_tangents(temp, tg,
                                                              task["t1_start"], task["t1_end"],
                                                              task["t2_start"], task["t2_end"])
                if not np.isnan(onset_temp):
                    onset_tg = np.interp(onset_temp, temp, tg)
                    ax1.plot(onset_temp, onset_tg, 'go', label=f"Onset TG {legend_name}")
                    results.append({"Datei": legend_name, "Signal": "Onset TG", "Temperatur [°C]": onset_temp})
                    if show_tangents:
                        m1, b1, m2, b2 = fits
                        x_fit = np.linspace(task["t1_start"], task["t2_end"], 200)
                        ax1.plot(x_fit, m1*x_fit+b1, '--', color='grey', linewidth=1)
                        ax1.plot(x_fit, m2*x_fit+b2, '--', color='grey', linewidth=1)

            elif task["type"] == "Delta TG" and show_tg:
                mask = (df["Program Temperature"] >= task["start"]) & (df["Program Temperature"] <= task["end"])
                tg = df.loc[mask, "Weight_plot"].values
                if len(tg) > 1:
                    delta = tg[0] - tg[-1]
                    unit = "%" if weight_option == "%" else "mg"
                    results.append({"Datei": legend_name, "Signal": "ΔTG", f"ΔTG [{unit}]": delta})

    ax1.set_xlabel("Temperatur [°C]")
    if show_tg:
        ax1.set_ylabel("Gewicht" + (" [%]" if weight_option=="%" else " [mg]"))
    if show_dsc and ax2 is not None:
        ax2.set_ylabel("Heat Flow [mW], exo = down")
    ax1.grid(True, linestyle="--", alpha=0.5)

    if not auto_x and x_min is not None and x_max is not None:
        ax1.set_xlim(x_min, x_max)
    if show_tg and not auto_y1 and y1_min is not None and y1_max is not None:
        ax1.set_ylim(y1_min, y1_max)
    if show_dsc and ax2 is not None and not auto_y2 and y2_min is not None and y2_max is not None:
        ax2.set_ylim(y2_min, y2_max)

    # Legende unten
    all_lines = tg_lines + dsc_lines
    all_labels = tg_labels + dsc_labels
    if all_lines:
        ax1.legend(all_lines, all_labels, loc="upper center",
                   bbox_to_anchor=(0.5, -0.15), ncol=2, frameon=False)

    fig.tight_layout()
    st.pyplot(fig)

    # Ergebnisse als Tabelle
    if results:
        df_results = pd.DataFrame(results)
        st.subheader("Auswertung Tasks")
        st.table(df_results)

    # Download Plot
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=300, bbox_inches="tight")
    st.download_button("📥 Plot herunterladen", data=buf.getvalue(),
                       file_name="STA_plot.png", mime="image/png")
