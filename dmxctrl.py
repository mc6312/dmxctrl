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


DEBUG = False

TITLE = 'DMXCtrl'
VERSION = '0.5%s' % (' [DEBUG]' if DEBUG else '')
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
from dmxctrlcfg import *

from colorsys import hls_to_rgb


COLORS_PALETTE_COLS = len(PALETTE_HUE_NAMES)

def __init_palette():
    pal = []

    __PALETTE_SATURATIONS = 9

    for sat in range(__PALETTE_SATURATIONS):
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
        owner       - экземпляр Gtk.Window - окна консоли."""

    def setup(self):
        """Создание виджетов, установка значений атрибутов.
        Метод должен быть перекрыт классом-потомком."""

        raise NotImplementedError('%s.create_widgets() not implemented' % self.__class__.__name__)

    def value_changed(self, widget):
        """Метод должен вызываться при изменении значения (положения
        движка и т.п.). Также он вызывается из конструктора после
        создания всех виджетов и установки значений атрибутов.
        Для отсылки значений каналов устройствам в конкретной реализации
        этого метода должен быть вызов self.owner.set_channel_values().
        Метод должен быть перекрыт классом-потомком."""

        pass

    def __init__(self, control_, owner_):
        """Конструктор не должен перекрываться классом-потомком без
        большой необходимости. Действия, которые требуется совершить
        при инициализации, должны выполняться методом setup()."""

        self.widget = None
        self.control = control_
        self.owner = owner_

        self.setup()

        # первый вызов - начальные значения уровней в каналах
        # загружены из файла, и их следует сразу послать устройствам
        self.value_changed(self)

    def setMinLevel(self):
        """Установка максимального значения"""

        pass

    def setMaxLevel(self):
        """Установка минимального значения"""
        pass


class PanelWidget(ControlWidget):
    def setup(self):
        self.widget = Gtk.Frame.new()
        self.widget.set_can_focus(False)

        if not self.control.hidename or self.control.icon:
            lbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, WIDGET_SPACING)
            lbox.set_border_width(WIDGET_SPACING)

            if self.control.icon:
                lbox.pack_start(self.owner.load_icon_image(self.control), False, False, 0)

            if not self.control.hidename:
                lbox.pack_start(Gtk.Label.new(self.control.name), False, False, 0)

            self.widget.set_label_widget(lbox)

        self.widget.set_label_align(0.5, 0.5)
        self.widget.set_tooltip_text(self.control.getCommentStr())

    def add_child(self, cw):
        self.widget.add(cw)


class LevelWidget(ControlWidget):
    def setup(self):
        self.widget = Gtk.Box.new(Gtk.Orientation.VERTICAL, WIDGET_SPACING)

        tts = self.control.getCommentStr()

        if not self.control.hidename:
            slab = Gtk.Label.new(self.control.name)
            slab.set_tooltip_text(tts)
            if len(self.control.name) > 2:
                slab.set_angle(270)

            self.widget.pack_start(slab, False, False, 0)

        if self.control.icon:
            self.widget.pack_start(self.owner.load_icon_image(self.control), False, False, 0)

        #!!!
        if self.control.steps > 0:
            sstep = 255.0 / self.control.steps
        else:
            sstep = 1.0

        self.adjustment = Gtk.Adjustment.new(self.control.value,
            0.0, 255.0,
            sstep,
            16.0 if self.control.steps == 0 else sstep,
            0.0)

        self.scale = Gtk.Scale.new(Gtk.Orientation.VERTICAL, None)
        self.scale.set_tooltip_text(tts)
        self.scale.set_draw_value(False)
        self.scale.set_inverted(True)

        if self.control.steps > 0:
            spos = 0.0

            nsteps = self.control.steps
            while nsteps > 0:
                self.scale.add_mark(spos, Gtk.PositionType.LEFT, None)
                spos += sstep
                nsteps -= 1

        self.scale.set_adjustment(self.adjustment)

        self.scale.connect('value-changed', self.value_changed)

        self.widget.pack_start(self.scale, True, True, 0)

    def value_changed(self, scale):
        self.owner.set_channel_values(self.control.channel, [int(self.scale.get_value())])

    def setMinLevel(self):
        self.scale.set_value(0)

    def setMaxLevel(self):
        self.scale.set_value(255)


class ColorLevelWidget(LevelWidget):
    def setup(self):
        super().setup()

        rgba = Gdk.RGBA()
        rgba.parse(self.control.color)

        self.clrbtn = Gtk.ColorButton.new_with_rgba(rgba)
        self.clrbtn.add_palette(Gtk.Orientation.VERTICAL, 1, None)
        self.clrbtn.add_palette(Gtk.Orientation.VERTICAL,
                           COLORS_PALETTE_COLS,
                           COLORS_PALETTE)
        self.clrbtn.connect('color-set', self.value_changed)

        self.widget.pack_end(self.clrbtn, False, False, 0)

    def value_changed(self, wgt):
        level = self.scale.get_value()
        # 0.0 - 255.0

        rgba = self.clrbtn.get_rgba()
        # 0.0 - 1.0

        self.owner.set_channel_values(self.control.channel,
                            [int(rgba.red * level),
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

    def __init__(self, cfg):
        self.cfg = cfg

        resldr = get_resource_loader()
        uibldr = resldr.load_gtk_builder('dmxctrl.ui')

        iconSize = Gtk.IconSize.MENU

        print('DMX client wrapper initialization...', file=sys.stderr)
        self.wrapper = ClientWrapper()

        self.window, self.headerBar,\
        imgTbtnConsoleScrollable, self.tbtnConsoleScrollable,\
        self.mnuMainConsoleScrollable = get_ui_widgets(uibldr,
            'wndConsole', 'headerBar', 'imgTbtnConsoleScrollable',
            'tbtnConsoleScrollable', 'mnuMainConsoleScrollable')

        imgTbtnConsoleScrollable.set_from_pixbuf(resldr.load_pixbuf_icon_size('images/consolescrollable.svg', iconSize))
        #
        self.swnd = Gtk.ScrolledWindow()
        self.swnd.set_border_width(WIDGET_SPACING)

        self.setup_console_scrollability(self.cfg.consoleScrollability)

        self.swnd.set_overlay_scrolling(False)
        #self.swnd.set_min_content_width(WIDGET_BASE_WIDTH * 40)
        self.swnd.set_propagate_natural_width(True)

        self.window.add(self.swnd)
        self.window.set_size_request(-1, WIDGET_BASE_HEIGHT * 20)

        self.boxControls = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, WIDGET_SPACING)
        self.swnd.add(self.boxControls)

        if DEBUG:
            imgDebug = Gtk.Image.new_from_icon_name('dialog-warning', iconSize)
            imgDebug.set_tooltip_text('Warning!\nDebug version!')
            self.headerBar.pack_end(imgDebug)

        self.smallIconSizePx = Gtk.IconSize.lookup(iconSize)[-1]

        winIconSizePx = Gtk.IconSize.lookup(Gtk.IconSize.DIALOG)[1] * 2
        #print(f'{winIconSizePx=}, {Gtk.IconSize.lookup(iconSize)[0]=}')
        icon = resldr.load_pixbuf('images/dmxctrls.svg', winIconSizePx, winIconSizePx)
        self.window.set_icon(icon)

        self.window.set_title(TITLE_VERSION)

        self.consoleFile = ''
        self.console = None
        self.consoleWidgets = []
        #!!!
        self.channels = array('B', [0] * 512)
        #
        self.dmxSendEnabled = True
        self.dmxTimer = True

        #
        #
        #
        self.mnuFileRecent = uibldr.get_object('mnuFileRecent')
        self.update_recent_files_menu()

        #
        #
        #
        self.dlgAbout = uibldr.get_object('dlgAbout')
        self.dlgAbout.set_logo(icon)
        self.dlgAbout.set_program_name(TITLE)
        self.dlgAbout.set_version('v%s' % VERSION)
        self.dlgAbout.set_copyright(COPYRIGHT)
        self.dlgAbout.set_website(URL)
        self.dlgAbout.set_website_label(URL)

        #
        #
        #
        mnuMainDumpChannels = uibldr.get_object('mnuMainDumpChannels')

        mnuMainDumpChannels.set_sensitive(DEBUG)
        mnuMainDumpChannels.set_visible(DEBUG)
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

    def setup_console_scrollability(self, s):
        self.cfg.consoleScrollability = s

        self.swnd.set_policy(Gtk.PolicyType.AUTOMATIC if s else Gtk.PolicyType.NEVER,
            Gtk.PolicyType.NEVER)

        self.tbtnConsoleScrollable.set_active(s)
        self.mnuMainConsoleScrollable.set_active(s)

    def tbtnConsoleScrollable_toggled(self, btn):
        self.setup_console_scrollability(btn.get_active())

    def mnuMainConsoleScrollable_toggled(self, mi):
        self.setup_console_scrollability(mi.get_active())

    def update_recent_files_menu(self):
        if not self.cfg.recentFiles:
            self.mnuFileRecent.set_submenu()
        else:
            mnu = Gtk.Menu.new()
            mnu.set_reserve_toggle_size(False)

            for ix, rfn in enumerate(self.cfg.recentFiles):
                # сокращаем отображаемое имя файла, длину пока приколотим гвоздями
                #TODO когда-нибудь сделать сокращение отображаемого в меню имени файла по человечески
                lrfn = len(rfn)
                if lrfn > 40:
                    disprfn = '%s...%s' % (rfn[:3], rfn[lrfn - 34:])
                else:
                    disprfn = rfn

                mi = Gtk.MenuItem.new_with_label(disprfn)
                mi.connect('activate', self.file_open_recent, ix)
                mnu.append(mi)

            mnu.show_all()

            self.mnuFileRecent.set_submenu(mnu)

    def file_open_recent(self, wgt, ix):
        fname = self.cfg.recentFiles[ix]

        # проверяем наличие файла обязательно, т.к. в списке недавних
        # могут быть уже удалённые файлы или лежащие на внешних
        # неподключённых носителях
        # при этом метод file_open_filename() проверку производить
        # не должен, т.к. в первую очередь расчитан на вызов после
        # диалога выбора файла, который несуществующего файла не вернёт.
        # кроме того, сообщение об недоступном файле _здесь_ должно
        # отличаться от просто "нету файла"

        if not os.path.exists(fname):
            msg_dialog(self.window, TITLE,
                'File "%s" is missing' % fname)
        else:
            self.consoleFile = fname
            self.load_console()

    def create_named_icons(self):
        for iname, ihue in PALETTE_HUE_NAMES.items():
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

            cc.set_source(cairo.SolidPattern(*hls_to_rgb(ihue, 0.5, 1.0)))
            cc.arc(center, center, radius1, 0.0, circle)
            cc.fill()

            self.icons[iname.lower()] = Gdk.pixbuf_get_from_surface(csurf, 0, 0, self.smallIconSizePx, self.smallIconSizePx)

    def mnuMainAbout_activate(self, mnu):
        self.dlgAbout.show_all()
        self.dlgAbout.run()
        self.dlgAbout.hide()

    def mnuMainDumpChannels_activate(self, mnu):
        cd = []

        cn = 0
        for row in range(16):
            cr = ['%.3d:' % cn]

            for col in range(32):
                cr.append('%.2x' % self.channels[cn])
                cn += 1

            cd.append(' '.join(cr))

        print('*** Channel values ***\n%s' % ('\n'.join(cd)))

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
                if self.load_console():
                    self.cfg.add_recent_file(fn)
                    self.update_recent_files_menu()

    def show_exception(self, ex):
        etrace = '\n'.join(format_exception(*sys.exc_info()))
        ex = str(ex)

        print('%s\n%s' % (ex, etrace), file=sys.stderr)

        msg_dialog(self.window, 'Error', ex)

    def __process_cmdline(self):
        if len(sys.argv) >= 2:
            self.consoleFile = os.path.abspath(sys.argv[1])

    def load_icon_image(self, ctrl):
        """Загрузка иконки (встроенной или из файла) с именем ctrl.icon.
        Возвращает экземпляр Gtk.Image."""

        # на этом этапе ctrl.icon содержит правильный путь
        # или проверенное имя встроенной иконки
        if ctrl.isInternalIcon:
            pbuf = self.icons[ctrl.icon]
        else:
            pbuf = Pixbuf.new_from_file_at_size(ctrl.icon,
                                                self.smallIconSizePx,
                                                self.smallIconSizePx)

        return Gtk.Image.new_from_pixbuf(pbuf)

    def load_console(self):
        """Загрузка файла описания консоли.
        Путь к файлу должен быть в self.consoleFile.
        Метод возвращает булевское значение - True в случае успешной загрузки."""

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

            ctltype = type(ctrl)
            cwgtclass = CONTROL_WIDGETS.get(ctltype, None)
            if cwgtclass is None:
                raise Exception('Internal error: unimplemented support for control: %s' % ctltype.__name__)

            cwgt = cwgtclass(ctrl, self)
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

                self.console = DMXControls(self.consoleFile)

                self.headerBar.set_tooltip_text(self.console.getCommentStr())

                __step = 'Building console UI'
                __show_step()
                for cc in self.console.children:
                    self.boxControls.pack_start(_build_console_widgets(cc), False, False, 0)
                    #self.boxControls.insert(_build_console_widgets(cc), -1)

            except Exception as ex:
                self.show_exception('%s error.\n%s' % (__step, ex))
                _clear_console()

        self.boxControls.show_all()

        self.dmxSendEnabled = self.console is not None

        st = os.path.splitext(os.path.split(self.consoleFile)[-1])[0]

        if self.console and self.console.name:
            st = self.console.name
            ret = True
        else:
            ret = False

        self.headerBar.set_subtitle(st)

        print('DMXControls is %sloaded' % ('' if ret else 'not '), file=sys.stderr)
        return ret

    def set_channel_values(self, channel, values):
        """Установка значений в каналах.

        channel - номер первого изменяемого канала;
        values  - список целых значений."""

        for cv in values:
            # вынимание!
            # каналы в контролах нумеруются от 1 (как в протоколе DMX-512)
            # но массив channels имеет индексаци1 от 0!
            self.channels[channel - 1] = cv
            channel += 1

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

    def __send_channels(self):
        if self.console:
            self.wrapper.Client().SendDmx(self.console.universe, self.channels, self.__DMX_sent)

    def timer_func(self, data):
        if self.dmxSendEnabled:
            self.__send_channels()

        return self.dmxTimer

    def main(self):
        try:
            Gtk.main()
        finally:
            print('Black out DMX channels...', file=sys.stderr)

            for ix in range(len(self.channels)):
                self.channels[ix] = 0

            self.__send_channels()


def main():
    cfg = Config()
    print('Loading settings...', file=sys.stderr)
    cfg.load()

    try:
        MainWnd(cfg).main()
    finally:
        print('Saving settings...', file=sys.stderr)
        cfg.save()

    return 0

if __name__ == '__main__':
    print('[debugging %s]' % __file__)

    sys.argv.append('example.dmxctrl')
    sys.exit(main())
