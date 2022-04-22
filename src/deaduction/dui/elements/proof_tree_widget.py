"""
# Display trials for proof trees #

Author(s)     : F Le Roux
Maintainer(s) : F. Le Roux
Created       : 03 2022 (creation)
Repo          : https://github.com/dEAduction/dEAduction

Copyright (c) 2020 the dEAduction team

This file is part of dEAduction.

    dEAduction is free software: you can redistribute it and/or modify it under
    the terms of the GNU General Public License as published by the Free
    Software Foundation, either version 3 of the License, or (at your option)
    any later version.

    dEAduction is distributed in the hope that it will be useful, but WITHOUT
    ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
    FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for
    more details.

    You should have received a copy of the GNU General Public License along
    with dEAduction.  If not, see <https://www.gnu.org/licenses/>.
"""

import logging
from typing import Union, Optional
from PySide2.QtWidgets import (QApplication, QFrame, QLayout,
                               QHBoxLayout, QVBoxLayout, QGridLayout,
                               QLineEdit, QListWidget, QWidget, QGroupBox,
                               QLabel, QTextEdit, QSizePolicy)
from PySide2.QtWidgets import QScrollArea
from PySide2.QtCore import Qt, Signal, Slot, QSettings, QEvent
from PySide2.QtGui import QFont, QColor, QPalette, QIcon, QPainter, QPixmap
import sys

import deaduction.pylib.config.vars as cvars
import deaduction.pylib.config.dirs as cdirs

if __name__ != "__main__":
    from deaduction.pylib.proof_tree import GoalNode
    from deaduction.pylib.mathobj import MathObject

log = logging.getLogger(__name__)
global _
# _ = lambda x: x


def display_object(math_objects):
    """
    Recursively convert MathObjects inside math_objects to str in html format.
    """
    if math_objects is None:
        return None
    elif isinstance(math_objects, str):
        return math_objects
    elif isinstance(math_objects, list):
        return list([display_object(mo) for mo in math_objects])
    elif isinstance(math_objects, tuple):
        return tuple(display_object(mo) for mo in math_objects)
    else:
        if math_objects.math_type.is_prop():
            return math_objects.math_type.to_display(format_="html")
        else:
            return math_objects.to_display(format_="html")


def operator_arrow():
    # arrow_label.setScaledContents(True)
    # arrow_label.setMaximumSize(self.height(), self.height())
    arrow_label = QLabel()
    arrow_icon_path = cdirs.icons / "right_arrow.png"
    pixmap = QPixmap(str(arrow_icon_path.resolve()))
    arrow_label.setPixmap(pixmap)

    return arrow_label


class DisclosureTriangle(QLabel):
    """
    A dynamic QLabel that changes appearance and call a function when clicked.
    """

    def __init__(self, slot: callable, hidden=False):
        super().__init__()
        self.slot = slot
        self.setText("▷" if hidden else "▽")
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)

    def mousePressEvent(self, ev) -> None:
        """
        Modify self's appearance and call the slot function.
        """
        self.setText("▷" if self.text() == "▽" else "▽")
        self.slot()


class VertBar(QFrame):
    def __init__(self):
        super().__init__()
        self.setFrameShape(QFrame.VLine)
        self.setFrameShadow(QFrame.Raised)
        self.setLineWidth(1)
        self.setMidLineWidth(2)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.MinimumExpanding)


class RawLabelMathObject(QLabel):
    """
    Mother class for displaying a MathObject.
    """

    def __init__(self, math_object=None, html_msg: callable = None):
        """
        Either math_object or html_msg is not None. If html_msg is not None
        then it ias a callable with parameter use_color.
        """
        super().__init__()
        assert math_object or html_msg
        self.html_msg = html_msg
        self.math_object = math_object
        self.setTextFormat(Qt.RichText)
        self.setText(self.txt)

    @property
    def is_prop(self):
        if self.math_object:
            return self.math_object.math_type.is_prop()

    @property
    def txt(self):
        if self.html_msg:
            return self.html_msg(use_color=self.isEnabled())

        use_color = self.isEnabled()
        if isinstance(self.math_object, str):
            return self.math_object
        else:
            txt = (self.math_object.math_type.to_display(format_="html",
                                                         use_color=use_color)
                   if self.is_prop
                   else self.math_object.to_display(format_="html",
                                                    use_color=use_color))
        return txt

    def changeEvent(self, event) -> None:
        """
        In case object is enabled/disabled, change to display colored variables.
        """
        self.setText(self.txt)
        event.accept()


class GenericLMO(RawLabelMathObject):
    """
    A class for displaying MathObject inside a frame.
    """
    def __init__(self, math_object, new=True):
        super().__init__(math_object)
        # The following is used in the style sheet
        is_new = "new" if new else "old"
        is_prop = "prop" if self.is_prop else "obj"
        self.setObjectName(is_new + "_" + is_prop)


