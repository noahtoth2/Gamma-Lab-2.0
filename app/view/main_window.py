from collections import defaultdict
import os
from PyQt5.QtWidgets import (
    QMainWindow,
    QHBoxLayout,
    QVBoxLayout,
    QWidget,
    QToolButton,
    QGroupBox,
    QLabel,
    QSizePolicy,
    QApplication,
)
from app.view.main_window_ui import Ui_MainWindow 
from PyQt5.QtGui import QIcon, QFontMetrics, QFont, QPixmap, QPainter
from PyQt5.QtCore import QSize, Qt, QPropertyAnimation, QEasingCurve, QEvent
from PyQt5.QtWidgets import QFrame

from core.plugins.interfaces import IPlugin
from core.utils.plugin_alerts import PluginAlerts

class MainWindow(QMainWindow):
    def __init__(self, kernel):
        super().__init__()
        self.kernel = kernel

        # Register the main window as a service in the kernel so plugins can access it.
        self.kernel.register_service("MainWindow", self)

        # Prefer embedded resource; fallback to file path
        icon = QIcon(":/assets/logos/app-logo.png")
        if icon.isNull():
            icon = QIcon("assets/logos/app-logo.png")
        self.setWindowIcon(icon)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        
        self.alerts = PluginAlerts()
        self.alerts.parent = self

        self.kernel.event.connect(self.on_kernel_event)

        self.current_section = "Home"
        self.active_plugin = None  # Currently active plugin
        self.active_plugin_widget = None  # Widget of the active plugin
        self.plugin_widgets = {}  # Store plugin widgets to preserve work/state

        # Workspace area where plugins render
        self.plugin_area = self.ui.workspace

        # Initialize sidebar functionality
        self.setup_sidebar_functionality()

        if not self.plugin_area.layout():
            self.plugin_layout = QVBoxLayout(self.plugin_area)
            self.plugin_layout.setContentsMargins(0,0,0,0)
        else:
            self.plugin_layout = self.plugin_area.layout()

        # Single watermark label (does not intercept mouse events)
        self._bg_logo_label = QLabel(self.plugin_area)
        self._bg_logo_label.setObjectName("gammaLabWatermark")
        self._bg_logo_label.setAlignment(Qt.AlignCenter)
        self._bg_logo_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self._bg_logo_label.setAttribute(Qt.WA_TranslucentBackground, True)
        self._bg_logo_label.setAttribute(Qt.WA_NoSystemBackground, True)
        self._bg_logo_label.setStyleSheet("background: transparent; border: none;")
        self._bg_logo_pixmap = QPixmap("assets/logos/app-logo.png")
        # Watermark opacity (applied to PNG alpha channel)
        # Very subtle for plugins' background
        self._logo_opacity = 0.1
        # Keep it behind content by default
        self._bg_logo_label.lower()
        self._bg_logo_label.setScaledContents(False)
        # Adjust initial size and scale
        self._position_background_logo()
        # Track workspace area resize events
        self.plugin_area.installEventFilter(self)

        # Home welcome panel (shown in Home when no plugin is active)
        self._home_welcome = self._build_home_welcome_widget()
        self.plugin_layout.addWidget(self._home_welcome)

        # Forced watermark state (not used now, but kept for API symmetry)
        self._watermark_forced = False
        # Initial visibility
        self._update_background_logo_visibility()
        self._update_home_welcome_visibility()

        # Section button dictionary
        self.section_buttons = {
            "Home": self.ui.bnt_home,
            "Preprocessing": self.ui.btn_preprocessing,
            "Analysis": self.ui.btn_analysis,
            "Measure": self.ui.btn_measure,
            "FAQ": self.ui.btn_faq,
        }

        for section, btn in self.section_buttons.items():
            btn.setCheckable(True)
            btn.clicked.connect(lambda _, s=section: self.switch_section(s))

        # Show Home plugins by default
        self.switch_section(self.current_section)
        
        self._app_quitting = False
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self._on_app_about_to_quit)


    '''buttons section'''
    # Update buttons when a new plugin is registered
    def on_plugin_registered(self, name):
        plugin = self.kernel.get_plugin(name)
        if plugin and plugin.category() == self.current_section:
            
            self.add_plugin_button(name)

    # Switch section
    def switch_section(self, section):
        self.current_section = section
        self.setWindowTitle(f"Gamma Lab - {self.current_section}")

        # Toggle the section button
        for btn in self.section_buttons.values():
            btn.setChecked(False)
        if section in self.section_buttons:
            self.section_buttons[section].setChecked(True)

        # Layout of the blue container
        contenedor = self.ui.buttonContainer.layout()
        while contenedor.count():
            item = contenedor.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        # Align left with no outer margins
        contenedor.setContentsMargins(0, 0, 0, 0)
        contenedor.setSpacing(8)
        contenedor.setAlignment(Qt.AlignLeft)

        # Group plugins by subcategory
        subcategories = defaultdict(list)
        for name in self.kernel.get_plugins_by_category(section):
            plugin = self.kernel.get_plugin(name)
            subcategories[plugin.subcategory()].append(name)

        # Build each subcategory and put a divider between them
        subcats = list(subcategories.items())
        for idx, (subcat, plugins) in enumerate(subcats):
            group_box = QGroupBox(subcat, self.ui.buttonContainer)
            group_box.setAlignment(Qt.AlignHCenter | Qt.AlignBottom)
            row = QHBoxLayout(group_box)
            row.setContentsMargins(0, 6, 0, 22)
            row.setSpacing(34)

            for name in plugins:
                row.addWidget(self.add_plugin_button(name))

            contenedor.addWidget(group_box, 0, Qt.AlignVCenter)

        # Push everything to the left
        contenedor.addStretch(1)
        # Update section-dependent visuals
        self._update_background_logo_visibility()
        self._update_home_welcome_visibility()
        
    def add_plugin_button(self, name):
        plugin = self.kernel.get_plugin(name)
        btn = QToolButton(self.ui.buttonContainer)
        btn.setObjectName(f"btn_{name}")
        btn.setCheckable(False)
        btn.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)

        # Fixed size (consistent with QSS)
        btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        btn.setMinimumWidth(96); btn.setMaximumWidth(96)
        btn.setMinimumHeight(76)

        # Icon
        try:
            icon_path = plugin.icon()
            if icon_path:
                btn.setIcon(QIcon(icon_path))
                btn.setIconSize(QSize(26, 26))
        except Exception as e:
            print("Icon not available for plugin", name, "->", e)

        label = plugin.name()
        fm_width = 96 - 8
        btn.setText(self._wrap_button_text(label, btn.font(), fm_width))

        btn.clicked.connect(lambda _, n=name: self.on_button_click(n))
        return btn

    def _wrap_button_text(self, text: str, font: QFont, max_width: int) -> str:
        """
        Insert an optimal line break so the text fits in 1–2 lines
        within 'max_width'. If it already fits on one line, leave it as is.
        """
        fm = QFontMetrics(font)
        if fm.horizontalAdvance(text) <= max_width:
            return text

        # Try to break at the last space so the first line fits <= max_width
        words = text.split()
        if len(words) == 1:
            # No spaces; hard-cut at the largest substring that fits
            for i in range(len(text)-1, 0, -1):
                if fm.horizontalAdvance(text[:i]) <= max_width:
                    return text[:i] + "\n" + text[i:]
            return text  # fallback
        else:
            # Build line 1 with the maximum number of words that fit
            line1 = words[0]
            for w in words[1:]:
                candidate = f"{line1} {w}"
                if fm.horizontalAdvance(candidate) <= max_width:
                    line1 = candidate
                else:
                    # The rest goes to the second line
                    line2 = " ".join(words[len(line1.split()):])
                    # If the second line is still too long, it's fine: button height supports it
                    return line1 + "\n" + line2
            # If everything fit, no second line needed
            return line1

    # Clean workspace
    def clear_plugin_area(self):
        if self.active_plugin_widget and self.active_plugin:
            try:
                self.active_plugin.stop()
            except Exception as e:
                self.alerts.warning(f"An error occurred while stopping the VTK render plugin.\n\nDetails:\n{str(e)}", "Error stopping plugin")
            self.active_plugin_widget.setVisible(False)

        self.active_plugin_widget = None
        self.active_plugin = None
        # Update background/placeholder visibility
        self._update_background_logo_visibility()
        self._update_home_welcome_visibility()


    # Insert the active plugin's widget into the workspace
    def show_plugin_widget(self, plugin: IPlugin):
        try:
            plugin.process(None)
        except Exception as e:
            print("Error resuming plugin:", e)
        
        if plugin is None:
            return

        # Start plugin if not started yet
        if not getattr(plugin, "started", False):
            try:
                plugin.start(self.kernel)
                plugin.started = True
            except Exception as e:
                print("Error starting plugin:", e)

        # Reuse if it already exists
        if plugin.name() in self.plugin_widgets:
            widget = self.plugin_widgets[plugin.name()]
        else:
            # Get widget from plugin
            try:
                widget = plugin.get_widget(parent=self.plugin_area)
            except Exception as e:
                self.alerts.error(f"An error occurred while rendering the plugin widget '{plugin.name()}'.\n\nDetails:\n{str(e)}", "Error rendering plugin")
                print("[Main Window] Error in plugin get_widget:", e)
                widget = None

            # If no widget is returned, create a placeholder
            if widget is None:
                self.alerts.error(f"No UI available for the plugin '{plugin.name()}'.", "Error rendering plugin")


                placeholder = QWidget(parent=self.plugin_area)
                layout = QVBoxLayout(placeholder)
                layout.addWidget(QLabel(f"No UI available for {plugin.name()}"))
                widget = placeholder

            widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self.plugin_layout.addWidget(widget)
            self.plugin_widgets[plugin.name()] = widget

        # Hide previous and show the new one
        self.clear_plugin_area()
        widget.setVisible(True)
        self.active_plugin_widget = widget
        self.active_plugin = plugin
        # Update background/placeholder visibility
        self._update_background_logo_visibility()
        self._update_home_welcome_visibility()

        # Notify it is shown
        if hasattr(plugin, "on_show"):
            try:
                plugin.on_show()
            except Exception as e:
                print("Error in plugin on_show:", e)

    def eventFilter(self, obj, event):
        if obj is self.plugin_area and event.type() == QEvent.Resize:
            self._position_background_logo()
        return super().eventFilter(obj, event)

    def _position_background_logo(self):
        """Center and scale watermark inside the workspace area."""
        if not hasattr(self, "_bg_logo_label"):
            return
        if self._bg_logo_pixmap.isNull():
            return
        area_size = self.plugin_area.size()
        # Scale to ~50% of the shortest side and center
        target = int(min(area_size.width(), area_size.height()) * 0.5)
        if target <= 0:
            return
        scaled = self._bg_logo_pixmap.scaled(
            target, target, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        # Apply global opacity using painter (preserves PNG transparency)
        scaled = self._make_translucent(scaled, self._logo_opacity)
        w = scaled.width(); h = scaled.height()
        x = max(0, (area_size.width() - w) // 2)
        y = max(0, (area_size.height() - h) // 2)
        self._bg_logo_label.setPixmap(scaled)
        self._bg_logo_label.setGeometry(x, y, w, h)

    def _has_any_signal(self) -> bool:
        try:
            datastore = self.kernel.get_service("DataStore")
            if not datastore:
                return False
            sigs = datastore.get_signals()
            return bool(sigs)
        except Exception:
            return False

    def _has_active_signal(self) -> bool:
        try:
            datastore = self.kernel.get_service("DataStore")
            if not datastore:
                return False
            return datastore.get_active_signal() is not None
        except Exception:
            return False

    def _has_active_trials(self) -> bool:
        try:
            datastore = self.kernel.get_service("DataStore")
            if not datastore:
                return False
            sig = datastore.get_active_signal()
            if not sig:
                return False
            # If there is any TrialDataset associated
            try:
                td = sig.get_active_trials(sig.name, None)
                return td is not None and getattr(td, "trials", None) is not None and td.trials.size > 0
            except Exception:
                # If the method signature differs or fails, assume there are no active trials
                return sig.number_of_trials_dataset() > 0
        except Exception:
            return False

    def _update_background_logo_visibility(self):
        """Show watermark when there is no active signal and not in Home."""
        if not hasattr(self, "_bg_logo_label"):
            return
        visible = (self.current_section != "Home") and (not self._has_active_signal())
        self._bg_logo_label.setVisible(visible)
        if visible:
            self._bg_logo_label.lower()
            self._position_background_logo()

    def _build_home_welcome_widget(self) -> QWidget:
        """Build centered Home welcome with big title, small subtitle and a divider line."""
        w = QWidget(self.plugin_area)
        w.setObjectName("homeWelcomePanel")

        outer = QVBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Center block
        block = QWidget(w)
        block_layout = QVBoxLayout(block)
        block_layout.setContentsMargins(40, 40, 40, 40)
        block_layout.setSpacing(12)

        # Logo (bigger)
        logo = QLabel(block)
        logo.setAttribute(Qt.WA_TranslucentBackground, True)
        logo.setAttribute(Qt.WA_NoSystemBackground, True)
        logo.setStyleSheet("background: transparent; border: none;")
        pix = QPixmap("assets/logos/app-logo.png").scaled(200, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        logo.setPixmap(pix)
        block_layout.addWidget(logo, 0, Qt.AlignHCenter)

        # Title (very large, centered)
        title = QLabel("Welcome to GAMMA LAB", block)
        f = title.font()
        try:
            f.setPointSize(160)
        except Exception:
            pass
        f.setBold(True)
        title.setFont(f)
        title.setStyleSheet("color: #2a63a9;")
        block_layout.addWidget(title, 0, Qt.AlignHCenter)

        # Small subtitle
        subtitle = QLabel("To get started, open a signal", block)
        f2 = subtitle.font()
        try:
            f2.setPointSize(max(10, f2.pointSize() + 2))
        except Exception:
            pass
        subtitle.setFont(f2)
        subtitle.setStyleSheet("color: #6f7a86;")
        block_layout.addWidget(subtitle, 0, Qt.AlignHCenter)

        # Divider line using app defaults
        line = QFrame(block)
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        block_layout.addWidget(line)

        # Assemble outer layout with vertical centering effect
        outer.addStretch(1)
        outer.addWidget(block, 0, Qt.AlignHCenter)
        outer.addStretch(2)

        w.setVisible(False)
        return w

    def _update_home_welcome_visibility(self):
        """Home welcome is visible only in Home when no plugin UI is active."""
        if not hasattr(self, "_home_welcome"):
            return
        show = (self.current_section == "Home") and (self.active_plugin_widget is None)
        self._home_welcome.setVisible(show)

    # Explicit control from plugins
    def show_watermark(self):
        self._watermark_forced = False
        if hasattr(self, "_bg_logo_label"):
            self._update_background_logo_visibility()

    def hide_watermark(self):
        self._watermark_forced = False
        if hasattr(self, "_bg_logo_label"):
            self._update_background_logo_visibility()

    def _make_translucent(self, pix: QPixmap, opacity: float) -> QPixmap:
        """Return a copy of the pixmap with a global opacity applied."""
        try:
            if pix.isNull():
                return pix
            opacity = max(0.0, min(1.0, float(opacity)))
            out = QPixmap(pix.size())
            out.fill(Qt.transparent)
            painter = QPainter(out)
            painter.setOpacity(opacity)
            painter.drawPixmap(0, 0, pix)
            painter.end()
            return out
        except Exception:
            return pix

    def _schedule_watermark_autohide(self):
        """Wait for the plugin to create its content (e.g., VTK) and hide the watermark."""
        delays = [0, 120, 350, 1000]
        for d in delays:
            QTimer.singleShot(d, self._check_and_autohide_plugin_content)

    # Heuristic auto-hide removed; plugins control the watermark

               
    # Event when a plugin button is clicked: show its UI and optionally process
    def on_button_click(self, name):
        plugin = self.kernel.get_plugin(name)
        if plugin:
            print(f"Plugin button clicked: {name}")
            self.show_plugin_widget(plugin)
            if hasattr(plugin, "process"):
                try:
                    plugin.process("Window opened")
                except Exception as e:
                    print("Error in plugin process:", e)
        else:
            print("Plugin not found:", name)



    '''Sidebar'''

    def on_kernel_event(self, topic: str, payload: object):
        """
        Listen to events emitted by the Kernel.
        """
        if topic == "signal_added":
            print(f"New signal added: {payload}")
            self.update_signal_list()
            self._update_background_logo_visibility()
        elif topic in ("signal_active_changed", "trials_generated", "trial_discard_updated"):
            # State changes that affect data availability
            self._update_background_logo_visibility()

    def setup_sidebar_functionality(self):
        sidebar = self.ui.widget_3
        sidebar.setMaximumWidth(250)
        """Initialize and connect all sidebar functions."""
        # Sidebar collapse
        self.ui.collapse_explorer_btn.clicked.connect(lambda: self.toggle_sidebar_collapse(sidebar))
        self.ui.collapse_explorer_btn.setIcon(QIcon("assets/icons/home/icn_collapse.png"))

        self.update_signal_list()
        # Signal selection
        self.ui.selected_signal_comboBox.currentIndexChanged.connect(self.on_signal_selected)

        # Future sections
        self.setup_explorer_section()
        self.setup_calculus_section()
        self.setup_results_section()

    # Collapse and expand the sidebar
    def toggle_sidebar_collapse(self, sidebar):
        
        current_width = sidebar.width()

        if current_width > 0:
            self._last_sidebar_width = current_width

            # Allow full collapse
            sidebar.setMinimumWidth(0)

            # Collapse animation
            self._sidebar_animation = QPropertyAnimation(sidebar, b"maximumWidth")
            self._sidebar_animation.setDuration(250)
            self._sidebar_animation.setStartValue(current_width)
            self._sidebar_animation.setEndValue(0)
            self._sidebar_animation.setEasingCurve(QEasingCurve.InOutCubic)
            self._sidebar_animation.start()

            self.ui.collapse_explorer_btn.setIcon(QIcon("assets/icons/home/icn_expand.png"))

        else:
            width = getattr(self, "_last_sidebar_width", 250)

            # Restore width and minimum limit
            sidebar.setMinimumWidth(100)

            # Expansion animation
            self._sidebar_animation = QPropertyAnimation(sidebar, b"maximumWidth")
            self._sidebar_animation.setDuration(250)
            self._sidebar_animation.setStartValue(0)
            self._sidebar_animation.setEndValue(width)
            self._sidebar_animation.setEasingCurve(QEasingCurve.InOutCubic)
            self._sidebar_animation.start()

            self.ui.collapse_explorer_btn.setIcon(QIcon("assets/icons/home/icn_collapse.png"))


    def on_signal_selected(self):
        """
        Runs when the user changes the selected signal in the combo box.
        Updates the active signal in the DataStore.
        """
        datastore = self.kernel.get_service("DataStore")
        if not datastore:
            print("⚠️ DataStore service not found.")
            return

        selected_key = self.ui.selected_signal_comboBox.currentText()
        if not selected_key:
            print("No signal selected.")
            return

        try:
            datastore.set_active_signal(selected_key)
            self.kernel.emit_event("signal_active_changed", {"key": selected_key})

            print(f"[Main Window] Active signal changed to: {selected_key}")
        except ValueError as e:
            print(f"[Main Window] Error changing active signal: {e}")
        finally:
            # Hide watermark if a signal is active; otherwise show it
            self._update_background_logo_visibility()


    def update_signal_list(self):
        """Handle the selection of a signal from the combo box."""

        datastore = self.kernel.get_service("DataStore")
        if not datastore:
            print("DataStore service not found.")
            return
        
        signals = datastore.get_signals()
        active_signal_key = datastore.get_active_signal_key()

        # Clear combo
        self.ui.selected_signal_comboBox.blockSignals(True)
        self.ui.selected_signal_comboBox.clear()

        for key in signals.keys():
            self.ui.selected_signal_comboBox.addItem(key)

        # Select the active signal if present
        if active_signal_key and active_signal_key in signals:
            index = self.ui.selected_signal_comboBox.findText(active_signal_key)
            if index >= 0:
                self.ui.selected_signal_comboBox.setCurrentIndex(index)

        self.ui.selected_signal_comboBox.blockSignals(False)

        # Update logo visibility depending on loaded signals
        self._update_background_logo_visibility()



        # selected_signal = self.ui.selected_signal_comboBox.currentText()
        # if selected_signal:
        #     print(f"Selected signal: {selected_signal}")
        #     # Here you could notify the kernel or load the selected signal
        # else:
        #     print("No signal selected.")
        pass


    # === FUTURE FUNCTIONS (placeholder with pass) ===
    def setup_explorer_section(self):
        """Initialize the explorer section (currently empty)."""
        pass

    def setup_calculus_section(self):
        """Initialize the calculations section (currently empty)."""
        pass

    def setup_results_section(self):
        """Initialize the results section (currently empty)."""
        pass
    
    def _on_app_about_to_quit(self):
        """Shut down plugins and their UI safely. Idempotent."""
        if self._app_quitting:
            return
        self._app_quitting = True

        # 1) Stop the active plugin, if any
        try:
            if self.active_plugin and hasattr(self.active_plugin, "stop"):
                self.active_plugin.stop()
        except Exception as e:
            print("stop(active_plugin) error:", e)

        # 2) Stop the rest (if your kernel exposes a way to list them)
        try:
            # Option A: if you have a method to list them all
            if hasattr(self.kernel, "get_all_plugins"):
                for name in self.kernel.get_all_plugins():
                    p = self.kernel.get_plugin(name)
                    if p is not None and hasattr(p, "stop"):
                        try: p.stop()
                        except Exception as e: print(f"stop({name}) error:", e)
            else:
                # Option B: use those that are instantiated in the UI
                for name in list(self.plugin_widgets.keys()):
                    p = self.kernel.get_plugin(name)
                    if p is not None and hasattr(p, "stop"):
                        try: p.stop()
                        except Exception as e: print(f"stop({name}) error:", e)
        except Exception as e:
            print("stop(all) error:", e)

        # 3) Hide widgets and clear references (avoid late renders)
        try:
            for name, w in list(self.plugin_widgets.items()):
                if w is not None:
                    w.setVisible(False)
            self.plugin_widgets.clear()
            self.active_plugin_widget = None
            self.active_plugin = None
        except Exception as e:
            print("cleanup widgets error:", e)

    def closeEvent(self, event):
        self._on_app_about_to_quit()
        super().closeEvent(event)
