"""
########################################################
# exercisewidget.py : provide the ExerciseWidget class #
########################################################

Author(s)      : - Kryzar <antoine@hugounet.com>
                 - Florian Dupeyron <florian.dupeyron@mugcat.fr>
Maintainers(s) : - Kryzar <antoine@hugounet.com>
                 - Florian Dupeyron <florian.dupeyron@mugcat.fr>
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

from functools import           partial
import logging
from gettext import gettext as  _
from pathlib import Path
import trio
from typing import              Callable
import qtrio

from PySide2.QtCore import (    Signal,
                                Slot,
                                Qt)
from PySide2.QtGui import       QIcon
from PySide2.QtWidgets import ( QAction,
                                QDesktopWidget,
                                QGroupBox,
                                QHBoxLayout,
                                QInputDialog,
                                QMainWindow,
                                QMessageBox,
                                QToolBar,
                                QVBoxLayout,
                                QWidget)

from deaduction.dui.utils import        replace_delete_widget
from deaduction.dui.widgets import (    ActionButton,
                                        ActionButtonsWidget,
                                        LeanEditor,
                                        StatementsTreeWidget,
                                        StatementsTreeWidgetItem,
                                        ProofStatePOWidget,
                                        ProofStatePOWidgetItem,
                                        TargetWidget)
from deaduction.pylib.actions import (  Action,
                                        InputType,
                                        MissingParametersError,
                                        WrongUserInput)
import deaduction.pylib.actions.generic as generic
from deaduction.pylib.coursedata import (   Definition,
                                            Exercise,
                                            Theorem)
from deaduction.pylib.server.exceptions import FailedRequestError
from deaduction.pylib.mathobj import (  Goal,
                                        ProofState)
from deaduction.pylib.server import     ServerInterface

log = logging.getLogger(__name__)


###########
# Widgets #
###########


class ExerciseToolbar(QToolBar):

    def __init__(self):
        super().__init__(_('Toolbar'))

        icons_dir = Path('share/graphical_resources/icons/')
        self.undo_action = QAction(
                QIcon(str((icons_dir / 'undo_action.png').resolve())),
                _('Undo action'), self)
        self.redo_action = QAction(
                QIcon(str((icons_dir / 'redo_action.png').resolve())),
                _('Redo action'), self)

        self.toggle_lean_editor_action = QAction(
                QIcon(str((icons_dir / 'lean_editor.png').resolve())),
                _('Toggle L∃∀N'), self)

        self.addAction(self.undo_action)
        self.addAction(self.redo_action)
        self.addAction(self.toggle_lean_editor_action)


class ExerciseCentralWidget(QWidget):
    """
    Main, central and biggest widget in the exercise window. This
    widgets contains many crucial children widgets:
        - the target widget (self.target_wgt);
        - the Context area widgets:
            * the objects widget (self.objects_wgt);
            * the properies widget (self.props_wgt);
        - the Action area widgets:
            * the logic buttons (self.logic_btns);
            * the proof techniques buttons (self.proof_btns);
            * the statements tree (self.statements_tree, see
              StatementsTreeWidget.__doc__).
    All of these are instanciated in self.__init__ thanks to widget
    classes defined elsewhere (mainly actions_widgets_classes.py and
    context_widgets_classes.py) and properly arranged in layouts.

    Self is instantiated with only an instance of the class Exercise.
    However, when this happens, it does not have a context nor a target
    (L∃∀N has not yet been called, see ExerciseMainWindow.__init__!):
    empty widgets are displayed for Context elements. Once L∃∀N has been
    successfully called and sent back a goal (an instance of the class
    Goal contains a target, objects and properties, see
    deaduction.pylib.mathobj.Goal), Context elements widgets are changed
    with the method update_goal.

    Note that nor the exercise (used in self.__init__) or the goal are
    kept as class attributes.

    :attribute logic_btns ActionButtonsWidget: Logic buttons available
        for this exercise.
    :attribute objects_wgt ProofStatePOWidget: Widget for context
        objects (e.g. f:X->Y a function).
    :attribute proof_btns ActionButtonsWidget: Proof technique buttons
        available for this exercise.
    :attribute props_wgt ProofStatePOWidget: Widget for context
        properties (e.g. f is continuous).
    :attribute statements_tree StatementsTreeWidget: Tree widget for
        statements (theorems, definitions, past exercises) available to
        this exercise.
    :attribute target_wgt TargetWidget: Widget to display the context
        target.

    :property actions_buttons [ActionButtons]: A list of all objects
        and properties (instances of the class ProofStatePoWidgetItem).
    :property context_items [ProofStatePOWidgetItems]: A list of all
        objects and properties (instances of the class
        ProofStatePoWidgetItem).
    """

    def __init__(self, exercise: Exercise):
        """
        Init self with an instance of the class Exercise. See
        self.__doc__.

        :param exercise: The instance of the Exercise class representing
            an exercise to be solved by the user.
        """

        super().__init__()

        # ───────────── Init layouts and boxes ───────────── #
        # I wish none of these were class atributes, but we need at
        # least self.__main_lyt and self.__context_lyt in the method
        # self.update_goal.

        self.__main_lyt     = QVBoxLayout()
        self.__context_lyt  = QVBoxLayout()
        context_actions_lyt = QHBoxLayout()
        actions_lyt         = QVBoxLayout()

        actions_gb = QGroupBox(_('Actions (transform context and target)'))
        context_gb = QGroupBox(_('Context (objects and properties)'))

        # ──────────────── Init Actions area ─────────────── #

        self.logic_btns = ActionButtonsWidget(exercise.available_logic)
        self.proof_btns = ActionButtonsWidget(
                exercise.available_proof_techniques)

        statements           = exercise.available_statements
        outline              = exercise.course.outline
        self.statements_tree = StatementsTreeWidget(statements, outline)

        # ─────── Init goal (Context area and target) ────── #

        self.objects_wgt = ProofStatePOWidget()
        self.props_wgt   = ProofStatePOWidget()
        self.target_wgt  = TargetWidget()

        # ───────────── Put widgets in layouts ───────────── #

        # Actions
        actions_lyt.addWidget(self.logic_btns)
        actions_lyt.addWidget(self.proof_btns)
        actions_lyt.addWidget(self.statements_tree)
        actions_gb.setLayout(actions_lyt)

        # Context
        self.__context_lyt.addWidget(self.objects_wgt)
        self.__context_lyt.addWidget(self.props_wgt)
        context_gb.setLayout(self.__context_lyt)

        # https://i.kym-cdn.com/photos/images/original/001/561/446/27d.jpg
        context_actions_lyt.addWidget(context_gb)
        context_actions_lyt.addWidget(actions_gb)
        self.__main_lyt.addWidget(self.target_wgt)
        self.__main_lyt.addLayout(context_actions_lyt)

        self.setLayout(self.__main_lyt)

    ##############
    # Properties #
    ##############

    @property
    def actions_buttons(self) -> [ActionButton]:
        """
        Do not delete! A list of all logic buttons and proof technique
        buttons (instances of the class ActionButton).
        """

        return self.logic_btns.buttons + self.proof_btns.buttons 
    
    ###########
    # Methods #
    ###########
    

    def freeze(self, yes=True):
        """
        Freeze interface if yes: 
            - disable objects and properties;
            - disable all buttons;
        unfreeze it otherwise.

        :param yes: See above.
        """

        to_freeze = [self.objects_wgt,
                     self.props_wgt,
                     self.logic_btns,
                     self.proof_btns,
                     self.statements_tree]
        for widget in to_freeze:
            widget.setEnabled(not yes)

    def update_goal(self, new_goal: Goal):
        """
        Change goal widgets (self.objects_wgts, self.props_wgt and
        self.target_wgt) to new widgets, corresponding to new_goal.

        :param new_goal: The goal to update self to.
        """

        # Init context (objects and properties). Get them as two list of
        # (ProofStatePO, str), the str being the tag of the prop. or obj.
        # FIXME: tags
        new_context    = new_goal.tag_and_split_propositions_objects()
        new_target     = new_goal.target
        new_target_tag = '='  # new_target.future_tags[1]
        new_objects    = new_context[0]
        new_props      = new_context[1]

        new_objects_wgt = ProofStatePOWidget(new_objects)
        new_props_wgt   = ProofStatePOWidget(new_props)
        new_target_wgt  = TargetWidget(new_target, new_target_tag)

        # Replace in the layouts
        replace_delete_widget(self.__context_lyt,
                              self.objects_wgt, new_objects_wgt)
        replace_delete_widget(self.__context_lyt,
                              self.props_wgt, new_props_wgt)
        replace_delete_widget(self.__main_lyt,
                              self.target_wgt, new_target_wgt,
                              ~Qt.FindChildrenRecursively)

        # Set the attributes to the new values
        self.objects_wgt  = new_objects_wgt
        self.props_wgt    = new_props_wgt
        self.target_wgt   = new_target_wgt
        self.current_goal = new_goal


###############
# Main window #
###############


class ExerciseMainWindow(QMainWindow):
    """
    This class is reponsible for both managing the whole interface for
    exercises and communicating with a so-called server interface
    (self.servint, not instanciated in this class, self.servint is an
    alias to an already existing instance): a middle man between the
    interface and L∃∀N. For the interface, it instanciates (see
    self.__init__) ExerciseCentralWidget, a toolbar, and probably more
    things in the future (a status bar and a menu bar among others). For
    the communication with self.servint, it is this class which:
        1. store user selection of math. objects or properties
           (self.current_selection);
        2. detects when an action button (in self.cw.logic_btns or
           in self.cw.proof_btns) or a statement (in
           self.cw.statements_tree) is clicked on;
        3. sends {the current goal, current selection} and {clicked
           action button (with self.__server_call_action)} xor {clicked
           statement (with self.__server_call_statement)} to the server
           interface;
        4. waits for some response (e.g. a new goal, an exception asking
           for new user parameters).

    The communication with the server interface to *send* data (e.g.
    undo button clicked or goal, current selection and action button
    clicked) is achieved in the method self.server_task with signals and
    slots. User interface, server interface and L∃∀N server are
    different entities which remeain separated by design, that is (among
    other things) why signals are used. It is the method
    self.server_task which is in charge of receiving signals and calling
    functions / methods accordingly (although not using Qt's mechanism
    of slots).

    The communication with the server interface to *receive* data (e.g.
    a goal change) is also achieved with signals and slots. Such signals
    are simply connected to Qt Slots in self.__init__; this is much
    simpler than sending data.

    Finally, all of this uses asynchronous processes (keywords async and
    await) using trio and qtrio.
    """

    window_closed         = Signal()
    __action_triggered    = Signal(ActionButton)
    __statement_triggered = Signal(StatementsTreeWidgetItem)

    def __init__(self, exercise: Exercise, servint: ServerInterface):
        super().__init__()

        # ─────────────────── Attributes ─────────────────── #

        self.exercise          = exercise
        self.current_goal      = None
        self.current_selection = []
        self.cw                = ExerciseCentralWidget(exercise)
        self.lean_editor       = LeanEditor()
        self.servint           = servint
        self.toolbar           = ExerciseToolbar()

        # ─────────────────────── UI ─────────────────────── #

        self.setCentralWidget(self.cw)
        self.addToolBar(self.toolbar)
        self.toolbar.redo_action.setEnabled(False)  # No history at beginning
        self.toolbar.undo_action.setEnabled(False)  # same

        # ──────────────── Signals and slots ─────────────── #

        # Actions area
        for action_button in self.cw.actions_buttons:
            action_button.action_triggered.connect(self.__action_triggered)
        self.cw.statements_tree.itemClicked.connect(self.__statement_triggered)

        # UI
        self.toolbar.toggle_lean_editor_action.triggered.connect(
                self.lean_editor.toggle)

        # Server communication
        self.servint.proof_state_change.connect(self.update_proof_state)
        self.servint.lean_file_changed.connect(self.__update_lean_editor)
        self.servint.proof_no_goals.connect(self.fireworks)
        self.servint.nursery.start_soon(self.server_task)  # Start server task

    ###########
    # Methods #
    ###########

    def closeEvent(self, event):
        super().closeEvent(event)
        self.window_closed.emit()

    @property
    def current_selection_as_pspos(self):
        """
        Do not delete! Used many times.
        """

        return [item.proofstatepo for item in self.current_selection]

    def pretty_current_selection(self):
        msg = 'Current user selection: '
        msg += str([item.text() for item in self.current_selection])

        return msg

    def update_goal(self, new_goal: Goal):
        # Reset current context selection
        self.clear_current_selection()

        # Update UI and attributes
        self.cw.update_goal(new_goal)
        self.current_goal = new_goal

        # Reconnect Context area signals and slots
        self.cw.objects_wgt.itemClicked.connect(self.process_context_click)
        self.cw.props_wgt.itemClicked.connect(self.process_context_click)

    ##################################
    # Async tasks and server methods #
    ##################################
    
    # ─────────────────── Server task ────────────────── #
     
    async def server_task(self):
        self.freeze()
        await self.servint.exercise_set(self.exercise)
        self.freeze(False)

        async with qtrio.enter_emissions_channel(
                signals=[self.lean_editor.editor_send_lean,
                         self.toolbar.redo_action.triggered,
                         self.window_closed,
                         self.toolbar.undo_action.triggered,
                         self.__action_triggered,
                         self.__statement_triggered]) as emissions:
            async for emission in emissions.channel:
                if emission.is_from(self.lean_editor.editor_send_lean):
                    await self.process_async_signal(self.__server_send_editor_lean)

                elif emission.is_from(self.toolbar.redo_action.triggered):
                    # No need to call self.update_goal, this emits the
                    # signal proof_state_change of which
                    # self.update_goal is a slot
                    await self.process_async_signal(self.servint.history_redo)

                elif emission.is_from(self.toolbar.undo_action.triggered):
                    await self.process_async_signal(self.servint.history_undo)

                elif emission.is_from(self.window_closed):
                    break

                elif emission.is_from(self.__action_triggered):
                    # TODO: comment, what is emission.args[0]?
                    await self.process_async_signal(partial(self.__server_call_action,
                                                            emission.args[0]))

                elif emission.is_from(self.__statement_triggered):
                    await self.process_async_signal(partial(self.__server_call_statement,
                                                            emission.args[0]))

    # ──────────────── Template function ─────────────── #
    
    async def process_async_signal(self, process_function: Callable):
        self.freeze(True)

        try:
            await process_function()
        except FailedRequestError as e:
            # Display an error message
            # TODO: make it a separate class
            message_box = QMessageBox(self)
            message_box.setIcon(QMessageBox.Critical)
            message_box.setWindowTitle(_('Action not understood'))
            message_box.setText(_('Action not understood'))

            detailed = ""
            for error in e.errors:
                rel_line_number = error.pos_line \
                        - self.exercise.lean_begin_line_number
                detailed += f'* at {rel_line_number}: {error.text}\n'

            message_box.setDetailedText(detailed)
            message_box.setStandardButtons(QMessageBox.Ok)
            message_box.exec_()

            # Abort and go back to last goal
            await self.servint.history_undo()

        finally:
            self.freeze(False)
            # Required because history is always changed with signals
            self.toolbar.undo_action.setEnabled(
                    not self.servint.lean_file.history_at_beginning)
            self.toolbar.redo_action.setEnabled(
                    not self.servint.lean_file.history_at_end)

    # ─────────────── Specific functions ─────────────── #
    # To be called as process_function in the above

    async def __server_call_action(self, action_btn: ActionButton):
        action = action_btn.action
        user_input = []

        # Send action and catch exception when user needs to:
        #   - choose A or B when having to prove (A OR B) ;
        #   - enter an element when clicking on 'exists' button.
        while True:
            try:
                if user_input == []:
                    code = action.run(self.current_goal,
                                      self.current_selection_as_pspos)
                else:
                    code = action_btn.action.run(self.current_goal,
                            self.current_selection, user_input)
            except MissingParametersError as e:
                if e.input_type == InputType.Text:
                    text, ok = QInputDialog.getText(action_btn,
                            e.title, e.output)
                elif e.input_type == InputType.Choice:
                    text, ok = QInputDialog.getItem(action_btn,
                            _("Choose element"), "", e.list_of_choices,
                            0, False)
                if ok:
                    user_input.append(text)
                else:
                    break
            except WrongUserInput:
                self.clear_current_selection()
                break
            else:
                await self.servint.code_insert(action.caption, code)
                break

    async def __server_call_statement(self, item: StatementsTreeWidgetItem):
        # Do nothing is user clicks on a node
        if isinstance(item, StatementsTreeWidgetItem):
            item.setSelected(False)
            statement = item.statement

            if isinstance(statement, Definition):
                code = generic.action_definition(self.current_goal,
                        self.current_selection_as_pspos, statement)
            elif isinstance(statement, Theorem):
                code = generic.action_theorem(self.current_goal,
                        self.current_selection_as_pspos, statement)

            await self.servint.code_insert(statement.pretty_name, code)

    async def __server_send_editor_lean(self):
        await self.servint.code_set(_('Code from editor'),
                self.lean_editor.code_get())

    #########
    # Slots #
    #########

    @Slot()
    def clear_current_selection(self):
        for item in self.current_selection:
            item.mark_user_selected(False)
        self.current_selection = []

    @Slot()
    def freeze(self, yes=True):
        self.cw.freeze(yes)
        self.toolbar.setEnabled(not yes)

    @Slot()
    def fireworks(self):
        # TODO: make it a separate class
        QMessageBox.information(self, _('Target solved'), _('Target solved!'),
                                QMessageBox.Ok)

    @Slot(ProofStatePOWidgetItem)
    def process_context_click(self, item: ProofStatePOWidgetItem):

        # One clicked, one does not want the item to remain visually
        # selected
        item.setSelected(False)

        if item not in self.current_selection:
            item.mark_user_selected(True)
            self.current_selection.append(item)
        else:
            item.mark_user_selected(False)
            self.current_selection.remove(item)

    @Slot()
    def __update_lean_editor(self):
        self.lean_editor.code_set(self.servint.lean_file.inner_contents)

    @Slot(ProofState)
    def update_proof_state(self, proofstate: ProofState):
        # Weird that this methods only does this.
        # TODO: maybe delete it to only have self.update_goal?
        self.update_goal(proofstate.goals[0])
