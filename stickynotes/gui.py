# Copyright © 2012-2013 Umang Varma <umang.me@gmail.com>
# 
# This file is part of indicator-stickynotes.
# 
# indicator-stickynotes is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
# 
# indicator-stickynotes is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
# more details.
# 
# You should have received a copy of the GNU General Public License along with
# indicator-stickynotes.  If not, see <http://www.gnu.org/licenses/>.

from datetime import datetime
from string import Template
from gi.repository import Gtk, Gdk, Gio, GObject, GtkSource
from locale import gettext as _
import os.path
import colorsys

def load_global_css():
    """Adds a provider for the global CSS"""
    global_css = Gtk.CssProvider()
    global_css.load_from_path(os.path.join(os.path.dirname(__file__), "..",
        "style_global.css"))
    Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(),
            global_css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

class StickyNote:
    """Manages the GUI of an individual stickynote"""
    def __init__(self, note):
        """Initializes the stickynotes window"""
        self.path = os.path.abspath(os.path.join(os.path.dirname(__file__),
            '..'))
        self.note = note
        self.noteset = note.noteset
        self.locked = self.note.properties.get("locked", False)
        self.builder = Gtk.Builder()
        GObject.type_register(GtkSource.View)
        self.builder.add_from_file(os.path.join(self.path,
            "StickyNotes.glade"))
        self.builder.connect_signals(self)
        # Get necessary objects
        self.txtNote = self.builder.get_object("txtNote")
        self.winMain = self.builder.get_object("MainWindow")
        self.winMain.set_name("main-window")
        self.bAdd = self.builder.get_object("bAdd")
        self.imgAdd = self.builder.get_object("imgAdd")
        self.imgResizeR = self.builder.get_object("imgResizeR")
        self.eResizeR = self.builder.get_object("eResizeR")
        self.bLock = self.builder.get_object("bLock")
        self.imgLock = self.builder.get_object("imgLock")
        self.imgUnlock = self.builder.get_object("imgUnlock")
        self.bClose = self.builder.get_object("bClose")
        self.confirmDelete = self.builder.get_object("confirmDelete")
        # Load CSS template and initialize Gtk.CssProvider
        with open(os.path.join(self.path, "style.css")) as css_file:
            self.css_template = Template(css_file.read())
        self.css = Gtk.CssProvider()
        self.style_contexts = [self.winMain.get_style_context(),
                self.txtNote.get_style_context()]
        # Update window-specific style. Global styles are loaded initially!
        self.update_style()
        # Ensure buttons are displayed with images
        settings = Gtk.Settings.get_default()
        settings.props.gtk_button_images = True
        # Set text buffer
        self.bbody = GtkSource.Buffer()
        self.bbody.begin_not_undoable_action()
        self.bbody.set_text(self.note.body)
        self.bbody.set_highlight_matching_brackets(False)
        self.bbody.end_not_undoable_action()
        self.txtNote.set_buffer(self.bbody)
        # Show and hide so winMain and widgets are realized and mapped.
        self.winMain.show()
        self.winMain.hide()
        # Make resize work
        self.winMain.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.eResizeR.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        # Move Window
        self.winMain.move(*self.note.properties.get("position", (10,10)))
        self.winMain.resize(*self.note.properties.get("size", (200,150)))
        # Mouse over
        self.eResizeR.get_window().set_cursor(Gdk.Cursor.new_for_display(
                    self.eResizeR.get_window().get_display(),
                    Gdk.CursorType.BOTTOM_RIGHT_CORNER))
        # Set locked state
        self.set_locked_state(self.locked)

    def show(self, widget=None, event=None):
        """Shows the stickynotes window"""
        self.winMain.present()
        self.winMain.stick()
        self.winMain.move(*self.note.properties.get("position", (10,10)))
        self.winMain.resize(*self.note.properties.get("size", (200,150)))

    def hide(self, *args):
        """Hides the stickynotes window"""
        self.winMain.hide()

    def update_note(self):
        """Update the underlying note object"""
        self.note.update(self.bbody.get_text(self.bbody.get_start_iter(),
            self.bbody.get_end_iter(), True))

    def move(self, widget, event):
        """Action to begin moving (by dragging) the window"""
        self.winMain.begin_move_drag(event.button, event.x_root,
                event.y_root, event.get_time())
        return False

    def resize(self, widget, event, *args):
        """Action to begin resizing (by dragging) the window"""
        self.winMain.begin_resize_drag(Gdk.WindowEdge.SOUTH_EAST,
                event.button, event.x_root, event.y_root, event.get_time())
        return True

    def properties(self):
        """Get properties of the current note"""
        prop = {"position":self.winMain.get_position(),
                "size":self.winMain.get_size(), "locked":self.locked}
        if not self.winMain.get_visible():
            prop["position"] = self.note.properties.get("position", (10, 10))
            prop["size"] = self.note.properties.get("size", (200, 150))
        return prop

    def update_style(self):
        """Updates the style using CSS template"""
        css_string = self.css_template.substitute(**self.css_data())\
                .encode("ascii", "replace")
        self.css.load_from_data(css_string)
        for context in self.style_contexts:
            context.add_provider(self.css,
                    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def css_data(self):
        """Returns data to substitute into the CSS template"""
        data = {}
        # Converts to RGB hex. All RGB/HSV values are scaled to a max of 1
        rgb_to_hex = lambda x: "#" + "".join(["{:02x}".format(int(255*a))
            for a in x])
        hsv_to_hex = lambda x: rgb_to_hex(colorsys.hsv_to_rgb(*x))
        bg_end_hsv = self.note.cat_prop("bgcolor_hsv")
        # bg_start_hsv is computed by "lightening" bg_end_hsv. 
        bg_start_hsv = [bg_end_hsv[0], bg_end_hsv[1], bg_end_hsv[2] + .60]
        if bg_start_hsv[2] > 1:
            bg_start_hsv[1] -= bg_start_hsv[2] - 1
            bg_start_hsv[2] = 1
        if bg_start_hsv[1] < 0:
            bg_start_hsv[1] = 0
        data.update({"bg_start": hsv_to_hex(bg_start_hsv), "bg_end":
                hsv_to_hex(bg_end_hsv)})
        data["text_color"] = rgb_to_hex(self.note.cat_prop("textcolor"))
        return data

    def save(self, *args):
        self.note.noteset.save()
        return False

    def add(self, *args):
        self.note.noteset.new()
        return False

    def delete(self, *args):
        confirm = self.confirmDelete.run()
        self.confirmDelete.hide()
        if confirm == 1:
            self.note.delete()
            self.winMain.hide()
            return False
        else:
            return True

    def set_locked_state(self, locked):
        """Change the locked state of the stickynote"""
        self.locked = locked
        self.txtNote.set_editable(not self.locked)
        self.txtNote.set_cursor_visible(not self.locked)
        self.bLock.set_image({True:self.imgLock,
            False:self.imgUnlock}[self.locked])
        self.bLock.set_tooltip_text({True: _("Unlock"),
            False: _("Lock")}[self.locked])

    def lock_clicked(self, *args):
        """Toggle the locked state of the note"""
        self.set_locked_state(not self.locked)

    def quit(self, *args):
        Gtk.main_quit()

    def focus_out(self, *args):
        self.save(*args)

def show_about_dialog():
    glade_file = os.path.abspath(os.path.join(os.path.dirname(__file__),
            '..', "GlobalDialogs.glade"))
    builder = Gtk.Builder()
    builder.add_from_file(glade_file)
    winAbout = builder.get_object("AboutWindow")
    ret =  winAbout.run()
    winAbout.destroy()
    return ret

class SettingsDialog:
    """Manages the GUI of the settings dialog"""
    def __init__(self, noteset):
        self.noteset = noteset
        self.path = os.path.abspath(os.path.join(os.path.dirname(__file__),
            '..'))
        glade_file = (os.path.join(self.path, "GlobalDialogs.glade"))
        self.builder = Gtk.Builder()
        self.builder.add_from_file(glade_file)
        self.builder.connect_signals(self)
        widgets = ["wSettings", "bgcolor", "textcolor"]
        for w in widgets:
            setattr(self, w, self.builder.get_object(w))
        self.bgcolor.set_rgba(Gdk.RGBA(*colorsys.hsv_to_rgb(
            *self.note.cat_prop("bgcolor_hsv")), alpha=1))
        self.textcolor.set_rgba(Gdk.RGBA(*self.note.cat_prop(
            "textcolor"), alpha=1))
        ret =  self.wSettings.run()
        self.wSettings.destroy()

    def update_color(self, *args):
        """Action to update the default background color"""
        try:
            rgba = self.bgcolor.get_rgba()
        except TypeError:
            rgba = Gdk.RGBA()
            self.bgcolor.get_rgba(rgba)
            # Some versions of GObjectIntrospection are affected by
            # https://bugzilla.gnome.org/show_bug.cgi?id=687633 
        hsv = colorsys.rgb_to_hsv(rgba.red, rgba.green, rgba.blue)
        self.noteset.properties["d_bgcolor_hsv"] = hsv
        for note in self.noteset.notes:
            note.gui.update_style()
        # Remind GtkSourceView's that they are transparent, etc.
        load_global_css()

    def update_textcolor(self, *args):
        """Action to update the default text color"""
        try:
            rgba = self.textcolor.get_rgba()
        except TypeError:
            rgba = Gdk.RGBA()
            self.textcolor.get_rgba(rgba)
        self.noteset.properties["d_textcolor"] = [rgba.red, rgba.green, rgba.blue]
        for note in self.noteset.notes:
            note.gui.update_style()
