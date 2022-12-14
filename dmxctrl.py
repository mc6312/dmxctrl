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
VERSION = '0.12%s' % (' [DEBUG]' if DEBUG else '')
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

from dmxctrldata import *
from dmxctrlcfg import *

from colorsys import hls_to_rgb


COLORS_PALETTE_COLS = len(PALETTE_HUE_NAMES) - len(PALETTE_SPECIAL_COLORS)


def hue_to_rgba(hue, saturation=1.0):
    r, g, b = hue_to_rgb1(hue, saturation)

    return Gdk.RGBA(r, g, b, 1.0)


def __init_palette():
    pal = []

    __PALETTE_SATURATIONS = 9

    for sat in range(__PALETTE_SATURATIONS):
        for hue in PALETTE_HUE_NAMES.values():
            if hue not in PALETTE_SPECIAL_COLORS:
                pal.append(hue_to_rgba(hue, 1.0 / (1 + sat)))

    for l in range(COLORS_PALETTE_COLS):
        v = 1.0 - l / COLORS_PALETTE_COLS
        pal.append(Gdk.RGBA(v, v, v, 1.0))

    return pal


COLORS_PALETTE = __init_palette()


def bool_gtk_orientation(v):
    return Gtk.Orientation.VERTICAL if v else Gtk.Orientation.HORIZONTAL


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

    def format_tooltip_text(self, control):
        cstr = control.getCommentStr()
        if cstr:
            cstr = '%s\n\n' % cstr

        if DEBUG:
            cstr = '%s\n\n%s' % (cstr, control)

        return '%sChannel: %d' % (cstr, control.channel)

    def set_tooltip_text(self, widget, control):
        widget.set_tooltip_text(self.format_tooltip_text(control))

    def value_changed(self, widget):
        """Метод должен вызываться при изменении значения (положения
        движка и т.п.), т.е. это обработчик соответствующего сигнала виджета.
        Также он вызывается из конструктора после создания всех виджетов
        и установки значений атрибутов.

        Параметры:
            param   - экземпляр Gtk.Widget в случае вызова в качестве
                      обработчика сигнала виджета;
                      None при вызове из конструктора ControlWidget.

        Конкретные реализации метода могут иметь больше параметров,
        т.к. некоторые виджеты Gtk передают более одного параметра
        обработчику сигнала. Первым параметром передаётся экземпляр Gtk.Widget.

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
        self.value_changed(None)

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

        if self.control.name or self.control.icon:
            lbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, WIDGET_SPACING)
            lbox.set_border_width(WIDGET_SPACING)

            if self.control.icon:
                lbox.pack_start(self.owner.load_icon_image(self.control), False, False, 0)

            if self.control.name:
                lbox.pack_start(Gtk.Label.new(self.control.name), False, False, 0)

            self.widget.set_label_widget(lbox)

        self.widget.set_label_align(0.5, 0.5)
        self.set_tooltip_text(self.widget, self.control)

        self.box = Gtk.Box.new(bool_gtk_orientation(self.control.vertical),
                           WIDGET_SPACING)
        self.box.set_border_width(WIDGET_SPACING)
        self.widget.add(self.box)

    def add_child(self, cwgt, cctrl):
        self.box.pack_start(cwgt, cctrl.expand, cctrl.expand, 0)


class SwitchWidget(ControlWidget):
    def setup(self):
        _ornt = bool_gtk_orientation(self.control.vertical)

        swbox = Gtk.Grid.new()
        swbox.set_column_homogeneous(True)
        swbox.set_row_homogeneous(True)
        swbox.set_hexpand(self.control.expand)
        swbox.set_vexpand(self.control.expand)
        # на случай особо извращённых тем GTK
        swbox.set_column_spacing(0)
        swbox.set_row_spacing(0)

        nbuttons = len(self.control.children)

        if self.control.buttonsPerLine <= 0:
            ncols = nbuttons
            nrows = 1
        else:
            ncols = self.control.buttonsPerLine
            nrows = nbuttons // ncols
            if nbuttons % ncols:
                nrows += 1

        if self.control.vertical:
            nrows, ncols = ncols, nrows

        if self.control.name or self.control.icon:
            self.widget = Gtk.Box.new(_ornt, WIDGET_SPACING)
            self.set_tooltip_text(self.widget, self.control)

            if self.control.icon:
                self.widget.pack_start(self.owner.load_icon_image(self.control), False, False, 0)

            if self.control.name:
                lab = Gtk.Label.new(self.control.name)
                lab.set_line_wrap(True)
                self.widget.pack_start(lab, False, False, 0)

            self.widget.pack_start(swbox, self.control.expand, self.control.expand, 0)
        else:
            self.widget = swbox

        # словарь, где ключи - ссылки на экземпляры Gtk.RadioButton,
        # а значения - соответствующие им значения для каналов
        # т.к. предполагается, что будет использован Python 3.6 или новее,
        # будем надеяться, что словарь сохранит элементы
        # в той же очерёдности, что и при добавлении
        self.radioButtons = dict()
        self.activeButton = None

        rgrp = None

        #
        #
        #
        ixo = 0
        rowsbl = None
        for row in range(nrows):
            sblwgt = rowsbl
            gpos = Gtk.PositionType.BOTTOM

            for col in range(ncols):
                if ixo < nbuttons:
                    opt = self.control.children[ixo]
                    ixo += 1

                    rbtn = Gtk.RadioButton.new_with_label_from_widget(rgrp, opt.name)
                    # для борьбы с авторами тем, которые шибко любят
                    # закруглять углы у всего подряд надругаемся над css;
                    # слитно расположенные кнопки со скруглёнными углами
                    # выглядят отвратно, потому кнопки будут квадратные
                    set_widget_style(b'* { border-radius:0 }', rbtn)

                    if ixo == self.control.active:
                        self.activeButton = rbtn

                    rbtn.set_mode(False)
                    if opt.icon:
                        rbtn.set_image(self.owner.load_icon_image(opt))

                    if opt.comments:
                        self.set_tooltip_text(rbtn, opt)

                    if not rgrp:
                        rgrp = rbtn

                    self.radioButtons[rbtn] = opt.value

                    rbtn.connect('toggled', self.value_changed)

                    swbox.attach_next_to(rbtn, sblwgt, gpos, 1, 1)
                    sblwgt = rbtn
                    if col == 0:
                        rowsbl = sblwgt
                        gpos = Gtk.PositionType.RIGHT

        _rbtns = list(self.radioButtons.keys())
        self.minButton = _rbtns[0]
        self.maxButton = _rbtns[-1]

        self.activeButton.set_active(True)

    def value_changed(self, rbtn):
        if rbtn is None:
            rbtn = self.activeButton
        elif not rbtn.get_active():
            return

        self.owner.set_channel_values(self.control.channel,
                                      self.radioButtons[rbtn])
        self.activeButton = rbtn

    def setMinLevel(self):
        """Установка максимального значения"""

        self.minButton.set_active(True)

    def setMaxLevel(self):
        """Установка минимального значения"""

        self.maxButton.set_active(True)


class LevelWidget(ControlWidget):
    def setup(self):
        if self.control.vertical:
            scmincx = -1
            scmincy = WIDGET_BASE_HEIGHT * 3
            _ornt = Gtk.Orientation.VERTICAL
        else:
            scmincx = WIDGET_BASE_WIDTH * 6
            scmincy = -1
            _ornt = Gtk.Orientation.HORIZONTAL

        self.widget = Gtk.Box.new(_ornt, WIDGET_SPACING)

        self.set_tooltip_text(self.widget, self.control)

        if self.control.icon:
            self.widget.pack_start(self.owner.load_icon_image(self.control), False, False, 0)

        if self.control.name:
            slab = Gtk.Label.new(self.control.name)
            if self.control.vertical and (len(self.control.name) > 2):
                slab.set_angle(270)

            self.widget.pack_start(slab, False, False, 0)

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

        self.scale = Gtk.Scale.new(_ornt, None)
        self.scale.set_size_request(scmincx, scmincy)
        self.scale.set_draw_value(False)
        self.scale.set_inverted(self.control.vertical)

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

        rgba = Gdk.RGBA(self.control.color[0] / 255,
                        self.control.color[1] / 255,
                        self.control.color[2] / 255,
                        1.0)

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
    ColorLevel: ColorLevelWidget,
    Switch: SwitchWidget}


class MainWnd():
    def wnd_destroy(self, widget, data=None):
        self.dmxSendEnabled = False
        self.dmxTimer = False
        Gtk.main_quit()

    def __init__(self, cfg):
        self.cfg = cfg
        self.errorTitle = '%s error' % TITLE_VERSION
        # детальный заголовок сообщения об ошибке - только при инициализации
        # позже она не будет нужна

        resldr = get_resource_loader()
        uibldr = resldr.load_gtk_builder('dmxctrl.ui')

        iconSize = Gtk.IconSize.MENU

        self.window, self.headerBar, imgTbtnConsoleScrollable,\
        self.tbtnConsoleScrollable, self.labConsoleName,\
        self.stackPages, self.boxConsole, self.boxRecents,\
        self.swndControls, self.vpControls = get_ui_widgets(uibldr,
            'wndConsole', 'headerBar', 'imgTbtnConsoleScrollable',
            'tbtnConsoleScrollable', 'labConsoleName',
            'stackPages', 'boxConsole', 'boxRecents',
            'swndControls', 'vpControls')

        #
        print('Connecting to OLA daemon...', file=sys.stderr)
        try:
            from ola.ClientWrapper import ClientWrapper
            self.wrapper = ClientWrapper()
        except Exception as ex:
            self.show_exception(ex)
            sys.exit(-1)
        #

        self.boxControls = None

        imgTbtnConsoleScrollable.set_from_pixbuf(resldr.load_pixbuf_icon_size('images/consolescrollable.svg', iconSize))
        #
        self.swndControls.set_border_width(WIDGET_SPACING)

        self.setup_console_scrollability(self.cfg.consoleScrollability)

        #self.swnd.set_overlay_scrolling(False)
        #self.swnd.set_propagate_natural_width(True)

        self.window.set_size_request(-1, WIDGET_BASE_HEIGHT * 20)

        if DEBUG:
            imgDebug = Gtk.Image.new_from_icon_name('dialog-warning', iconSize)
            imgDebug.set_tooltip_text('Warning!\nDebug version!')
            self.headerBar.pack_end(imgDebug)

        self.smallIconSizePx = Gtk.IconSize.lookup(iconSize)[-1]

        winIconSizePx = Gtk.IconSize.lookup(Gtk.IconSize.DIALOG)[1] * 2
        icon = resldr.load_pixbuf('images/dmxctrl.png', winIconSizePx, winIconSizePx)
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
        # список ранее использованных файлов
        #
        self.tvRecentFiles = TreeViewShell.new_from_uibuilder(uibldr, 'tvRecentFiles')
        self.update_recent_files_lv()

        #
        #
        #
        self.dlgAbout = uibldr.get_object('dlgAbout')
        logoSizePx = Gtk.IconSize.lookup(Gtk.IconSize.DIALOG)[1] * 4
        logo = resldr.load_pixbuf('images/dmxctrl.png', logoSizePx, logoSizePx)
        self.dlgAbout.set_logo(logo)
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

        self.errorTitle = 'Error'

        self.window.show_all()
        uibldr.connect_signals(self)

        GLib.timeout_add(1000 / 30, self.timer_func, None)

    def setup_console_scrollability(self, s):
        self.cfg.consoleScrollability = s

        self.swndControls.set_policy(Gtk.PolicyType.AUTOMATIC if s else Gtk.PolicyType.NEVER,
            Gtk.PolicyType.NEVER)

        self.tbtnConsoleScrollable.set_active(s)

    def tbtnConsoleScrollable_toggled(self, btn):
        self.setup_console_scrollability(btn.get_active())

    def update_recent_files_lv(self):
        self.tvRecentFiles.refresh_begin()

        for rfn in self.cfg.recentFiles:
            self.tvRecentFiles.store.append((rfn,))

        self.tvRecentFiles.refresh_end()

    def recent_file_open(self, path):
        fname = self.cfg.recentFiles[path.get_indices()[0]]

        # проверяем наличие файла обязательно, т.к. в списке недавних
        # могут быть уже удалённые файлы или лежащие на внешних
        # неподключённых носителях

        if not os.path.exists(fname):
            msg_dialog(self.window, TITLE,
                'File "%s" is missing' % fname)
        else:
            self.consoleFile = fname
            self.load_console()

    def btnOpenRecentFile_clicked(self, btn):
        _, r = self.tvRecentFiles.selection.get_selected_rows()
        if r:
            self.recent_file_open(r[0])

    def tvRecentFiles_row_activated(self, tv, path, col):
        self.recent_file_open(path)

    def btnRemoveRecentFile_clicked(self, btn):
        print('btnRemoveRecentFile_clicked() not implemented', file=sys.stderr)

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

            cc.set_source(cairo.SolidPattern(*hue_to_rgba(ihue)))
            cc.arc(center, center, radius1, 0.0, circle)
            cc.fill()

            self.icons[iname.lower()] = Gdk.pixbuf_get_from_surface(csurf, 0, 0, self.smallIconSizePx, self.smallIconSizePx)

    def mnuMainSwitchToConsole_activate(self, mnu):
        self.stackPages.set_visible_child(self.boxConsole)

    def mnuMainSwitchToRecents_activate(self, mnu):
        self.stackPages.set_visible_child(self.boxRecents)

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
                    self.update_recent_files_lv()

    def show_exception(self, ex):
        etrace = '\n'.join(format_exception(*sys.exc_info()))
        ex = str(ex)

        print('%s\n%s' % (ex, etrace), file=sys.stderr)

        msg_dialog(self.window, self.errorTitle, ex)

    def __process_cmdline(self):
        #TODO сделать человеческую обработку командной строки
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

            if self.boxControls:
                self.boxControls.destroy()
                self.boxControls = None

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
            if isinstance(ctrl, Regulator):
                self.consoleWidgets.append(cwgt)

            if isinstance(ctrl, Container):
                for child in ctrl.children:
                    subwgt = _build_console_widgets(child)
                    cwgt.add_child(subwgt, child)

            return cwgt.widget

        self.dmxSendEnabled = False

        __step = ''

        def __show_step():
            print('* %s...' % __step, file=sys.stderr)

        if self.consoleFile:
            try:
                __step = 'loading console from "%s"' % self.consoleFile
                __show_step()

                if not os.path.exists(self.consoleFile):
                    raise Exception('File "%s" is not found' % self.consoleFile)

                self.console = DMXControls(self.consoleFile)
                if not self.console.children:
                    raise Exception('No controls defined in file "%s"' % self.consoleFile)

                self.headerBar.set_tooltip_text(self.console.getCommentStr())

                __step = 'building console UI'
                __show_step()
                self.boxControls = Gtk.Box.new(bool_gtk_orientation(self.console.vertical),
                                               WIDGET_SPACING)
                self.vpControls.add(self.boxControls)

                for cc in self.console.children:
                    self.boxControls.pack_start(_build_console_widgets(cc), False, False, 0)

            except Exception as ex:
                self.show_exception('Error %s.\n%s' % (__step, ex))
                _clear_console()

        if self.boxControls:
            self.boxControls.show_all()

        self.dmxSendEnabled = self.console is not None

        if self.console and self.console.name:
            scname = self.console.name
            stitle = os.path.splitext(os.path.split(self.consoleFile)[-1])[0]
            stip = ''.join(self.console.comments)
            self.stackPages.set_visible_child(self.boxConsole)
            ret = True
        else:
            scname = ''
            stitle = ''
            stip = None
            ret = False

        self.headerBar.set_subtitle(stitle)
        self.labConsoleName.set_text(scname)
        self.labConsoleName.set_tooltip_text(stip)

        print('Console is %sloaded' % ('' if ret else 'not '), file=sys.stderr)
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
