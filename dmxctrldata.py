#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" This file is part of DMXCtrl.

    DMXCtrl is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    DMXCtrl is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with DMXCtrl.  If not, see <http://www.gnu.org/licenses/>."""


import xml.sax

from gi import require_version as gi_require_version
gi_require_version('Gdk', '3.0')
from gi.repository.Gdk import RGBA

import os.path


# значения цветов для встроенной палитры и иконок
HUE_BLACK = -1
HUE_WHITE = -2
__HUE_360 = 1.0 / 360
PALETTE_HUE_NAMES = {
    'black':        HUE_BLACK,
    'red':          0   * __HUE_360,
    'orange':       30  * __HUE_360,
    'yellow':       60  * __HUE_360,
    'yellowgreen':  90  * __HUE_360,
    'green':        120 * __HUE_360,
    'greenblue':    160 * __HUE_360,
    'cyan':         180 * __HUE_360,
    'deepblue':     210 * __HUE_360,
    'blue':         240 * __HUE_360,
    'purple':       260 * __HUE_360,
    'magenta':      300 * __HUE_360,
    'white':        HUE_WHITE,
    }


class Control():
    """Базовый класс "контрола" - управляющего элемента.
    Этот класс напрямую не используется, используются его потомки.

    Атрибуты класса:
        TAG                     - строка, имя тэга в XML-описании;
        PARENTS = set()         - множество строк - имена допустимых
                                  родительских тэгов;
        PARAMETERS = set()      - множество строк - имена обязательных
                                  параметров;
        OPTIONS = {'channel'}   - множество строк - имена необязательных
                                  параметров;
        CHANNELS = 0            - количество каналов, занимаемых контролом;
                                  0 для контейнеров (и прочих, не изменяющих
                                  значения в каналах),
                                  >0 для изменяющих значения.
        Атрибуты, содержащие множества, должны дополняться или
        перекрываться в классе-потомке, прочие - должны перекрываться.

    Атрибуты экземпляра класса:
        console     - внутренний атрибут, ссылка на экземпляр DMXControls,
                      который содержит все Control'ы (и позволяет им
                      дёргать себя за всякие полезные методы);
        comments    - список строк, текстовое описание контрола
                      для отображения в UI (напр. в виде всплывающей
                      подсказки);
        channel     - целое, номер первого используемого канала;
                      для обычного Control и потомков по умолчанию
                      устанавливается в None (которое соответствует
                      значению "auto" в файле);
                      значение может быть:
                      1. явно указано в файле соответствующим атрибутом;
                      2. задано на основе счётчика (в т.ч. инициализированного
                         значением родительского Control'а);
                      окончательное присваивание значений производится
                      в методе DMXControls.endElement() (аналогично атрибутам
                      NamedControl.name), т.е. после завершения загрузки
                      все важные атрибуты будут так или иначе заданы;
        children    - список дочерних контролов (для потомков Container)
                      или список контролов с данными для самого контрола."""

    TAG = None
    PARENTS = set()
    PARAMETERS = set()
    OPTIONS = {'channel'}
    CHANNELS = 0

    def __init__(self):
        # конструкторы задают значения атрибутов по умолчанию,
        # реальные значения устанавливает загрузчик методом Control.setParameter()
        self.console = None
        self.comments = []
        self.channel = None
        self.children = []

    def strAttrToInt(self, ns, vs, strict=True, minv=None, maxv=None):
        """Преобразование строкового значения атрибута в целое.

        Параметры:
            ns      - строка,  имя атрибута (для отображения в сообщениях
                      об ошибках);
            vs      - строка, значение атрибута;
            strict  - булевское значение;
                      если False - s может быть спецзначением
                      "*" или "auto", в этом случае метод возвращает
                      None, иначе int(s) должно быть только
                      положительным целым числом;
            minv    - None или целое число; минимальное значение;
                      если None - значение не проверяется;
            maxv    - None или целое число; максимальное значение;
                      если None - значение не проверяется."""

        if vs.lower() in ('*', 'auto'):
            if not strict:
                return None

            raise ValueError('attribute "%s" must be positive integer' % ns)

        v = int(vs)

        if (minv is not None and v < minv) or (maxv is not None and v > maxv):
            raise ValueError('attribute "%s" is out of range' % ns)

        return v

    def strAttrToBool(self, ns, vs):
        """Преобразование строкового значения атрибута в булевское.

        Параметры:
            ns      - строка,  имя атрибута (для отображения в сообщениях
                      об ошибках);
            vs      - строка, значение атрибута."""

        try:
            return bool(int(vs))
        except ValueError:
            vs = vs.lower()

            if vs in ('true', 'yes'):
                return True
            elif vs in ('false', 'no'):
                return False
            else:
                raise ValueError('attribute "%s" must be boolean or integer' % ns)

    def setParameter(self, ns, vs):
        """Установка значения атрибута экземпляра класса.

        ns  - строка, имя атрибута;
        vs  - строка, значение атрибута.

        В случае неизвестного значения name метод не должен делать ничего -
        проверка имён производится в методе DMXControls.startElement().
        В случае прочих ошибок должны генерироваться исключения.
        Метод может быть перекрыт классом-потомком."""

        if ns == 'channel':
            self.channel = self.strAttrToInt(ns, vs, False, 1, 512)

    def getCommentStr(self):
        return ' '.join(self.comments)

    def checkParameters(self):
        """Проверка наличия и правильности всех параметров.
        Вызывается методом DMXControls.endElement().
        В случае ошибок метод должен вызывать исключения.
        Перекрывается при необходимости классом-потомком."""

        pass


