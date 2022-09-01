#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" dmxctrl.py

    Copyright 2022 MC-6312

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>."""


TITLE = 'DMXCtrl'
VERSION = '0.2'
TITLE_VERSION = '%s v%s' % (TITLE, VERSION)


from gtktools import *
from gi.repository import Gtk, GLib #, Gdk, GObject, Pango
#from gi.repository.GdkPixbuf import Pixbuf

import sys
from traceback import format_exception
from array import array
from ola.ClientWrapper import ClientWrapper

from dmxctrldata import *


class ControlWidget():
    """Костыль для увязывания Gtk-виджета и dmxctrldata.Control"""

    def __init__(self, control, widget):
        self.widget = widget
        self.control = control

    def setMinLevel(self):
        pass

    def setMaxLevel(self):
        pass

    def getChannelValues(self):
        return 0


class LevelWidget(ControlWidget):
    def setMinLevel(self):
        self.widget.set_value(0)

    def setMaxLevel(self):
        self.widget.set_value(255)

    def getChannelValues(self):
        return [int(self.widget.get_value())]


class MainWnd():
    def wnd_destroy(self, widget, data=None):
        self.dmxSendEnabled = False
        self.dmxTimer = False
        Gtk.main_quit()

    def __init__(self):
        resldr = get_resource_loader()
        uibldr = resldr.load_gtk_builder('dmxctrl.ui')

        print('DMX client wrapper initialization...', file=sys.stderr)
        self.wrapper = ClientWrapper()

        self.window, self.headerBar, self.boxControls = get_ui_widgets(uibldr, 'wndConsole', 'headerBar', 'boxControls')

        iconsize = Gtk.IconSize.lookup(Gtk.IconSize.DIALOG)[1] * 4
        icon = resldr.load_pixbuf('images/dmxctrls.svg', iconsize, iconsize)
        self.window.set_icon(icon)

        self.window.set_title(TITLE_VERSION)
        self.window.set_size_request(WIDGET_BASE_WIDTH * 60, WIDGET_BASE_HEIGHT * 20)

        self.consoleFile = ''
        self.console = None
        self.consoleWidgets = []
        self.channels = array('B', [0] * 512)
        self.dmxSendEnabled = True
        self.dmxTimer = True

        #
        #
        #
        self.dlgException, self.labExMessage, self.labExInfo = get_ui_widgets(uibldr,
            'dlgException', 'labExMessage', 'labExInfo')
        #
        #
        #

        self.__process_cmdline()

        #
        #
        #
        self.dlgFileOpen = uibldr.get_object('dlgFileOpen')

        #
        #
        #

        print('Setting up console...', file=sys.stderr)
        if self.consoleFile:
            self.load_console()

        self.window.show_all()
        uibldr.connect_signals(self)

        GLib.timeout_add(1000 / 30, self.timer_func, None)

    def mnuFileOpen_activate(self, mnu):
        if self.consoleFile:
            self.dlgFileOpen.select_filename(self.consoleFile)

        self.dlgFileOpen.show_all()
        r = self.dlgFileOpen.run()
        self.dlgFileOpen.hide()

        if r == Gtk.ResponseType.OK:
            fn = self.dlgFileOpen.get_filename()

            if fn:
                self.consoleFile = fn
                self.load_console()

    def show_exception(self, ex):
        efmt = format_exception(*sys.exc_info())

        self.labExMessage.set_text(str(ex))
        self.labExInfo.set_text('\n'.join(efmt))

        self.dlgException.show_all()
        self.dlgException.run()
        self.dlgException.hide()

    def __process_cmdline(self):
        if len(sys.argv) >= 2:
            self.consoleFile = os.path.abspath(sys.argv[1])

    def load_console(self):
        def _clear_console():
            self.console = None
            self.consoleWidgets.clear()

            for i in range(len(self.channels)):
                self.channels[i] = 0

            for wg in self.boxControls.get_children():
                wg.destroy()

        _clear_console()

        def _build_console_widgets(ctrl):
            """Рекурсивное создание Gtk.Widget соотв. типа.
            На входе: экземпляр Control.
            На выходе: Gtk.Widget."""

            def _children_widgets(ctrl):
                if len(ctrl.children) == 1:
                    return _build_console_widgets(ctrl.children[0])
                else:
                    box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, WIDGET_SPACING)

                    for child in ctrl.children:
                        cwgt = _build_console_widgets(child)
                        box.pack_start(cwgt, False, False, 0)

                    return box

            def _make_level(level):
                box = Gtk.Box.new(Gtk.Orientation.VERTICAL, WIDGET_SPACING)

                tts = level.getCommentStr()

                slab = Gtk.Label.new(level.name)
                slab.set_tooltip_text(tts)
                if len(level.name) > 2:
                    slab.set_angle(270)

                box.pack_start(slab, False, False, 0)

                #!!!
                scale = Gtk.Scale.new(Gtk.Orientation.VERTICAL, None)
                scale.set_tooltip_text(tts)
                scale.set_draw_value(False)
                scale.set_range(0, 255)
                scale.set_inverted(True)

                lw = LevelWidget(level, scale)
                scale.connect('value-changed', self.level_changed, lw)
                self.consoleWidgets.append(lw)

                box.pack_start(scale, True, True, 0)

                return box

            if isinstance(ctrl, Level):
                return _make_level(ctrl)

            elif isinstance(ctrl, Panel):
                ret = Gtk.Frame.new(ctrl.name)
                ret.set_label_align(0.5, 0.5)
                ret.set_tooltip_text(ctrl.getCommentStr())

                cwgt = _children_widgets(ctrl)
                cwgt.set_border_width(WIDGET_SPACING)
                ret.add(cwgt)
                return ret

            else:
                raise Exception('Internal error: unimplemented support for control: %s' % ctrl.__class__.__name__)

        self.dmxSendEnabled = False

        if self.consoleFile:
            try:
                print('Loading console from "%s"...' % self.consoleFile, file=sys.stderr)

                self.console = DMXControlsLoader(self.consoleFile)

                self.headerBar.set_tooltip_text(self.console.getCommentStr())

                for cc in self.console.children:
                    #self.hboxControls.pack_start(_build_console_widgets(cc), False, False, 0)
                    self.boxControls.insert(_build_console_widgets(cc), -1)

            except Exception as ex:
                self.show_exception('Error loading console description from file "%s".\n%s' % (self.consoleFile, ex))
                _clear_console()

        self.boxControls.show_all()

        self.dmxSendEnabled = self.console is not None

        st = os.path.splitext(os.path.split(self.consoleFile)[-1])[0]

        if self.console and self.console.name:
            st = self.console.name

        self.headerBar.set_subtitle(st)

    def btnAllLevelsMin_clicked(self, btn):
        for wctl in self.consoleWidgets:
            wctl.setMinLevel()

    def btnAllLevelsMax_clicked(self, btn):
        for wctl in self.consoleWidgets:
            wctl.setMaxLevel()

    def level_changed(self, scale, lw):
        for ixch, cv in enumerate(lw.getChannelValues(), lw.control.channel - 1):
            self.channels[ixch] = cv

    def btnDebug_clicked(self, btn):
        ixch = 0
        for y in range(16):
            print('%.3d  \033[1m%s\033[0m' % (ixch, ' '.join(map(lambda v: '%.2x' % v, self.channels[ixch:ixch + 32]))))
            ixch += 32

    def __DMX_sent(self, state):
        #self.lastState = state

        if not state.Succeeded():
            self.wrapper.Stop()
            print('DMX communication error %s' % str(state), file=sys.stderr)

    def timer_func(self, data):
        if self.dmxSendEnabled and self.console:
            self.wrapper.Client().SendDmx(self.console.universe, self.channels, self.__DMX_sent)

        return self.dmxTimer

    def main(self):
        Gtk.main()


def main():
    MainWnd().main()

    return 0

if __name__ == '__main__':
    print('[debugging %s]' % __file__)

    sys.argv.append('example.dmxctrl')
    sys.exit(main())
