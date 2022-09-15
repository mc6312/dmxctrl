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
from colorsys import hls_to_rgb
import os.path


# значения цветов для встроенной палитры и иконок
HUE_BLACK = -1
HUE_GRAY = -2
HUE_WHITE = -3
PALETTE_SPECIAL_COLORS = (HUE_BLACK, HUE_GRAY, HUE_WHITE)

grad_to_hue = lambda g: g / 360.0

PALETTE_HUE_NAMES = {
    'black':        HUE_BLACK,
    'gray':         HUE_GRAY,
    'white':        HUE_WHITE,
    'red':          grad_to_hue(0),
    'orange':       grad_to_hue(30),
    'yellow':       grad_to_hue(60),
    'yellowgreen':  grad_to_hue(90),
    'green':        grad_to_hue(120),
    'greenblue':    grad_to_hue(160),
    'cyan':         grad_to_hue(180),
    'deepblue':     grad_to_hue(210),
    'blue':         grad_to_hue(240),
    'purple':       grad_to_hue(260),
    'magenta':      grad_to_hue(300),
    }


def hue_to_rgb1(hue, saturation=1.0):
    """Преобразование значения оттенка с указанной насыщенностью
    в значения R, G, B в диапазоне 0.0-1.0.

    hue         - float, оттенок в диапазоне 0.0-1.0
                  или код цвета HUE_*;
    saturation  - float, насыщенность в диапазоне 0.0-1.0;
                  если hue=HUE_*, параметр saturation не используется.

    Возвращает список из трёх float."""

    if hue == HUE_BLACK:
        return 0, 0, 0
    elif hue == HUE_WHITE:
        return 1.0, 1.0, 1.0
    elif hue == HUE_GRAY:
        return 0.5, 0.5, 0.5

    return hls_to_rgb(hue, 0.5, saturation)


