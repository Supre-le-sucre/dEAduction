"""
###################################################################
# context_widgets_classes.py : context widgets for ExerciseWidget #
###################################################################

Author(s)      : Kryzar antoine@hugounet.com
Maintainers(s) : Kryzar antoine@hugounet.com
Date           : July 2020

Copyright (c) 2020 the dEAduction team

This file is part of d∃∀duction.

    d∃∀duction is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    d∃∀duction is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with d∃∀duction. If not, see <https://www.gnu.org/licenses/>.
"""

from pathlib import   Path
from typing  import ( List,
                      Tuple)

from PySide2.QtGui     import ( QBrush,
                                QColor,
                                QIcon)
from PySide2.QtWidgets import ( QHBoxLayout,
                                QLabel,
                                QWidget,
                                QListWidget,
                                QListWidgetItem)

from deaduction.pylib.mathobj import ProofStatePO


#############
# Utilities #
#############


class _TagIcon(QIcon):

    def __init__(self, tag: str):
        icons_folder = Path('share/graphical_resources/icons/')

        if tag not in ['=', '+', '≠']:
            # TODO: catch the exception below
            raise ValueError('tag must be one of "=", "+", "≠". tag: {tag}.')
        elif tag == '=':
            super().__init__('')  # No icon, empty icon trick
            return None
        elif tag == '+':
            icon_path = icons_folder / 'tag_plus.png'
        elif tag == '≠':
            icon_path = icons_folder / 'tag_different.png'

        super().__init__(str(icon_path.resolve()))


################################
# ProofStatePO widgets classes #
################################

# Classes for the two main widgets in 'Context' part of the exercise
# window. Class ProofStatePOWidget is a parent widget containing
# a list of ProofStatePOWidgetItem. Both 'Objects' and 'Properties'
# widgets use those same two classes.

class ProofStatePOWidgetItem(QListWidgetItem):
    """
    Objects (e.g. f:X->Y a function) and properties (e.g. f is
    continuous) are coded as instances of the class ProofStatePO.
    The class ProofStatePOWidgetItem is 'just' the widget in charge of
    containing an instance of the class ProofStatePO and displaying it.

    :atribute proofstatepo (ProofStatePo): The instance of the class
        ProofStatePO self is initiated with.
    """

    def __init__(self, proofstatepo: ProofStatePO, tag: str):
        """
        One creates a ProofStatePOWidgetItem with a ProofStatePO and
        a tag (see _TagIcon). The tag is not an attribute or method
        of the ProofStatePO, it varies at each new goal and is given
        by TODO.

        :param proofstatepo: The ProofStatePO one wants to display.
        :param tag: The tag of proofstatepo.
        :return: An instance of the class ProofStatePOWidgetItem.
        """

        super().__init__()
        self.proofstatepo = proofstatepo  # Keep the pspo as attribute.
        self.setIcon(_TagIcon(tag))
        caption = f'{proofstatepo.format_as_utf8()} : ' \
                  f'{proofstatepo.math_type.format_as_utf8()}'
        self.setText(caption)

    def __eq__(self, other):
        """
        Define the operator == for the class ProofStatePOWidgetItem.
        Do not delete! It is usefull to check if a given instance of
        the class ProofStatePOWidgetItem is in a list of instances of
        this class (the 'for item in pspo_list:' test).

        :param other: An instance of the class ProofStatePOWidgetItem.
        :return: A boolean.
        """

        return self is other  # Brutal but that is what we need.

    def mark_user_selected(self, yes: bool=True):
        """
        Change self's background to green if yes or to normal color
        (e.g. white in light mode) if not yes. Note that this method
        does nothing else ; in particular, it does not add / remove
        self to / from ExerciseMainWindow.current_selection.

        :param yes: Change self's background to green if yes or to
            normal color (e.g. white in light mode) if not yes.
        """

        self.setBackground(QBrush(QColor('limegreen')) if yes else QBrush())


class ProofStatePOWidget(QListWidget):

    def __init__(self, tagged_proofstatepos: [Tuple[ProofStatePO, str]]=[]):
        super().__init__()
        self.items = []

        for proofstatepo, tag in tagged_proofstatepos:
            item = ProofStatePOWidgetItem(proofstatepo, tag)
            self.addItem(item)
            self.items.append(item)


##########################
# Target widgets classes #
##########################


class TargetLabel(QLabel):

    def __init__(self, target: ProofStatePO=None, tag: str=None):
        super().__init__()
        # Display
        #   ∀ x ∈ X, ∃ ε, …
        # and not
        #   H : ∀ x ∈ X, ∃ ε, …
        # where H might be the lean name of the target. That's what
        # the .math_type is for.
        self.setText(target.math_type.format_as_utf8() if target else '…')
        # TODO: add tag
#        if tag:
#            self.setIcon(_TagIcon(tag))

        # Cosmetics
        self.setStyleSheet('font-size: 32pt;')


class TargetWidget(QWidget):

    def __init__(self, target: ProofStatePO=None, tag: str=None):
        super().__init__()
        self.target = target
        self.tag = tag
        self._main_layout = QHBoxLayout()

        self.target_label = TargetLabel(self.target, self.tag)
        self._main_layout.addStretch()
        self._main_layout.addWidget(self.target_label)
        self._main_layout.addStretch()
        self.setLayout(self._main_layout)
