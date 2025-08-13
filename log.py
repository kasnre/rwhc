import logging

class TextHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        try:
            msg = self.format(record) + "\n"
            self.text_widget.after(0, lambda m=msg: self.append(m))
        except Exception:
            pass

    def append(self, msg):
        try:
            self.text_widget.config(state="normal")
            self.text_widget.insert("end", msg)
            self.text_widget.see("end")
            self.text_widget.config(state="disabled")
        except Exception:
            pass