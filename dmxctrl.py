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
VERSION = '0.4'
TITLE_VERSION = '%s v%s' % (TITLE, VERSION)
COPYRIGHT = '🄯 2022 MC-6312'
URL = 'https://github.com/mc6312/dmxctrl'


from gtktools import *
from gi.repository import Gtk, GLib, Gdk #, GObject, Pango
from gi.repository.GdkPixbuf import Pixbuf
import cairo
from math import pi

import sys
import os.path
from traceback import format_exception
from array import array
from ola.ClientWrapper import ClientWrapper

from dmxctrldata import *


from colorsys import hls_to_rgb


# значения цветов для функции hls_to_rgb()
__HUE_360 = 1.0 / 360
PALETTE_HUE_NAMES = {
    'RED':      0.0,
    'GREEN':    120 * __HUE_360,
    'BLUE':     240 * __HUE_360,
    'ORANGE':   30 * __HUE_360,
    'YELLOW':   60 * __HUE_360,
    'CYAN':     180 * __HUE_360,
    'MAGENTA':  300 * __HUE_360,
    }

COLORS_PALETTE_COLS = len(PALETTE_HUE_NAMES)

def __init_palette():
    pal = []

    SATURATIONS = 8

    for sat in range(SATURATIONS):
        for hue in PALETTE_HUE_NAMES.values():
            r, g, b = hls_to_rgb(hue, 0.5, 1.0 / (1 + sat))
            rgba = Gdk.RGBA(r, g, b, 1.0)
            pal.append(rgba)

    return pal


COLORS_PALETTE = __init_palette()


class ControlWidget():
    """Костыль для увязывания Gtk-виджета и dmxctrldata.Control.

    Атрибуты:
        widget      - экземпляр потомка Gtk.Widget, создаётся конструктором
                      для добавления в UI, может содержать другие виджеты;
        control     - экземпляр потомка dmxctrldata.Control, на основе
                      которого создаются виджеты;
        onChange    - callback - функция или метод, вызываемый при изменении
                      значения виджетом;
                      принимает два параметра:
                      1й: ссылка на экземпляр ControlWidget;
                      2й: список значений для каналов DMX512."""

    def __init__(self, control_, onChange_):
        """Конструктор должен быть перекрыт классом-потомком"""

        self.widget = None
        self.control = control_
        self.onChange = onChange_

    def setMinLevel(self):
        """Установка максимального значения"""

        pass

    def setMaxLevel(self):
        """Установка минимального значения"""
        pass

    def getChannelValues(self):
        return [0]


class PanelWidget(ControlWidget):
    def __init__(self, control_, onChange_):
        super().__init__(control_, onChange_)

        self.widget = Gtk.Frame.new()

        if not self.control.hidename or self.control.icon:
            lbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, WIDGET_SPACING)
            lbox.set_border_width(WIDGET_SPACING)

            if self.control.icon:
                lbox.pack_start(Gtk.Image.new_from_pixbuf(self.control.icon), False, False, 0)

            if not self.control.hidename:
                lbox.pack_start(Gtk.Label.new(self.control.name), False, False, 0)

            self.widget.set_label_widget(lbox)

        self.widget.set_label_align(0.5, 0.5)
        self.widget.set_tooltip_text(control_.getCommentStr())

    def add_child(self, cw):
        self.widget.add(cw)