class LayoutMathObject(QHBoxLayout):
    """
    Display a LabelMathObject inside a h-layout so that the box is not too big.
    """

    def __init__(self, math_object, align=None, new=True):
        super().__init__()
        if align in (None, "right"):
            self.addStretch(1)
        self.addWidget(GenericLMO(math_object, new=new))
        if align in (None, "left"):
            self.addStretch(1)


class LayoutMathObjects(QVBoxLayout):
    """
    Display a vertical pile of LayoutMathObjects.
    """

    def __init__(self, math_objects, align=None, new=True):
        super().__init__()
        self.addStretch(1)
        for math_object in math_objects:
            self.addLayout(LayoutMathObject(math_object, align=align, new=new))
        self.addStretch(1)


class OperatorLMO(RawLabelMathObject):
    """
    Display a MathObject which is a property operating on other objects.
    """

    def __init__(self, math_object):
        super().__init__(math_object)
        self.setObjectName("operator")


class LayoutOperator(QWidget):
    """
    Display a OperatorLMO inside a v-layout so that the box is not too big.
    """

    def __init__(self, math_object):
        super().__init__()
        layout = QVBoxLayout()
        layout.addStretch(1)
        layout.addWidget(OperatorLMO(math_object))
        layout.addStretch(1)
        self.setLayout(layout)


###########################
# Context / target blocks #
###########################
class ContextWidget(QWidget):
    """
    A widget for displaying new context object on one line.
    """

    def __init__(self, math_objects):
        super().__init__()
        self.layout = QHBoxLayout()
        self.layout.addStretch(1)

        self.math_objects = []
        for math_object in math_objects:
            self.add_child(math_object)

        self.setLayout(self.layout)

    def add_child(self, math_object: QWidget):
        """
        Insert a child math_object at the end, just before the stretch item.
        """
        # FIXME: unused?
        self.math_objects.append(math_object)
        item = GenericLMO(math_object)
        self.layout.insertWidget(self.layout.count()-1, item)


class PureContextWidget(ContextWidget):
    """
    A widget for displaying new context object from a pure context step,
    e.g. modus ponens, shown as output of an "operator" object receiving some
    "input objects", as in
    y --> [f surjective] --> x, f(x)=y.
    """

    def __init__(self, premises, operator, conclusions):
        super().__init__([])
        self.premises = premises
        self.operator = operator
        self.conclusions = conclusions

        input_layout = LayoutMathObjects(premises, align="right", new=False)
        output_layout = LayoutMathObjects(conclusions, align="left")
        operator_wdg = LayoutOperator(operator)

        # Input -> Operator -> output:
        if premises:
            self.layout.addLayout(input_layout)
            self.layout.addWidget(operator_arrow())
        self.layout.addWidget(operator_wdg)
        self.layout.addWidget(operator_arrow())
        self.layout.addLayout(output_layout)

        self.layout.addStretch(1)


goal_msg_dict={"solved": _("Goal!"),
               "conditionally_solved": "",
               "under_construction": _("(to be solved...)")}


