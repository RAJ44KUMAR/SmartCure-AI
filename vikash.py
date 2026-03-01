import streamlit as st
import requests
import pandas as pd
import matplotlib.pyplot as plt

# ======================================
# CONFIG
# ======================================

API_KEY = "8ddb31ab767134c27b970bfd11d16aa1"

CURING_COST = {
    "Normal Water Curing": 200,
    "Steam Curing": 800,
    "Accelerated Admixture": 500,
    "Hot Water Curing": 1000,
    "Membrane Curing": 300,
    "Covered Shed Curing": 600
}

CEMENT_COST = {
    "OPC 43": 300,
    "OPC 53": 350,
    "PPC": 280
}

CEMENT_FACTOR = {
    "OPC 43": 1.0,
    "OPC 53": 1.2,
    "PPC": 0.9
}

CURING_MULTIPLIER = {
    "Normal Water Curing": 1.0,
    "Steam Curing": 1.5,
    "Accelerated Admixture": 1.3,
    "Hot Water Curing": 1.6,
    "Membrane Curing": 0.95,
    "Covered Shed Curing": 1.0
}

MAX_COST = 2000

# ======================================
# WEATHER
# ======================================

def get_weather(location):
    url = f"https://api.openweathermap.org/data/2.5/forecast?q={location}&appid={API_KEY}&units=metric"
    response = requests.get(url)
    data = response.json()

    temps, humidity, rain_prob = [], [], []

    for item in data["list"][:40]:
        temps.append(item["main"]["temp"])
        humidity.append(item["main"]["humidity"])
        rain_prob.append(item.get("pop", 0))

    return {
        "avg_temp": sum(temps)/len(temps),
        "avg_humidity": sum(humidity)/len(humidity),
        "max_rain_prob": max(rain_prob),
        "temp_series": temps
    }

# ======================================
# STRENGTH MODEL
# ======================================

def predict_strength(hours, temp, cement_factor, wc_ratio, curing):
    maturity = hours * (temp / 25)
    return (
        0.8 * maturity *
        cement_factor *
        CURING_MULTIPLIER[curing] *
        (1 - wc_ratio)
    )

# ======================================
# BASELINE
# ======================================

def calculate_baseline(weather, required_strength,
                       wc_ratio, cement_type,
                       max_hours):

    for hours in range(8, max_hours + 1, 2):
        strength = predict_strength(
            hours,
            weather["avg_temp"],
            CEMENT_FACTOR[cement_type],
            wc_ratio,
            "Normal Water Curing"
        )

        if strength >= required_strength:
            baseline_time = hours
            baseline_cost = CEMENT_COST[cement_type] + CURING_COST["Normal Water Curing"]
            return baseline_time, baseline_cost

    return None, None

# ======================================
# BALANCED OPTIMIZATION
# ======================================

def optimize(location, required_strength,
             wc_ratio, cement_type,
             time_weight, cost_weight,
             max_hours):

    weather = get_weather(location)

    best_result = None
    best_score = float("inf")

    for curing in CURING_COST.keys():
        for hours in range(8, max_hours + 1, 2):

            strength = predict_strength(
                hours,
                weather["avg_temp"],
                CEMENT_FACTOR[cement_type],
                wc_ratio,
                curing
            )

            if strength >= required_strength:

                total_cost = CEMENT_COST[cement_type] + CURING_COST[curing]

                norm_time = hours / max_hours
                norm_cost = total_cost / MAX_COST

                score = (time_weight * norm_time) + \
                        (cost_weight * norm_cost)

                if score < best_score:
                    best_score = score
                    best_result = {
                        "Curing": curing,
                        "Cycle Time": hours,
                        "Cost": total_cost,
                        "Strength": round(strength, 2),
                        "Weather": weather
                    }

                break

    return best_result

# ======================================
# FASTEST OPTION
# ======================================

def find_fastest_option(weather, required_strength,
                        wc_ratio, cement_type,
                        max_hours):

    fastest = None
    min_time = float("inf")

    for curing in CURING_COST.keys():
        for hours in range(8, max_hours + 1, 2):

            strength = predict_strength(
                hours,
                weather["avg_temp"],
                CEMENT_FACTOR[cement_type],
                wc_ratio,
                curing
            )

            if strength >= required_strength:

                total_cost = CEMENT_COST[cement_type] + CURING_COST[curing]

                if hours < min_time:
                    min_time = hours
                    fastest = {
                        "Curing": curing,
                        "Cycle Time": hours,
                        "Cost": total_cost
                    }

                break

    return fastest

# ======================================
# SCHEDULE
# ======================================

def generate_schedule(weather, required_strength,
                      wc_ratio, cement_type,
                      max_hours):

    schedule = []
    cement_factor = CEMENT_FACTOR[cement_type]

    for day in range(5):

        day_temps = weather["temp_series"][day*8:(day+1)*8]
        avg_temp = sum(day_temps)/len(day_temps)

        best_hours = None

        for hours in range(8, max_hours + 1, 2):
            strength = predict_strength(
                hours,
                avg_temp,
                cement_factor,
                wc_ratio,
                "Normal Water Curing"
            )

            if strength >= required_strength:
                best_hours = hours
                break

        risk = "Low"
        if avg_temp < 15 or avg_temp > 38:
            risk = "Moderate"
        if weather["max_rain_prob"] > 0.6:
            risk = "High"

        schedule.append({
            "Day": f"Day {day+1}",
            "Avg Temp (°C)": round(avg_temp,2),
            "Estimated Cycle Time (hrs)": best_hours,
            "Risk Level": risk
        })

    return pd.DataFrame(schedule)