class LevelWidget(ControlWidget):
    def __init__(self, control_, onChange_):
        super().__init__(control_, onChange_)

        self.widget = Gtk.Box.new(Gtk.Orientation.VERTICAL, WIDGET_SPACING)

        tts = control_.getCommentStr()

        if not control_.hidename:
            slab = Gtk.Label.new(control_.name)
            slab.set_tooltip_text(tts)
            if len(control_.name) > 2:
                slab.set_angle(270)

            self.widget.pack_start(slab, False, False, 0)

        if control_.icon:
            self.widget.pack_start(Gtk.Image.new_from_pixbuf(control_.icon), False, False, 0)

        #!!!
        self.scale = Gtk.Scale.new(Gtk.Orientation.VERTICAL, None)
        self.scale.set_tooltip_text(tts)
        self.scale.set_draw_value(False)
        self.scale.set_range(0, 255)
        self.scale.set_inverted(True)
        self.scale.set_value(control_.value)

        self.scale.connect('value-changed', self.level_changed)

        self.widget.pack_start(self.scale, True, True, 0)

    def level_changed(self, scale):
        self.onChange(self, [int(self.scale.get_value())])

    def setMinLevel(self):
        self.scale.set_value(0)

    def setMaxLevel(self):
        self.scale.set_value(255)


class ColorLevelWidget(LevelWidget):
    def __init__(self, control_, onChange_):
        super().__init__(control_, onChange_)

        rgba = Gdk.RGBA()
        rgba.parse(control_.color)

        self.clrbtn = Gtk.ColorButton.new_with_rgba(rgba)
        self.clrbtn.add_palette(Gtk.Orientation.VERTICAL, 1, None)
        self.clrbtn.add_palette(Gtk.Orientation.VERTICAL,
                           COLORS_PALETTE_COLS,
                           COLORS_PALETTE)
        self.clrbtn.connect('color-set', self.level_changed)

        self.widget.pack_end(self.clrbtn, False, False, 0)

    def level_changed(self, wgt):
        level = self.scale.get_value()
        # 0.0 - 255.0

        rgba = self.clrbtn.get_rgba()
        # 0.0 - 1.0

        self.onChange(self, [int(rgba.red * level),
                             int(rgba.green * level),
                             int(rgba.blue * level)])