class TargetWidget(QWidget):
    """
    A widget for displaying a new target, with a target_msg (generally "Proof of
    ...") and a layout for displaying the proof of the new target.
    A disclosure triangle allows showing / hiding the proof.
    The layout is a 4x2 grid layout, with the following ingredients:
    triangle     |  "Proof of target"
    -----------------------------
    vertical bar | content_layout

    The content_layout contains
        - self.children_layout
        _ self.status_label
    The children_layout is designed to welcome the content of the
    logical_children of the WidgetGoalBlock to which the TargetWidget belongs,
    which will be gathered in a single widget.
    The status_label display the status of the target (goal solved?).
    """

    def __init__(self, parent_wgb, target: MathObject, target_msg: callable,
                 hidden=False):
        super().__init__()
        self.hidden = False
        self.target = target
        self.target_msg = target_msg
        self.parent_wgb = parent_wgb

        # Title and frame:
        self.triangle = DisclosureTriangle(self.toggle, hidden=False)
        self.triangle.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.vert_bar = VertBar()
        self.title_label = RawLabelMathObject(html_msg=self.target_msg)
        self.title_label.setTextFormat(Qt.RichText)
        self.title_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # Children, status:
        self.content_layout = QVBoxLayout()
        self.children_layout = QVBoxLayout()
        self.status_label = QLabel(self.status_msg)
        self.status_label.setStyleSheet("font-style: italic;")
        self.content_layout.addLayout(self.children_layout, 0)
        self.content_layout.addWidget(self.status_label, 1)
        # self.content_layout.addWidget(QLabel(""), 0, 2)  # Just to add stretch
        # self.content_layout.setColumnStretch(2, 1)
        self.status_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.children_wgt = []

        layout = QGridLayout()  # 2x3, five items
        layout.addWidget(self.triangle, 0, 0)
        layout.addWidget(self.vert_bar, 1, 0)
        layout.addWidget(self.title_label, 0, 1)
        layout.addWidget(QLabel(""), 0, 2)  # Just to add stretch
        layout.addLayout(self.content_layout, 1, 1)

        # layout.setSizeConstraint(QLayout.SetMinAndMaxSize)

        layout.setColumnStretch(2, 1)
        layout.setAlignment(self.triangle, Qt.AlignHCenter)
        layout.setAlignment(self.vert_bar, Qt.AlignHCenter)
        self.main_layout = layout
        self.setLayout(layout)

        if hidden:
            self.toggle()

    def toggle(self):
        """
        Toggle on / off the display of the content.
        """
        self.hidden = not self.hidden
        if self.hidden:  # Content_layout is the fourth layoutItem
            self.main_layout.takeAt(4)
            # self.context_widget.hide()
            # for child in self.children_wgt:
            #     child.hide()
            self.status_label.hide()
        else:
            self.main_layout.addLayout(self.content_layout, 1, 1)
            # for child in self.children_wgt:
            #     child.show()
            self.status_label.show()

    @property
    def status_msg(self) -> Optional[str]:
        if self.parent_wgb.is_solved():
            return _("Goal!")
        elif self.parent_wgb.is_conditionally_solved():
            return None
        else:
            return "( ... under construction... )"

    # def changeEvent(self, event):
    #     self.set_status()

    def set_status(self):
        if not self.status_msg:
            self.status_label.hide()
        else:
            self.status_label.show()
            self.status_label.setText(self.status_msg)

    def add_child(self, child):
        self.children_layout.addWidget(child)

    def remove_child(self, child):
        self.children_layout.removeWidget(child)


########################
# Abstract Goal blocks #
########################
class AbstractGoalBlock:
    """
    A generic class for dealing with the logical part of WidgetGoalBlock.
    An AbstractGoalBlock may have one target and two context lists,
    corresponding to new context element to be displayed before / after the
    target.
    - rw = None / "rw" / "implicit_rw".
    """
    merge = True  # Set to False to prevent any merging
    goal_nb = 0

    def __init__(self, logical_parent, goal_node,
                 context1: [MathObject] = None,
                 target: MathObject = None, context2=None,
                 pure_context: tuple = None,
                 merge_up=False, merge_down=False, rw=None):

        self._context1 = context1 if context1 else []
        self._target = target
        self.context2 = context2 if context2 else []
        self.pure_context = pure_context if pure_context else ()

        self.logical_parent = logical_parent  # Usually set by parent
        self.logical_children = []
        self.goal_nb = AbstractGoalBlock.goal_nb
        AbstractGoalBlock.goal_nb += 1

        self.wanna_merge_up = merge_up
        self.wanna_merge_down = merge_down
        self.rw = rw

        self.goal_node = goal_node

    def is_recursively_solved(self):
        return self.goal_node.is_recursively_solved()

    @property
    def merge_up(self):
        """
        True if self's content should be merged with parent's.
        """
        return (AbstractGoalBlock.merge
                and self.wanna_merge_up and self.logical_parent is not None
                and self.logical_parent.wanna_merge_down
                and self.isEnabled() == self.logical_parent.isEnabled())

    @property
    def merge_down(self):
        """
        True if self's content should be merged with (lonely) child's.
        """
        return (AbstractGoalBlock.merge
                and self.wanna_merge_down and len(self.logical_children) == 1
                and self.logical_children[0].wanna_merge_up
                and self.isEnabled() == self.logical_children[0].isEnabled())

    @property
    def context1(self):
        """
        Fusion self 's _context with child's context. Note that this will call
        recursively to all descendant's _context, as far as they are IntroWGB.
        """
        if self.merge_down:
            return self._context1 + self.logical_children[0].context1
        else:
            return self._context1

    @property
    def target(self):
        if self.merge_down:
            return self.logical_children[0].target
        else:
            return self._target

    def set_invisible(self, yes=True):
        """
        This is used for instance for WGB corresponding to end of proof,
        which are not supposed to be displayed.
        """
        self._is_visible = not yes

    def is_visible(self, reference_level=-1):
        if self._is_visible is not None:
            return self._is_visible

        if reference_level == -1:
            reference_level = WidgetGoalBlock.rw_level
        return self.rw_level <= reference_level
        # and not self.merge_up

    @property
    def displayable_children(self):
        """
        Return the list of children that should be displayed (either here or
        by an ascendant).
        """
        return [child for child in self.logical_children if
                child.is_visible() and not child.merge_up]

    @property
    def descendants_not_displayed_by_self(self):
        """
        Return the ordered list of descendants that are not displayed by their
        parent, and should be displayed by one of self's ascendants.
        """
        if self.is_visible() and not self.merge_up:
            # Self will handle descendants
            return []
        else:
            descendants = []
            for child in self.logical_children:
                descendants.extend(child.descendants_not_displayed_by_self)
            return self.displayable_children + descendants

    @property
    def descendants_displayed_by_self(self):
        """
        Determine the ordered list of widgets that should be displayed in
        self.children_layout.
        """
        if not self.is_visible() or self.merge_up:
            return []
        else:
            descendants = []
            for child in self.logical_children:
                descendants.extend(child.descendants_not_displayed_by_self)
            return self.displayable_children + descendants

    @property
    def target_msg(self) -> callable:
        if self.merge_down:
            return self.logical_children[0].target_msg  # No parentheses!
        else:
            return self.goal_node.html_msg  # (callable)

    def add_logical_child(self, child):
        self.logical_children.append(child)


