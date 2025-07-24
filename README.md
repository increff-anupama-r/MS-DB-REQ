# README: MS-Req Form Component

This document provides a detailed overview of the MS-Req Form Component, its features, and how it integrates with the Open WebUI backend to provide a seamless user experience for creating Notion database entries directly from the chat interface.

## 1. Overview

This is a highly interactive and intelligent conversational UI component designed to guide users through the process of creating a structured data artifact, which is then submitted to a Notion database. It replaces a traditional, static web form with a dynamic, chat-based workflow, making the data entry process more intuitive and user-friendly.

The component operates as a state machine, managing the conversation flow from asking questions to validating input, handling edits, and finally submitting the completed form.

## 2. Key Features

- **Conversational Form Filling:** Guides users step-by-step through required and optional fields in a chat-like manner.
- **Real-time Input Validation:** Each piece of user input is validated in real-time. The component provides immediate, context-aware feedback for invalid data (e.g., incorrect date formats, unsafe inputs, or values that don't meet quality standards).
- **Intelligent Data Parsing:** Utilizes libraries like `dayjs` for natural language date parsing (e.g., "tomorrow", "next week") and `js-levenshtein` for fuzzy matching of options.
- **Dynamic Name Suggestions:** For fields like "Owner" and "Created By," the component queries a backend API (`/api/v1/notion/users/suggest`) to provide real-time name suggestions as the user types, reducing errors and ensuring consistency.
- **File and URL Attachments:** Users can upload files or add URLs as attachments. Files are securely uploaded to the Open WebUI backend (`/api/v1/files/`) and linked in the final Notion entry.
- **State Management & Progress Tracking:** A visual progress bar and status indicators for each field keep the user informed of their progress. The component's state (`asking`, `editing`, `review`, `submitting`) is carefully managed to control the UI flow.
- **User Commands:** Supports commands for a better user experience:
  - `edit <field>`: Allows the user to jump back and edit a specific field.
  - `submit`: Initiates the final submission process.
  - `help`: Displays a help message.
  - `cancel`: Aborts the form.
- **Error Handling & Retries:** Features robust error handling for API failures during submission, with clear messages and guidance for the user.
- **Local Session Persistence:** The form's state is saved to `localStorage`, allowing users to refresh the page and resume where they left off.

## 3. Open WebUI Integration

This component is a powerful example of the synergy between the SvelteKit frontend and the Python backend in Open WebUI.

### Architecture

- **Frontend (`src/`):** A SvelteKit application responsible for the entire user interface. This component (`ArtifactFormChat.svelte`) lives within this frontend codebase.
- **Backend (`backend/`):** A Python server (likely using FastAPI or a similar framework) that exposes a REST API under the `/api/v1/` prefix.
- **API Communication:** The SvelteKit frontend communicates with the Python backend via API calls. During development, a proxy is configured to forward requests from the frontend dev server to the backend server to avoid CORS issues.

### Integration Steps

1.  **Activation:** The `ArtifactFormChat` component is designed to be embedded within the main chat interface of Open WebUI. It is likely activated when a user navigates to the MS-Form icon available in the left panel.

2.  **Data Flow:**

    - The parent chat view renders `ArtifactFormChat`, passing in props like `history` and `submitPrompt`.
    - The component takes control of the user interaction, making its own API calls to the backend for its specific needs:
      - `POST /api/v1/files/`: To upload file attachments.
      - `POST /api/v1/notion/users/suggest`: To fetch name suggestions for form fields.
      - `POST /api/v1/notion/requests`: (Handled by `createFeatureRequest`) To submit the final, structured data to the backend.
    - The Python backend handles the core business logic:
      - Authenticating the user via their `localStorage.token`.
      - Storing uploaded files securely.
      - Interfacing with the external Notion API using the server's credentials to create the database entry.

3.  **Completion and Handoff:** Once the process is `done` or `canceled`, the component uses the `dispatch` function to emit an event. This signals to the parent chat component that its task is complete, allowing the main chat interface to resume control.

## 4. How to Clone and Use

This section guides you through setting up the Open WebUI project to use this.

### Prerequisites

- [Node.js](https://nodejs.org/) (v18.13.0 or later)
- [Python](https://www.python.org/) (3.9 or later)

### 1. Clone & Install

Clone the repository and install the necessary dependencies for both the frontend and backend.

```bash
# Clone the repository
git clone https://github.com/increff-anupama-r/MS-REQ.git
cd MS-REQ

# Install frontend dependencies
npm install

# Set up backend virtual environment and install dependencies
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd ..
```

### 2. Configure Environment

Create a `.env` file in the root directory by copying the example file.
Open the new `.env` file and add your credentials. The following are essential for the Notion integration to work:

- `NOTION_INTEGRATION_TOKEN`: Your secret token from your Notion integration.
- `NOTION_DB_ID`: The ID of the Notion database where requests will be stored.
- `WEBUI_SECRET_KEY`: A long, random string for session security.

### 3. Run the Application

You need two separate terminal windows to run the frontend and backend servers.

**Terminal 1: Start Backend Server**

```bash
# From the project root directory
cd backend
./dev.sh
```

> The backend API will be running at `http://localhost:8081`.

**Terminal 2: Start Frontend Server**

```bash
# From the project root directory
npm run dev
```

> The frontend application will be available at `http://localhost:5173`.

**Alternate approach**

```bash
./start.sh
```

### 4. Use the Feature

Once the application is running, open `http://localhost:8081` in your browser.