class NamedControl(Control):
    """Контрол с отображаемым именем.

    Необязательные атрибуты экземпляра класса (в дополнение
    к наследственным):
        name        - строка, имя для отображения в UI;
                      если не указано - контрол будет отображаться
                      без текстовой метки;
        icon        - строка, имя графического файла с иконкой или
                      встроенной иконки;
                      если не указано - в UI иконки не будет;
        isInternalIcon - внутренний атрибут, True, если в self.icon
                      имя встроенной иконки."""

    OPTIONS = Control.OPTIONS | {'name', 'icon'}

    def __init__(self):
        super().__init__()

        self.name = ''
        self.icon = None
        self.isInternalIcon = False

    def __setup_icon_path(self, fname):
        """Проверка правильности пути/имени иконки.
        Ругань в случае ошибок, установка атрибутов в случае отсутствия
        ошибок."""

        self.isInternalIcon = False

        if fname.startswith('@'):
            # путь относительно загружаемого файла описания консоли
            self.icon = os.path.join(os.path.split(self.console.filename)[0], fname[1:])
        elif fname.startswith('!'):
            # встроенная иконка
            self.icon = fname[1:]
            if not self.icon in PALETTE_HUE_NAMES:
                raise Exception('invalid internal icon name in "icon" attribute')

            self.isInternalIcon = True
        else:
            # "обычный" полный или относительный путь в файловой системе
            self.icon = os.path.abspath(os.path.expanduser(fname))

        if not self.isInternalIcon and not os.path.exists(self.icon):
            raise Exception('invalid "icon" attribute - file "%s" is missing' % self.icon)

    def setParameter(self, ns, vs):
        super().setParameter(ns, vs)

        if ns == 'name':
            self.name = vs
        elif ns == 'icon':
            # правильность пути проверяется
            # сама иконка загружается при построении UI
            self.__setup_icon_path(vs)


class Container(NamedControl):
    """Контрол-контейнер. Может содержать другие контролы,
    не может менять значение в каналах.
    Атрибут "channel" только хранит значение для инициализации
    соотв. атрибутов во вложенных контролах.

    Атрибут "children" содержит список вложенных экземпляров Control.

    Атрибуты экземпляра класса (в дополнение к унаследованным):
        vertical    - булевское значение; если равно True -
                      вложенные элементы располагаются по вертикали;
                      значение по умолчанию - False (горизонтальное
                      расположение элементов)."""

    OPTIONS = NamedControl.OPTIONS | {'vertical'}

    def __init__(self):
        super().__init__()

        self.vertical = False

    def setParameter(self, ns, vs):
        super().setParameter(ns, vs)

        if ns == 'vertical':
            self.vertical = self.strAttrToBool(ns, vs)


class Panel(Container):
    """Панель, содержащая другие элементы."""

    TAG = 'panel'
    PARENTS = {'dmxcontrols', 'panel'}


class Regulator(NamedControl):
    """Активный контрол - может менять значение в своём канале.
    Этот класс - базовый для прочих активных контролов, напрямую
    не используется."""

    PARENTS = {'dmxcontrols', 'panel'}


