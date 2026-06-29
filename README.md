# AI-Powered Meeting Management System

A comprehensive, modern Django-based web application designed to streamline meeting scheduling, attendance tracking, and AI-driven transcription & summarization.

## 🌟 Key Features

- **Automated AI Minutes of Meeting (MoM):**
  - Upload large audio files (`.mp3`, `.wav`, `.m4a`, `.aac`).
  - Seamlessly chunks and processes long recordings using the **Google Gemini API**.
  - Intelligent transcription with speaker identification.
  - Auto-generates concise summaries, key discussion points, and extracts action items.
  
- **Professional Exports:**
  - One-click downloads of transcripts and AI summaries in **PDF**, **Word (.docx)**, and **Text (.txt)** formats.

- **Robust Scheduling & RSVP:**
  - Create and schedule meetings with specific date, time, and duration.
  - Automatically sends beautiful, responsive HTML email invitations to participants.
  - One-click RSVP buttons ("Accept" or "Decline") embedded directly in the email.
  
- **Task & Action Item Management:**
  - Automatically generated action items from AI summaries are assigned to participants.
  - Track statuses (Pending, In Progress, Completed) across projects.

- **Dynamic UI/UX:**
  - Built with a modern, responsive Glassmorphism design.
  - Features real-time notifications, interactive dashboards, and smooth page transitions.
  - Graceful backend error handling (e.g., handles invalid API keys without crashing).

## 🛠️ Tech Stack

- **Backend:** Python, Django
- **Database:** SQLite (default for development)
- **AI Integration:** Google Gemini API (`google-generativeai`)
- **Audio Processing:** `pydub`, FFmpeg (for intelligent audio chunking)
- **Document Generation:** `reportlab` (PDF), `python-docx` (Word)
- **Frontend:** HTML5, Vanilla CSS, Bootstrap 5, Lucide Icons
- **Environment Management:** `python-dotenv`

## 🚀 Setup Instructions

### 1. Prerequisites
- **Python 3.8+** installed.
- **FFmpeg** installed on your system and added to your system's PATH (required by `pydub` for audio chunking).

### 2. Installation

Clone the repository:
```bash
git clone https://github.com/PriyatharshniSiva/Meeting-Management.git
cd Meeting-Management
```

Create a virtual environment and activate it:
```bash
python -m venv venv
# On Windows
.\venv\Scripts\activate
# On Mac/Linux
source venv/bin/activate
```

Install the required Python dependencies:
```bash
pip install -r requirements.txt
```

*(If a requirements.txt is missing, here are the core libraries: `django`, `google-generativeai`, `pydub`, `python-dotenv`, `reportlab`, `python-docx`)*

### 3. Environment Variables
Create a `.env` file in the root directory (same level as `manage.py`) and add your credentials:
```env
# Google Gemini API Key for transcription and summarization
GEMINI_API_KEY=your_actual_gemini_api_key_here

# Django Email Settings (for sending RSVP invites)
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_app_password
```

### 4. Database Setup
Apply the Django migrations to set up your SQLite database:
```bash
python manage.py makemigrations
python manage.py migrate
```

### 5. Run the Application
Start the development server:
```bash
python manage.py runserver
```
Visit `http://127.0.0.1:8000/` in your browser to access the application.

---

## 🎨 Design Philosophy
This project heavily prioritizes visual excellence. It moves away from generic templates and embraces curated HSL color palettes, dark modes, subtle micro-animations, and responsive glassmorphism to deliver a state-of-the-art, premium feel to the end user.
