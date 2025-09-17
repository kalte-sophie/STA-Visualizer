import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import io

st.title("STA Daten Visualisierung – mit Baseline-Korrektur")

# Checkboxen für Signale
show_tg = st.checkbox("TG anzeigen", value=True)
show_dsc = st.checkbox("DSC anzeigen", value=True)

# TG in mg oder %
weight_option = st.radio("TG anzeigen als:", ("mg", "%"))

# Dateien hochladen
uploaded_files = st.file_uploader("STA CSV Dateien hochladen", type=["csv"], accept_multiple_files=True)

# Sidebar: Achsenlimits
st.sidebar.header("Achsenlimits")

# X-Achse
auto_x = st.sidebar.checkbox("X-Achse Auto", value=True)
if not auto_x:
    x_min = st.sidebar.number_input("Temperatur min (°C)", value=0.0)
    x_max = st.sidebar.number_input("Temperatur max (°C)", value=1000.0)
else:
    x_min, x_max = None, None

# Y1 (TG)
if show_tg:
    auto_y1 = st.sidebar.checkbox("TG-Achse Auto", value=True)
    if not auto_y1:
        y1_min = st.sidebar.number_input("TG min", value=0.0)
        y1_max = st.sidebar.number_input("TG max", value=100.0)
    else:
        y1_min, y1_max = None, None
else:
    auto_y1, y1_min, y1_max = True, None, None

# Y2 (DSC)
if show_dsc:
    auto_y2 = st.sidebar.checkbox("DSC-Achse Auto", value=True)
    if not auto_y2:
        y2_min = st.sidebar.number_input("DSC min", value=-10.0)
        y2_max = st.sidebar.number_input("DSC max", value=10.0)
    else:
        y2_min, y2_max = None, None
else:
    auto_y2, y2_min, y2_max = True, None, None

if uploaded_files:
    fig, ax1 = plt.subplots(figsize=(8,5))

    tg_lines = []
    tg_labels = []
    dsc_lines = []
    dsc_labels = []

    colors = plt.cm.tab10.colors
    ax2 = None  # nur erzeugen, wenn nötig

    for i, uploaded_file in enumerate(uploaded_files):
        df = pd.read_csv(uploaded_file)

        # Optional: Baseline-Datei hochladen
        baseline_file = st.file_uploader(f"Baseline für {uploaded_file.name} hochladen (optional)", type=["csv"], key=f"baseline_{i}")
        if baseline_file is not None:
            df_baseline = pd.read_csv(baseline_file)
            df["Unsubtracted Weight"] = df["Unsubtracted Weight"] - df_baseline["Unsubtracted Weight"]
            df["Unsubtracted Heat Flow"] = df["Unsubtracted Heat Flow"] - df_baseline["Unsubtracted Heat Flow"]
            st.info(f"Basislinie für {uploaded_file.name} angewendet")

        # Legendenname
        legend_name = st.text_input(f"Legendenname für {uploaded_file.name}", value=uploaded_file.name, key=f"legend_{i}")

        # TG in %
        if weight_option == "%":
            start_weight = df["Unsubtracted Weight"].iloc[0]
            df["Weight_plot"] = df["Unsubtracted Weight"] / start_weight * 100
        else:
            df["Weight_plot"] = df["Unsubtracted Weight"]

        color = colors[i % len(colors)]

        # Plotten
        if show_tg:
            line, = ax1.plot(df["Program Temperature"], df["Weight_plot"], color=color, linestyle="-")
            tg_lines.append(line)
            tg_labels.append(f"TG - {legend_name}")

        if show_dsc:
            if ax2 is None:  # rechte Achse nur einmal erzeugen
                ax2 = ax1.twinx()
            line, = ax2.plot(df["Program Temperature"], df["Unsubtracted Heat Flow"], color=color, linestyle="--")
            dsc_lines.append(line)
            dsc_labels.append(f"DSC - {legend_name}")

    ax1.set_xlabel("Temperatur [°C]")
    if show_tg:
        ax1.set_ylabel("Gewicht" + (" [%]" if weight_option=="%" else " [mg]"))
    if show_dsc and ax2 is not None:
        ax2.set_ylabel("Heat Flow [mW], exo = down")

    ax1.grid(True, linestyle="--", alpha=0.5)

    # Achsenlimits setzen
    if not auto_x:
        ax1.set_xlim(x_min, x_max)
    if show_tg and not auto_y1:
        ax1.set_ylim(y1_min, y1_max)
    if show_dsc and ax2 is not None and not auto_y2:
        ax2.set_ylim(y2_min, y2_max)

    # Legende unten in 2 Spalten: TG links, DSC rechts
    all_lines = tg_lines + dsc_lines
    all_labels = tg_labels + dsc_labels
    ncol = 2
    if all_lines:  # Legende nur, wenn es auch Kurven gibt
        ax1.legend(all_lines, all_labels, loc="upper center",
                   bbox_to_anchor=(0.5, -0.15), ncol=ncol, frameon=False)

    fig.tight_layout()
    st.pyplot(fig)

    # Download
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=300, bbox_inches="tight")
    st.download_button("📥 Plot herunterladen", data=buf.getvalue(),
                       file_name="STA_plot.png", mime="image/png")
