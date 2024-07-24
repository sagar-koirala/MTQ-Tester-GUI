import customtkinter
from pathlib import Path
import serial
import time
from datetime import datetime
from PIL import Image, ImageTk
import serial.tools.list_ports 
import threading
import queue
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# customtkinter.set_appearance_mode("Light")

class MTQtesterApp(customtkinter.CTk):
    OUTPUT_PATH = Path(__file__).parent
    ASSETS_PATH = OUTPUT_PATH / Path(r"D:\MTQ_measure\build\assets\frame0")
    def __init__(self):
        super().__init__()

        self.geometry("1032x744")
        # self.wm_resizable(width=False, height=False)
        self.title("MTQ Tester")

        self.received_dataBuffer = b''

        # serial connection attribute
        self.serial_connection = None
        self.deviceConnected = False

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

        # plotter vars
        self.lines = {}
        self.timestamps = []
        self.plot_data_queue = queue.Queue()
        self.read_thread = None
        self.plot_thread = None
        self.stop_event = threading.Event()
        self.lock = threading.Lock()

        # Set up the grid layout
        self.grid_rowconfigure((0,1,4,5), weight=1)
        self.grid_rowconfigure(2, weight=9)
        self.grid_rowconfigure(3, weight=4)
        self.grid_columnconfigure((0,1), weight=1)

        # App label frame
        self.app_label_frame = customtkinter.CTkFrame(self, height=38, corner_radius=10, fg_color="#242424")
        self.app_label_frame.grid(row = 0, column = 0,columnspan =2,padx=10, pady=0, sticky ="nsew")
        # App label
        self.app_label = customtkinter.CTkLabel(self.app_label_frame, text="MTQ Tester Interface",font=customtkinter.CTkFont(family="Inter" ,size = 24, weight="bold"))
        self.app_label.grid(row=0, column=0, sticky = "w")

        # Connection Settings
        self.com_port_dropdown = customtkinter.CTkComboBox(self.app_label_frame, values=self.get_com_ports(), command=self.disconenct_to_serial)
        self.com_port_dropdown.grid(row=0, column=1, pady=5, padx=(0,0))

        self.baud_rate_dropdown = customtkinter.CTkComboBox(self.app_label_frame, values=["9600", "19200", "38400", "57600", "115200"], command=self.disconenct_to_serial)
        self.baud_rate_dropdown.grid(row=0, column=1, pady=5, padx=(295,0))

        self.connect_button = customtkinter.CTkButton(self.app_label_frame, text="Connect",command=self.connect_to_serial)
        self.connect_button.grid(row=0, column=1, pady=5, padx=(618,0),sticky="e")
        self.connect_button_defColor = self.connect_button.cget("fg_color")
        self.connect_button_defHoverColor = self.connect_button.cget("hover_color")
        # Console frame
        self.console_frame = customtkinter.CTkFrame(self,width=494, height=615, corner_radius=10, fg_color="#2B2B2B")
        self.console_frame.grid(row = 1, column = 0,rowspan = 3, padx=(10,5), pady=(0,5),sticky ="nsew")
        # console hex/utf8 option menu
        self.console_dtype_menu = customtkinter.CTkSegmentedButton(self.console_frame,width=300)
        self.console_dtype_menu.grid(row=0, column=0, padx=(10, 5), pady=6, sticky="nws")
        self.console_dtype_menu.configure(values=["Utf8","Hex","Dec","Binary"])
        self.console_dtype_menu.set("Utf8")
        # Clear button
        self.btn_clear_console = customtkinter.CTkButton(self.console_frame, text="Clear", width=60,fg_color='transparent',border_color="#949A9f", hover_color = "grey",border_width=2,command=self.clear_console)
        self.btn_clear_console.grid(row=0, column = 0, padx=(0,70), pady=6, sticky="e")
        # lock button
        self.btn_lock = customtkinter.CTkButton(self.console_frame, text="Lock", width=60,fg_color='transparent',border_color="#949A9f", hover_color = "grey",border_width=2, command=self.toggle_scroll_lock)
        self.btn_lock.grid(row=0, column = 0, padx=(0,5), pady=6, sticky="e")
        # create scrollable textbox
        self.console_textbox = customtkinter.CTkTextbox(self.console_frame,height=567, width=480 , activate_scrollbars=False,font=customtkinter.CTkFont(family="Inter" ,size = 13, weight="normal"))
        self.console_textbox.grid(row=1, column=0,padx=(7,5),pady=(0,5),sticky="nsew")
        self.textbox_scrollbar = customtkinter.CTkScrollbar(self.console_frame,bg_color="#1E1e1e", command=self.console_textbox.yview, width=15)
        self.textbox_scrollbar.grid(row=1, column=0,padx=10, pady = (5,10),sticky="nse")
        self.console_textbox.configure(yscrollcommand=self.textbox_scrollbar.set)
        self.console_textbox_scroll = True
        self.console_textbox.tag_config('timestamp', foreground='grey')
        self.console_textbox.tag_config('received', foreground='white')
        self.console_textbox.tag_config('sent', foreground='yellow')
        self.console_textbox.tag_config('error', foreground = "red")

        # output_browse_frameframe
        self.output_path_frame = customtkinter.CTkFrame(self, width=494, height=66, corner_radius=10, fg_color="#242424")
        self.output_path_frame.grid(row = 4, column = 0,padx=(10,5), sticky ="nsew")

        self.output_path_label = customtkinter.CTkLabel(self.output_path_frame, text="Output Path:",font=customtkinter.CTkFont(family="Inter" ,size = 16, weight="bold"))
        self.output_path_label.grid(row = 0, column = 0, sticky = "w")
        self.output_path_entry = customtkinter.CTkEntry(self.output_path_frame, width=380)
        self.output_path_entry.grid(row = 1, column = 0, sticky = "w")
        self.output_path_entry.insert(0, str(self.OUTPUT_PATH))  # default output folder
        # browse button
        self.button_image_browse = customtkinter.CTkImage(Image.open(self.relative_to_assets("folder_browse_icon.png")), size=(21,16))
        self.btn_browse_folder = customtkinter.CTkButton(self.output_path_entry, image=self.button_image_browse, text=None, width=10, height=5, fg_color='transparent', hover_color="grey", command=self.browwse_output_folder)
        self.btn_browse_folder.grid(row=0, column = 0, padx=(0,5), pady=0, sticky = "e")
        self.save_data_button = customtkinter.CTkButton(self.output_path_frame, text="Save Data", width=100,command=self.save_data)
        self.save_data_button.grid(row = 1, column = 1, padx=(15,0),sticky ="e")

        # plotter frame
        self.plotter_frame = customtkinter.CTkFrame(self, width=502, height=486, corner_radius=10, fg_color="#2B2B2B")
        self.plotter_frame.grid(row = 1, column = 1,rowspan = 2,pady=(0,5), padx=(5,10),sticky ="nsew")

        # plot value checkboxes frame
        self.entry_frame = customtkinter.CTkFrame(master=self.plotter_frame, height=20)
        self.entry_frame.grid(row=0, column=0, pady=6, padx=(10,0), sticky="w")

        self.btn_clear_chart = customtkinter.CTkButton(self.plotter_frame, text="Clear", width=60,fg_color='transparent',border_color="#949A9f", hover_color = "grey",border_width=2,command=self.clear_chart)
        self.btn_clear_chart.grid(row=0, column = 0, padx=(10,10), pady=6, sticky="e")

        # graph area
        self.graph_frame = customtkinter.CTkFrame(self.plotter_frame, width=492, height=425, corner_radius=10, fg_color="#1E1E1E")
        self.graph_frame.grid(row = 1, column = 0,rowspan = 2,pady=(0,6), padx=(7,5),sticky ="nsew")
    
        self.fig, self.ax = plt.subplots(figsize=(self.graph_frame.winfo_width()*4.9 , self.graph_frame.winfo_height()*4),facecolor="#1E1E1E")
        self.ax.set_facecolor("#1E1e1e")
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.graph_frame)
        self.canvas.get_tk_widget().grid(row=0,column=0, padx=1, pady=5, sticky="sew")
        self.ax.spines['left'].set_color("grey")
        self.ax.spines['bottom'].set_color("grey")
        self.ax.spines['right'].set_color("#1E1e1e")
        self.ax.spines['top'].set_color("#1E1e1e")
        self.ax.tick_params(axis='x', colors='grey')
        self.ax.tick_params(axis='y', colors='grey')

        # CMD selector frame
        self.cmdSel_frame = customtkinter.CTkFrame(self, width=502, height=115, corner_radius=10, fg_color="#2B2B2B")
        self.cmdSel_frame.grid(row = 3, column = 1,pady=(5,5), padx=(5,10),sticky ="nsew")

        self.pwrsel_label = customtkinter.CTkLabel(self.cmdSel_frame, text="Select MTQ power", font=customtkinter.CTkFont(family="Inter" ,size = 16, weight="bold"))
        self.pwrsel_label.grid(row=0, column=0,columnspan=2,padx=(10,0), sticky = "w")
        self.X_label = customtkinter.CTkLabel(self.cmdSel_frame, text="X", font=customtkinter.CTkFont(family="Inter" ,size = 16, weight="normal"))
        self.X_label.grid(row=1, column=0,padx=(10,0), pady=2,sticky = "w")
        self.Y_label = customtkinter.CTkLabel(self.cmdSel_frame, text="Y", font=customtkinter.CTkFont(family="Inter" ,size = 16, weight="normal"))
        self.Y_label.grid(row=2, column=0,padx=(10,0), pady=2,sticky = "w")
        self.Z_label = customtkinter.CTkLabel(self.cmdSel_frame, text="Z", font=customtkinter.CTkFont(family="Inter" ,size = 16, weight="normal"))
        self.Z_label.grid(row=3, column=0,padx=(10,0),pady=2, sticky = "w")

        self.slider_X = customtkinter.CTkSlider(self.cmdSel_frame, from_=self.MTQ_min_pwr, to=self.MTQ_max_pwr, number_of_steps=self.MTQ_max_pwr, height=25, width=250, command=self.update_slider_vals)
        self.slider_X.grid(row=1, column=1, padx=(5, 5),  sticky="w")
        self.slider_Y = customtkinter.CTkSlider(self.cmdSel_frame, from_=self.MTQ_min_pwr, to=self.MTQ_max_pwr, number_of_steps=self.MTQ_max_pwr,height=25, width=250, command=self.update_slider_vals)
        self.slider_Y.grid(row=2, column=1, padx=(5, 5),  sticky="w")
        self.slider_Z = customtkinter.CTkSlider(self.cmdSel_frame, from_=self.MTQ_min_pwr, to=self.MTQ_max_pwr, number_of_steps=self.MTQ_max_pwr,height=25, width=250, command=self.update_slider_vals)
        self.slider_Z.grid(row=3, column=1, padx=(5, 5), sticky="w")
        self.pwrX_label = customtkinter.CTkEntry(self.cmdSel_frame, placeholder_text=str(int(self.slider_X.get())), width=50, border_color='#2B2B2B',fg_color='transparent', font=customtkinter.CTkFont(family="Inter" ,size = 12, weight="bold"))
        self.pwrX_label.grid(row=1, column=2, sticky = "w")
        self.pwrY_label = customtkinter.CTkEntry(self.cmdSel_frame, placeholder_text=str(int(self.slider_Y.get())), width=50, border_color='#2B2B2B',fg_color='transparent',font=customtkinter.CTkFont(family="Inter" ,size = 12, weight="bold"))
        self.pwrY_label.grid(row=2, column=2, sticky = "w")
        self.pwrZ_label = customtkinter.CTkEntry(self.cmdSel_frame, placeholder_text=str(int(self.slider_Z.get())),width=50, border_color='#2B2B2B',fg_color='transparent', font=customtkinter.CTkFont(family="Inter" ,size = 12, weight="bold"))
        self.pwrZ_label.grid(row=3, column=2, sticky = "w")



        self.pwrsel_label = customtkinter.CTkLabel(self.cmdSel_frame, text="Select Command", font=customtkinter.CTkFont(family="Inter" ,size = 16, weight="bold"))
        self.pwrsel_label.grid(row=0, column=3,rowspan=2,padx=(20,0), sticky="wse")
        self.cmdSel_dropdown = customtkinter.CTkComboBox(self.cmdSel_frame, values=list(self.MTQ_ctrl_commands.keys()), command=self.update_tx_CMD)
        self.cmdSel_dropdown.grid(row=2, column=3,padx=(20,0), sticky = "wne")


        # tx_console_frame frame
        self.tx_console_frame = customtkinter.CTkFrame(self, width=502, height=92, corner_radius=10, fg_color="#242424")
        self.tx_console_frame.grid(row = 4, column = 1,padx=(5,10),pady=(0,0),sticky ="nsew")
        self.tx_console_label = customtkinter.CTkLabel(self.tx_console_frame, text="Tx Console", font=customtkinter.CTkFont(family="Inter" ,size = 16, weight="bold"))
        self.tx_console_label.grid(row=0, column=0, sticky = "w")
        self.tx_console_entry = customtkinter.CTkEntry(self.tx_console_frame, placeholder_text="Select Tx Command", width=389)
        self.tx_console_entry.grid(row=1, column=0, pady=0, sticky = "w")
        self.tx_console_send_button = customtkinter.CTkButton(self.tx_console_frame, text="Send", width=100, command=self.send_serial)
        self.tx_console_send_button.grid(row=1, column=1,padx=(15,0),pady=0,sticky = "e")

        # tx hex/utf8 option menu
        self.tx_console_dtype_menu = customtkinter.CTkSegmentedButton(self.tx_console_frame,width=300, height=16)
        self.tx_console_dtype_menu.grid(row=0, column=0, pady=(0,5), sticky="e")
        self.tx_console_dtype_menu.configure(values=[" Utf8 ", " Hex ","Dec","Binary"])
        self.tx_console_dtype_menu.set(" Hex ")

        # message frame
        self.message_frame = customtkinter.CTkFrame(self, fg_color="#242424")
        self.message_frame.grid(row = 5, column = 0, columnspan =2, padx=(10,0),sticky="nswe")
        self.message_box = customtkinter.CTkLabel(self.message_frame, text="Connect to begin", font=customtkinter.CTkFont(family="Inter" ,size = 12))
        self.message_box.grid(sticky = "w")

    def relative_to_assets(self, path: str) -> Path:
        return self.ASSETS_PATH / Path(path)
    
    def get_com_ports(self):
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]
    
    def browwse_output_folder(self):
        self.selected_folder_path = customtkinter.filedialog.askdirectory()
        if self.selected_folder_path:
            self.output_path_entry.delete(0, customtkinter.END)
            self.output_path_entry.insert(0, self.selected_folder_path)

    def disconenct_to_serial(self, event=None):
        if self.deviceConnected:
            self.deviceConnected = False
            self.stop_event.set()
            if self.read_thread and self.read_thread.is_alive():
                self.read_thread.join(timeout=1)
            if self.plot_thread and self.plot_thread.is_alive():
                self.plot_thread.join(timeout=1)
            # time.sleep(0.1)
            self.serial_connection.close()
            self.message_box.configure(text="Device disconnected")
            self.connect_button.configure(text="connect", fg_color=self.connect_button_defColor, hover_color="#144870")

    def connect_to_serial(self):
        if not self.deviceConnected:
            selected_port = self.com_port_dropdown.get()
            selected_baud_rate = self.baud_rate_dropdown.get()
            try:
                self.serial_connection = serial.Serial(selected_port, selected_baud_rate)
                self.deviceConnected = True
                if self.read_thread is None or not self.read_thread.is_alive():
                    self.stop_event.clear()
                    self.read_thread = threading.Thread(target=self.read_serial)
                    self.read_thread.start()
                    self.plot_thread = threading.Thread(target=self.animate_plot)
                    self.plot_thread.start()
                self.message_box.configure(text="Connected to "+selected_port+" Baud rate: "+selected_baud_rate)
                self.connect_button.configure(text="Disconnect",fg_color="green",hover_color="darkgreen")
            except serial.SerialException as e:
                print(f"Failed to connect to {selected_port} at {selected_baud_rate} baud rate: {e}")
                self.message_box.configure(text="Error opening serial port: "+selected_port)
        else:
            self.disconenct_to_serial()

    def read_serial(self):
        buffer = b''
        while not self.stop_event.is_set():
            try:
                with self.lock:
                    if self.serial_connection.in_waiting:
                        data = self.serial_connection.read(self.serial_connection.in_waiting)
                        buffer += data
                        if b'\n' in buffer:
                            lines = buffer.split(b'\n')
                            for line in lines[:-1]:
                                self.plot_data_queue.put(line.decode('utf-8'))
                                # self.animate_plot()
                                self.display_message(line+b'\n', msg_type="received")
                            buffer = lines[-1]
            except serial.SerialException as e:
                print("Serial error:", e)
                self.stop_event.set()

    def display_message(self, msg, msg_type):
        timestamp = datetime.now().strftime("%H:%M:%S,")
        self.console_textbox.insert(customtkinter.END, f"{timestamp} ", 'timestamp')
        try:
            if(self.console_dtype_menu.get() =="Utf8"):
                self.console_textbox.insert(customtkinter.END, msg.decode('utf-8'), msg_type)
            elif(self.console_dtype_menu.get() == "Hex"):
                hex_data = '  '.join(f'{b:02x}' for b in msg)
                self.console_textbox.insert(customtkinter.END, hex_data + '\n', msg_type)
            elif(self.console_dtype_menu.get() == "Dec"):
                decimal_data = '  '.join(f'{b:03}' for b in msg)
                self.console_textbox.insert(customtkinter.END, decimal_data + '\n', msg_type)
            else:
                binary_data = '  '.join(f'{b:08b}' for b in msg)
                self.console_textbox.insert(customtkinter.END, binary_data + '\n', msg_type)
            if self.console_textbox_scroll:
                self.console_textbox.yview(customtkinter.END)
        except:
            self.console_textbox.insert(customtkinter.END, f"Message decoding error\n", 'error')
    
    def animate_plot(self):
        while not self.stop_event.is_set():
            try:
                # Blocking call, wait for new data
                line = self.plot_data_queue.get(timeout=1)  # Timeout to periodically check stop_event
                values = list(map(float, line.strip().split(',')))
            except queue.Empty:
                continue  # No data, just continue the loop
            except ValueError:
                values = None

            if values:
                timestamp = datetime.now()
                self.timestamps.append(timestamp)
                if len(self.timestamps) > 100:
                    self.timestamps.pop(0)  # Keep the last 100 timestamps
                for idx, value in enumerate(values):
                    label = f'Value {idx+1}'
                    if label not in self.lines:
                        line, = self.ax.plot([], [], label=label)
                        self.lines[label] = (line, [])
                    line, data = self.lines[label]
                    data.append(value)
                    if len(data) > 100:
                        data.pop(0)  # Keep the last 100 data points
                    line.set_data(self.timestamps[-len(data):], data)
                self.ax.relim()
                self.ax.autoscale_view()
                self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%M:%S'))
                legend = self.ax.legend(loc='upper left')

                # Connect toggle function to legend
                for legend_line in legend.get_lines():
                    legend_line.set_picker(True)
                self.fig.canvas.mpl_connect('pick_event', self.toggle_line)
                self.canvas.draw()


    # Function to toggle line visibility
    def toggle_line(self, event):
        legend = event.artist
        label = legend.get_label()
        line = self.lines[label][0]
        visible = not line.get_visible()
        line.set_visible(visible)
        legend.set_alpha(1.0 if visible else 0.2)
        plt.draw()

    def save_data(self):
        output_path = self.output_path_entry.get()
        output_path += '\output.csv'
        data = self.console_textbox.get("1.0", customtkinter.END).strip().split('\n')
        if len(data) > 1:
            try:
                with open(output_path, mode='w', newline='') as csvfile:
                    csvfile.write('Timestamp,'+'MTQ time,'+"Gyro X,"+"Gyro Y,"+"Gyro Z\n")
                    for line in data:
                        csvfile.write(str(line) + '\n')
                self.message_box.configure(text_color="green",text=f"Data saved to {output_path}")
                
            except Exception as e:
                self.message_box.configure(text_color="red",text="Error Generating CSV data")
        else:
            self.message_box.configure(text_color="red",text="No data to save")
        
    def clear_console(self):
        self.console_textbox.delete(0.0,'end')
    
    def clear_chart(self):
        self.lines = {}
        self.timestamps = []
        # Clear the axes
        self.ax.cla()
        # Re-apply the styling and formatting
        self.ax.set_facecolor("#1E1E1E")
        self.ax.spines['left'].set_color("grey")
        self.ax.spines['bottom'].set_color("grey")
        self.ax.spines['right'].set_color("#1E1E1E")
        self.ax.spines['top'].set_color("#1E1E1E")
        self.ax.tick_params(axis='x', colors='grey')
        self.ax.tick_params(axis='y', colors='grey')
        self.ax.xaxis.set_major_formatter(mdates.DateFormatter('%M:%S'))
        # Redraw the canvas
        self.canvas.draw()

    def toggle_scroll_lock(self):
        self.console_textbox_scroll = not self.console_textbox_scroll
        if self.console_textbox_scroll:
            self.btn_lock.configure(fg_color = "transparent")
        else:
            self.btn_lock.configure(fg_color = "darkgrey", hover_color = "grey")
    
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
    
    def update_tx_CMD(self, event = None):
        selected_command = self.cmdSel_dropdown.get()
        cmd_regID = list(self.MTQ_ctrl_commands.get(selected_command))[0]
        if selected_command != "MTQ Set Power":
            cmd_data = list(self.MTQ_ctrl_commands.get(selected_command))[1]
        else:
            cmd_data = [int(self.slider_X.get()), int(self.slider_Y.get()), int(self.slider_Z.get())]
        command = self.encode_command(cmd_regID, cmd_data)
        self.tx_console_entry.delete(0, customtkinter.END)
        self.tx_console_entry.insert(0, command.hex())

    def send_serial(self):
        data_to_send = self.tx_console_entry.get()
        if self.deviceConnected:
            if data_to_send:
                byte_data = bytearray.fromhex(data_to_send)
                self.serial_connection.write(byte_data)
                self.display_message(byte_data, 'sent')
                self.message_box.configure(text=self.cmdSel_dropdown.get()+" command sent")
            else:
                self.message_box.configure(text="Tx console empty: Select command to send.")
        else:
                self.message_box.configure(text="Device not connected yet")

    def update_slider_vals(self, event = None):
        self.pwrX_label.delete(0, customtkinter.END)
        self.pwrY_label.delete(0, customtkinter.END)
        self.pwrZ_label.delete(0, customtkinter.END)
        self.pwrX_label.insert(0,str(int(self.slider_X.get())))
        self.pwrY_label.insert(0,str(int(self.slider_Y.get())))
        self.pwrZ_label.insert(0,str(int(self.slider_Z.get())))
        self.update_tx_CMD()

    def on_closing(self):
        self.disconenct_to_serial()
        self.quit()
        self.destroy()

if __name__ == "__main__":
    app = MTQtesterApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()