import zmq
import pickle
import tkinter as tk
from tkinter import messagebox
from tkinter import Toplevel, BOTH, RIGHT, Y, BOTTOM, X
from tkinter import ttk
import pandas as pd

class LogViewer:
  def __init__(self, parent):
    self.window = Toplevel(parent)
    self.window.title("Prediction Log Viewer")
    self.window.geometry("1200x600")
    
    # Create treeview
    self.tree = ttk.Treeview(self.window)
    self.tree.pack(fill=BOTH, expand=True, padx=10, pady=10)
    
    # Add vertical scrollbar
    vsb = tk.Scrollbar(self.window, orient="vertical", command=self.tree.yview)
    vsb.pack(side=RIGHT, fill=Y)
    self.tree.configure(yscrollcommand=vsb.set)
    
    # Add horizontal scrollbar
    hsb = tk.Scrollbar(self.window, orient="horizontal", command=self.tree.xview)
    hsb.pack(side=BOTTOM, fill=X)
    self.tree.configure(xscrollcommand=hsb.set)
    
    self.load_csv_data()

  def load_csv_data(self):
    try:
      # Read CSV file
      df = pd.read_csv('predictions.csv')
      
      # Configure columns
      self.tree["columns"] = list(df.columns)
      self.tree["show"] = "headings"
      
      # Set column headings
      for column in df.columns:
        self.tree.heading(column, text=column)
        # Adjust column width based on content
        max_width = max(
          len(str(column)),
          df[column].astype(str).str.len().max()
        ) * 10
        self.tree.column(column, width=min(max_width, 300))
      
      # Add data rows
      for idx, row in df.iterrows():
        self.tree.insert("", "end", values=list(row))
        
    except FileNotFoundError:
      tk.messagebox.showerror("Error", "No prediction log file found!")
    except Exception as e:
      tk.messagebox.showerror("Error", f"Error loading log data: {str(e)}")

def setup_client_connection(address="tcp://localhost:5555"):
  context = zmq.Context()
  socket = context.socket(zmq.REQ)
  socket.connect(address)
  return socket

def validate_input(data, feature_count):
  if not isinstance(data, list):
    raise ValueError("Input data must be a list.")
  if len(data) != feature_count:
    raise ValueError(f"Input data must have exactly {feature_count} features.")
  if not all(isinstance(i, (int, float)) for i in data):
    raise ValueError("All elements in input data must be integers or floats.")
  if any(i <= 0 for i in data):
    raise ValueError("All elements in input data must be greater than 0.")
  return True

def predict(socket, feature_entries):
  try:
    data_to_predict = [float(entry.get()) for entry in feature_entries]
    feature_count = 8
    validate_input(data_to_predict, feature_count)
    socket.send(pickle.dumps(data_to_predict))
    message = socket.recv()
    result_message = pickle.loads(message)
    messagebox.showinfo("Prediction Result", f"Server Response:\n{result_message}")
    
  except ValueError as ve:
    messagebox.showerror("Validation Error", f"Validation Error: {str(ve)}")
    for entry in feature_entries:
      entry.delete(0, tk.END)
  except zmq.ZMQError as ze:
    messagebox.showerror("Communication Error", f"ZMQ Communication Error: {str(ze)}")
  except Exception as e:
    messagebox.showerror("Error", f"Client Error: {str(e)}")

def download_data():
  def search_and_download():
    try:
      id_to_search = int(id_entry.get())
      df = pd.read_csv('predictions.csv')
      result_df = df[df['id'] == id_to_search]
      if result_df.empty:
        messagebox.showerror("Error", "ID not found in the CSV file.")
      else:
        result_df.to_excel(f'prediction_{id_to_search}.xlsx', index=False)
        messagebox.showinfo("Success", f"Data for ID {id_to_search} has been saved to prediction_{id_to_search}.xlsx")
      download_window.destroy()
    except ValueError:
      messagebox.showerror("Error", "Please enter a valid ID.")
    except Exception as e:
      messagebox.showerror("Error", f"Error: {str(e)}")

  download_window = Toplevel()
  download_window.title("Download Data")
  download_window.geometry("300x150")
  
  tk.Label(download_window, text="ID:").pack(pady=10)
  id_entry = tk.Entry(download_window)
  id_entry.pack(pady=5)
  
  tk.Button(download_window, text="OK", command=search_and_download).pack(pady=10)

def main():
  try:
    socket = setup_client_connection()
  except Exception as e:
    messagebox.showerror("Connection Error", f"Could not connect to server: {str(e)}")
    return

  root = tk.Tk()
  root.title("Diabetes Prediction Client")

  feature_labels = [
    "Pregnancies", "Glucose", "Blood Pressure", "Skin Thickness",
    "Insulin", "BMI", "Diabetes Pedigree Function", "Age"
  ]
  feature_entries = []

  for i, label in enumerate(feature_labels):
    tk.Label(root, text=label).grid(row=i, column=0, padx=10, pady=5, sticky="w")
    entry = tk.Entry(root)
    entry.grid(row=i, column=1, padx=10, pady=5)
    feature_entries.append(entry)

  predict_button = tk.Button(
    root, text="Predict",
    command=lambda: predict(socket, feature_entries)
  )
  predict_button.grid(row=len(feature_labels), column=0, columnspan=2, pady=10)
  
  view_log_button = tk.Button(
    root, text="View Prediction Log",
    command=lambda: LogViewer(root)
  )
  view_log_button.grid(row=len(feature_labels)+1, column=0, columnspan=2, pady=10)

  download_button = tk.Button(
    root, text="Download",
    command=download_data
  )
  download_button.grid(row=len(feature_labels)+2, column=0, columnspan=2, pady=10)

  root.mainloop()

if __name__ == "__main__":
  main()