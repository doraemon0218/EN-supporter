import hashlib
from datetime import date, datetime

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

PATIENT_FILE = "patients.csv"
FORMULA_SETTING_FILE = "facility_formula_settings.csv"
INFUSION_RECORD_FILE = "infusion_records.csv"

# 時系列グラフ: 成分ごとの固定色（実測＝濃色、Day7目標＝同系の淡色）
TS_SERIES_COLOR_DOMAIN: list[str] = [
    "エネルギー(kcal/day)",
    "たんぱく質(g/day)",
    "糖質(g/day)",
    "Day7目標エネルギー(kcal/day)",
    "Day7目標たんぱく質(g/day)",
    "Day7目標糖質(g/day)",
]
TS_SERIES_COLOR_RANGE: list[str] = [
    "#dc2626",  # エネルギー 実測（赤）
    "#2563eb",  # たんぱく質 実測（青）
    "#15803d",  # 糖質 実測（緑）
    "#fca5a5",  # Day7 エネルギー（薄赤）
    "#93c5fd",  # Day7 たんぱく質（薄青）
    "#86efac",  # Day7 糖質（薄緑）
]

# 経腸栄養製剤のスナップショットと投与実績を保存する列（マスタにない製剤を手入力する場合も notes で補足可能）
INFUSION_RECORD_COLUMNS: list[str] = [
    "patient_id",
    "record_date",
    "icu_day",
    "formula_name",
    "vendor",
    "kcal_per_ml",
    "protein_g_per_100ml",
    "fiber_g_per_100ml",
    "osmolality_mOsmL",
    "rate_ml_h",
    "hours_per_day",
    "volume_ml_day",
    "kcal_day",
    "protein_g_day",
    "carbohydrate_g_day",
    "fiber_g_day",
    "lipid_g_day",
    "day7_target_kcal",
    "day7_target_protein_g",
    "day7_target_carbohydrate_g",
    "route",
    "notes",
]


def normalize_infusion_records(df: pd.DataFrame) -> pd.DataFrame:
    """既存CSVに列を追加し、保存時の列順を固定する。"""
    out = df.copy()
    for col in INFUSION_RECORD_COLUMNS:
        if col not in out.columns:
            out[col] = np.nan
    for col in ("route", "notes"):
        if col in out.columns:
            out[col] = out[col].apply(lambda x: "" if pd.isna(x) else str(x))
    return out[INFUSION_RECORD_COLUMNS]


def load_formulas() -> pd.DataFrame:
    """data_formulas.csv を毎回読み込む（マスタ更新を即時反映するためキャッシュしない）。"""
    df = pd.read_csv("data_formulas.csv")
    numeric_cols = ["kcal_per_ml", "protein_g_per_100ml", "fiber_g_per_100ml", "osmolality_mOsmL"]
    for c in numeric_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def load_patients() -> pd.DataFrame:
    try:
        df = pd.read_csv(PATIENT_FILE)
    except FileNotFoundError:
        return pd.DataFrame(columns=["patient_id", "icu_admission_date", "today", "height_cm", "weight_kg", "created_at"])
    return df


def save_patients(df: pd.DataFrame) -> None:
    df.to_csv(PATIENT_FILE, index=False)


def load_formula_settings(formulas: pd.DataFrame) -> pd.DataFrame:
    base = formulas[["name", "vendor"]].drop_duplicates().copy()
    base["enabled"] = True
    try:
        saved = pd.read_csv(FORMULA_SETTING_FILE)
    except FileNotFoundError:
        return base

    if not {"name", "enabled"}.issubset(saved.columns):
        return base

    merged = base.merge(saved[["name", "enabled"]], on="name", how="left", suffixes=("", "_saved"))
    merged["enabled"] = merged["enabled_saved"].apply(
        lambda v: str(v).strip().lower() in {"1", "true", "yes", "y"} if pd.notna(v) else True
    )
    return merged[["name", "vendor", "enabled"]]


def save_formula_settings(settings_df: pd.DataFrame) -> None:
    settings_df[["name", "enabled"]].to_csv(FORMULA_SETTING_FILE, index=False)


def apply_formula_settings(formulas: pd.DataFrame, settings_df: pd.DataFrame) -> pd.DataFrame:
    enabled_names = settings_df.loc[settings_df["enabled"], "name"].tolist()
    return formulas[formulas["name"].isin(enabled_names)].copy()


def _formula_checkbox_key(name: str) -> str:
    return "fc_" + hashlib.sha256(str(name).encode("utf-8")).hexdigest()


def _coerce_setting_enabled(val: object) -> bool:
    if isinstance(val, (bool, np.bool_)):
        return bool(val)
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return True
    s = str(val).strip().lower()
    return s in {"1", "true", "yes", "y"}


def init_formula_checkbox_session(formulas_df: pd.DataFrame, settings_df: pd.DataFrame) -> None:
    """採用製剤チェックのセッション初期値を、マスタと保存済み設定から補完する。"""
    en_map = {str(r["name"]): _coerce_setting_enabled(r["enabled"]) for _, r in settings_df.iterrows()}
    for nm in formulas_df["name"].astype(str).tolist():
        k = _formula_checkbox_key(nm)
        if k not in st.session_state:
            st.session_state[k] = bool(en_map.get(nm, True))