######################
# Widget Goal blocks #
######################
class WidgetGoalBlock(QWidget, AbstractGoalBlock):
    """
    A generic widget for displaying an AbstractGoalNode. It has three
    optional widgets:
     - one widget for showing some context objects in a horizontal layout,
     - another one for showing a target,
     - and a third one for showing a second context list under the target.

    If self has a target_widget, then it has a children_layout inside to
    welcome children (and descendants). If not, children are passed to
    logical_parent.

    IMPORTANT: children are assumed to be added afterwards,
    by creating a new WidgetGoalBlock with self as logical_parent. Indeed the
    __init__() method calls set_layout_without_children, but does not add
    children.
    """
    rw_level = 1  # show rw but not implicit rw

    def __init__(self, logical_parent, goal_node,
                 context1=None, target=None, context2=None, pure_context=None,
                 merge_down=False, merge_up=False, rw_level=0):
        """
        rw_level =  0 if self is not a rw operation,
                    1 if self is a rw operation
                    2 if self is an implicit rw operation
        self will be displayed only if self.rw_level <= cls.rw_level.
        """
        assert (pure_context is None or (context1 is None and target is None
                                         and context2 is None))
        super().__init__()
        AbstractGoalBlock.__init__(self, logical_parent=logical_parent,
                                   goal_node=goal_node,
                                   context1=context1,
                                   target=target, context2=context2,
                                   pure_context=pure_context,
                                   merge_down=merge_down, merge_up=merge_up)
        self._is_visible = None

        # Main widgets containers:
        self.pure_context_widget: Optional[PureContextWidget] = None
        self.context1_widget: Optional[ContextWidget] = None
        self.target_widget: Optional[TargetWidget] = None
        self.context2_widget: Optional[ContextWidget] = None
        self.children_widgets = []

        # Set main_layout with just one stretch
        self.main_layout = QVBoxLayout()
        self.main_layout.setSizeConstraint(QLayout.SetMinAndMaxSize)
        self.main_layout.addStretch(1)
        self.setLayout(self.main_layout)

        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        if logical_parent:
            self.logical_parent.add_logical_child(self)
        self.set_layout_without_children()

    def __repr__(self):
        return self.context1, self.target, self.context2, self.pure_context

    # def set_invisible(self, yes=True):
    #     """
    #     This is used for instance for WGB corresponding to end of proof,
    #     which are not supposed to be displayed.
    #     """
    #     self._is_visible = not yes
    #
    # def is_visible(self, reference_level=-1):
    #     if self._is_visible is not None:
    #         return self._is_visible
    #
    #     if reference_level == -1:
    #         reference_level = WidgetGoalBlock.rw_level
    #     return self.rw_level <= reference_level
    #     # and not self.merge_up

    @property
    def children_layout(self):
        if self.is_visible() and self.target_widget:
            return self.target_widget.children_layout
        else:
            return None

    # @property
    # def displayable_children(self):
    #     """
    #     Return the list of children that should be displayed (either here or
    #     by an ascendant).
    #     """
    #     return [child for child in self.logical_children if
    #             child.is_visible() and not child.merge_up]
    #
    # @property
    # def _non_displayed_descendants(self):
    #     """
    #     Return the ordered list of descendants that are not displayed by their
    #     parent, and should be displayed by self or its parent.
    #     """
    #     if self.is_visible() and not self.merge_up:
    #         # Self will handle children
    #         return []
    #     else:
    #         return self.displayable_children + self._non_displayed_descendants
    #
    # @property
    # def descendants_to_be_displayed(self):
    #     """
    #     Determine the ordered list of widgets that should be displayed in
    #     self.children_layout.
    #     """
    #     if not self.is_visible() or self.merge_up:
    #         return []
    #     return self.displayable_children + self._non_displayed_descendants
    #
    # @property
    # def target_msg(self) -> callable:
    #     if self.merge_down:
    #         return self.logical_children[0].target_msg
    #     else:
    #         return self.goal_node.html_msg

    def set_layout_without_children(self):
        """
        Populate main_layout from scratch, but does NOT take care of children.
        """

        # Clear target and context. Context2_widget is a child of target_widget.
        for wdg in (self.pure_context_widget,
                    self.target_widget,
                    self.context1_widget):
            if wdg and self.main_layout.indexOf(wdg) != -1:
                self.main_layout.removeWidget(wdg)
                wdg.hide()
            self.context1_widget = None
            self.context2_widget = None
            self.target_widget = None
            self.pure_context_widget = None

        if self.merge_up:
            # Children must be added afterwards
            self.logical_parent.set_layout_without_children()
            return
        if not self.is_visible:
            return

        # Create and insert new widgets (at pole position, in reverse order):
        if self.pure_context:
            premises, operator, conclusions = self.pure_context
            self.pure_context_widget = PureContextWidget(premises, operator,
                                                         conclusions)
            self.main_layout.insertWidget(0, self.pure_context_widget)

        if self.target:
            self.target_widget = TargetWidget(self, self.target,
                                              self.target_msg)
            self.main_layout.insertWidget(0, self.target_widget)

        if self.context1:
            self.context1_widget = ContextWidget(self.context1)
            self.main_layout.insertWidget(0, self.context1_widget)

        if self.context2 and self.target_widget:
            self.context2_widget = ContextWidget(self.context2)
            self.children_layout.addWidget(self.context2_widget)

    def add_widget_child(self, child):
        """
        Add the child if self has a children_layout, else call parent.This
        method is called when adding a logical child or by a child who
        delegates the display of its children widgets.
        """
        if not child.is_visible() or child.merge_up:
            return
        if self.children_layout:
            self.children_widgets.append(child)
            self.children_layout.addWidget(child)
        else:
            self.logical_parent.add_widget_child(child)

    def add_logical_child(self, child):
        """
        This method must be called to add a new child, but NOT to reset an
        existing child.
        """
        super().add_logical_child(child)
        self.add_widget_child(child)
        if self.target_widget:  # Maybe goal has been solved by child
            self.target_widget.set_status()

    def set_children_widgets(self):
        """
        Display directly descendants_to_be_displayed.
        """
        if self.children_layout:
            for child in self.descendants_displayed_by_self:
                self.children_widgets.append(child)
                self.children_layout.addWidget(child)

    # def recursive_update(self):
    #     """
    #     Perform an update, e.g. after a change of details level.
    #     """
    #     for child in self.logical_children:
    #         child.recursive_update()
    #     self.set_layout_without_children()
    #     self.set_children_widgets()

    def is_solved(self):
        self.goal_node.is_recursively_solved()

    def is_conditionally_solved(self):
        """
        True if self is not solved but will be as soon as the descendant
        target are.
        """
        if self.is_solved() or not self.logical_children:
            return False
        if self.merge_down:
            return self.logical_children [0].is_conditionally_solved()
        else:
            return all([child.target or child.is_conditionally_solved() or
                        child.is_solved() for child in self.logical_children])

    def enable_recursively(self, till_goal_nb):
        """
        Recursively disable self from the indicated goal_node nb.
        Note that tree must be updated to adapt merging.
        """
        if self.goal_nb > till_goal_nb:
            self.setEnabled(False)
        else:
            self.setEnabled(True)
        for child in self.logical_children:
            child.enable_recursively(till_goal_nb)

    def check_context1(self):
        """
        Check if context1_widget displays the content of context1.
        """
        if not self.context1:
            return self.context1_widget is None
        elif not self.context1_widget:
            return False

        if len(self.context1) != len(self.context1_widget.math_objects):
            return False
        tests = [math_obj in self.context1 for math_obj in
                 self.context1_widget.math_objects]
        return all(tests)

    def check_context2(self):
        """
        Check if context1_widget displays the content of context1.
        """
        if not self.context2:
            return self.context2_widget is None
        elif not self.context2_widget:
            return False
        if len(self.context2) != len(self.context2_widget.math_objects):
            return False
        tests = [math_obj in self.context2 for math_obj in
                 self.context2_widget.math_objects]
        return all(tests)

    def check_target(self):
        """
        Check if target_widget displays the content of target.
        """
        if not self.target_widget:
            return self.target is None
        else:
            return self.target == self.target_widget.target

    def check_children(self):
        """
        Check if children_widget displays descendants_to_be_displayed.
        """
        return self.children_widgets == self.descendants_displayed_by_self

    def is_up_to_date(self):
        """
        Check if display is coherent with datas. Specifically,
        compare the contents of
        - context1 and context1_widget,
        - target and target_widget,
        - context2 and context2_widget,
        - descendants_to_be_displayed and children_widgets.
        """
        return all([self.check_context1(),
                    self.check_target(),
                    self.check_context2(),
                    self.check_children()])

    def update(self):
        log.debug(f"Updating WGB for nb {self.goal_nb}: {self.goal_node}...")
        log.debug(f"merge down: {self.merge_down}, enabled: {self.isEnabled()}")
        if self.is_up_to_date():
            log.debug("... is up to date")
            return
        else:
            log.debug("...setting layout and children")
            self.set_layout_without_children()
            self.set_children_widgets()

    def update_recursively(self):
        self.update()
        for child in self.logical_children:
            child.update_recursively()


