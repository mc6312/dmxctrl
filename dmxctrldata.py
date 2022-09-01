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


class Control():
    # следующие параметры класса ДОЛЖНЫ быть перекрыты классом-потомком
    TAG = None          # строка, имя тэга в XML-описании
    PARENTS = set()     # множество строк - имена допустимых родительских тэгов
    PARAMETERS = set()  # множество строк - имена обязательных параметров
    OPTIONS = {'channel'}  # множество строк - имена необязательных параметров
    CHANNELS = 0        # количество каналов, занимаемых контролом;
                        # 0 для контейнеров (и прочих, не изменяющих
                        # значения в каналах), >0 для изменяющих значения

    def __init__(self):
        # конструкторы задают значения атрибутов по умолчанию,
        # реальные значения устанавливает загрузчик методом Control.setParameter()
        self.parent = None
        self.comments = []
        # channel для обычного Control и потомков устанавливается в None
        # (которое соответствует значению "auto" в файле)
        # значение может быть:
        # 1. явно указано в файле соответствующим атрибутом;
        # 2. задано на основе счётчика (в т.ч. инициализированного
        #    значением родительского Control'а)
        # окончательное присваивание значений производится в методе
        # DMXControlsLoader.endElement() (аналогично атрибутам NamedControl.name)
        # т.е. после завершения загрузки все важные атрибуты будут
        # так или иначе заданы
        self.channel = None # !

    def strArgToInt(self, s, strict=True):
        """Преобразование строкового значения атрибута в целое.

        Параметры:
            s       - строка;
            strict  - булевское значение;
                      если False - s может быть спецзначением
                      "*" или "auto", в этом случае метод возвращает
                      None, иначе int(s) должно быть только
                      положительным целым числом."""

        if s.lower() in ('*', 'auto'):
            if not strict:
                return None

            raise ValueError('attribute value must be positive integer')

        return int(s)

    def setParameter(self, ns, vs):
        """Установка значения атрибута экземпляра класса.

        ns  - строка, имя атрибута;
        vs  - строка, значение атрибута.

        В случае неизвестного значения name метод не должен делать ничего -
        проверка имён производится в методе DMXControlsLoader.startElement().
        В случае прочих ошибок должны генерироваться исключения.
        Метод может быть перекрыт классом-потомком."""

        if ns == 'channel':
            self.channel = self.strArgToInt(vs, False)
            if self.channel is not None and (self.channel < 1 or self.channel > 512):
                raise ValueError('channel number out of range')

    def getCommentStr(self):
        return ' '.join(self.comments)

    def checkParameters(self):
        """Проверка наличия и правильности всех параметров.
        Вызывается методом DMXControlsLoader.endElement().
        В случае ошибок метод должен вызывать исключения.
        Перекрывается при необходимости классом-потомком."""

        pass


class NamedControl(Control):
    OPTIONS = Control.OPTIONS | {'name'}

    def __init__(self):
        super().__init__()

        self.name = ''

    def setParameter(self, ns, vs):
        super().setParameter(ns, vs)

        if ns == 'name':
            self.name = vs


class Container(NamedControl):
    """Контрол-контейнер. Может содержать другие контролы,
    не может менять значение в каналах.
    Атрибут "channel" только хранит значение для инициализации
    соотв. атрибутов во вложенных контролах."""

    OPTIONS = NamedControl.OPTIONS

    def __init__(self):
        super().__init__()

        self.children = []


class Panel(Container):
    TAG = 'panel'
    PARENTS = {'dmxcontrols', 'panel'}

    pass


class Regulator(NamedControl):
    """Активный контрол - может менять значение в своём канале.
    Этот класс - базовый для прочих активных контролов, напрямую
    не используется."""

    pass


class Level(Regulator):
    TAG = 'level'
    PARENTS = {'dmxcontrols', 'panel'}
    OPTIONS = Regulator.OPTIONS | {'value'}
    CHANNELS = 1

    def __init__(self):
        super().__init__()

        self.value = 0

    def setParameter(self, ns, vs):
        super().setParameter(ns, vs)

        if ns == 'value':
            self.value = self.strArgToInt(vs)
            if self.value < 0 or self.value > 255:
                raise ValueError('value out of range')


class DMXControlsLoader(Container, xml.sax.ContentHandler):
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

        self.namedCounts = {DMXControlsLoader:0, Panel:0, Level:0}

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

    CHILD_CLASSES = (Panel, Level)

    def setParameter(self, ns, vs):
        super().setParameter(ns, vs)

        if ns == 'universe':
            self.universe = self.strArgToInt(vs)
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

        def checkSetParameters():
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
                raise self.Error(self, str(ex))

        if stackLen == 1:
            # вот таким тупым способом проверяем формат файла
            if name != self.TAG:
                raise self.Error(self, 'invalid root tag - file is not a DMXControls file')

            self.stackTop.obj = self
            checkSetParameters()
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
                        checkSetParameters()

                        oparent = self.getParent()
                        oparent.obj.children.append(self.stackTop.obj)
                        self.stackTop.obj.parent = oparent.obj

                        isValidClass = True
                        break

                if not isValidClass:
                    raise self.Error(self, 'unsupported tag "%s"' % name)

    def endElement(self, name):
        if self.stackTop.obj:
            self.stackTop.obj.checkParameters()

            # принудительно создаём имена объектам, если имён не было в файле
            otype = type(self.stackTop.obj)
            if otype in self.namedCounts and not self.stackTop.obj.name:
                cnt = self.namedCounts[otype] + 1
                self.namedCounts[otype] = cnt
                self.stackTop.obj.name = '%s #%d' % (otype.__name__, cnt)

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

    dmxc = DMXControlsLoader('example.dmxctrl')
    #print(help(dmxc))

    def __dump_ctl(ctl, indent):
        print('%s%s %s channel=%s' % (indent, '=' if isinstance(ctl, Container) else '>', ctl.name, ctl.channel))

        indent += ' '

        if isinstance(ctl, Container):
            for c in ctl.children:
                __dump_ctl(c, indent)

    print('%s universe=%s channel=%s' % (dmxc.name, dmxc.universe, dmxc.channel))
    for un in dmxc.children:
        __dump_ctl(un, '')
