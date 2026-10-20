import sys
from PyQt6.QtWidgets import QApplication, QDialog, QVBoxLayout, QTabWidget, QTextBrowser, QTableWidget, QTableWidgetItem, QPushButton, QHBoxLayout, QWidget
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtCore import Qt

class DamageBreakdownDialog(QDialog):
    def __init__(self, parent=None, breakdown_text='', w_meta=None, mod_objs=None, metrics=None, riven_stats=None):
            super().__init__(parent)
            self.setWindowTitle("Warframe Damage Breakdown")
            self.setModal(True)
            self.breakdown_text = breakdown_text
            self.w_meta = w_meta
            self.mod_objs = mod_objs or []
            self.metrics = metrics or {}
            self.riven_stats = riven_stats or {}
            self.setup_ui()
            self.apply_dark_theme()
            if breakdown_text or w_meta or mod_objs:
                self.set_data(breakdown_text, w_meta, mod_objs, metrics, riven_stats)

    def setup_ui(self):
        layout = QVBoxLayout()

        # Tab Widget
        tab_widget = QTabWidget()
        layout.addWidget(tab_widget)

        # Tab 1: QTextBrowser for HTML content
        self.text_browser = QTextBrowser()
        self.text_browser.setHtml(self.generate_html_content())
        tab_widget.addTab(self.text_browser, "Calculation Steps")

        # Tab 2: QTableWidget for mod contribution table
        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(8)
        self.table_widget.setHorizontalHeaderLabels(["모드명", "피해", "멀티샷", "속성", "치확", "치피", "연사/공속", "비고"])
        self.table_widget.setRowCount(5)  # Example rows
        self.populate_table()
        tab_widget.addTab(self.table_widget, "Mod Contribution")

        # Buttons
        button_layout = QHBoxLayout()
        copy_button = QPushButton("Copy to Clipboard")
        copy_button.clicked.connect(self.copy_to_clipboard)
        button_layout.addWidget(copy_button)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)

        self.setLayout(layout)
        self.apply_dark_theme()

    def generate_html_content(self):
            text = getattr(self, 'breakdown_text', '') or ''
            if not text:
                return """
                <html>
                <head>
                    <style>
                        body { background-color: #0f172a; color: #D4AF37; }
                    </style>
                </head>
                <body>
                    <h1>No Damage Breakdown Available</h1>
                </body>
                </html>
                """

            lines = text.split('\n')
            html_content = """
            <html>
            <head>
                <style>
                    body { background-color: #0f172a; color: #D4AF37; }
                    h1 { color: #D4AF37; }
                    .section-header { color: #D4AF37; font-weight: bold; }
                    .step { background-color: #1e293b; color: #38bdf8; border: 1px solid #38bdf8; padding: 5px; border-radius: 5px; }
                    .bullet-item { background-color: #1e293b; color: #D4AF37; padding: 5px; border-radius: 5px; }
                    .total-highlight { background-color: #D4AF37; color: #0f172a; padding: 5px; border-radius: 5px; }
                </style>
            </head>
            <body>
                <h1>Damage Calculation Breakdown</h1>
            """

            for line in lines:
                line = line.strip()
                if line.startswith(('1.', '2.', '3.', '4.', '5.', '6.', '7.')):
                    html_content += f'<p class="section-header">{line}</p>'
                elif line.startswith(('①', '②', '③', '④', '⑤', '⑥', '⑦')):
                    html_content += f'<p class="step">{line}</p>'
                elif line.startswith('•'):
                    html_content += f'<p class="bullet-item">{line}</p>'
                elif line.startswith('Total:'):
                    html_content += f'<p class="total-highlight">{line}</p>'
                else:
                    html_content += f'<p>{line}</p>'

            html_content += """
            </body>
            </html>
            """
            return html_content

    def populate_table(self):
            self.table_widget.setRowCount(0)  # Clear existing rows
            self.table_widget.setColumnCount(8)
            self.table_widget.setHorizontalHeaderLabels(["모드명", "피해", "멀티샷", "속성", "치확", "치피", "연사/공속", "비고"])

            if not self.mod_objs:
                return

            data = []
            total_damage = 0
            total_multishot = 0
            total_elemental_damage = 0
            total_crit_chance = 0
            total_crit_damage = 0
            total_fire_rate = 0

            for m in self.mod_objs:
                mod_name = m.get('kr_name') or m.get('name')
                damage = float(m.get('damage') or 0.0)
                multishot = float(m.get('multishot') or 0.0)
                elemental_damage = float(m.get('elemental_damage') or 0.0)
                crit_chance = float(m.get('crit_chance') or 0.0)
                crit_damage = float(m.get('crit_damage') or 0.0)
                fire_rate = float(m.get('fire_rate') or 0.0)

                total_damage += damage
                total_multishot += multishot
                total_elemental_damage += elemental_damage
                total_crit_chance += crit_chance
                total_crit_damage += crit_damage
                total_fire_rate += fire_rate

                is_zero = not any([damage, multishot, elemental_damage, crit_chance, crit_damage, fire_rate])
                note = "[스탠스]" if "stance" in str(m.get("type", "")).lower() else ("[유틸리티]" if is_zero else "-")

                row_data = [
                    mod_name,
                    f"+{damage*100:.1f}%" if damage != 0 else "-",
                    f"+{multishot*100:.1f}%" if multishot != 0 else "-",
                    f"+{elemental_damage*100:.1f}%" if elemental_damage != 0 else "-",
                    f"+{crit_chance*100:.1f}%" if crit_chance != 0 else "-",
                    f"+{crit_damage*100:.1f}%" if crit_damage != 0 else "-",
                    f"+{fire_rate*100:.1f}%" if fire_rate != 0 else "-",
                    note
                ]
                data.append(row_data)

            if self.riven_stats:
                riven_row = [
                    "Riven",
                    f"+{self.riven_stats.get('damage', 0):.1f}",
                    f"+{self.riven_stats.get('multishot', 0):.1f}",
                    self.riven_stats.get('elemental_damage', ""),
                    f"+{self.riven_stats.get('crit_chance', 0)*100:.1f}%" if self.riven_stats.get('crit_chance', 0) != 0 else "-",
                    f"+{self.riven_stats.get('crit_damage', 0)*100:.1f}%" if self.riven_stats.get('crit_damage', 0) != 0 else "-",
                    f"+{self.riven_stats.get('fire_rate', 0)*100:.1f}%" if self.riven_stats.get('fire_rate', 0) != 0 else "-",
                    "고유 롤 옵션 합산"
                ]
                data.append(riven_row)

            summary_row = [
                "🎯 총합 적용치",
                f"+{total_damage*100:.1f}%",
                f"+{total_multishot*100:.1f}%",
                f"+{total_elemental_damage*100:.1f}%",
                f"+{total_crit_chance*100:.1f}%",
                f"+{total_crit_damage*100:.1f}%",
                f"+{total_fire_rate*100:.1f}%",
                "연산 대입값 (Total Sum)"
            ]
            data.append(summary_row)

            self.table_widget.setRowCount(len(data))
            for row, row_data in enumerate(data):
                for col, value in enumerate(row_data):
                    item = QTableWidgetItem(value)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    if value != "0" and value != "-":
                        item.setBackground(QColor("#1e293b"))
                    self.table_widget.setItem(row, col, item)

    def copy_to_clipboard(self):
        selected_text = self.table_widget.selectedRanges()
        if not selected_text:
            return

        clipboard = QApplication.clipboard()
        clipboard.clear()
        for range in selected_text:
            text = ""
            for row in range.rowCount():
                for col in range.columnCount():
                    item = self.table_widget.item(range.topRow() + row, range.leftColumn() + col)
                    if item:
                        text += item.text() + "\t"
                text = text.strip() + "\n"
            clipboard.setText(text.strip())

    def apply_dark_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor("#0f172a"))
        palette.setColor(QPalette.ColorRole.WindowText, QColor("#D4AF37"))
        palette.setColor(QPalette.ColorRole.Base, QColor("#1e293b"))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#1e293b"))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#D4AF37"))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#0f172a"))
        palette.setColor(QPalette.ColorRole.Text, QColor("#D4AF37"))
        palette.setColor(QPalette.ColorRole.Button, QColor("#1e293b"))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor("#D4AF37"))
        palette.setColor(QPalette.ColorRole.BrightText, QColor("#D4AF37"))
        palette.setColor(QPalette.ColorRole.Link, QColor("#D4AF37"))
        palette.setColor(QPalette.ColorRole.Highlight, QColor("#D4AF37"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#0f172a"))
        self.setPalette(palette)

    def set_data(self, breakdown_text='', w_meta=None, mod_objs=None, metrics=None, riven_stats=None):
        self.breakdown_text = breakdown_text
        self.w_meta = w_meta
        self.mod_objs = mod_objs
        self.metrics = metrics
        self.riven_stats = riven_stats
    
        if w_meta:
            self.setWindowTitle(f"Warframe Damage Breakdown - {w_meta.get('name', 'Unknown Weapon')}")
    
        self.text_browser.setHtml(self.generate_html_content())
        self.populate_table()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    dialog = DamageBreakdownDialog()
    dialog.show()
    sys.exit(app.exec())