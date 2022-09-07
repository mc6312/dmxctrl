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


import json
import os, os.path


JSON_ENCODING = 'utf-8'


class Config():
    CFGFN = 'settings.json'
    CFGAPP = 'dmxctrl'

    CONSOLE_SCROLLABILITY = 'console_scrollability'

    RECENTFILES = 'recentfiles'
    MAX_RECENT_FILES = 24

    def __init__(self):
        self.consoleScrollability = False

        # ранее открывавшиеся файлы (список строк)
        self.recentFiles = []

        # определяем каталог для настроек
        # или принудительно создаём, если его ещё нет

        # некоторый костылинг вместо xdg.BaseDirectory, которого есть не для всех ОС
        self.configDir = os.path.join(os.path.expanduser('~'), '.config', self.CFGAPP)
        if not os.path.exists(self.configDir):
            os.makedirs(self.configDir)

        self.configPath = os.path.join(self.configDir, self.CFGFN)
        # вот сейчас самого файла может ещё не быть!

    def load(self):
        E_SETTINGS = 'Ошибка в файле настроек "%s": %%s' % self.configPath

        if os.path.exists(self.configPath):
            with open(self.configPath, 'r', encoding=JSON_ENCODING) as f:
                d = json.load(f)
                #
                # общие настройки
                #
                self.consoleScrollability = d.get(self.CONSOLE_SCROLLABILITY, self.consoleScrollability)

                #
                # список открывавшихся файлов
                #
                rfl = d.get(self.RECENTFILES, [])
                if not isinstance(rfl, list):
                    raise ValueError(E_SETTINGS % ('недопустимый тип элемента "%s"' % self.RECENTFILES))

                self.recentFiles.clear()

                for ix, rfn in enumerate(rfl, 1):
                    if not isinstance(rfn, str):
                        raise TypeError(E_SETTINGS % ('недопустимый тип элемента #%d списка "%s"' % (ix, self.RECENTFILES)))

                    rfn = rfn.strip()
                    if not rfn:
                        continue

                    # проверку на наличие файлов - пока нафиг: а вдруг оне на флэшке невоткнутой?
                    #if not os.path.exists(rfn):
                    #    continue

                    self.add_recent_file(rfn)

    def add_recent_file(self, fname):
        if fname in self.recentFiles:
            return

        self.recentFiles.append(fname)

        if len(self.recentFiles) > self.MAX_RECENT_FILES:
            del self.recentFiles[0]

    def save(self):
        tmpd = {self.CONSOLE_SCROLLABILITY:self.consoleScrollability}

        if self.recentFiles:
            tmpd[self.RECENTFILES] = self.recentFiles

        with open(self.configPath, 'w+', encoding=JSON_ENCODING) as f:
            json.dump(tmpd, f, ensure_ascii=False, indent='  ')

    def __repr__(self):
        r = []

        for k, v in self.__dict__.items():
            r.append('%s=%s' % (k, v))

        return '%s(%s)' % (self.__class__.__name__, ', '.join(r))


if __name__ == '__main__':
    print('[debugging %s]' % __file__)

    cfg = Config()
    cfg.load()
    print(cfg)
    #cfg.save()
