"""
calculator.py : provide the Calculator and CalculatorWindow class.

Author(s)     : Frédéric Le Roux frederic.le-roux@imj-prg.fr
Maintainer(s) : Frédéric Le Roux frederic.le-roux@imj-prg.fr
Created       : 06 2023 (creation)
Repo          : https://github.com/dEAduction/dEAduction

Copyright (c) 2023 the d∃∀duction team

This file is part of d∃∀duction.

    d∃∀duction is free software: you can redistribute it and/or modify it under
    the terms of the GNU General Public License as published by the Free
    Software Foundation, either version 3 of the License, or (at your option)
    any later version.

    d∃∀duction is distributed in the hope that it will be useful, but WITHOUT
    ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
    FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
    more details.

    You should have received a copy of the GNU General Public License along
    with dEAduction.  If not, see <https://www.gnu.org/licenses/>.
"""

if __name__ == '__main__':
    from deaduction.dui.__main__ import language_check

    language_check()

import sys

from typing import Union, List

from PySide2.QtWidgets import (QApplication, QWidget, QPushButton, QToolButton,
                               QHBoxLayout, QVBoxLayout, QLabel)

from deaduction.pylib.pattern_math_obj import (PatternMathObject,
                                               MarkedPatternMathObject,
                                               MarkedMetavar,
                                               CalculatorPatternLines,
                                               calculator_group,
                                               logic_group)

from deaduction.dui.elements import TargetLabel

global _


class CalculatorButton(QToolButton):
    """
    A class to display a button associated to a (list of)
    MarkedPatternMathObjects. Pressing the button insert (one of) the pattern
    at the current cursor position in the MarkedPatternMathObject under
    construction.
    """

    def __init__(self, symbol):
        super().__init__()
        self.pattern_s = CalculatorPatternLines.marked_patterns[symbol]
        self.setText(symbol)


class CalculatorButtons(QHBoxLayout):
    """
    A class to display a line of CalculatorButton.
    """

    def __init__(self, title: str, line: [str]):
        super().__init__()
        self.title = title
        self.line = line
        self.buttons = [CalculatorButton(symbol) for symbol in line]
        for button in self.buttons:
            self.addWidget(button)


class CalculatorMainWindow(QWidget):
    """
    A class to display a "calculator", i.e. a QWidget that enables usr to
    build a new MathObject (a new mathematical object or property).
    """

    def __init__(self, calc_patterns: [CalculatorPatternLines]):
        super().__init__()
        self.buttons_groups = []
        main_lyt = QVBoxLayout()
        for calc_pattern in calc_patterns:
            title = calc_pattern.title
            main_lyt.addWidget(QLabel(calc_pattern.title + _(':')))
            for line in calc_pattern.lines:
                buttons_lyt = CalculatorButtons(title, line)
                # FIXME: improve UI
                main_lyt.addLayout(buttons_lyt)
                self.buttons_groups.append(buttons_lyt)

        self.target_label = TargetLabel(None)
        main_lyt.addWidget(self.target_label)

        self.setLayout(main_lyt)

    def buttons(self):
        return sum([], [buttons_group.buttons
                        for buttons_group in self.buttons_groups])

    def set_target(self, target):
        target = PatternMathObject(node='MVAR', info={}, children=[],
                                   math_type=target)
        self.target_label.set_target(target)


class CalculatorController:
    """
    The calculator controller. This is initiated with
    - a MarkedPatternMathObject, typically just a Metavar, that stands for
    the object under construction.
    - a dictionary of CalculatorGroup instances, that is used to build the
    various buttons groups.
    """

    def __init__(self, target: MarkedPatternMathObject = None,
                 context=None,
                 calculator_groups=None):
        self.target = target
        if calculator_groups:
            self.calculator_groups = calculator_groups
        else:  # Standard groups
            self.calculator_groups = [calculator_group]

        self.calculator_ui = CalculatorMainWindow(self.calculator_groups)
        self.calculator_ui.set_target(target)

    def show(self):
        self.calculator_ui.show()


def main():

    app = QApplication([])
    calculator = CalculatorController()

    calculator.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()