class GoalSolvedWGB(WidgetGoalBlock):
    """
    This WGB reflects GoalNode.goal_solved, a fake goal node with target
    "goal solved". It should remain invisible.
    """
    def __init__(self, logical_parent, goal_node):
        super().__init__(logical_parent, goal_node)
        self.set_invisible()


class ByCasesWGB(WidgetGoalBlock):
    """
    Display of one sub-case of a proof by cases.
    """
    def __init__(self, logical_parent, goal_node, target, context):
        super().__init__(logical_parent, goal_node,
                         target=target, context2=context,
                         merge_down=False, merge_up=False)


class IntroWGB(WidgetGoalBlock):
    """
    Display of introduction of elements to prove universal props.
    Try to merge with parent and child.
    """
    def __init__(self, logical_parent, goal_node, context=None, target=None):
        super().__init__(logical_parent, goal_node, context, target,
                         merge_down=True, merge_up=True)


class IntroImpliesWGB(WidgetGoalBlock):
    """
    Display of introduction of elements to prove universal props or
    implications. Try to merge with parent but not child.
    """
    def __init__(self, logical_parent, goal_node, context=None, target=None):
        super().__init__(logical_parent, goal_node, context, target,
                         merge_down=False, merge_up=True)


class PureContextWGB(WidgetGoalBlock):

    def __init__(self, logical_parent, goal_node,
                 premises, operator, conclusions):
        super().__init__(logical_parent, goal_node,
                         pure_context=(premises, operator, conclusions))