def repr_to_str(obj):
    """Форматирование строки с именем класса и значениями полей экземпляра
    класса для использования в методах obj.__repr__().

    Параметры:
        obj - экземпляр произвольного класса.

    Функция возвращает строку."""

    r = []

    def __repr_item(ni, vi):
        if isinstance(vi, str):
            rv = '"%s"' % vi
        elif isinstance(vi, (int, float, bool)):
            rv = str(vi)
        else:
            try:
                # если это что-то спискообразное - показываем
                # только имя типа и количество элементов
                lvi = len(vi)
                rv = '%s(%s)' % (type(vi).__name__,
                                 '' if not lvi else '%d item(s)' % lvi)
            except TypeError:
                # т.к. объекты могут содержать поля, ссылающиеся
                # на другие объекты, можно получить бесконечную рекурсию
                # а потому для вс
                rv = '<%s>' % type(vi).__name__

        return '%s=%s' % (ni, rv)

    d = getattr(obj, '__dict__', None)
    if d:
        for k, v in d.items():
            r.append(__repr_item(k, v))

    d = getattr(obj, '__slots__', None)
    if d:
        for k in d:
            r.append(__repr_item(k, getattr(obj, k)))

    return '%s(%s)' % (obj.__class__.__name__, ', '.join(r))


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
        USE_PARENT_CHANNEL      - булевское значение;
                                  управляет присвоением значения атрибуту
                                  channel при загрузке файла описания
                                  консоли, если он не указан явно
                                  (см. описание атрибута channel).
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
                      3. используется значение "родительского" Control'а,
                         если атрибут класса USE_PARENT_CHANNEL равен True.
                      Окончательное присваивание значений производится
                      в методе DMXControls.endElement() (аналогично атрибутам
                      NamedControl.name), т.е. после завершения загрузки
                      все важные атрибуты будут так или иначе заданы;
        expand      - булевское значение; если равен True - контрол
                      занимает всё свободное место на консоли;
                      по умолчанию - False;
        children    - список дочерних контролов (для потомков Container)
                      или список контролов с данными для самого контрола."""

    TAG = None
    PARENTS = set()
    PARAMETERS = set()
    OPTIONS = {'channel', 'expand'}
    USE_PARENT_CHANNEL = False

    def __init__(self):
        # конструкторы задают значения атрибутов по умолчанию,
        # реальные значения устанавливает загрузчик методом Control.setParameter()
        self.console = None
        self.comments = []
        self.channel = None
        self.children = []
        self.expand = False

    def getNChannels(self):
        """Возвращает количество каналов, занимаемых контролом.

        Потомки Container (и прочих, не изменяющих значения в каналах)
        должны возвращать 0.

        Потомки Regulator и подобные должны возвращать ненулевые значения.

        Метод может быть перекрыт классом-потомком."""

        return 0

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

    def strAttrToIntList(self, ns, vs, strict=True, minv=None, maxv=None):
        """Преобразование строкового значения атрибута в список целых.

        Параметры:
            vs      - список целых, разделенных пробелами;
            прочие параметры такие же, как у метода strAttrToInt.

        Метод возвращает список целых."""

        r = []

        for vix, vss in enumerate(vs.split(None), 1):
            r.append(self.strAttrToInt('%s:%d' % (ns, vix), vss, strict, minv, maxv))

        return r

    def strAttrToRGB(self, ns, vs):
        """Преобразование строкового значения атрибута, задающего цвет,
        в список целых.

        Параметры:
            ns      - строка,  имя атрибута (для отображения в сообщениях
                      об ошибках);
            vs      - строка, значение атрибута, в формате:
                      1. список из трех целых в диапазоне 0..255,
                         разделённых пробелами;
                      2. цвет в web-формате - "#RRGGBB", "#RGB";
                      3. название цвета из внутренней палитры -
                         PALETTE_HUE_NAMES;
                      4. цвет в формате hls(hue, lightness, saturation)",
                         где hue        - значение оттенка, 0..360;
                             lightness  - значение светлоты, 0..100;
                             saturation - значение насыщенности, 0..100).

        Метод возвращает список из трёх целых."""

        vs = vs.lower()

        _error = 'invalid value of attribute "%s" - %%s' % ns

        def __hex_to_rgb(s, mulv):
            r = []
            step = len(s) // 3
            ix = 1 # пропускаем "#"!
            for pn in 'RGB':
                try:
                    r.append(int(s[ix:ix + step], 16) * mulv)
                except ValueError as ex:
                    raise ValueError(_error % ('invalid %s:%s value' % (ns, pn))) from ex

                ix += step

            return r

        if vs in PALETTE_HUE_NAMES:
            # имя цвета
            return list(map(lambda c: int(c * 255),
                            hue_to_rgb1(PALETTE_HUE_NAMES[vs], 1.0)))
        elif vs.startswith('#'):
            # веб-формат "#RRGGBB"
            lvs = len(vs)
            if lvs == 4:
                #RGB
                return __hex_to_rgb(vs, 16)
            elif lvs == 7:
                #RRGGBB
                return __hex_to_rgb(vs, 1)
            else:
                raise ValueError(_error % 'bad RGB value format')
        elif vs.startswith('hls('):
            # hls(h, l, s)
            if not vs.endswith(')'):
                raise ValueError(_error % 'brackets are not closed')

            vs = list(map(lambda s: s.strip(), vs[4:-1].split(',')))
            if len(vs) != 3:
                raise ValueError(_error % 'invalid hls() parameters')

            r, g, b = hls_to_rgb(self.strAttrToInt('%s:hue' % ns, vs[0], True, 0, 360) / 360.0,
                                 self.strAttrToInt('%s:lightness' % ns, vs[1], True, 0, 100) / 100.0,
                                 self.strAttrToInt('%s:saturation' % ns, vs[2], True, 0, 100) / 100.0)
            return [int(r * 255), int(g * 255), int(b * 255)]
        else:
            # список целых?
            return self.strAttrToIntList(ns, vs, True, 0, 255)

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
        elif ns == 'expand':
            self.expand = self.strAttrToBool(ns, vs)

    def getCommentStr(self):
        return ' '.join(self.comments)

    def checkParameters(self):
        """Проверка наличия и правильности всех параметров.
        Вызывается методом DMXControls.endElement().
        В случае ошибок метод должен вызывать исключения.
        Перекрывается при необходимости классом-потомком."""

        pass

    def __repr__(self):
        # для отладки
        return repr_to_str(self)


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
                      значение по умолчанию - True;
        active      - целое, номер активной "кнопки" (элемента
                      из списка children);
                      по умолчанию - 1;
        nchannels   - количество каналов DMX512, значения которых
                      изменяет Switch;
                      по умолчанию - 1;
        bpl         - целое; количество "кнопок" в строке (или столбце,
                      если vertical=True);
                      значения <=0, "*" или "auto" означают, что
                      кнопки будут расположены в одну строку или столбец
                      без ограничения количества.
        Список значений для выбора (экземпляров SwitchOption) хранится
        в атрибуте children."""

    TAG = 'switch'
    OPTIONS = Regulator.OPTIONS | {'vertical', 'active', 'nchannels', 'bpl'}

    def __init__(self):
        super().__init__()

        self.vertical = True
        self.active = 1
        self.nchannels = 1
        self.buttonsPerLine = 0

    def getNChannels(self):
        return self.nchannels

    def setParameter(self, ns, vs):
        super().setParameter(ns, vs)

        if ns == 'vertical':
            self.vertical = self.strAttrToBool(ns, vs)
        elif ns == 'active':
            # проверка максимального значения будет в методе checkParameters(),
            # т.к. количество option будет известно только тогда
            self.active = self.strAttrToInt(ns, vs, minv=1)
        elif ns == 'nchannels':
            self.nchannels = self.strAttrToInt(ns, vs, minv=1, maxv=512)
        elif ns == 'bpl':
            self.buttonsPerLine = self.strAttrToInt(ns, vs, strict=False)

    def checkParameters(self):
        lc = len(self.children)
        if lc < 2:
            raise ValueError('%s must contain at least two options' % self.__class__.__name__)

        for ixo, opt in enumerate(self.children, 1):
            if len(opt.value) != self.nchannels:
                raise ValueError('option #%d has the wrong number of channel values in attribute "value"' % ixo)

        if self.active > lc:
            raise ValueError('"active" value out of range')


