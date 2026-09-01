import os
import uuid
import streamlit as st
from dotenv import load_dotenv, find_dotenv
from google import genai
from google.genai import types

import db

# Load local environment variables with robust path detection
script_dir = os.path.dirname(os.path.abspath(__file__))
for env_filename in [".env", ".env.txt", ".env.local"]:
    env_path = os.path.join(script_dir, env_filename)
    if os.path.exists(env_path):
        load_dotenv(dotenv_path=env_path, override=True)
load_dotenv(find_dotenv(usecwd=True), override=True)

# Initialize Persistent Storage (SQLite)
db.init_db()

# Set Streamlit Page Configuration
st.set_page_config(
    page_title="AI Diet & Supplement Coach",
    page_icon="🥗",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Styling for polished UI
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }
    .subtitle {
        color: #6c757d;
        font-size: 1.05rem;
        margin-bottom: 1.2rem;
    }
    .disclaimer {
        font-size: 0.8rem;
        color: #888;
        border-top: 1px solid #eee;
        padding-top: 10px;
        margin-top: 20px;
    }
</style>
""", unsafe_allow_html=True)

# ----------------- Helper Functions ----------------- #
def calculate_nutrition_baselines(age, sex, height_cm, weight_kg, activity_level, goal):
    """Calculates BMR & TDEE using the standard Mifflin-St Jeor equation."""
    if sex == "Male":
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + 5
    else:
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 161

    activity_multipliers = {
        "Sedentary (desk job, minimal exercise)": 1.2,
        "Lightly Active (light exercise 1-3 days/wk)": 1.375,
        "Moderately Active (moderate exercise 3-5 days/wk)": 1.55,
        "Very Active (hard exercise 6-7 days/wk)": 1.725,
        "Extra Active (intense training / physical job)": 1.9
    }
    tdee = bmr * activity_multipliers.get(activity_level, 1.2)

    goal_adjustments = {
        "Weight Loss (Deficit -20%)": tdee * 0.80,
        "Mild Fat Loss (Deficit -10%)": tdee * 0.90,
        "Maintenance": tdee,
        "Lean Muscle Gain (Surplus +10%)": tdee * 1.10,
        "Muscle Growth (Surplus +15%)": tdee * 1.15,
        "Longevity & Health Optimization": tdee,
        "Better Energy & Athletic Performance": tdee * 1.05
    }
    target_calories = goal_adjustments.get(goal, tdee)
    return int(round(bmr)), int(round(tdee)), int(round(target_calories))

def start_new_conversation(initial_assistant_message="Hello! 👋 I'm your AI Diet & Supplement Coach. How can I help you reach your health and nutrition goals today?"):
    """Starts a new persistent conversation session."""
    new_id = str(uuid.uuid4())
    db.create_conversation(new_id, title="New Consultation")
    db.save_message(new_id, "assistant", initial_assistant_message)
    st.session_state.current_conv_id = new_id
    st.session_state.messages = [{"role": "assistant", "content": initial_assistant_message}]

# ----------------- Session State Initialization ----------------- #
saved_convs = db.list_conversations()

if "current_conv_id" not in st.session_state:
    if saved_convs:
        # Load the most recent conversation
        st.session_state.current_conv_id = saved_convs[0]["id"]
        st.session_state.messages = db.get_conversation_messages(st.session_state.current_conv_id)
    else:
        # Start a brand new one
        start_new_conversation()
else:
    # Ensure current messages in session match the DB
    st.session_state.messages = db.get_conversation_messages(st.session_state.current_conv_id)

# ----------------- Sidebar: Conversations & Profile ----------------- #
with st.sidebar:
    st.header("💬 Conversations")
    
    col_new, col_del = st.columns([3, 1])
    with col_new:
        if st.button("➕ New Chat", use_container_width=True):
            start_new_conversation()
            st.rerun()
    with col_del:
        if st.button("🗑️", help="Delete current conversation", use_container_width=True):
            if st.session_state.current_conv_id:
                db.delete_conversation(st.session_state.current_conv_id)
                remaining = db.list_conversations()
                if remaining:
                    st.session_state.current_conv_id = remaining[0]["id"]
                else:
                    start_new_conversation()
                st.rerun()

    # Re-fetch active conversations for the selector
    current_conv_list = db.list_conversations()
    if current_conv_list:
        conv_options = {c["id"]: c["title"] for c in current_conv_list}
        selected_id = st.selectbox(
            "Select Chat Session",
            options=list(conv_options.keys()),
            format_func=lambda cid: conv_options.get(cid, "Untitled"),
            index=list(conv_options.keys()).index(st.session_state.current_conv_id) if st.session_state.current_conv_id in conv_options else 0,
            label_visibility="collapsed"
        )
        if selected_id != st.session_state.current_conv_id:
            st.session_state.current_conv_id = selected_id
            st.session_state.messages = db.get_conversation_messages(selected_id)
            st.rerun()

    st.caption(f"Storage: **{db.get_storage_mode()}**")
    
    fs_warning = db.get_firestore_warning()
    if fs_warning:
        st.info(f"ℹ️ {fs_warning}", icon="☁️")

    st.markdown("---")
    st.header("👤 Your Profile")
    
    # Load persistent profile from database (Firestore or SQLite)
    saved_profile = db.get_user_profile()

    # API Key Handling (checks env, streamlit secrets, or user input)
    env_api_key = (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip().strip('"').strip("'")
    secret_key = ""
    try:
        secret_key = str(st.secrets.get("GEMINI_API_KEY") or st.secrets.get("GOOGLE_API_KEY") or "").strip().strip('"').strip("'")
    except Exception:
        secret_key = ""
    
    default_key = env_api_key or secret_key or ""

    if not default_key:
        gemini_api_key = st.text_input(
            "🔑 Gemini API Key",
            type="password",
            help="Get your free key at https://aistudio.google.com/app/apikey"
        )
    else:
        gemini_api_key = default_key
        st.success("API Key loaded from environment", icon="✅")

    st.markdown("---")
    
    sex_options = ["Male", "Female"]
    saved_sex_idx = sex_options.index(saved_profile.get("sex", "Male")) if saved_profile.get("sex") in sex_options else 0
    
    activity_options = [
        "Sedentary (desk job, minimal exercise)",
        "Lightly Active (light exercise 1-3 days/wk)",
        "Moderately Active (moderate exercise 3-5 days/wk)",
        "Very Active (hard exercise 6-7 days/wk)",
        "Extra Active (intense training / physical job)"
    ]
    saved_act_idx = activity_options.index(saved_profile.get("activity_level")) if saved_profile.get("activity_level") in activity_options else 2

    goal_options = [
        "Weight Loss (Deficit -20%)",
        "Mild Fat Loss (Deficit -10%)",
        "Maintenance",
        "Lean Muscle Gain (Surplus +10%)",
        "Muscle Growth (Surplus +15%)",
        "Longevity & Health Optimization",
        "Better Energy & Athletic Performance"
    ]
    saved_goal_idx = goal_options.index(saved_profile.get("goal")) if saved_profile.get("goal") in goal_options else 0

    col1, col2 = st.columns(2)
    with col1:
        age = st.number_input("Age", min_value=14, max_value=100, value=int(saved_profile.get("age", 28)), step=1)
        height_cm = st.number_input("Height (cm)", min_value=100, max_value=230, value=int(saved_profile.get("height_cm", 175)), step=1)
    with col2:
        sex = st.selectbox("Sex", sex_options, index=saved_sex_idx)
        weight_kg = st.number_input("Weight (kg)", min_value=30.0, max_value=250.0, value=float(saved_profile.get("weight_kg", 75.0)), step=0.5)

    activity_level = st.selectbox("Activity Level", activity_options, index=saved_act_idx)
    goal = st.selectbox("Primary Goal", goal_options, index=saved_goal_idx)

    diet_pref_options = ["None / Balanced", "Vegetarian", "Vegan", "Pescatarian", "Keto / Low-Carb", "Mediterranean", "Paleo", "Gluten-Free", "Dairy-Free", "Halal", "Kosher", "Intermittent Fasting"]
    saved_diet_prefs = [p for p in saved_profile.get("diet_pref", ["None / Balanced"]) if p in diet_pref_options]
    if not saved_diet_prefs:
        saved_diet_prefs = ["None / Balanced"]

    diet_pref = st.multiselect("Dietary Preferences / Restrictions", diet_pref_options, default=saved_diet_prefs)
    allergies = st.text_input("Allergies / Disliked Foods", value=saved_profile.get("allergies", ""), placeholder="e.g., Peanuts, shellfish, lactose, cilantro")
    current_supplements = st.text_area("Current Supplements", value=saved_profile.get("current_supplements", ""), placeholder="e.g., Creatine 5g, Vitamin D3 2000IU, Whey protein", height=70)
    medical_notes = st.text_area("Medical Conditions / Medications", value=saved_profile.get("medical_notes", ""), placeholder="e.g., Asthma (inhaler), no known allergies", height=70)

    # Auto-persist profile if modified
    current_profile_data = {
        "age": age,
        "sex": sex,
        "height_cm": height_cm,
        "weight_kg": weight_kg,
        "activity_level": activity_level,
        "goal": goal,
        "diet_pref": diet_pref,
        "allergies": allergies,
        "current_supplements": current_supplements,
        "medical_notes": medical_notes,
    }

    if current_profile_data != saved_profile:
        db.save_user_profile(current_profile_data)

    # Calculate and Display Baselines
    bmr, tdee, target_calories = calculate_nutrition_baselines(age, sex, height_cm, weight_kg, activity_level, goal)
    
    st.markdown("### 📊 Estimated Baselines")
    col_m1, col_m2 = st.columns(2)
    col_m1.metric("BMR (Basal)", f"{bmr} kcal")
    col_m2.metric("TDEE (Maintain)", f"{tdee} kcal")
    st.metric("🎯 Target Daily Energy", f"{target_calories} kcal/day")

# ----------------- Main Chat Section ----------------- #
st.markdown('<div class="main-title">🥗 AI Diet & Supplement Coach</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Evidence-based nutrition, customized meal planning, and safe supplement guidance.</div>', unsafe_allow_html=True)

# Build context for the AI
user_context = f"""
USER PROFILE:
- Age: {age} | Sex: {sex} | Height: {height_cm} cm | Weight: {weight_kg} kg
- Activity Level: {activity_level}
- Primary Goal: {goal}
- Calculated BMR: {bmr} kcal/day
- Calculated TDEE (Maintenance): {tdee} kcal/day
- Suggested Caloric Target: {target_calories} kcal/day
- Dietary Preferences: {", ".join(diet_pref)}
- Allergies/Restrictions: {allergies if allergies else 'None specified'}
- Current Supplements: {current_supplements if current_supplements else 'None specified'}
- Medications / Conditions: {medical_notes if medical_notes else 'None specified'}
"""

SYSTEM_INSTRUCTION = f"""
You are an expert, empathetic, and evidence-based AI Dietitian and Supplement Coach.
Your mission is to provide highly practical, scientifically sound nutrition and supplement advice tailored specifically to the user.