class SubstitutionWGB(WidgetGoalBlock):

    def __init__(self, logical_parent, goal_node,
                 premises, definition, conclusions):
        super().__init__(logical_parent, goal_node,
                         pure_context=(premises, definition, conclusions))


###############
# Main Window #
###############
class ProofTreeWindow(QWidget):
    """
    A widget for displaying the proof tree.
    """

    def __init__(self, context=None, target=None):
        """
        Context and target are the elements of the initial goal.
        """
        super().__init__()
        self.setWindowTitle("Proof Tree")
        settings = QSettings("deaduction")
        if settings.value("proof_tree/geometry"):
            self.restoreGeometry(settings.value("proof_tree/geometry"))

        main_layout = QVBoxLayout()
        self.main_window = QScrollArea()
        main_layout.addWidget(self.main_window)

        if context or target:
            main_block = WidgetGoalBlock(context, target)
            self.set_main_block(main_block)

        self.setLayout(main_layout)

        self.main_block = None

        self.set_style_sheet()

    def set_style_sheet(self):
        color_var = cvars.get("display.color_for_variables")
        color_prop = cvars.get("display.color_for_props")
        color_op = cvars.get("display.color_for_operator_props")
        new_border_width = "2px"
        old_border_width = "1px"
        op_border_width = "4px"
        old_border_style = "dotted"
        self.setStyleSheet("QLabel#new_obj:enabled {padding: 5px;"
                               f"border-width: {new_border_width};"
                               f"border-color: {color_var};"
                               "border-style: solid;"
                               "border-radius: 10px;}"
                           "QLabel#new_obj:!enabled {padding: 5px;"
                                f"border-width: {new_border_width};"
                                "border-color: lightgrey;"
                                "border-style: solid;"
                                "border-radius: 10px;}"
                           "QLabel#old_obj:enabled {padding: 5px;"
                               f"border-width: {old_border_width};"
                               f"border-color: {color_var};"
                               f"border-style: {old_border_style};"
                               "border-radius: 10px;}"
                           "QLabel#old_obj:!enabled {padding: 5px;"
                               f"border-width: {old_border_width};"
                               "border-color: lightgrey;"
                               f"border-style: {old_border_style};"
                               "border-radius: 10px;}"
                           "QLabel#new_prop:enabled {padding: 5px;"
                               f"border-width: 2px;"
                               f"border-color: {color_prop};"
                               "border-style: solid;"
                               "border-radius: 10px;}"
                           "QLabel#new_prop:!enabled {padding: 5px;"
                               f"border-width: {new_border_width};"
                               "border-color: lightgrey;"
                               "border-style: solid;"
                               "border-radius: 10px;}"
                           "QLabel#old_prop:enabled {padding: 5px;"
                               f"border-width: {old_border_width};"
                               f"border-color: {color_prop};"
                               f"border-style: {old_border_style};"
                               "border-radius: 10px;}"
                           "QLabel#old_prop:!enabled {padding: 5px;"
                               f"border-width: {old_border_width};"
                               "border-color: lightgrey;"
                               f"border-style: {old_border_style};"
                               "border-radius: 10px;}"
                           "OperatorLMO:enabled {padding: 5px;"
                               f"border-width: {op_border_width};"
                               f"border-color: {color_op};"
                               "border-style: solid;"
                               "border-radius: 10px;}"
                           "OperatorLMO:!enabled {padding: 5px;" 
                               f"border-width: {op_border_width};"
                               "border-color: lightgrey;"
                               "border-style: solid;"
                               "border-radius: 10px;}"
                           )

    def set_main_block(self, block: WidgetGoalBlock):
        self.main_block = block
        self.main_window.setWidget(block)

    def update(self):
        if self.main_block:
            self.main_block.update_recursively()

    def closeEvent(self, event):
        # Save window geometry
        settings = QSettings("deaduction")
        settings.setValue("proof_tree/geometry", self.saveGeometry())
        event.accept()
        self.hide()
        # TODO: save tree state

    @Slot()
    def toggle(self):
        self.setVisible(not self.isVisible())


