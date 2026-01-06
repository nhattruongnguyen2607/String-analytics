# Streamlit Merge & Performance Dashboard (Modular)

## Files
- `app.py`: entrypoint chạy Streamlit
- `functions.py`: toàn bộ helper functions (I/O, merge, analysis, UI render)

## UI
- Sidebar có 2 tab:
  - **MERGE**: upload/merge và bấm Run Merge
  - **ANALYSIS**: filter dạng cascade (Plant → Inverter → Azimuth → Capacity) + nút Generate

## Run
```bash
pip install -r requirements.txt
streamlit run app.py
```