class Switch(Regulator):
    """Переключатель готовых значений.

    Атрибуты экземпляра класса (в дополнение к унаследованным):
        vertical    - булевское значение; если равно True -
                      движок вертикальный;
                      значение по умолчанию - True."""

    TAG = 'switch'
    OPTIONS = Regulator.OPTIONS | {'vertical'}

    def __init__(self):
        super().__init__()

        self.options = []
        self.vertical = True

    def setParameter(self, ns, vs):
        super().setParameter(ns, vs)

        if ns == 'vertical':
            self.vertical = self.strAttrToBool(ns, vs)

    def checkParameters(self):
        if len(self.children) < 2:
            raise ValueError('%s must contain at least two options' % self.__class__.__name__)


class SwitchOption(NamedControl):
    TAG = 'option'
    PARENTS = {'switch'}
    PARAMETERS = NamedControl.PARAMETERS | {'value'}

    def __init__(self):
        super().__init__()

        self.value = 0

    def __repr__(self):
        return '%s(name="%s", value=%d, icon="%s")' % (self.__class__.__name__,
                    self.name, self.value, self.icon)

    def setParameter(self, ns, vs):
        super().setParameter(ns, vs)

        if ns == 'value':
            self.value = self.strAttrToInt(ns, vs, minv=0, maxv=255)


class Level(Regulator):
    """Движок-регулятор уровня.

    Атрибуты экземпляра класса (в дополнение к унаследованным):
        value       - целое, начальное положение движка (0..255);
                      по умолчанию - 0;
        steps       - целое, количество шагов движка (0..32);
                      значение 0 указывает плавное изменение положения
                      движка, без шагов;
                      при steps=1 движок фактически работает как переключатель
                      между значениями 0 и 255;
                      по умолчанию - 0;
        vertical    - булевское значение; если равно True -
                      движок вертикальный;
                      значение по умолчанию - True."""

    TAG = 'level'
    OPTIONS = Regulator.OPTIONS | {'value', 'steps', 'vertical'}
    CHANNELS = 1

    def __init__(self):
        super().__init__()

        self.value = 0
        self.steps = 0
        self.vertical = True

    def setParameter(self, ns, vs):
        super().setParameter(ns, vs)

        if ns == 'value':
            self.value = self.strAttrToInt(ns, vs, minv=0, maxv=255)
        elif ns == 'steps':
            self.steps = self.strAttrToInt(ns, vs, minv=0, maxv=32)
        elif ns == 'vertical':
            self.vertical = self.strAttrToBool(ns, vs)


class ColorLevel(Level):
    TAG = 'colorlevel'
    OPTIONS = Level.OPTIONS | {'color'}
    CHANNELS = 3

    def __init__(self):
        super().__init__()

        self.color = '#000000'

    def setParameter(self, ns, vs):
        super().setParameter(ns, vs)

        if ns == 'color':
            #TODO возможно, стоит сделать более строгую проверку значения
            if vs.startswith('#'):
                if len(vs) not in (4, 7):
                    raise ValueError('invalid color RGB value format')

            self.color = vs


