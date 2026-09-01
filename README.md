# 🥗 AI Diet and Supplement Coach

A lightweight, effective, and evidence-based **AI Diet & Supplement Coach** built with **Streamlit**, the **Google Gemini API**, and **Google Cloud Firestore**.

---

## ✨ Features

- **💬 Dual Storage (Local SQLite + Cloud Firestore)**:
  - Automatically saves all your consultations.
  - **Local Mode**: Uses zero-config local SQLite (`chat_history.db`).
  - **Cloud Mode**: Connects to **Google Cloud Firestore** (GCP) for permanent cloud sync across devices and serverless hosting.
  - Resume past conversations, create new chat sessions (`➕ New Chat`), or delete old consultations.
- **Personalized Biometrics & Baselines**:
  - Computes exact BMR (Basal Metabolic Rate) and TDEE (Total Daily Energy Expenditure) using the Mifflin-St Jeor equation.
  - Automatically calculates target calories and macro goals according to personal fitness objectives.
- **Evidence-Based Nutrition & Supplement Guidance**:
  - Scientifically backed meal planning, recipe suggestions, and macro splits.
  - Safety-first supplement reviews with dosage timing, upper intake warnings, and medication interaction checks.
- **Interactive Chat Interface**:
  - Streaming conversational responses with context memory.
  - 1-click quick prompt buttons (7-Day Meal Plan, Supplement Stack Review, Workout Nutrition, Grocery List).

---

## 🚀 Quick Start (Run Locally)

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Up Your API Key
Get a free Gemini API key at [Google AI Studio](https://aistudio.google.com/app/apikey).

Create a `.env` file from the example:
```bash
cp .env.example .env
```
Add your key inside `.env`:
```env
GEMINI_API_KEY=your_gemini_api_key_here
```

### 3. Launch the App
```bash
streamlit run app.py
```
*(By default, it will store chats in local SQLite. You can connect GCP Firestore below for cloud storage).*

---

## ☁️ Setting Up Google Cloud Firestore (Free Cloud Database)

Google Cloud Firestore has an **Always-Free tier** (1 GB storage, 50,000 reads/day, 20,000 writes/day):

### Step 1: Create a Firestore Database in GCP
1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. In the search bar, search for **Firestore** and click **Create Database**.
3. Choose **Native Mode** and select a region close to you (e.g. `us-central1` or `europe-west1`).
4. Click **Create Database**.

### Step 2: Create a Service Account Key
1. In GCP Console, go to **IAM & Admin > Service Accounts**.
2. Click **Create Service Account**, name it (e.g. `diet-coach-app`), and click **Create and Continue**.
3. Grant the role: **Cloud Datastore User** (or *Firebase Rules Admin*).
4. Click **Done**.
5. Click on your newly created service account > **Keys** tab > **Add Key** > **Create new key** > **JSON**.
6. A `.json` key file will download to your computer.

### Step 3: Connect to your App
- **For Local Development**: Save the downloaded JSON file as `serviceAccountKey.json` inside your project root folder (it is already ignored by `.gitignore`).
- **For Streamlit Community Cloud (Hosted on Internet)**:
  In your Streamlit app dashboard, go to **Settings > Secrets** and paste your credentials:
  ```toml
  GEMINI_API_KEY = "your_gemini_key"

  [gcp_service_account]
  type = "service_account"
  project_id = "your-project-id"
  private_key_id = "..."
  private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
  client_email = "..."
  client_id = "..."
  auth_uri = "https://accounts.google.com/o/oauth2/auth"
  token_uri = "https://oauth2.googleapis.com/token"
  auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
  client_x509_cert_url = "..."
  ```

---

## 🌐 How to Host on the Internet for Free (Streamlit Cloud)

1. Push your repository to **GitHub**.
2. Go to [share.streamlit.io](https://share.streamlit.io) and log in with GitHub.
3. Select your repository, set the main file to `app.py`, add your secrets, and click **Deploy**!
