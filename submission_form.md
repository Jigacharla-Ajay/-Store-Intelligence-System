# Hackathon Submission Details

Here is the content you can copy and paste directly into your submission form!

---

### **Title**
**Purplle Store Intelligence — Real-Time CCTV Analytics**

---

### **Description**
A complete, end-to-end Store Intelligence Pipeline built for the Purplle Tech Challenge 2026. This system transforms raw CCTV video feeds into actionable, real-time retail analytics. 

**Key Features:**
1. **Computer Vision Pipeline**: Utilizes YOLOv8 and an IoU Centroid Tracker to detect and track individuals across multiple camera feeds. It maps pixel coordinates to physical store zones (e.g., Skincare, Billing) using polygon ray-casting.
2. **High-Performance API**: A production-grade, async FastAPI backend built on PostgreSQL and Redis. It features idempotent batch ingestion capable of handling 500+ events per second.
3. **Advanced Analytics**: Computes real-time conversion funnels, dynamic zone heatmaps, queue abandonment rates, and average dwell times.
4. **Automated Anomaly Detection**: Actively monitors store health, instantly flagging issues like dead zones, severe queue spikes, and offline camera feeds.
5. **Real-Time Dashboard**: A clean, responsive React frontend (Vite) that connects via WebSockets to provide a live, zero-latency operational view of the store.

The entire solution is 100% Docker-containerized, boasts comprehensive design documentation, and is backed by a robust test suite (38/38 passing integration tests).

---

### **Theme**
Purplle Tech Challenge 2026 — Round 2 Problem Statement

---

### **Snapshots**
*(You will need to take 2-3 screenshots of the React Dashboard running on your screen and upload them here!)*

---

### **Video URL / Demo Link / Repository URL**
*(If you are hosting the code on GitHub or recording a Loom video of the dashboard, paste those links here. If not, you can just write "N/A - See Source Code Zip" or leave them blank if they are optional).*

---

### **Source Code**
*(Right-click your `purplle` folder, compress/zip it, and upload the `.zip` file here. Make sure to delete the `videos/` folder inside if the zip file is too large!)*

---

### **Instructions to Run**
**Prerequisites:** Ensure Docker Desktop is installed and running on your machine.

**Step 1:** Extract the provided source code zip file.
**Step 2:** Open a terminal/command prompt inside the root project directory.
**Step 3:** Boot the entire application stack by running the following command:
```bash
docker compose up -d --build
```
**Step 4:** Wait approximately 15-20 seconds for the database to seed and the containers to fully boot.
**Step 5:** The system is now fully operational! You can access the components at the following local URLs:
*   **Real-Time Dashboard:** [http://localhost:3000](http://localhost:3000)
*   **API Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)
*   **Pipeline Logs:** Run `docker logs -f store_intelligence_pipeline` in your terminal to watch the computer vision model process frames in real-time.

To gracefully shut down the application, run: `docker compose down`