class DMXControls(Container, xml.sax.ContentHandler):
    TAG = 'dmxcontrols'
    OPTIONS = Container.OPTIONS | {'universe'}

    class Error(ValueError):
        def __init__(self, loader, msg):
            super().__init__('Error at position %s of file "%s": %s' % (loader.getLocatorStr(), loader.filename, msg))

    class __StkItem():
        __slots__ = 'name', 'obj'

        def __init__(self, n, o):
            super().__init__()

            self.name = n
            self.obj = o

    def __init__(self, filename):
        super().__init__()
        xml.sax.ContentHandler.__init__(self)

        self.filename = filename
        self.universe = 1
        self.channel = 1

        self.locator = None
        self.stack = []
        self.stackTop = None
        self.curChannel = 1

        parser = xml.sax.make_parser()
        parser.setContentHandler(self)
        parser.parse(filename)

    def getParent(self):
        return self.stack[-2] if len(self.stack) >= 2 else None

    def getStackStr(self):
        return '/'.join(map(lambda i: i.name, self.stack))

    def setDocumentLocator(self, locator):
        self.locator = locator

    def getLocatorStr(self):
        ss = self.getStackStr()

        return '?' if not self.locator else '%d:%d%s' % (
            self.locator.getLineNumber(),
            self.locator.getColumnNumber(),
            '' if not ss else ' (%s)' % ss)

    CHILD_CLASSES = (Panel, Level, ColorLevel, Switch, SwitchOption)

    def setParameter(self, ns, vs):
        super().setParameter(ns, vs)

        if ns == 'universe':
            self.universe = self.strAttrToInt(ns, vs)
            if self.universe is None:
                self.universe = 1
            elif self.universe < 1:
                raise self.Error('invalid universe value')

    def startElement(self, name, attributes):
        self.stackTop = self.__StkItem(name, None)
        self.stack.append(self.stackTop)
        stackLen = len(self.stack)
        #

        def checkParent(parents):
            if self.getParent().name not in parents:
                pss = tuple(map(lambda v: '"%s"' % v, parents))

                psa = pss[-1]

                if len(pss) >= 2:
                    psa = '%s or %s' % (', '.join(pss[:-1]), psa)

                raise self.Error(self, '"%s" must be child of %s' % (name, psa))

        def checkSetAttributes():
            try:
                extra = set(attributes.keys()) - set(self.stackTop.obj.PARAMETERS | self.stackTop.obj.OPTIONS)
                if extra:
                    raise Exception('unsupported parameter(s) - %s' % (', '.join(map(lambda v: '"%s"' % v, extra))))

                # обязательные параметры
                for pname in self.stackTop.obj.PARAMETERS:
                    pval = attributes.get(pname, None)
                    if pval is None:
                        raise Exception('required parameter "%s" is missing' % pname)

                    #print('%s parameter: %s=%s' % (name, pname, pval))
                    self.stackTop.obj.setParameter(pname, pval)

                # необязательные параметры
                for pname in self.stackTop.obj.OPTIONS:
                    pval = attributes.get(pname, None)

                    if pval is not None:
                        #print('%s option: %s=%s' % (name, pname, pval))
                        self.stackTop.obj.setParameter(pname, pval)

                # принудительная установка атрибута "channel" при необходимости
                if self.stackTop.obj.channel is not None:
                    # если канал задан явно - меняем значение глобального атрибута
                    self.curChannel = self.stackTop.obj.channel
                else:
                    # иначе - задаём атрибут "channel" текущему объекту на основе глобального
                    self.stackTop.obj.channel = self.curChannel

                if isinstance(self.stackTop.obj, Regulator):
                    # глобальный счётчик изменяют только активные контролы,
                    # т.к. контейнеры сами каналов не занимают, только
                    # хранят начальное значение канала для вложенных контролов
                    self.curChannel += self.stackTop.obj.CHANNELS

            except Exception as ex:
                raise self.Error(self, str(ex)) from ex

        if stackLen == 1:
            # вот таким тупым способом проверяем формат файла
            if name != self.TAG:
                raise self.Error(self, 'invalid root tag - file is not a DMXControls file')

            self.stackTop.obj = self
            checkSetAttributes()
        else:
            # служебные тэги
            if name == 'br':
                self.getParent().obj.comments.append('\n')
            # тэги контролов
            else:
                isValidClass = False

                for cclass in self.CHILD_CLASSES:
                    if name == cclass.TAG:
                        checkParent(cclass.PARENTS)

                        self.stackTop.obj = cclass()
                        self.stackTop.obj.console = self

                        checkSetAttributes()

                        oparent = self.getParent()
                        oparent.obj.children.append(self.stackTop.obj)

                        isValidClass = True
                        break

                if not isValidClass:
                    raise self.Error(self, 'unsupported tag "%s"' % name)

    def endElement(self, name):
        if self.stackTop.obj:
            try:
                self.stackTop.obj.checkParameters()
            except Exception as ex:
                raise self.Error(self, str(ex)) from ex

        #
        self.stackTop = self.stack.pop() if self.stack else None

    def characters(self, s):
        s = s.strip()
        if not s:
            return

        if self.stackTop and self.stackTop.obj:
            self.stackTop.obj.comments.append(s)
        else:
            self.comments.append(s)


if __name__ == '__main__':
    print('[debugging %s]' % __file__)

    dmxc = DMXControls('example.dmxctrl')
    #print(help(dmxc))

    def _dump_dict(d, indent):
        r = []

        for k, v in d.items():
            r.append('%s%s="%s"' % ('%s - ' % indent, k, v))

        return '\n'.join(r)

    def __dump_ctl(ctl, indent):
        print('%s%s %s:"%s"%s %s' % (
                indent,
                '=' if isinstance(ctl, Container) else '>',
                ctl.__class__.__name__,
                ctl.name,
                '' if not ctl.icon else ' (%s)' % ctl.icon,
                _dump_dict(ctl.__dict__, indent)))

        indent += ' '

        if isinstance(ctl, Container):
            for c in ctl.children:
                __dump_ctl(c, indent)

    print('\033[1m%s\033[0m' % _dump_dict(dmxc.__dict__, ' '))
    for un in dmxc.children:
        __dump_ctl(un, '')