class SwitchOption(NamedControl):
    """Значение для выбора переключателем готовых значений (Switch).

    Атрибуты экземпляра класса (в дополнение к унаследованным):
        value   - список из одного и более целых - значения для каналов
                  DMX512, изменяемых Switch;
                  методу setParameter может передаваться в нескольких
                  форматах:
                    1. список из одного и более целых, разделённых
                       пробелами;
                    2. цвет (сохраняются значения для трёх каналов);
                       формат значения такой же, как у метода
                       strArgToRGB.
                  значение по умолчанию - [0]."""

    TAG = 'option'
    PARENTS = {'switch'}
    PARAMETERS = NamedControl.PARAMETERS | {'value'}
    USE_PARENT_CHANNEL = True

    def __init__(self):
        super().__init__()

        self.value = [0]

    def setParameter(self, ns, vs):
        super().setParameter(ns, vs)

        if ns == 'value':
            self.value = self.strAttrToRGB(ns, vs)


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

    def __init__(self):
        super().__init__()

        self.value = 0
        self.steps = 0
        self.vertical = True

    def getNChannels(self):
        return 1

    def setParameter(self, ns, vs):
        super().setParameter(ns, vs)

        if ns == 'value':
            self.value = self.strAttrToInt(ns, vs, minv=0, maxv=255)
        elif ns == 'steps':
            self.steps = self.strAttrToInt(ns, vs, minv=0, maxv=32)
        elif ns == 'vertical':
            self.vertical = self.strAttrToBool(ns, vs)


class ColorLevel(Level):
    """Движок-регулятор уровня с кнопкой выбора цвета.
    Движок при этом регулирует яркость.

    Атрибуты экземпляра класса (в дополнение к унаследованным):
        color   - значение цвета в виде списка из трёх целых
                  в диапазоне 0..255."""

    TAG = 'colorlevel'
    OPTIONS = Level.OPTIONS | {'color'}

    def __init__(self):
        super().__init__()

        self.color = [0, 0, 0]

    def getNChannels(self):
        return 3

    def setParameter(self, ns, vs):
        super().setParameter(ns, vs)

        if ns == 'color':
            self.color = self.strAttrToRGB(ns, vs)


class DMXControls(Container, xml.sax.ContentHandler):
    TAG = 'dmxcontrols'
    OPTIONS = Container.OPTIONS | {'universe'}

    class Error(ValueError):
        def __init__(self, loader, msg):
            super().__init__('Error at position %s of file "%s": %s' % (loader.getLocatorStr(), loader.filename, msg))

    class __StkItem():
        def __init__(self, n, o):
            super().__init__()

            self.name = n
            self.obj = o

        def __repr__(self):
            return repr_to_str(self)

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
        #print(f'\033[32m%sstartElement({name})\033[0m' % (' ' * stackLen))

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
                    # иначе - задаём атрибут "channel" текущему объекту
                    # принудительно
                    if self.stackTop.obj.USE_PARENT_CHANNEL:
                        prnt = self.getParent()

                        self.stackTop.obj.channel = prnt.obj.channel if prnt else self.curChannel
                    else:
                        self.stackTop.obj.channel = self.curChannel

                if isinstance(self.stackTop.obj, Regulator):
                    # глобальный счётчик изменяют только активные контролы,
                    # т.к. контейнеры сами каналов не занимают, только
                    # хранят начальное значение канала для вложенных контролов
                    self.curChannel += self.stackTop.obj.getNChannels()

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
        #
        self.stackTop = self.stack.pop() if self.stack else None

        #indent = '  ' * len(self.stack)
        #print(f'\033[32m%sendElement({name}): %s\033[0m' % (
        #      indent,
        #      self.stackTop))
        if self.stackTop.obj:
            try:
                self.stackTop.obj.checkParameters()
            except Exception as ex:
                raise self.Error(self, str(ex)) from ex


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

    def __dump_ctl(ctl, indent):
        print('%s%s' % (indent, repr(ctl)))

        indent += ' '

        if isinstance(ctl, Container):
            for c in ctl.children:
                __dump_ctl(c, indent)

    print('\033[1m%s\033[0m' % repr(dmxc))
    for un in dmxc.children:
        __dump_ctl(un, '')