# ======================================
# UI
# ======================================

st.set_page_config(page_title="AI Precast Optimizer", layout="wide")
st.title("🏗 SmartCure AI: Climate-Intelligent Optimization of Precast Curing Strategies")

col1, col2 = st.columns(2)

with col1:
    location = st.text_input("Project Location", "Patna")
    required_strength = st.slider("Required Early Strength (MPa)", 10, 50, 25)
    wc_ratio = st.slider("Water-Cement Ratio", 0.30, 0.60, 0.40)
    cement_type = st.selectbox("Cement Type", ["OPC 43", "OPC 53", "PPC"])

with col2:
    time_weight = st.slider("Time Priority", 0.0, 1.0, 0.7)
    cost_weight = 1 - time_weight
    max_hours = st.slider("Maximum Curing Time Limit (hrs)", 24, 120, 72)

if st.button("Run AI Optimization 🚀"):

    result = optimize(location, required_strength,
                      wc_ratio, cement_type,
                      time_weight, cost_weight,
                      max_hours)

    if result is None:
        st.error("No feasible solution found.")
        st.stop()

    weather = result["Weather"]

    st.subheader("📊 Balanced Optimization Result")
    st.write("Best Curing:", result["Curing"])
    st.write("Cycle Time:", result["Cycle Time"])
    st.write("Cost:", result["Cost"])

    # Baseline
    baseline_time, baseline_cost = calculate_baseline(
        weather, required_strength,
        wc_ratio, cement_type,
        max_hours
    )

    st.subheader("📌 Baseline (Normal Water Curing)")

    if baseline_time is None:
        st.warning("⚠ Under normal curing, required strength not achievable.")
    else:
        st.write("Baseline Time:", baseline_time)
        st.write("Baseline Cost:", baseline_cost)

    # Fastest
    fastest = find_fastest_option(
        weather, required_strength,
        wc_ratio, cement_type,
        max_hours
    )

    if fastest and baseline_time:

        time_saved = baseline_time - fastest["Cycle Time"]
        extra_cost = fastest["Cost"] - baseline_cost

        st.subheader("⚡ Fastest Possible Option")
        st.write("Method:", fastest["Curing"])
        st.write("Time Saved:", time_saved, "hrs")
        st.write("Extra Cost: ₹", extra_cost)

        if time_saved > 0:
            cost_per_hour = extra_cost / time_saved
            st.write("Cost per Hour Saved: ₹", round(cost_per_hour,2))

            st.subheader("💡 Upgrade Worth It?")

            if cost_per_hour < 50:
                st.success("✅ Worth Upgrading")
            elif cost_per_hour < 150:
                st.warning("⚖ Moderate Tradeoff")
            else:
                st.error("❌ Not Worth It")

    # Baseline vs Optimized Graph
    if baseline_time:
        st.subheader("📊 Baseline vs Optimized Comparison")

        categories = ["Cycle Time (hrs)", "Cost (₹)"]
        baseline_vals = [baseline_time, baseline_cost]
        optimized_vals = [result["Cycle Time"], result["Cost"]]

        x = range(len(categories))

        plt.figure()
        plt.bar(x, baseline_vals, width=0.4)
        plt.bar([i + 0.4 for i in x], optimized_vals, width=0.4)
        plt.xticks([i + 0.2 for i in x], categories)
        st.pyplot(plt)

    # Strength Growth Curve
    st.subheader("📈 Strength Growth Curve (Strength vs Time)")

    hours_range = list(range(8, max_hours+1, 2))
    strength_curve = [
        predict_strength(h,
                         weather["avg_temp"],
                         CEMENT_FACTOR[cement_type],
                         wc_ratio,
                         result["Curing"])
        for h in hours_range
    ]

    plt.figure()
    plt.plot(hours_range, strength_curve)
    plt.xlabel("Time (hrs)")
    plt.ylabel("Strength (MPa)")
    st.pyplot(plt)

    # Cycle Time vs Cost Tradeoff
    st.subheader("📊 Cycle Time vs Cost Tradeoff")

    cycle_list = []
    cost_list = []

    for curing in CURING_COST.keys():
        for hours in range(8, max_hours+1, 4):

            strength = predict_strength(
                hours,
                weather["avg_temp"],
                CEMENT_FACTOR[cement_type],
                wc_ratio,
                curing
            )

            if strength >= required_strength:
                total_cost = CEMENT_COST[cement_type] + CURING_COST[curing]
                cycle_list.append(hours)
                cost_list.append(total_cost)
                break

    plt.figure()
    plt.scatter(cycle_list, cost_list)
    plt.xlabel("Cycle Time (hrs)")
    plt.ylabel("Cost (₹)")
    st.pyplot(plt)

    # Temperature Trend
    st.subheader("🌡 Temperature Trend")
    df = pd.DataFrame({"Temperature": weather["temp_series"]})
    plt.figure()
    plt.plot(df["Temperature"])
    st.pyplot(plt)

    # Schedule
    st.subheader("📅 5-Day Schedule")
    schedule_df = generate_schedule(
        weather, required_strength,
        wc_ratio, cement_type,
        max_hours
    )
    st.dataframe(schedule_df)