##############
# Controller #
##############
# if __name__ != "__main__":
def widget_goal_block(parent_widget: Optional[WidgetGoalBlock],
                      goal_node: GoalNode) -> WidgetGoalBlock:
    """
    All WidgetGoalBlock to be inserted in the ProofTreeWidget should be
    created by calling this method.
    """
    # FIXME: goal solved case!!
    new_context = goal_node.goal.new_context
    target = goal_node.goal.target.math_type
    if goal_node.is_intro:
        wgb = IntroWGB(logical_parent=parent_widget, goal_node=goal_node,
                       context=new_context, target=target)
    elif goal_node.is_implies:
        wgb = IntroImpliesWGB(logical_parent=parent_widget,
                              goal_node=goal_node,
                              context=new_context, target=target)
    elif goal_node.is_by_cases:
        wgb = ByCasesWGB(logical_parent=parent_widget,
                         goal_node=goal_node,
                         context=new_context, target=target)
    elif goal_node.is_pure_context:
        premises, operator, conclusions = goal_node.is_pure_context
        wgb = PureContextWGB(parent_widget, goal_node,
                             premises, operator, conclusions)
    elif goal_node.is_goal_solved() or goal_node.is_all_goals_solved():
        wgb = GoalSolvedWGB(parent_widget, goal_node)
    elif goal_node.is_context_substitution:  # TODO: clean this up
        if goal_node.parent.statement:
            definition = goal_node.parent.statement.pretty_name
            premises = goal_node.parent.selection
        else:
            definition = goal_node.parent.selection[0]
            premises = goal_node.parent.selection[1:]
        conclusions = goal_node.goal.new_context

        wgb = SubstitutionWGB(parent_widget, goal_node,
                              premises, definition, conclusions)
    else:
        wgb = WidgetGoalBlock(logical_parent=parent_widget,
                              goal_node=goal_node,
                              target=target, context2=new_context)

    return wgb


def update_from_node(wgb: WidgetGoalBlock, gn: GoalNode):
    """
    Recursively update the WidgetProofTree from (under) the given node.
    We have the following alternative:
    - either there is a new child goal_node for which we will create a
    child wgb;
    - or some child_wgb does not match the corresponding child goal_node:
    in this case all children_wgb should be deleted and new ones will be
    created.
    - or all children wgb match corresponding children goal_nodes.
    """
    pairs = list(zip(wgb.logical_children, gn.children_goal_nodes))
    if (len(wgb.logical_children) > len(gn.children_goal_nodes)
        or any([child_wgb.goal_node is not child_gn
                for child_wgb, child_gn in pairs])):
        # Case 1: Some child_wgb is obsolete: reset all children
        wgb.logical_children = []
        wgb.set_layout_without_children()
        for child_gn in gn.children_goal_nodes:
            child_wgb = widget_goal_block(wgb, child_gn)
        pairs = zip(wgb.logical_children, gn.children_goal_nodes)

    elif len(wgb.logical_children) < len(gn.children_goal_nodes):
        # Case 2: new children
        new_index = len(wgb.logical_children)
        new_children_gn = gn.children_goal_nodes[new_index:]
        for child_gn in new_children_gn:
            child_wgb = widget_goal_block(wgb, child_gn)
        pairs = zip(wgb.logical_children, gn.children_goal_nodes)

    # In any case, recursively update children
    for child_wgb, child_gn in pairs:
        update_from_node(child_wgb, child_gn)