def collect_formula_settings_from_session(formulas_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for nm in formulas_df["name"].astype(str).tolist():
        k = _formula_checkbox_key(nm)
        rows.append({"name": nm, "enabled": bool(st.session_state.get(k, True))})
    return pd.DataFrame(rows)


def load_infusion_records() -> pd.DataFrame:
    try:
        df = pd.read_csv(INFUSION_RECORD_FILE)
    except FileNotFoundError:
        return pd.DataFrame(columns=INFUSION_RECORD_COLUMNS)
    return normalize_infusion_records(df)


def save_infusion_records(df: pd.DataFrame) -> None:
    normalize_infusion_records(df).to_csv(INFUSION_RECORD_FILE, index=False)


def upsert_infusion_record(record: dict[str, object]) -> None:
    records = load_infusion_records()
    if records.empty:
        updated = normalize_infusion_records(pd.DataFrame([record]))
    else:
        is_same = (records["patient_id"].astype(str) == str(record["patient_id"])) & (
            records["record_date"].astype(str) == str(record["record_date"])
        )
        records = records.loc[~is_same].copy()
        updated = pd.concat([records, pd.DataFrame([record])], ignore_index=True)
        updated = normalize_infusion_records(updated)
    save_infusion_records(updated)


def calc_requirements(weight_kg: float, kcal_per_kg: float, protein_g_per_kg: float) -> tuple[float, float]:
    return weight_kg * kcal_per_kg, weight_kg * protein_g_per_kg


def get_carbohydrate_per_100ml(formula_row: pd.Series) -> tuple[float, bool]:
    # 明示列があればそれを採用。なければエネルギーとたんぱく質から糖質を推定。
    if "carbohydrate_g_per_100ml" in formula_row.index and pd.notna(formula_row["carbohydrate_g_per_100ml"]):
        return float(formula_row["carbohydrate_g_per_100ml"]), False

    kcal_per_100ml = float(formula_row["kcal_per_ml"]) * 100
    protein_g_per_100ml = float(formula_row["protein_g_per_100ml"])
    estimated_carbohydrate = max((kcal_per_100ml - protein_g_per_100ml * 4) / 4, 0.0)
    return estimated_carbohydrate, True


def _sync_section4_from_planned_infusion(patient_id: str, planned_rate: float, planned_hours: float) -> tuple[str, str]:
    """2.の注入予定が変わったときだけ 4. の投与速度・時間を同じ値へ更新（4.で上書きした値は、2.を変更するまで保持）。"""
    kr = f"en_prev_planned_rate_{patient_id}"
    kh = f"en_prev_planned_hours_{patient_id}"
    ar = f"en_actual_rate_{patient_id}"
    ah = f"en_actual_hours_{patient_id}"
    pr, ph = float(planned_rate), float(planned_hours)
    if kr not in st.session_state:
        st.session_state[kr] = pr
        st.session_state[kh] = ph
        st.session_state[ar] = pr
        st.session_state[ah] = ph
    else:
        prev_r = float(st.session_state[kr])
        prev_h = float(st.session_state[kh])
        if abs(prev_r - pr) > 1e-9 or abs(prev_h - ph) > 1e-9:
            st.session_state[ar] = pr
            st.session_state[ah] = ph
            st.session_state[kr] = pr
            st.session_state[kh] = ph
    return ar, ah


def render_strategy_page(patient_row: pd.Series, formulas: pd.DataFrame) -> None:
    patient_id = str(patient_row["patient_id"])
    icu_admission_date = pd.to_datetime(patient_row["icu_admission_date"]).date()
    default_today = pd.to_datetime(patient_row["today"]).date()
    default_height = float(patient_row["height_cm"])
    default_weight = float(patient_row["weight_kg"])

    st.subheader(f"戦略立案: {patient_id}")

    with st.sidebar:
        st.header("患者情報（登録データ）")
        st.write(f"患者ID: **{patient_id}**")
        st.write(f"入室日: **{icu_admission_date}**")
        st.write(f"登録時体重: **{default_weight:.1f} kg**")
        st.write(f"登録時身長: **{default_height:.1f} cm**")

        st.markdown("---")
        st.header("本日の評価入力")
        today = st.date_input("本日の日付", value=default_today)
        ward_type = st.selectbox("病棟種別", ["ICU", "HCU", "一般病棟"])
        weight = st.number_input("体重 (kg)", min_value=20.0, max_value=200.0, value=default_weight, step=0.5)
        height = st.number_input("身長 (cm)", min_value=100.0, max_value=220.0, value=default_height, step=0.5)

        icu_stay_days = max(1, (today - icu_admission_date).days + 1)
        st.caption(f"{ward_type}在室日数（入室日をDay1）: Day{icu_stay_days}")

        bmi = weight / ((height / 100) ** 2)
        st.caption(f"BMI: {bmi:.1f}")

        st.markdown("---")
        st.header("栄養必要量（目標）")
        kcal_per_kg = st.number_input("エネルギー必要量 (kcal/kg/day)", min_value=15.0, max_value=40.0, value=25.0, step=0.5)
        protein_per_kg = st.number_input("たんぱく必要量 (g/kg/day)", min_value=0.5, max_value=3.0, value=1.2, step=0.1)
        target_kcal, target_protein = calc_requirements(weight, kcal_per_kg, protein_per_kg)
        target_carbohydrate = max((target_kcal - target_protein * 4) / 4, 0.0)
        st.caption(f"目標エネルギー: {target_kcal:.0f} kcal/day, 目標たんぱく: {target_protein:.1f} g/day")

    tab_plan, tab_assess, tab_formulas = st.tabs(["投与計画", "現状アセスメント", "製剤リスト編集"])

    with tab_plan:
        st.subheader("1. 製剤候補と目標量の計算")
        guideline_target_df = pd.DataFrame(
            {
                "項目": ["カロリー", "たんぱく質", "糖質"],
                "目標量（ガイドライン参考）": [
                    f"{target_kcal:.0f} kcal/day",
                    f"{target_protein:.1f} g/day",
                    f"{target_carbohydrate:.1f} g/day",
                ],
            }
        )
        st.table(guideline_target_df)

        filtered = formulas.copy()

        if filtered.empty:
            st.warning("採用製剤の設定で選択された製剤がありません。採用製剤の設定を確認してください。")
        else:
            filtered["必要量_mL_per_day"] = np.where(filtered["kcal_per_ml"] > 0, target_kcal / filtered["kcal_per_ml"], np.nan)
            filtered["たんぱく量_g_per_day_理論値"] = filtered["必要量_mL_per_day"] / 100 * filtered["protein_g_per_100ml"]
            filtered["kcal_per_100ml"] = filtered["kcal_per_ml"] * 100

            show_cols = [
                "name",
                "kcal_per_100ml",
                "protein_g_per_100ml",
                "osmolality_mOsmL",
            ]
            st.dataframe(
                filtered[show_cols].style.format(
                    {
                        "kcal_per_100ml": "{:.0f}",
                        "protein_g_per_100ml": "{:.1f}",
                        "osmolality_mOsmL": "{:.0f}",
                    }
                ),
                column_config={
                    "name": "商品名",
                    "kcal_per_100ml": "100mLあたりカロリー (kcal)",
                    "protein_g_per_100ml": "100mLあたりたんぱく質 (g)",
                    "osmolality_mOsmL": "浸透圧 (mOsm/L)",
                },
                use_container_width=True,
            )

            selected_name = st.selectbox("使用予定の製剤を選択", options=filtered["name"].tolist())
            selected_row = filtered[filtered["name"] == selected_name].iloc[0]

            st.markdown("---")
            st.subheader("2. 現在の投与量")
            st.caption(f"現在の入室日数（入室日を Day1 とする）: **Day{icu_stay_days}**")
            col_plan_rate, col_plan_hours = st.columns(2)
            with col_plan_rate:
                planned_rate = st.number_input("注入予定速度 (mL/h)", min_value=0.0, value=50.0, step=5.0)
            with col_plan_hours:
                planned_hours = st.number_input("注入予定時間 (h/day)", min_value=0.0, max_value=24.0, value=24.0, step=1.0)

            planned_volume = planned_rate * planned_hours
            planned_kcal = planned_volume * selected_row["kcal_per_ml"]
            planned_protein = planned_volume / 100 * selected_row["protein_g_per_100ml"]
            carbohydrate_per_100ml, is_estimated_carb = get_carbohydrate_per_100ml(selected_row)
            planned_carbohydrate = planned_volume / 100 * carbohydrate_per_100ml

            day7_target_ratio = st.number_input(
                "Day7時点の投与目標（ガイドライン必要量に対する達成率・%）",
                min_value=0.0,
                max_value=150.0,
                value=100.0,
                step=5.0,
                help="「栄養必要量（目標）」で算定したエネルギー・たんぱく必要量（ガイドライン上の理想）に対し、"
                "Day7 終了時点で投与でその何％ぶんを満たしたいかを指定します。",
            )
            day7_target_kcal = target_kcal * day7_target_ratio / 100 if target_kcal > 0 else 0.0
            day7_volume_target = day7_target_kcal / selected_row["kcal_per_ml"] if selected_row["kcal_per_ml"] > 0 else 0.0
            day7_protein_target = day7_volume_target / 100 * selected_row["protein_g_per_100ml"]
            day7_carb_target = day7_volume_target / 100 * carbohydrate_per_100ml
            st.caption(
                f"Day7 の目標エネルギー: **{day7_target_kcal:.0f} kcal/day**（ガイドライン必要量の {day7_target_ratio:.0f}% に相当）"
            )

            result_df = pd.DataFrame(
                {
                    "項目": ["投与量", "エネルギー", "たんぱく質", "糖質"],
                    "現在の投与予定": [
                        f"{planned_volume:.0f} mL/day",
                        f"{planned_kcal:.0f} kcal/day",
                        f"{planned_protein:.1f} g/day",
                        f"{planned_carbohydrate:.1f} g/day",
                    ],
                    "Day7時点の目標": [
                        f"{day7_volume_target:.0f} mL/day",
                        f"{day7_target_kcal:.0f} kcal/day",
                        f"{day7_protein_target:.1f} g/day",
                        f"{day7_carb_target:.1f} g/day",
                    ],
                }
            )
            st.table(result_df)
            if is_estimated_carb:
                st.caption("※ 糖質量は製剤データに糖質列がないため、エネルギーとたんぱく質量からの推定値です（Day7 目標の糖質も同様）。")

            st.markdown("---")
            st.subheader("3. 注入スケジュール（Day1〜Day7）")
            st.caption(
                "各 Day の「必要量達成率」は、いずれも **ガイドライン上の必要量（エネルギー目標）に対する達成率（%）** です。"
                "Day1 は現在の注入予定量から、Day7 は上で設定した目標率まで線形補間します。"
            )
            start_ratio = (planned_kcal / target_kcal * 100) if target_kcal > 0 else 0.0
            start_ratio = max(0.0, min(150.0, start_ratio))
            st.caption(f"Day1 開始時点の達成率（注入予定から自動）: **{start_ratio:.0f}%**（ガイドライン必要量に対する割合）")
            day_labels = [f"Day{i}" for i in range(1, 8)]
            day_ratios = [float(start_ratio)] * 7 if day7_target_ratio == start_ratio else np.linspace(start_ratio, day7_target_ratio, num=7).tolist()
            hours_per_day = st.number_input("1日の注入時間 (h)", min_value=4, max_value=24, value=24, step=1)

            def plan_for_ratio(ratio: float) -> dict[str, float]:
                kcal = target_kcal * ratio / 100
                volume = kcal / selected_row["kcal_per_ml"]
                rate = volume / hours_per_day
                protein = volume / 100 * selected_row["protein_g_per_100ml"]
                return {"kcal": kcal, "volume": volume, "rate": rate, "protein": protein}

            plans = [plan_for_ratio(r) for r in day_ratios]
            plan_df = pd.DataFrame(
                {
                    "Day": day_labels,
                    "必要量達成率_%（ガイドライン比）": day_ratios,
                    "予定エネルギー_kcal": [p["kcal"] for p in plans],
                    "予定総量_mL": [p["volume"] for p in plans],
                    "予定速度_mL_per_h": [p["rate"] for p in plans],
                    "予定たんぱく量_g": [p["protein"] for p in plans],
                }
            )

            current_day_for_table = min(7, max(1, icu_stay_days))

            def highlight_current_day(row: pd.Series) -> list[str]:
                if row["Day"] == f"Day{current_day_for_table}":
                    return ["background-color: #FFF3CD"] * len(row)
                return [""] * len(row)

            st.dataframe(
                plan_df.style.format(
                    {
                        "必要量達成率_%（ガイドライン比）": "{:.0f}",
                        "予定エネルギー_kcal": "{:.0f}",
                        "予定総量_mL": "{:.0f}",
                        "予定速度_mL_per_h": "{:.0f}",
                        "予定たんぱく量_g": "{:.1f}",
                    }
                ).apply(highlight_current_day, axis=1),
                use_container_width=True,
            )

            st.markdown("---")
            st.subheader("4. 本日の投与予定量")
            st.caption(
                "「2. 現在の投与量」の**注入予定速度・注入予定時間**を初期値として反映します。"
                "2. を変更するとここへ自動で上書きされるので、本日だけ異なる値にしたい場合はこの欄で調整してください。"
            )
            ar_key, ah_key = _sync_section4_from_planned_infusion(patient_id, planned_rate, planned_hours)
            col_cd1, col_cd2 = st.columns(2)
            with col_cd1:
                current_day = min(7, max(1, icu_stay_days))
                st.write(f"現在の Day: **Day{current_day}**")
                actual_rate = st.number_input(
                    "現在の投与速度 (mL/h)",
                    min_value=0.0,
                    value=float(st.session_state[ar_key]),
                    key=ar_key,
                    step=5.0,
                    help="初期値は 2. の注入予定速度。2. を変更すると自動反映されます。",
                )
                actual_hours = st.number_input(
                    "本日の実際の投与時間 (h/day)",
                    min_value=0.0,
                    max_value=24.0,
                    value=float(st.session_state[ah_key]),
                    key=ah_key,
                    step=1.0,
                    help="初期値は 2. の注入予定時間。3. のスケジュール用「1日の注入時間」とは別です。",
                )
            with col_cd2:
                st.markdown("**禁忌・注意状態チェック（目安）**")
                contraindication_options = [
                    "腸管虚血が疑われる",
                    "腸閉塞 / 穿孔が疑われる",
                    "制御困難なショック",
                    "大量の上部消化管出血",
                    "高用量血管作動薬の持続投与中",
                ]
                contraindications = [
                    opt
                    for idx, opt in enumerate(contraindication_options)
                    if st.checkbox(opt, key=f"contra_{patient_id}_{idx}")
                ]

            actual_volume_today = actual_rate * actual_hours
            actual_kcal_today = actual_volume_today * selected_row["kcal_per_ml"]
            carb_per_100ml_actual, _ = get_carbohydrate_per_100ml(selected_row)
            actual_carb_today = actual_volume_today / 100 * carb_per_100ml_actual
            proto_ratio_today = day_ratios[current_day - 1]
            proto_kcal_today = plans[current_day - 1]["kcal"]
            actual_ratio_today = (actual_kcal_today / target_kcal * 100) if target_kcal > 0 else 0.0
            gap_ratio = actual_ratio_today - proto_ratio_today
            gap_kcal = actual_kcal_today - proto_kcal_today

            detail_df = pd.DataFrame(
                {
                    "項目": ["製剤名", "投与速度 (mL/h)", "投与時間 (h/day)", "投与量 (mL/day)", "エネルギー (kcal/day)", "たんぱく質 (g/day)"],
                    "値": [
                        selected_row["name"],
                        f"{actual_rate:.0f}",
                        f"{actual_hours:.1f}",
                        f"{actual_volume_today:.0f}",
                        f"{actual_kcal_today:.0f}",
                        f"{actual_volume_today / 100 * selected_row['protein_g_per_100ml']:.1f}",
                    ],
                }
            )
            st.table(detail_df)
            col_gap1, col_gap2 = st.columns(2)
            with col_gap1:
                st.metric("実投与率 vs 目標（差）", f"{gap_ratio:+.1f} %pt")
            with col_gap2:
                st.metric("実エネルギー vs 目標（差）", f"{gap_kcal:+.0f} kcal/day")

            st.markdown("**現在値と目標値の見える化**")
            compare_df = pd.DataFrame(
                {
                    "項目": ["投与量 (mL/day)", "エネルギー (kcal/day)", "たんぱく質 (g/day)", "糖質 (g/day)", "達成率 (%)"],
                    f"Day{current_day}": [
                        actual_volume_today,
                        actual_kcal_today,
                        actual_volume_today / 100 * selected_row["protein_g_per_100ml"],
                        actual_carb_today,
                        actual_ratio_today,
                    ],
                    f"Day{current_day}理想目標": [
                        plans[current_day - 1]["volume"],
                        proto_kcal_today,
                        plans[current_day - 1]["protein"],
                        plans[current_day - 1]["volume"] / 100 * carb_per_100ml_actual,
                        proto_ratio_today,
                    ],
                    "Day7目標": [
                        day7_volume_target,
                        day7_target_kcal,
                        day7_protein_target,
                        day7_carb_target,
                        day7_target_ratio,
                    ],
                    "差分(現在-同Day理想)": [
                        actual_volume_today - plans[current_day - 1]["volume"],
                        actual_kcal_today - proto_kcal_today,
                        (actual_volume_today / 100 * selected_row["protein_g_per_100ml"]) - plans[current_day - 1]["protein"],
                        actual_carb_today - (plans[current_day - 1]["volume"] / 100 * carb_per_100ml_actual),
                        gap_ratio,
                    ],
                }
            )
            st.dataframe(
                compare_df.style.format(
                    {
                        f"Day{current_day}": "{:.1f}",
                        f"Day{current_day}理想目標": "{:.1f}",
                        "Day7目標": "{:.1f}",
                        "差分(現在-同Day理想)": "{:+.1f}",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )

            st.markdown("**時系列の見える化（患者の連日投与記録）**")
            all_records = load_infusion_records()
            patient_records = all_records[all_records["patient_id"].astype(str) == patient_id].copy()
            if not patient_records.empty:
                patient_records["icu_day"] = pd.to_numeric(patient_records["icu_day"], errors="coerce")
                patient_records["kcal_day"] = pd.to_numeric(patient_records["kcal_day"], errors="coerce")
                patient_records["protein_g_day"] = pd.to_numeric(patient_records["protein_g_day"], errors="coerce")
                patient_records["carbohydrate_g_day"] = pd.to_numeric(patient_records["carbohydrate_g_day"], errors="coerce")
                patient_records["day7_target_kcal"] = pd.to_numeric(patient_records["day7_target_kcal"], errors="coerce")
                patient_records = patient_records.dropna(subset=["icu_day"]).copy()
                patient_records["icu_day"] = patient_records["icu_day"].astype(int)
                patient_records = patient_records.sort_values(["icu_day", "record_date"]).drop_duplicates(
                    subset=["icu_day"], keep="last"
                )

                max_day = max(7, int(patient_records["icu_day"].max()))
                day_index = list(range(1, max_day + 1))
                time_series_df = (
                    patient_records.set_index("icu_day")[["kcal_day", "protein_g_day", "carbohydrate_g_day"]]
                    .reindex(day_index)
                    .copy()
                )

                # Day7目標は横軸 Day7 の点のみ表示
                time_series_df["Day7目標エネルギー(kcal/day)"] = np.nan
                time_series_df["Day7目標たんぱく質(g/day)"] = np.nan
                time_series_df["Day7目標糖質(g/day)"] = np.nan
                time_series_df.loc[7, "Day7目標エネルギー(kcal/day)"] = float(day7_target_kcal)
                time_series_df.loc[7, "Day7目標たんぱく質(g/day)"] = float(day7_protein_target)
                time_series_df.loc[7, "Day7目標糖質(g/day)"] = float(day7_carb_target)

                time_series_df = time_series_df.rename(
                    columns={
                        "kcal_day": "エネルギー(kcal/day)",
                        "protein_g_day": "たんぱく質(g/day)",
                        "carbohydrate_g_day": "糖質(g/day)",
                    }
                )
                time_series_df.index = [f"Day{d}" for d in time_series_df.index]
                chart_df = time_series_df.reset_index().rename(columns={"index": "Day"})
                long_df = chart_df.melt(id_vars="Day", var_name="系列", value_name="値").dropna(subset=["値"])

                ts_color = alt.Color(
                    "系列:N",
                    title="成分",
                    scale=alt.Scale(domain=TS_SERIES_COLOR_DOMAIN, range=TS_SERIES_COLOR_RANGE),
                    legend=alt.Legend(orient="top", titleFontSize=12, labelFontSize=11),
                )

                line = (
                    alt.Chart(long_df)
                    .mark_line(point=True, strokeWidth=2)
                    .encode(
                        x=alt.X("Day:N", title="Day", sort=None),
                        y=alt.Y("値:Q", title="値"),
                        color=ts_color,
                    )
                )
                labels = (
                    alt.Chart(long_df)
                    .mark_text(dy=-10, fontSize=11)
                    .encode(
                        x=alt.X("Day:N", sort=None),
                        y=alt.Y("値:Q"),
                        text=alt.Text("値:Q", format=".1f"),
                        color=alt.Color(
                            "系列:N",
                            scale=alt.Scale(domain=TS_SERIES_COLOR_DOMAIN, range=TS_SERIES_COLOR_RANGE),
                            legend=None,
                        ),
                    )
                )
                st.altair_chart((line + labels).interactive(), use_container_width=True)
                st.caption(
                    "色の対応: **赤系＝エネルギー** / **青系＝たんぱく質** / **緑系＝糖質**（濃＝実測、淡＝Day7目標）。"
                    " 下表でも同じ列順で確認できます。"
                )
                st.caption("グラフ値（カーソル不要で確認可能）")
                _col_order = [c for c in TS_SERIES_COLOR_DOMAIN if c in time_series_df.columns]
                _rest = [c for c in time_series_df.columns if c not in _col_order]
                _display_ts = time_series_df[_col_order + _rest]
                st.dataframe(
                    _display_ts.style.format("{:.1f}"),
                    use_container_width=True,
                )
            else:
                st.info("この患者の投与記録はまだありません。下のボタンで本日の計画を記録できます。")

            hist_all = load_infusion_records()
            hist_pat = hist_all[hist_all["patient_id"].astype(str) == str(patient_id)]
            if not hist_pat.empty:
                with st.expander("この患者の保存済み投与記録（製剤スナップショット含む）"):
                    st.dataframe(hist_pat, use_container_width=True)

            st.markdown("**投与記録に付与する情報（任意）**")
            st.caption("マスタにない製剤や併用などは備考に記載できます。保存時に製剤組成のスナップショットも記録されます。")
            col_rw, col_rn = st.columns(2)
            with col_rw:
                route_options = ["未入力", "経鼻胃管", "経口胃管", "経鼻空腸", "経口空腸", "経口", "その他"]
                route_sel = st.selectbox("投与経路", route_options, key=f"route_rec_{patient_id}")
            with col_rn:
                notes_rec = st.text_area(
                    "備考（希釈・併用・マスタ外製剤名・ロット等）",
                    value="",
                    key=f"notes_rec_{patient_id}",
                    height=72,
                )

            if st.button("この計画で投与を実施する", use_container_width=True):
                fiber_per_100ml = float(selected_row["fiber_g_per_100ml"]) if pd.notna(selected_row.get("fiber_g_per_100ml")) else 0.0
                fiber_g_day = actual_volume_today / 100.0 * fiber_per_100ml
                protein_g_day_val = actual_volume_today / 100.0 * float(selected_row["protein_g_per_100ml"])
                lipid_g_day = max(
                    0.0,
                    (float(actual_kcal_today) - protein_g_day_val * 4.0 - float(actual_carb_today) * 4.0) / 9.0,
                )
                osmolality_val = selected_row.get("osmolality_mOsmL")
                osmolality_val = float(osmolality_val) if osmolality_val is not None and pd.notna(osmolality_val) else np.nan
                route_saved = "" if route_sel == "未入力" else route_sel
                record = {
                    "patient_id": patient_id,
                    "record_date": today.isoformat(),
                    "icu_day": current_day,
                    "formula_name": selected_row["name"],
                    "vendor": selected_row["vendor"],
                    "kcal_per_ml": float(selected_row["kcal_per_ml"]),
                    "protein_g_per_100ml": float(selected_row["protein_g_per_100ml"]),
                    "fiber_g_per_100ml": fiber_per_100ml,
                    "osmolality_mOsmL": osmolality_val,
                    "rate_ml_h": actual_rate,
                    "hours_per_day": actual_hours,
                    "volume_ml_day": actual_volume_today,
                    "kcal_day": actual_kcal_today,
                    "protein_g_day": protein_g_day_val,
                    "carbohydrate_g_day": actual_carb_today,
                    "fiber_g_day": fiber_g_day,
                    "lipid_g_day": lipid_g_day,
                    "day7_target_kcal": day7_target_kcal,
                    "day7_target_protein_g": float(day7_protein_target),
                    "day7_target_carbohydrate_g": float(day7_carb_target),
                    "route": route_saved,
                    "notes": notes_rec.strip(),
                }
                upsert_infusion_record(record)
                st.success(f"Day{current_day} の投与記録を保存しました。")

            suggestions: list[str] = []
            if contraindications:
                suggestions.append("禁忌・注意状態が選択されています。全身管理を優先し、増量は慎重に検討してください。")
            elif actual_kcal_today >= day7_target_kcal and day7_target_kcal > 0:
                suggestions.append(
                    f"本日の実投与エネルギーは {actual_kcal_today:.0f} kcal/day で、"
                    f"Day7目標 {day7_target_kcal:.0f} kcal/day をすでに達成しています。"
                )
                suggestions.append("目標達成後は過不足が出ないよう、維持量の微調整を検討してください。")
            elif current_day < 7:
                proto_ratio_tomorrow = day_ratios[current_day]
                ideal_today_kcal = proto_kcal_today
                ideal_gap_kcal = actual_kcal_today - ideal_today_kcal
                rec_ratio_tomorrow = proto_ratio_tomorrow
                if ideal_gap_kcal < 0:
                    suggestions.append(
                        f"現時点では同Day理想目標より {abs(ideal_gap_kcal):.0f} kcal/day 不足しています。"
                        f"翌日はガイドライン必要量に対する達成率 **{proto_ratio_tomorrow:.0f}%** を目安に増量を検討してください。"
                    )
                elif ideal_gap_kcal > 0:
                    suggestions.append(
                        f"現時点では同Day理想目標より {ideal_gap_kcal:.0f} kcal/day 上回っています。"
                        f"翌日はガイドライン必要量に対する達成率 **{proto_ratio_tomorrow:.0f}%** を目安に過量投与へ注意してください。"
                    )
                else:
                    suggestions.append("現時点で同Day理想目標と一致しています。翌日も同プロトコルで継続可能です。")
                rec_plan_tomorrow = plan_for_ratio(rec_ratio_tomorrow)
                st.write(
                    f"- 翌日の推奨エネルギー: 約 {rec_plan_tomorrow['kcal']:.0f} kcal/day"
                    f"（ガイドライン必要量に対する達成率 {rec_ratio_tomorrow:.0f}% 相当）"
                )
                st.write(f"- 翌日の推奨総量・速度: 約 {rec_plan_tomorrow['volume']:.0f} mL/day, {rec_plan_tomorrow['rate']:.0f} mL/h")
            else:
                if day7_target_kcal > 0 and actual_kcal_today < day7_target_kcal:
                    deficit = day7_target_kcal - actual_kcal_today
                    suggestions.append(
                        f"現在 Day7 で目標に対して {deficit:.0f} kcal/day 未達です。"
                        "耐容性を確認しつつ、追加投与または翌日以降の補正を検討してください。"
                    )
                else:
                    suggestions.append("現在 Day7。目標達成状況を確認し、維持期の微調整を検討してください。")

            for s in suggestions:
                st.markdown(f"- {s}")

            csv = plan_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                label="この投与計画をCSVとしてダウンロード",
                data=csv,
                file_name=f"EN_plan_{patient_id}_{today}.csv",
                mime="text/csv",
            )

    with tab_assess:
        st.subheader("1. 昨日の実投与量")
        col_a, col_b = st.columns(2)
        with col_a:
            planned_volume = st.number_input("予定総量 (mL/day)", min_value=0.0, value=1500.0, step=50.0)
            actual_volume = st.number_input("実投与量 (mL/day)", min_value=0.0, value=1200.0, step=50.0)
        with col_b:
            _interrupt_hours = st.number_input("中断時間の合計 (h/day)", min_value=0.0, value=2.0, step=0.5)
            gastric_residual = st.number_input("最大胃残量 (mL)（任意）", min_value=0.0, value=0.0, step=10.0)

        achieved_ratio = (actual_volume / planned_volume * 100) if planned_volume > 0 else 0.0
        st.metric("予定量に対する実投与率", f"{achieved_ratio:.0f} %")

        st.subheader("2. 消化管耐容性")
        col_c, col_d = st.columns(2)
        with col_c:
            diarrhea_times = st.number_input("下痢回数 (/day)", min_value=0, max_value=20, value=0, step=1)
            vomiting_times = st.number_input("嘔吐回数 (/day)", min_value=0, max_value=20, value=0, step=1)
        with col_d:
            abd_distension = st.selectbox("腹部膨満感・鼓腸", ["なし", "軽度", "中等度", "高度"])
            _other_issues = st.text_area("その他所見 / 問題点（任意）")

        st.subheader("3. 評価と翌日への提案（目安）")
        comments: list[str] = []
        if achieved_ratio >= 90:
            comments.append("エネルギー投与率は概ね良好（>=90%）です。")
        elif 70 <= achieved_ratio < 90:
            comments.append("エネルギー投与率70-90%です。中断理由を確認し運用改善を検討してください。")
        else:
            comments.append("エネルギー投与率<70%です。中断原因を詳細確認し増量や運用変更を検討してください。")
        if diarrhea_times >= 3:
            comments.append("下痢が1日3回以上。感染性腸炎や薬剤性を鑑別し、製剤/速度調整を検討。")
        if vomiting_times >= 1:
            comments.append("嘔吐あり。胃排出遅延・イレウス評価と投与経路・薬剤調整を検討。")
        if gastric_residual >= 250:
            comments.append("胃残量が多め（>=250mL）。注入速度調整や運動改善薬の検討余地。")
        if abd_distension in ["中等度", "高度"]:
            comments.append("腹部膨満が中等度以上。速度見直しや一時減量を検討。")
        if not comments:
            comments.append("大きな問題はみられません。現行プラン継続を検討。")
        for c in comments:
            st.markdown(f"- {c}")

    with tab_formulas:
        st.subheader("製剤リスト（`data_formulas.csv` を編集）")
        st.dataframe(formulas, use_container_width=True)


MOBILE_FRIENDLY_CSS = """
<style>
    /* スマホ向け: タップ領域・文字サイズ（iOSフォーカス時の自動ズーム防止に16px以上） */
    .block-container { padding-left: max(16px, env(safe-area-inset-left)) !important;
                       padding-right: max(16px, env(safe-area-inset-right)) !important; }
    .stButton > button, button[kind="secondary"], [data-testid="baseButton-secondary"] {
        min-height: 48px !important;
        padding: 12px 18px !important;
        font-size: 1.05rem !important;
        border-radius: 12px !important;
        -webkit-tap-highlight-color: transparent;
    }
    [data-testid="stFormSubmitButton"] > button {
        min-height: 48px !important;
        padding: 12px 18px !important;
        font-size: 1.05rem !important;
        border-radius: 12px !important;
    }
    .stCheckbox label, .stRadio label, .stSelectbox label, .stNumberInput label,
    .stTextInput label, .stDateInput label, .stTextArea label { font-size: 1rem !important; }
    .stCheckbox { padding: 6px 0 !important; }
    input, textarea, [data-baseweb="select"] > div {
        min-height: 44px !important;
        font-size: 16px !important;
    }
</style>
"""

# 先頭行のホームボタンをビューポート右上に固定（先頭行以外の横並びは狭い画面で縦積み）
HOME_HEADER_CSS = """
<style>
    section.main .block-container div[data-testid="stHorizontalBlock"]:first-of-type > div[data-testid="column"]:last-of-type {
        position: fixed !important;
        top: calc(0.5rem + env(safe-area-inset-top, 0px)) !important;
        right: max(0.5rem, env(safe-area-inset-right, 0px)) !important;
        z-index: 1000020 !important;
        width: auto !important;
        min-width: 6.5rem !important;
        max-width: 46vw !important;
        flex: 0 0 auto !important;
        padding: 0.15rem 0.35rem !important;
        background: rgba(255, 255, 255, 0.97) !important;
        border-radius: 12px !important;
        box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1) !important;
    }
    section.main .block-container div[data-testid="stHorizontalBlock"]:first-of-type > div[data-testid="column"]:first-of-type {
        padding-right: 5.75rem !important;
    }
    @media (max-width: 640px) {
        section.main .block-container div[data-testid="stHorizontalBlock"]:first-of-type {
            flex-direction: row !important;
            align-items: flex-start !important;
        }
        section.main .block-container div[data-testid="stHorizontalBlock"]:first-of-type > div[data-testid="column"] {
            width: auto !important;
            min-width: 0 !important;
        }
        section.main .block-container div[data-testid="stHorizontalBlock"]:not(:first-of-type) {
            flex-direction: column !important;
            gap: 0.75rem !important;
        }
        section.main .block-container div[data-testid="stHorizontalBlock"]:not(:first-of-type) > div[data-testid="column"] {
            width: 100% !important;
            min-width: 100% !important;
            flex: 1 1 auto !important;
        }
    }
</style>
"""


def main() -> None:
    st.set_page_config(page_title="EN-supporter", layout="wide", initial_sidebar_state="collapsed")
    st.markdown(MOBILE_FRIENDLY_CSS + HOME_HEADER_CSS, unsafe_allow_html=True)

    if "page" not in st.session_state:
        st.session_state.page = "top"
    if "selected_patient_id" not in st.session_state:
        st.session_state.selected_patient_id = None

    title_col, home_col = st.columns([5, 1])
    with title_col:
        st.title("EN-supporter")
    with home_col:
        if st.button("ホーム", key="en_nav_home", use_container_width=True, help="トップへ"):
            st.session_state.page = "top"
            st.rerun()

    formulas = load_formulas()
    formula_settings = load_formula_settings(formulas)
    filtered_formulas = apply_formula_settings(formulas, formula_settings)
    patients = load_patients()

    if st.session_state.page == "top":
        if st.button("新規患者を登録する", use_container_width=True):
            st.session_state.page = "register"
            st.rerun()
        if st.button("登録済み患者で戦略立案", use_container_width=True):
            st.session_state.page = "strategy_select"
            st.rerun()
        if st.button("採用製剤の設定", use_container_width=True):
            st.session_state.page = "settings"
            st.rerun()
        return

    if st.session_state.page == "register":
        with st.form("new_patient_form", clear_on_submit=False):
            patient_id = st.text_input("患者ID")
            icu_admission_date = st.date_input("入室日", value=date.today())
            today = st.date_input("本日の日付", value=date.today())
            height_cm = st.number_input("身長 (cm)", min_value=100.0, max_value=220.0, value=170.0, step=0.5)
            weight_kg = st.number_input("体重 (kg)", min_value=20.0, max_value=200.0, value=60.0, step=0.5)
            submitted = st.form_submit_button("患者を登録", use_container_width=True, type="primary")

        if submitted:
            if not patient_id.strip():
                st.error("患者IDを入力してください。")
            elif patient_id in patients["patient_id"].astype(str).tolist():
                st.error("同じ患者IDが既に登録されています。別のIDを入力してください。")
            else:
                new_row = pd.DataFrame(
                    [
                        {
                            "patient_id": patient_id.strip(),
                            "icu_admission_date": icu_admission_date.isoformat(),
                            "today": today.isoformat(),
                            "height_cm": float(height_cm),
                            "weight_kg": float(weight_kg),
                            "created_at": datetime.now().isoformat(timespec="seconds"),
                        }
                    ]
                )
                updated = pd.concat([patients, new_row], ignore_index=True)
                save_patients(updated)
                st.session_state.page = "strategy_select"
                st.rerun()
        return

    if st.session_state.page == "strategy_select":
        if patients.empty:
            st.warning("登録済み患者がいません。先に新規患者を登録してください。")
            return
        if filtered_formulas.empty:
            st.warning("採用製剤の設定で採用製剤が1つも選択されていません。先に採用製剤の設定を行ってください。")
            if st.button("採用製剤の設定へ移動", use_container_width=True):
                st.session_state.page = "settings"
                st.rerun()
            return

        show_list = patients.copy()
        show_list["表示"] = show_list.apply(
            lambda r: f"{r['patient_id']} | 入室日: {r['icu_admission_date']} | 体重: {float(r['weight_kg']):.1f}kg",
            axis=1,
        )
        st.dataframe(
            show_list[["patient_id", "icu_admission_date", "today", "height_cm", "weight_kg", "created_at"]],
            use_container_width=True,
        )
        selected_label = st.selectbox("患者を選択", options=show_list["表示"].tolist())
        selected_idx = show_list.index[show_list["表示"] == selected_label][0]
        selected_patient = show_list.loc[selected_idx]

        if st.button("この患者で戦略立案へ進む", use_container_width=True):
            st.session_state.selected_patient_id = str(selected_patient["patient_id"])
            st.session_state.page = "strategy_detail"
            st.rerun()
        return

    if st.session_state.page == "strategy_detail":
        if st.session_state.selected_patient_id is None:
            st.warning("患者が選択されていません。患者選択画面に戻って選択してください。")
            if st.button("患者選択画面へ", use_container_width=True):
                st.session_state.page = "strategy_select"
                st.rerun()
            return

        target = patients[patients["patient_id"].astype(str) == str(st.session_state.selected_patient_id)]
        if target.empty:
            st.warning("選択中の患者が見つかりません。患者選択画面から再選択してください。")
            if st.button("患者選択画面へ", use_container_width=True):
                st.session_state.selected_patient_id = None
                st.session_state.page = "strategy_select"
                st.rerun()
            return

        selected_patient = target.iloc[0]
        if st.button("患者選択へ戻る", use_container_width=True):
            st.session_state.page = "strategy_select"
            st.rerun()

        st.markdown("---")
        render_strategy_page(selected_patient, filtered_formulas)
        return

    if st.session_state.page == "settings":
        st.subheader("採用製剤の設定")
        st.caption(
            "`data_formulas.csv` に登録されている全製剤を以下に表示します。"
            "施設で採用する製剤にチェックを入れて保存してください。戦略立案ではチェック済み製剤のみ使用します。"
        )

        init_formula_checkbox_session(formulas, formula_settings)

        if st.button("すべて採用", use_container_width=True):
            for nm in formulas["name"].astype(str).tolist():
                st.session_state[_formula_checkbox_key(nm)] = True
            st.rerun()
        if st.button("すべて解除", use_container_width=True):
            for nm in formulas["name"].astype(str).tolist():
                st.session_state[_formula_checkbox_key(nm)] = False
            st.rerun()

        st.caption(f"登録製剤数: **{len(formulas)}**（メーカー別に折りたたみ表示）")

        display_cols = ["name", "vendor", "kcal_per_ml", "protein_g_per_100ml", "fiber_g_per_100ml", "osmolality_mOsmL"]
        display_cols = [c for c in display_cols if c in formulas.columns]

        for vendor in sorted(formulas["vendor"].dropna().astype(str).unique()):
            sub = formulas[formulas["vendor"].astype(str) == vendor].sort_values("name").reset_index(drop=True)
            n = len(sub)
            with st.expander(f"{vendor}（{n}製剤）", expanded=(n <= 8)):
                for _, row in sub.iterrows():
                    nm = str(row["name"])
                    k = _formula_checkbox_key(nm)
                    hparts: list[str] = []
                    if "kcal_per_ml" in row.index and pd.notna(row["kcal_per_ml"]):
                        hparts.append(f"{float(row['kcal_per_ml']):.2f} kcal/mL")
                    if "protein_g_per_100ml" in row.index and pd.notna(row["protein_g_per_100ml"]):
                        hparts.append(f"たんぱく {float(row['protein_g_per_100ml']):.1f} g/100mL")
                    if "notes" in row.index and pd.notna(row["notes"]) and str(row["notes"]).strip():
                        hparts.append(str(row["notes"])[:180])
                    help_txt = " | ".join(hparts) if hparts else None
                    st.checkbox(nm, key=k, help=help_txt)

        if st.button("設定を保存", use_container_width=True):
            edited = collect_formula_settings_from_session(formulas)
            save_formula_settings(edited)
            st.success(f"設定を保存しました（採用 {int(edited['enabled'].sum())} 件）。")

        with st.expander("製剤マスタ一覧（参照）"):
            st.dataframe(formulas[display_cols], use_container_width=True, hide_index=True)

        if st.button("トップへ戻る", use_container_width=True):
            st.session_state.page = "top"
            st.rerun()


if __name__ == "__main__":
    main()


