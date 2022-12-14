# DMXCtrl

## ВВЕДЕНИЕ

1. Сие поделие является свободным ПО под лицензией [GPL v3](https://www.gnu.org/licenses/gpl.html).
2. Поделие создано и дорабатывается автором исключительно ради собственных
   нужд и развлечения, а также в соответствии с его представлениями об эргономике
   и функциональности.
3. Автор всех видал в гробу и ничего никому не должен, кроме явно
   прописанного в GPL.
4. Несмотря на вышеуказанное, автор совершенно не против, если поделие
   подойдёт кому-то еще, кроме тех, под кем прогорит сиденье из-за пунктов
   с 1 по 3.

## НАЗНАЧЕНИЕ

Протез консоли управления простейшими DMX512-совместимыми устройствами
для ситуаций, когда Web-консоль OLAD слишком примитивна, а QLC+ избыточна
и вызывает кровотечение из глаз.

**Внимание!**

  1. Это поделие создано для баловства, и категорически НЕ предназначено
     для управления взаправдашним сценическим оборудованием на взаправдашней
     сцене.
  2. Потроха поделия могут быть в любой момент изменены до полной
     неузнаваемости и несовместимости с предыдущей версией.

## ЧЕГО ХОЧЕТ

  - GNU/Linux или другую ОС, под которой заработает нижеперечисленное
  - Python 3.6 или новее
  - GTK 3.20 или новее и соответствующие питоньи модули
  - демон [olad](https://www.openlighting.org/ola/) с соответствующим питоньим модулем

## КАК ПОЛЬЗОВАТЬСЯ

Создать файл(ы) описания консоли и скормить их dmxctrl через командную
строку или диалог открытия файлов в UI.

## ФОРМАТ ФАЙЛА ОПИСАНИЯ КОНСОЛИ

Формат основан на XML.

Пример структуры:
```
<?xml version="1.0" encoding="UTF-8"?>
<dmxcontrols>
    Текст описания консоли
    <panel>
        <level/>
        <switch>
            <option/>
            ...
            <option/>
        </switch>
    </panel>
    <panel>
        <level/>
        <panel>
            <level/>
        </panel>
    </panel>
    <panel>
        <colorlevel/>
    </panel>
</dmxcontrols>
```

### ОБЩИЕ АТРИБУТЫ

Все элементы описания консоли могут иметь необязательные атрибуты:

#### name
Строка, название элемента (отображаемое в UI).

Если не указано (по умолчанию) - элемент отображается без текстовой метки.

#### icon

Строка, имя иконки для отображения в UI.

Значение по умолчанию - пустая строка.

Варианты значений:

  - имя графического файла:
    - абсолютное (полный путь в пределах ФС) или
      относительное (относительно текущего каталога);
    - "@подкаталог/.../имяфайла.расш" - путь к файлу
      относительно каталога, где расположен
      файл .dmxctrl;
    - "!имя" - имя встроенной в программу иконки,
      соответствует названиям цветов встроенной
      палитры (см. описание параметра colorlevel.color);

#### channel
Номер первого канала, используемого соответствующим элементом или
вложенными в него элементами, если они есть (также см. описания
конкретных элементов).

Значение по умолчанию для корневого элемента - 1, для вложенных -
присваивается программой, если они не указаны явно.

При явном указании номеров каналов возможна ситуация, когда более одного
элемента используют одни и те же каналы. Это не является ошибкой.

Для примера, одному и тому же каналу можно задавать значения плавно -
движком (level/colorlevel) и ступенчато - переключателем (switch).

#### expand
Булевское значение. Если "True" элемент будет занимать всё
свободное место на консоли.

Значение по умолчанию - False.

### НЕОБЯЗАТЕЛЬНЫЕ АТРИБУТЫ ЭЛЕМЕНТОВ-КОНТЕЙНЕРОВ (dmxcontrols и panel):

#### vertical
Булевское значение; если True - вложенные элементы будут расположены вертикально.

Значение по умолчанию - False (горизонтальное расположение элементов).

### ТЕКСТ

Между открывающим и закрывающим тэгами кроме вложенных элементов может
находиться текст описания элемента; для разделения строк в нём используется
тэг &lt;br/&gt;.

Описания отображаются в UI в виде всплывающих подсказок при наведении
мыши на соответствующий элемент.

### dmxcontrols
Корневой элемент файла.

#### Необязательные атрибуты:

##### universe
Номер universe DMX512. Значение по умолчанию - 1.

### panel
Панель. Может содержать другие элементы.

#### Необязательные атрибуты (кроме общих для всех элементов):
##### channel
Номер первого канала для вложенных элементов, если указан.
Иначе задаётся программой.

### level
Движок, управляющий значением в одном канале DMX512.

#### Необязательные атрибуты (кроме общих для всех элементов):
##### value
Целое, начальное значение для движка (0..255).
Значение по умолчанию - 0.

##### steps
Целое, количество шагов движка (0..32).

Значение 0 (по умолчанию) указывает плавное изменение положения движка, без шагов.

При steps=1 движок фактически работает как переключатель между значениями 0 и 255.

### colorlevel
Расширенный вариант элемента level - движок с кнопкой выбора цвета.
Движок управляет яркостью выбранного цвета, генерируя значения для трёх каналов.

#### Необязательные атрибуты (кроме общих для всех элементов и наследуемых от level):
##### color
Начальное значение цвета:
  - строка в формате "#RGB" или "#RRGGBB";
  - название цвета из встроенной палитры:
    black, red, orange, yellow, yellowgreen,
    green, greenblue, cyan, deepblue,
    blue, purple, magenta, white.

### switch
Переключатель из двух и более значений. Должен содержать два или более
элемента "option".

#### Необязательные атрибуты (кроме общих для всех элементов):
##### vertical
Булевское значение; если True - кнопки будут расположены вертикально.

Значение по умолчанию - True.

##### active
Целое число в диапазоне от 1 до количества элементов option - номер
активного (выбранного) элемента.

Значение по умолчанию - 1.

##### nchannels
Количество изменяемых переключателем каналов.

Значение по умолчанию - 1.

##### bpl
Целое число - количество кнопок в строке (или столбце, если vertical=True).

Значения <=0 (а также "*" или "auto") означают, что все кнопки будт
расположены в одну строку (или столбец).

#### option
Элемент с данными для switch.

##### Oбязательные атрибуты:
###### value
Список из одного и более целых в диапазоне 0..255, разделённых пробелами -
значения для изменяемых каналов. Количество значений должно соответствовать
значению атрибута switch.nchannels.

##### Необязательные атрибуты:
###### name
Текстовая строка для отображения на кнопке.

##### icon
Имя иконки для отображения на кнопке.