class ProofTreeController:
    """
    A class to create and update a ProofTreeWindow that reflects a ProofTree.
    """
    def __init__(self):
        self.proof_tree = None
        self.proof_tree_window = ProofTreeWindow()

    def set_proof_tree(self, proof_tree):
        self.proof_tree = proof_tree

    def enable(self, till_goal_nb):
        """
        Enable all WGB until a given goal_nb, disabled the others.
        Disabled WGB will be displayed in light grey. This is used when usr
        moves in the history.
        """
        main_block = self.proof_tree_window.main_block
        main_block.enable_recursively(till_goal_nb=till_goal_nb)

    def update(self):
        if not self.proof_tree.root_node:
            return
        elif not self.proof_tree_window.main_block:
            main_block = widget_goal_block(None,
                                           self.proof_tree.root_node)
            self.proof_tree_window.set_main_block(main_block)

        current_goal_node = self.proof_tree.current_goal_node
        # Adapt display to history move:
        # FIXME: this should be useless except in case of history move.
        if current_goal_node:
            goal_nb = current_goal_node.goal_nb
            log.debug(f"Enabling till {goal_nb}")
            self.enable(till_goal_nb=goal_nb)
            self.proof_tree_window.update()

        # Adapt display of ProofTreeWindow to ProofTree:
        update_from_node(self.proof_tree_window.main_block,
                         self.proof_tree.root_node)


def main():
    app = QApplication()
    main_window = ProofTreeWindow()
    AbstractGoalBlock.merge = True

    context0 = ["X", "Y", "f"]
    target0 = "f surjective ⇒ (∀A ⊂ Y, ∀A' ⊂ Y, ( f⁻¹(A) ⊂ f⁻¹(A') ⇒ A ⊂ A' ) )"
    main_block = WidgetGoalBlock(logical_parent=None,
                                 context1=context0, target=target0)

    main_window.set_main_block(main_block)
    main_window.show()

    # TODO: change to successive IntroBlocks:
    intro1 = IntroImpliesWGB(logical_parent=main_block,
                             context=["f surjective"],
                             target="(∀A ⊂ Y, ∀A' ⊂ Y, ( f⁻¹(A) ⊂ f⁻¹(A')"
                                    " ⇒ A ⊂ A' ) )")
    intro2a = IntroWGB(logical_parent=intro1,
                       context=["A"],
                       target="∀A' ⊂ Y, f⁻¹(A) ⊂ f⁻¹(A') ⇒ A ⊂ A'")
    intro2b = IntroWGB(logical_parent=intro2a,
                       context=["A'"], target="f⁻¹(A) ⊂ f⁻¹(A') ⇒ A ⊂ A'")
    intro3 = IntroImpliesWGB(logical_parent=intro2b,
                             context=["f⁻¹(A) ⊂ f⁻¹(A')"], target="A ⊂ A'")

    intro4 = IntroWGB(logical_parent=intro3,
                      context=["y"], target="y ∈ A => y ∈ A'")
    intro5 = IntroWGB(logical_parent=intro4,
                             context=["y ∈ A"], target="y ∈ A'")
    # intro2b.show()


    operator = [(["y"], "f surjective", ["x", "y = f(x)"]),
                (["y ∈ A"], "y = f(x)", ["f(x) ∈ A"]),
                (["f(x) ∈ A"], "definition image réciproque", ["x ∈ f⁻¹(A)"]),
                (["x ∈ f⁻¹(A)"], "f⁻¹(A) ⊂ f⁻¹(A')", ["x ∈ f⁻¹(A')"]),
                (["x ∈ f⁻¹(A')"], "definition image réciproque", ["f(x) ∈ A'"]),
                (["f(x) ∈ A'"], "y = f(x)", ["y ∈ A'"])]
    previous_block = intro5
    # op = operator[0]
    # pure_block0 = PureContextWGB(logical_parent=None,
    #                              premises=op[0],
    #                              operator=op[1],
    #                              conclusions=op[2])
    # pure_block0.show()
    for op in operator:
        pure_block = PureContextWGB(previous_block,
                                    premises=op[0],
                                    operator=op[1],
                                    conclusions=op[2])
        previous_block.add_logical_child(pure_block)
        previous_block = pure_block

    # case_block1 = ByCasesWGB(logical_parent=previous_block,
    #                          context=["y ∈ A"], target="First case: y ∈ A")
    # case_block2 = ByCasesWGB(logical_parent=previous_block,
    #                          context=["y ∉ A"], target="Second case: y ∉ A")
    # case_block1.show()
    # previous_block.set_children([case_block1, case_block2])
    #
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()

