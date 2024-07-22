from pathlib import Path
import tkinter as tk
from tkinter import scrolledtext
import serial
import time
import serial.tools.list_ports 
import threading
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.animation as animation

class MTQtesterApp:
    OUTPUT_PATH = Path(__file__).parent
    ASSETS_PATH = OUTPUT_PATH / Path(r"D:\MTQ_measure\build\assets\frame0")
    def __init__(self, root):
        self.root = root
        self.root.geometry("1032x744")
        self.root.configure(bg = "#FFFFFF")
        self.root.title("MTQ Tester")
        # serial connection attribute
        self.serial_connection = None
        self.running = False

        # MTQ control vals
        self.MTQ_max_pwr = 2000
        self.MTQ_min_pwr = 0
        self.header = b'#S'
        self.terminator = b'\n'
        self.MTQ_ctrl_commands = {
            "RUN": [b'\x08', b'\x01'],
            "Data Stream ON": [b'\x20', b'\x03'],
            "Data Stream OFF": [b'\x20', b'\x00'],
            "MTQ ON": [b'\x3A', b'\x01'],
            "MTQ Set Power": [b'\x38',b'\x00'],
            "MTQ OFF": [b'\x3A', b'\x00'],
            "STOP": [b'\x08', b'\x00']
        }

        # list to store plotting data
        self.timestamps = []
        self.y1_data = []
        self.y2_data = []
        self.y3_data = []
        
        canvas = tk.Canvas(self.root,bg = "#344865",height = 744,width = 1032,bd = 0,highlightthickness = 0,relief = "ridge")
        canvas.place(x = 0, y = 0)

        # static rectangles
        canvas.create_rectangle(0.0,0.0,1032.0,744.0,fill="#344865",outline="")
        canvas.create_rectangle(410.0,531.0,1015.0,731.0,fill="#3E5577",outline="")
        canvas.create_rectangle(618.0,34.0,748.0,68.0,fill="#344865",outline="")
        canvas.create_rectangle(748.0,34.0,878.0,68.0,fill="#344865",outline="")
        canvas.create_rectangle(5.0,92.0,394.0,670.0,fill="#344865",outline="")
        canvas.create_rectangle(6.0,687.0,270.0,726.0,fill="#344865",outline="")
        canvas.create_rectangle(405.0,91.0,1026.0,524.0,fill="#344865",outline="")
        canvas.create_rectangle(11.0,96.0,390.0,665.0,fill="#D9D9D9",outline="")   # Receive console
        canvas.create_rectangle(410.0,96.0,1019.0,520.0,fill="#D9D9D9",outline="") # Graph
        canvas.create_rectangle(435.0,554.0,749.0,590.0,fill="#3F5677",outline="")
        canvas.create_rectangle(435.0,592.0,747.0,628.0,fill="#3F5677",outline="")
        canvas.create_rectangle(433.0,628.0,748.0,669.0,fill="#3F5677",outline="")
        canvas.create_rectangle(433.0,686.0,838.0,726.0,fill="#3F5677",outline="")
        canvas.create_rectangle(747.0,550.0,838.0,592.0,fill="#3F5677",outline="")
        canvas.create_rectangle(868.0,601.0,1003.0,639.0,fill="#3F5677",outline="")
        canvas.create_rectangle(749.0,592.0,835.0,627.0,fill="#3F5677",outline="")
        canvas.create_rectangle(749.0,629.0,834.0,667.0,fill="#3F5677",outline="")
        canvas.create_rectangle(850.9999939241166,536.0,852.0,676.0,fill="#FFFFFF",outline="")

        # Static texts
        canvas.create_text(624.0, 15.0, anchor="nw", text="COM Port", fill="#FFFFFF", font=("Inter Medium", 15 * -1))
        canvas.create_text(751.0, 15.0, anchor="nw", text="Baud Rate", fill="#FFFFFF", font=("Inter Medium", 15 * -1))
        canvas.create_text(11.0,74.0, anchor="nw", text="Receive Console", fill="#FFFFFF", font=("Inter Medium", 15 * -1))
        canvas.create_text(410.0, 74.0, anchor="nw", text="Gyro Data Visualization", fill="#FFFFFF", font=("Inter Medium", 15 * -1))
        canvas.create_text(11.0, 15.0, anchor="nw", text="MTQ Tester Interface", fill="#FFFFFF", font=("Inter ExtraBold", 24 * -1))
        canvas.create_text( 439.0, 669.0, anchor="nw", text="Transmit Console", fill="#FFFFFF", font=("Inter Medium", 15 * -1))
        canvas.create_text(11.0, 669.0, anchor="nw", text="Output Path", fill="#FFFFFF", font=("Inter Medium", 15 * -1))
        canvas.create_text(439.0, 537.0, anchor="nw", text="Set MTQ Power", fill="#FFFFFF", font=("Inter Medium", 15 * -1))
        canvas.create_text(872.0, 580.0, anchor="nw", text="Select Command", fill="#FFFFFF", font=("Inter Medium", 15 * -1))
        canvas.create_text(422.0, 561.0, anchor="nw", text="X", fill="#FFFFFF", font=("Inter Medium", 15 * -1))
        canvas.create_text(422.0, 599.0, anchor="nw", text="y", fill="#FFFFFF", font=("Inter Medium", 15 * -1))
        canvas.create_text(422.0, 637.0, anchor="nw", text="z", fill="#FFFFFF", font=("Inter Medium", 15 * -1))

        # Create sliders
        self.slider_pwrX = tk.Scale(root, from_=self.MTQ_min_pwr, to=self.MTQ_max_pwr, orient=tk.HORIZONTAL, command=self.update_tx_CMD)
        self.slider_pwrX.place(x=439.0, y=557.0, width=395.0, height=31.0)

        self.slider_pwrY = tk.Scale(root, from_=self.MTQ_min_pwr, to=self.MTQ_max_pwr, orient=tk.HORIZONTAL, command=self.update_tx_CMD)
        self.slider_pwrY.place(x=439.0, y=595.0, width=395.0, height=31.0)

        self.slider_pwrZ = tk.Scale(root, from_=self.MTQ_min_pwr, to=self.MTQ_max_pwr, orient=tk.HORIZONTAL, command=self.update_tx_CMD)
        self.slider_pwrZ.place(x=439.0, y=632.0, width=395.0, height=31.0)

        # COM port selection option menu
        self.available_ports = self.get_com_ports()
        self.selected_port = tk.StringVar(self.root)
        if self.available_ports: self.selected_port.set(self.available_ports[0])  
        else: self.selected_port.set("No COM ports available")
        self.com_menu = tk.OptionMenu(self.root, self.selected_port, *self.available_ports, command=self.disconenct_to_serial)
        self.com_menu.place(x=624, y=39, width=110, height=25)

        # baud rate selection option menu
        self.baud_rates = ["9600", "14400", "19200", "38400", "57600", "115200"]
        self.selected_baud = tk.StringVar(self.root)
        self.selected_baud.set(self.baud_rates[0])  # Default value
        self.baud_rate_menu = tk.OptionMenu(self.root, self.selected_baud, *self.baud_rates, command=self.disconenct_to_serial)
        self.baud_rate_menu.place(x=751, y=39, width=110, height=25)

        # command selection option menu
        self.selected_command = tk.StringVar(self.root)
        self.selected_command.set(list(self.MTQ_ctrl_commands.keys())[0])  # Default value, first key of the command dictionary
        self.cmd_select_menu = tk.OptionMenu(self.root, self.selected_command, *self.MTQ_ctrl_commands.keys(), command=self.update_tx_CMD)
        self.cmd_select_menu.place(x=870, y=604, width=120, height=29)

        # tx data entry box
        self.entry_image_3 = tk.PhotoImage(file=self.relative_to_assets("entry_3.png"))  # Keep a reference in self
        self.entry_txConsole_bg = canvas.create_image(635.5,705.5,image=self.entry_image_3)
        self.entry_txConsole = tk.Entry(self.root, bd=0, bg="#D9D9D9", fg="#000716", highlightthickness=0)
        self.entry_txConsole.place(x=447.0, y=693.0, width=382.0, height=28.0)

        # output path entry box
        self.entry_image_4 = tk.PhotoImage(file=self.relative_to_assets("entry_4.png"))
        self.entry_outpath_bg = canvas.create_image(139.0,705.5,image=self.entry_image_4)
        self.entry_outPath = tk.Entry(bd=0,bg="#D9D9D9",fg="#000716",highlightthickness=0)
        self.entry_outPath.place(x=16.0,y=693.0,width=246.0,height=28.0)
        self.entry_outPath.insert(0, str(self.OUTPUT_PATH))  # default output folder

        # notification label
        self.notification_label = tk.Label(self.root, text="", fg="red", bg="#344865", font=("Inter Medium", 12))
        self.notification_label.place(x=629.0, y=70.0)

        # Browse folder button
        self.button_image_browse = tk.PhotoImage(file=self.relative_to_assets("folder_icon.png"))
        self.btn_browse = tk.Button(image=self.button_image_browse, borderwidth=0, highlightthickness=0, command=self.browwse_output_folder, relief="flat")
        self.btn_browse.place(x=235.0,y=693.0)

        # connect button
        self.button_image_1 = tk.PhotoImage(file=self.relative_to_assets("button_1.png"))
        self.btn_connect = tk.Button(image=self.button_image_1,borderwidth=0,highlightthickness=0,command=self.connect_to_serial,relief="flat")
        self.btn_connect.place(x=884.0,y=31.0,width=131.0,height=39.0)
        self.button_image_hover_1 = tk.PhotoImage(file=self.relative_to_assets("button_hover_1.png"))
        button_image_connected = tk.PhotoImage(file=self.relative_to_assets("button_connected_1.png"))
        # def btn_connect_hover(e):self.btn_connect.config(image=self.button_image_hover_1)
        # def btn_connect_leave(e):self.btn_connect.config(image=self.button_image_1)
        self.button_image_connected = tk.PhotoImage(file=self.relative_to_assets("button_connected_1.png"))
        # self.btn_connect.bind('<Enter>', btn_connect_hover)
        # self.btn_connect.bind('<Leave>', btn_connect_leave)

        # send button
        self.button_image_2 = tk.PhotoImage(file=self.relative_to_assets("button_2.png"))
        self.btn_send = tk.Button(image=self.button_image_2,borderwidth=0,highlightthickness=0,command=self.send_serial,relief="flat")
        self.btn_send.place(x=867.0,y=686.0,width=136.0,height=39.0)
        self.button_image_hover_2 = tk.PhotoImage(file=self.relative_to_assets("button_hover_2.png"))
        def btn_send_hover(e):self.btn_send.config(image=self.button_image_hover_2)
        def btn_send_leave(e):self.btn_send.config(image=self.button_image_2)
        self.btn_send.bind('<Enter>', btn_send_hover)
        self.btn_send.bind('<Leave>', btn_send_leave)

        # generate CSV button
        self.button_image_3 = tk.PhotoImage(file=self.relative_to_assets("button_3.png"))
        self.btn_saveCSV = tk.Button(image=self.button_image_3,borderwidth=0,highlightthickness=0,command=self.save_to_csv,relief="flat")
        self.btn_saveCSV.place(x=267.0,y=680.0,width=133.0,height=46.0)
        self.button_image_hover_3 = tk.PhotoImage(file=self.relative_to_assets("button_hover_3.png"))
        def btn_saveCSV_hover(e):self.btn_saveCSV.config(image=self.button_image_hover_3)
        def btn_saveCSV_leave(e):self.btn_saveCSV.config(image=self.button_image_3)
        self.btn_saveCSV.bind('<Enter>', btn_saveCSV_hover)
        self.btn_saveCSV.bind('<Leave>', btn_saveCSV_leave)

        # serial console  
        console_frame = tk.Frame(self.root)
        console_frame.place(x=11, y=96, width=378, height=569)
        self.console_text_area = scrolledtext.ScrolledText(console_frame, wrap=tk.WORD)
        self.console_text_area.place(x=5, y=5, width=368, height=559)  # Adjust dimensions as needed
        self.console_text_area.tag_config('timestamp', foreground='grey')
        self.console_text_area.tag_config('received', foreground='black')
        self.console_text_area.tag_config('sent', foreground='blue')

        # Visualisation area
        self.fig, self.ax = plt.subplots()
        self.canvas = FigureCanvasTkAgg(self.fig, master=root)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.place(x=415, y=101, width=599, height=414)  
        
    def relative_to_assets(self, path: str) -> Path:
        return self.ASSETS_PATH / Path(path)
    
    def encode_command(self, reg_id, data):
        command = bytearray()
        command.extend(self.header)
        command.extend(reg_id)
        if isinstance(data, int):
            command.append(data)
        elif isinstance(data, (bytearray, bytes)):
            command += data
        elif isinstance(data, (list, tuple)):
            for value in data:
                command.extend(value.to_bytes(2, byteorder='little', signed=True))
        command.extend(self.terminator)
        return command
    
    def update_tx_CMD(self, event=None):
        selected_command = self.selected_command.get()
        cmd_regID = list(self.MTQ_ctrl_commands.get(selected_command))[0]
        if selected_command != "MTQ Set Power":
            cmd_data = list(self.MTQ_ctrl_commands.get(selected_command))[1]
        else:
            cmd_data = [self.slider_pwrX.get(), self.slider_pwrY.get(), self.slider_pwrZ.get()]
        command = self.encode_command(cmd_regID, cmd_data)
        self.entry_txConsole.delete(0, tk.END)
        self.entry_txConsole.insert(0, command.hex())
            
    def browwse_output_folder(self):
        self.selected_folder_path = tk.filedialog.askdirectory()
        if self.selected_folder_path:
            self.entry_outPath.delete(0, tk.END)
            self.entry_outPath.insert(0, self.selected_folder_path)
    
    def get_com_ports(self):
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]
    
    def disconenct_to_serial(self, event=None):
         if self.running:
            self.running = False
            time.sleep(0.1)
            self.serial_connection.close()
            self.thread.join()  # Wait for the thread to finish
            self.btn_connect.config(image=self.button_image_1)

    def connect_to_serial(self):
        self.disconenct_to_serial()
        selected_port = self.selected_port.get()
        selected_baud_rate = self.selected_baud.get()
        try:
            self.serial_connection = serial.Serial(selected_port, selected_baud_rate)
            print(f"Connected to {selected_port} at {selected_baud_rate} baud rate.")
            self.notification_label.config(text="")
            self.running = True
            self.thread = threading.Thread(target=self.read_serial, daemon=False)
            self.thread.start()
            self.btn_connect.config(image=self.button_image_connected)
            self.notification_label.config(fg="green")
            self.notification_label.config(text="Connected to "+selected_port+" Baud rate: "+selected_baud_rate)
            
            
        except serial.SerialException as e:
            print(f"Failed to connect to {selected_port} at {selected_baud_rate} baud rate: {e}")
            self.notification_label.config(text="Error opening serial port: "+selected_port)

    def read_serial(self):
        while self.running:
            try:
                if self.serial_connection.in_waiting > 0:
                    data = self.serial_connection.readline().decode('utf-8').strip()
                    self.display_message(data, 'received')
                    self.process_and_plot_data(data)
            except serial.SerialException as e:
                print("Serial error:", e)                

    def send_serial(self):
        data_to_send = self.entry_txConsole.get()
        if self.running:
            if data_to_send:
                byte_data = bytearray.fromhex(data_to_send)
                self.serial_connection.write(byte_data)
                self.display_message(data_to_send, 'sent')
        else:
                self.notification_label.config(text="Device not connected yet")

    def display_message(self, message, msg_type):
        timestamp = datetime.now().strftime("%H:%M:%S,")
        self.console_text_area.insert(tk.END, f"{timestamp} ", 'timestamp')
        self.console_text_area.insert(tk.END, message + "\n", msg_type)
        self.console_text_area.yview(tk.END)

    def process_and_plot_data(self, data):
        try:
            values = list(map(float, data.strip().split(',')))
            if len(values) == 4:
                timestamp = values[0]
                y1 = values[1]
                y2 = values[2]
                y3 = values[3]

                # Append new data
                self.timestamps.append((datetime.now()).strftime('%M:%S'))  # Use system timestamp
                # self.timestamps.append(timestamp)  # Use MTQ timestamp
                self.y1_data.append(y1)
                self.y2_data.append(y2)
                self.y3_data.append(y3)

                #limit the number of points
                if len(self.timestamps) > 100:
                    self.timestamps.pop(0)
                    self.y1_data.pop(0)
                    self.y2_data.pop(0)
                    self.y3_data.pop(0)

                # Clear and update the plot
                self.ax.cla()
                self.ax.plot(self.timestamps, self.y1_data, label='Gyro X', color='red')
                self.ax.plot(self.timestamps, self.y2_data, label='Gyro Y', color='green')
                self.ax.plot(self.timestamps, self.y3_data, label='Gyro Z', color='blue')
                self.ax.legend(loc='upper right')
                self.ax.set_xlabel('Timestamp')
                self.ax.set_ylabel('Gyro Values')
                # self.ax.set_title('Real-time Data Plot')
                self.ax.tick_params(axis='x')
                self.canvas.draw()
        except ValueError:
            pass  # Handle invalid data

    def save_to_csv(self):
        output_path = self.entry_outPath.get()
        output_path += '\output.csv'
        data = self.console_text_area.get("1.0", tk.END).strip().split('\n')
        if len(data) > 1:
            try:
                with open(output_path, mode='w', newline='') as csvfile:
                    csvfile.write('Timestamp,'+'MTQ time,'+"Gyro X,"+"Gyro Y,"+"Gyro Z\n")
                    for line in data:
                        csvfile.write(str(line) + '\n')
                print(f"Data saved to {output_path}")
                self.notification_label.config(text="")
            except Exception as e:
                self.notification_label.config(text="Error Generating CSV data")
        else:
            self.notification_label.config(text="No data to save")

    def on_closing(self):
        if self.running:
            self.running = False
            time.sleep(0.1)
            self.serial_connection.close()
            self.thread.join() 
        self.root.quit()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = MTQtesterApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
