import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QLabel, QPushButton, QComboBox,
                           QSlider, QStatusBar, QListWidget, QListWidgetItem,
                           QSplitter, QFrame, QMessageBox)
from PyQt5.QtGui import QColor, QFont, QPixmap, QMovie, QIcon
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve
from radioglobe_core import RadioGlobeCore

class StationBrowser(QListWidget):
    stationSelected = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self.setStyleSheet("""
            QListWidget {
                background: white;
                border: 1px solid #ccc;
                font: 16pt "Segoe UI";
                color: black;
            }
            QListWidget::item {
                padding: 12px 8px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:selected {
                background: #e0e0e0;
                color: black;
            }
        """)
        self.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        
    def load_stations(self, stations):
        self.clear()
        if not stations:
            item = QListWidgetItem("No stations found")
            item.setForeground(Qt.black)
            item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
            self.addItem(item)
            return
            
        for station in stations:
            item = QListWidgetItem(
                f"{station['name']} | "
                f"{station.get('bitrate', '?')}kbps | "
                f"Votes: {station.get('votes', 0)}"
            )
            item.setForeground(Qt.black)
            item.setData(Qt.UserRole, station)
            self.addItem(item)

class RadioGlobeApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🌍 RadioGlobe Player")
        self.setMinimumSize(1000, 700)
        self.core = RadioGlobeCore()
        self.current_station = None
        self.typing_animation = QTimer()
        self.typing_chars = 0
        self.init_ui()
        
    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        
        # Clean theme
        main_widget.setStyleSheet("""
            QWidget {
                background: #f5f5f5;
            }
            QPushButton#play_button {
                background: #4CAF50;
                color: black;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                font: bold 14pt;
                min-width: 120px;
            }
            QPushButton#play_button:hover {
                background: #45a049;
            }
            QPushButton#stop_button {
                background: #f44336;
                color: black;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                font: bold 14pt;
                min-width: 120px;
            }
            QPushButton#stop_button:hover {
                background: #d32f2f;
            }
            QLabel#now_playing {
                font: 14pt;
                color: black;
                padding: 8px;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)
        
        # Country Selection
        country_box = QHBoxLayout()
        country_box.addWidget(QLabel("Select Country:"))
        self.country_combo = QComboBox()
        countries = self.core.get_countries()
        if countries:
            self.country_combo.addItems([c['name'] for c in countries])
            self.country_combo.currentTextChanged.connect(self.on_country_selected)
        country_box.addWidget(self.country_combo)
        layout.addLayout(country_box)
        
        # Main Content
        splitter = QSplitter(Qt.Horizontal)
        
        # Globe Display
        self.globe_display = QLabel()
        self.globe_movie = QMovie("rotating_earth.gif")
        self.globe_display.setMovie(self.globe_movie)
        self.globe_movie.start()
        splitter.addWidget(self.globe_display)
        
        # Station Browser
        self.station_browser = StationBrowser()
        self.station_browser.itemDoubleClicked.connect(self.on_station_selected)
        splitter.addWidget(self.station_browser)
        layout.addWidget(splitter)
        
        # Now Playing
        self.now_playing_bar = QLabel("No station selected")
        self.now_playing_bar.setObjectName("now_playing")
        self.now_playing_bar.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.now_playing_bar)
        
        # Controls
        control_box = QHBoxLayout()
        
        self.play_button = QPushButton("▶ Play")
        self.play_button.setObjectName("play_button")
        self.play_button.clicked.connect(self.play_current)
        
        self.stop_button = QPushButton("■ Stop")
        self.stop_button.setObjectName("stop_button")
        self.stop_button.clicked.connect(self.core.stop)
        
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        self.volume_slider.valueChanged.connect(self.core.set_volume)
        
        control_box.addWidget(self.play_button)
        control_box.addWidget(self.stop_button)
        control_box.addWidget(QLabel("Volume:"))
        control_box.addWidget(self.volume_slider)
        layout.addLayout(control_box)
        
        main_widget.setLayout(layout)

    def on_country_selected(self, country):
        stations, _ = self.core.get_stations(country)
        self.station_browser.load_stations(stations)

    def on_station_selected(self, item):
        station = self.station_browser.currentItem().data(Qt.UserRole)
        self.play_selected_station(station)

    def play_current(self):
        if item := self.station_browser.currentItem():
            self.play_selected_station(item.data(Qt.UserRole))

    def play_selected_station(self, station):
        if not station:
            return
            
        # Stop any existing typing animation
        try:
            self.typing_animation.timeout.disconnect()
        except TypeError:
            pass  # No connections to disconnect
            
        # Setup new typing animation
        name = f"Now Playing: {station['name']}"
        self.now_playing_bar.setText("")
        self.typing_chars = 0
        
        def update_text():
            if self.typing_chars <= len(name):
                self.now_playing_bar.setText(name[:self.typing_chars])
                self.typing_chars += 1
            else:
                self.typing_animation.stop()
                
        self.typing_animation.timeout.connect(update_text)
        self.typing_animation.start(50)
        
        if self.core.play(station['url']):
            self.current_station = station

    def closeEvent(self, event):
        self.core.stop()
        self.typing_animation.stop()
        event.accept()

if __name__ == "__main__":
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    window = RadioGlobeApp()
    window.show()
    sys.exit(app.exec_())