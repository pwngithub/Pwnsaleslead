# Pioneer Sales Lead App – v19.10.26

This is a **minimal demo build** of the Pioneer Sales Lead App.  
It includes a **CSV seed file** with 20 realistic tickets and auto-load support.  

---

## 🚀 Features
- Automatically loads `saleslead_seed.csv` on startup.  
- If the seed file is missing, the app falls back to the **JotForm API**.  
- Displays all tickets in a clean **preview table**.  
- Ready for expansion with **Add Ticket, Edit Ticket, KPI** tabs.  

---

## 📂 File Structure
```
pwnsaleslead_v19_10_26.zip
├── app.py                # Streamlit app
├── saleslead_seed.csv    # 20 realistic seed tickets
├── README.md             # Instructions
```

---

## ▶️ How to Run
1. Unzip the package.  
2. Install requirements (you need Python 3.9+):  
   ```bash
   pip install streamlit pandas
   ```
3. Run the app:  
   ```bash
   streamlit run app.py
   ```

---

## 📝 Usage Notes
- On startup, the app checks for `saleslead_seed.csv`.  
  - If found → loads tickets from the CSV (demo mode).  
  - If not → falls back to fetching tickets from JotForm API.  
- To reset data, simply replace or delete `saleslead_seed.csv`.  