{user_context}

GUIDELINES:
1. **Evidence-Based & Pragmatic**: Ground recommendations in sports nutrition science and dietary guidelines. Avoid fad diets and unproven claims.
2. **Personalization**: Always reference the user's specific caloric target (~{target_calories} kcal/day), dietary restrictions, and goals in your meal suggestions and macro breakdowns.
3. **Supplement Safety First**:
   - Check for potential contraindications or redundant dosing against their listed current supplements and medications.
   - Specify optimal timing (e.g., with meals, morning, pre-bed) and evidence grade.
   - Never recommend dangerous compounds or unverified mega-doses.
4. **Actionable Formatting**: Use markdown tables for meal plans, clear bullet points for recipes and macro splits, and bold key numbers.
5. **Medical Disclaimer**: Always remind users that advice is for educational purposes and they should consult a healthcare professional for clinical needs.
"""

# Quick Action Buttons
st.markdown("**Quick Prompts:**")
qp_cols = st.columns(4)
quick_prompt = None

if qp_cols[0].button("📅 7-Day Meal Plan", use_container_width=True):
    quick_prompt = "Please generate a realistic, delicious 7-day meal plan matching my target calories and dietary preferences, complete with estimated macros per meal."

if qp_cols[1].button("💊 Review Supplement Stack", use_container_width=True):
    quick_prompt = "Review my current supplements (or suggest a foundational evidence-based stack). Detail exact dosages, ideal timing, and scientific rationale."

if qp_cols[2].button("⚡ Pre/Post Workout Nutrition", use_container_width=True):
    quick_prompt = "What should I eat before and after workouts to maximize energy and muscle recovery for my goal?"

if qp_cols[3].button("🛒 Smart Grocery List", use_container_width=True):
    quick_prompt = "Give me a categorized weekly grocery shopping list (proteins, complex carbs, healthy fats, micronutrient-dense veggies) tailored to my goals."

# Display Existing Chat Messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Handle User Input (either typed or via quick action button)
user_input = st.chat_input("Ask about meal ideas, supplement timing, recipes, or macro tracking...")
active_input = quick_prompt if quick_prompt else user_input

if active_input:
    if not gemini_api_key:
        st.error("Please enter a Gemini API Key in the sidebar to chat with the Coach!")
    else:
        # If this is the first user prompt in the conversation, name the session
        user_messages = [m for m in st.session_state.messages if m["role"] == "user"]
        if len(user_messages) == 0:
            clean_title = (active_input[:35] + "...") if len(active_input) > 35 else active_input
            db.update_conversation_title(st.session_state.current_conv_id, clean_title)

        # Append and persist user message
        st.session_state.messages.append({"role": "user", "content": active_input})
        db.save_message(st.session_state.current_conv_id, "user", active_input)
        
        with st.chat_message("user"):
            st.markdown(active_input)

        # Generate response using Google GenAI SDK
        with st.chat_message("assistant"):
            response_container = st.empty()
            full_response = ""
            
            try:
                client = genai.Client(api_key=gemini_api_key)
                
                # Format conversation history
                contents = []
                for m in st.session_state.messages:
                    contents.append(
                        types.Content(
                            role="model" if m["role"] == "assistant" else "user",
                            parts=[types.Part.from_text(text=m["content"])]
                        )
                    )

                response_stream = client.models.generate_content_stream(
                    model="gemini-3.7-flash",
                    contents=contents,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION,
                        temperature=0.7,
                    )
                )

                for chunk in response_stream:
                    if chunk.text:
                        full_response += chunk.text
                        response_container.markdown(full_response + "▌")

                response_container.markdown(full_response)
                
                # Append and persist assistant response
                st.session_state.messages.append({"role": "assistant", "content": full_response})
                db.save_message(st.session_state.current_conv_id, "assistant", full_response)

            except Exception as e:
                error_msg = f"⚠️ Error generating response: {str(e)}"
                response_container.markdown(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
                db.save_message(st.session_state.current_conv_id, "assistant", error_msg)

st.markdown("""
<div class="disclaimer">
    <strong>Disclaimer:</strong> This AI Coach provides educational nutrition and supplement information based on published scientific literature. It is not medical advice, diagnosis, or treatment. Always consult a qualified physician or registered dietitian before beginning any new diet or supplement regimen.
</div>
""", unsafe_allow_html=True)