CONTROL_WIDGETS = {Panel: PanelWidget,
    Level: LevelWidget,
    ColorLevel: ColorLevelWidget}


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

        self.smallIconSizePx = Gtk.IconSize.lookup(Gtk.IconSize.MENU)[-1]

        winIconSizePx = Gtk.IconSize.lookup(Gtk.IconSize.DIALOG)[1] * 2
        icon = resldr.load_pixbuf('images/dmxctrls.svg', winIconSizePx, winIconSizePx)
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
        self.dlgAbout = uibldr.get_object('dlgAbout')
        self.dlgAbout.set_logo(icon)
        self.dlgAbout.set_program_name(TITLE)
        #self.dlgAbout.set_comments(SUB_TITLE)
        self.dlgAbout.set_version('v%s' % VERSION)
        self.dlgAbout.set_copyright(COPYRIGHT)
        self.dlgAbout.set_website(URL)
        self.dlgAbout.set_website_label(URL)

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
        self.icons = dict()
        self.create_named_icons()

        print('Setting up console...', file=sys.stderr)
        if self.consoleFile:
            self.load_console()

        self.window.show_all()
        uibldr.connect_signals(self)

        GLib.timeout_add(1000 / 30, self.timer_func, None)

    def create_named_icons(self):
        for iname, ihue in PALETTE_HUE_NAMES.items():
            r, g, b = hls_to_rgb(ihue, 0.5, 1.0)

            csurf = cairo.ImageSurface(cairo.FORMAT_ARGB32, self.smallIconSizePx, self.smallIconSizePx)

            cc = cairo.Context(csurf)
            #cc.scale(iconSize, iconSize)

            center = self.smallIconSizePx / 2.0
            radius = center * 0.7
            circle = 2 * pi

            cc.set_source(cairo.SolidPattern(0.0, 0.0, 0.0))

            cc.arc(center, center, radius, 0.0, circle)
            cc.fill()

            radius1 = radius - 1.0

            cc.set_source(cairo.SolidPattern(r, g, b))
            cc.arc(center, center, radius1, 0.0, circle)
            cc.fill()

            self.icons[iname.lower()] = Gdk.pixbuf_get_from_surface(csurf, 0, 0, self.smallIconSizePx, self.smallIconSizePx)

    def mnuMainAbout_activate(self, mnu):
        self.dlgAbout.show_all()
        self.dlgAbout.run()
        self.dlgAbout.hide()

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
        etrace = '\n'.join(format_exception(*sys.exc_info()))
        ex = str(ex)

        print('%s\n%s' % (ex, etrace), file=sys.stderr)

        self.labExMessage.set_text(ex)
        self.labExInfo.set_text(etrace)

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

        def load_control_icon(ctrl):
            """Загружает Gdk.Pixbuf из файла и масштабирует
            до размера стандартной иконки и присваивает
            экземпляр Gdk.Pixbuf атрибуту ctrl.icon."""

            filename = ctrl.iconName
            fromFile = True

            if filename.startswith('@'):
                # путь относительно загружаемого файла описания консоли
                filename = os.path.join(os.path.split(self.consoleFile)[0], filename[1:])
            elif filename.startswith('!'):
                # встроенная иконка
                fromFile = False
                filename = filename[1:]
            else:
                filename = os.path.abspath(os.path.expanduser(filename))

            #print('load_control_icon(): loading from "%s"' %  filename, file=sys.stderr)

            ctrl.icon = self.icons[filename] if not fromFile else Pixbuf.new_from_file_at_size(filename,
                                                                        self.smallIconSizePx,
                                                                        self.smallIconSizePx)

        def _build_console_widgets(ctrl):
            """Рекурсивное создание Gtk.Widget соотв. типа.
            На входе: экземпляр Control.
            На выходе: Gtk.Widget."""

            ctltype = type(ctrl)
            cwgtclass = CONTROL_WIDGETS.get(ctltype, None)
            if cwgtclass is None:
                raise Exception('Internal error: unimplemented support for control: %s' % ctltype.__name__)

            if ctrl.iconName:
                load_control_icon(ctrl)

            cwgt = cwgtclass(ctrl, self.onControlChanged)
            self.consoleWidgets.append(cwgt)

            if isinstance(ctrl, Container):
                if len(ctrl.children) == 1:
                    cwgtchild = _build_console_widgets(ctrl.children[0])
                else:
                    cwgtchild = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, WIDGET_SPACING)

                    for child in ctrl.children:
                        subwgt = _build_console_widgets(child)
                        cwgtchild.pack_start(subwgt, False, False, 0)

                cwgtchild.set_border_width(WIDGET_SPACING)
                cwgt.add_child(cwgtchild)

            return cwgt.widget

        self.dmxSendEnabled = False

        __step = ''

        def __show_step():
            print('%s...' % __step, file=sys.stderr)

        if self.consoleFile:
            try:
                __step = 'Loading console from "%s"' % self.consoleFile
                __show_step()

                self.console = DMXControlsLoader(self.consoleFile)

                self.headerBar.set_tooltip_text(self.console.getCommentStr())

                __step = 'Building console UI'
                __show_step()
                for cc in self.console.children:
                    self.boxControls.insert(_build_console_widgets(cc), -1)

            except Exception as ex:
                self.show_exception('%s error.\n%s' % (__step, ex))
                _clear_console()

        self.boxControls.show_all()

        self.dmxSendEnabled = self.console is not None

        st = os.path.splitext(os.path.split(self.consoleFile)[-1])[0]

        if self.console and self.console.name:
            st = self.console.name

        self.headerBar.set_subtitle(st)

    def onControlChanged(self, ctrlwgt, chanValues):
        for ixch, cv in enumerate(chanValues, ctrlwgt.control.channel - 1):
            self.channels[ixch] = cv

    def btnAllLevelsMin_clicked(self, btn):
        for wctl in self.consoleWidgets:
            wctl.setMinLevel()

    def btnAllLevelsMax_clicked(self, btn):
        for wctl in self.consoleWidgets:
            wctl.setMaxLevel()

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
