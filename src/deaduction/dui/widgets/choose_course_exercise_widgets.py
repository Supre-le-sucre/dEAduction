"""
#######################################################################
# choose_course_exercise_widgets.py : course/exercise chooser widgets #
#######################################################################

    Provide StartExerciseDialog: the dialog used by the user to choose
    a course, then an exercise, and start the latter. 

    The class to be used elsewhere in the program is
    StartExerciseDialog (inherits QDialog). The other classes
    (AbstractCoExChooser, CourseChooser, ExerciseChooser) are meant to
    be used in this file only, for technical purposes.

Author(s)      : Kryzar <antoine@hugounet.com>
Maintainers(s) : Kryzar <antoine@hugounet.com>
Date           : October 2020

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

import sys
from functools import partial
from gettext import   gettext as _
from pathlib import   Path
import pickle
from typing  import ( Any,
                      Dict,
                      Optional )

from PySide2.QtCore    import ( Signal,
                                Slot )
from PySide2.QtGui     import ( QFont,
                                QPixmap )
from PySide2.QtWidgets import ( QApplication,
                                QCheckBox,
                                QDialog,
                                QFileDialog,
                                QFrame,
                                QGroupBox,
                                QHBoxLayout,
                                QLabel,
                                QLayout,
                                QLineEdit,
                                QListWidget,
                                QListWidgetItem,
                                QSpacerItem,
                                QPushButton,
                                QTabWidget,
                                QTreeWidgetItem,
                                QTextEdit,
                                QVBoxLayout,
                                QWidget )

from deaduction.dui.widgets      import ( MathObjectWidget,
                                          StatementsTreeWidget,
                                          StatementsTreeWidgetItem )
from deaduction.dui.utils        import   DisclosureTree
from deaduction.config           import ( add_to_recent_courses,
                                          get_recent_courses )
from deaduction.pylib.coursedata import ( Course,
                                          Exercise )


# TODO: Put this function somewhere else (course classmethod?)
def read_pkl_course(course_path: Path) -> Course:
    """
    Extract an instance of the class Course from a .pkl file.

    :param course_path: The path of the course we want to instanciate.
    :return: The instance of the Course class.
    """

    with course_path.open(mode='rb') as input:
        course = pickle.load(input)

    return course


class HorizontalLine(QFrame):
    """
    An horizontal line (like <hr> in HTML) QWidget.
    """

    def __init__(self):

        super().__init__()
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)


class RecentCoursesLW(QListWidget):

    def __init__(self):

        super().__init__()

        courses_paths, titles, exercise_numbers = get_recent_courses()
        info = zip(courses_paths, titles, exercise_numbers)
        for course_path, course_title, exercise_number in info:
            item = RecentCoursesLWI(course_path, course_title)
            self.addItem(item)

    def add_browsed_course(self, course_path: Path, title: str):

        displayed_title = f'(browsed) {title}'
        item = RecentCoursesLWI(course_path, displayed_title)
        self.insertItem(0, item)
        self.setItemSelected(item, True)
    

class RecentCoursesLWI(QListWidgetItem):
    """
    A class to display recent courses and store their Path
    title           str, title to be displayed
    course_path     str, to be displayed in tooltips, and stored as a Path
    number          int, number of last exercise done in this course
    """

    def __init__(self, course_path: Path, title: str):

        w_or_wo = 'w/' if course_path.suffix == '.pkl' else 'w/o'
        super().__init__(f'{title} [{w_or_wo} preview]')

        self.setToolTip(str(course_path))
        self.__course_path = course_path

    @property
    def course_path(self):
        return self.__course_path


class AbstractCoExChooser(QWidget):
    """
    This class was made for technical purposes and is not to be used
    outside this file. In StartExerciseDialog, both the course and the
    exercise choosers have the same structure:
        - a browser area (browse courses or browse exercices inside one
          course) on top;
        - a previewer area (preview the title, task, description, etc)
          on bottom.
    In other words, course and exercise choosers contain different
    widgets which are organized in the same way. Therefore, both
    CourseChooser and ExerciseChooser inherit from this class
    (AbstractCoExChooser). It looks like this:

    |------------|
    |   browser  |
    |------------|
    |   preview  |
    |------------|

    For the details, the bowser part never changes and is instanciated
    at init (browser_layout passed as argument). On the opposite, there
    is a preview only if something (a course or exercise) has been
    chosen. This preview is set with the method set_preview, which is
    called in StartExerciseDialog. Now, CourseChooser and
    ExerciseChooser need to have their own sub-widgets. The way to do
    that here is to redefine __init__ (for the browser) and set_preview
    (for the preview), define the sub-widgets inside the definitions,
    and call super().__init__ and super().set_preview with the defined
    widgets.
    """

    def __init__(self, browser_layout: QLayout):
        """
        Init self by preparing layouts and adding the (fixed)
        browser_layout (not a QWidget!).

        :param browser_layout: QLayout to be displayed for the browser
            area.
        """

        super().__init__()

        no_preview_yet = QLabel(_('No preview yet.'))
        no_preview_yet.setStyleSheet('color: gray;')
        self.__preview_wgt = no_preview_yet

        self.__main_layout = QVBoxLayout()
        self.__main_layout.addLayout(browser_layout)
        self.__main_layout.addItem(QSpacerItem(1, 5))
        self.__main_layout.addWidget(HorizontalLine())
        self.__main_layout.addItem(QSpacerItem(1, 5))
        self.__main_layout.addWidget(self.__preview_wgt)

        self.setLayout(self.__main_layout)

    def set_preview(self, main_widget: QWidget=None, title: str=None,
                    subtitle: str=None, details: Dict[str, str]=None,
                    description: str=None):
        # TODO: Make widget a QLayout instead?
        """
        Set the preview area (given something (course or exercise) has
        been chosen. The preview area is made of a title, a
        substitle, details, a description and a widget. The widget is of
        course specific to CourseChooser or ExerciseChooser and defined
        when the set_preview method is redefined in CourseChooser or
        ExerciseChooser. Visually, the preview area looks like this:

        |----------------------------|
        | title (big)                |
        | subtitle (small, italic)   |
        | |> Details:                |
        |     …: …                   |
        |     …: …                   |
        |                            |
        | description .............. |
        | .......................... |
        | .......................... |
        |                            |
        | |------------------------| |
        | |         widget         | |
        | |------------------------| |
        |----------------------------|
        """

        preview_wgt = QWidget()
        layout      = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        if title:
            title_wgt = QLabel(title)
            title_wgt.setStyleSheet('font-weight: bold;' \
                                    'font-size:   17pt;')
            layout.addWidget(title_wgt)

        if subtitle:
            subtitle_wgt = QLabel(subtitle)
            subtitle_wgt.setStyleSheet('font-style: italic;' \
                                       'color:      gray;')
            subtitle_lyt = QHBoxLayout()
            subtitle_lyt.addWidget(subtitle_wgt)
            layout.addLayout(subtitle_lyt)

        if details:
            details_wgt = DisclosureTree('Details', details)
            layout.addWidget(details_wgt)

        if description:
            description_wgt = QLabel(description)
            description_wgt.setWordWrap(True)
            layout.addWidget(description_wgt)

        if main_widget:
            layout.addWidget(main_widget)

        layout.addStretch()

        preview_wgt.setLayout(layout)
        self.__main_layout.replaceWidget(self.__preview_wgt, preview_wgt)
        self.__preview_wgt.deleteLater()
        self.__preview_wgt = preview_wgt


class CourseChooser(AbstractCoExChooser):
    """
    The course chooser.
    - The browser part is made of a browse-button to browse courses
      files and a QListWidget displaying recent courses.
    - The preview area has no main_widget.
    """

    course_selected = Signal(Course, str, bool)

    def __init__(self):
        """
        See AbstractCoExChooser.__init__ docstring. Here, the browser
        layout is made of a browse-button to browse courses files
        and a QListWidget displayling recent courses.
        """

        self.__browse_btn = QPushButton(_('Browse files for course'))
        self.__previous_courses_wgt = RecentCoursesLW()

        self.__browse_btn.clicked.connect(self.__browse_courses)
        self.__previous_courses_wgt.itemClicked.connect(
                partial(self.__recent_course_clicked, goto_exercise=False))
        self.__previous_courses_wgt.itemDoubleClicked.connect(
                partial(self.__recent_course_clicked, goto_exercise=True))

        self.__browse_btn.setAutoDefault(False)

        browser_lyt = QVBoxLayout()
        browser_lyt.addWidget(self.__browse_btn)
        browser_lyt.addWidget(self.__previous_courses_wgt)

        super().__init__(browser_lyt)

    def set_preview(self):
        """
        Set course preview. See AbstractCoExChooser.set_preview
        docstring. Here, there is no main_widget. Course metadata are
        displayed in the disclosure triangle by passing them as details
        in super().set_preview.

        :param Course: Course to be previewed.
        """

        # TODO: Add these properties to the course class?
        title       = self.__course.metadata.get('Title',       None)
        subtitle    = self.__course.metadata.get('Subtitle',    None)
        description = self.__course.metadata.get('Description', None)

        details = self.__course.metadata
        # Remove title, subtitle and description from details
        # TODO: Prevent user for using a 'Path' attribute (in the course
        # file) when writing a course.
        # TODO: Add course path.
        for key in ['Title', 'Subtitle', 'Description']:
            if key in details:
                details.pop(key)
        if not details:  # Set details to None if empty
            details = None

        super().set_preview(main_widget=None, title=title, subtitle=subtitle,
                            details=details, description=description)

        self.course_selected.emit(self.__course, self.__course_filetype,
                                  self.__goto_exercise)

    def __instanciate_course(self, course_path: Path):

        course_filetype = course_path.suffix
        if course_filetype == '.lean':
            course = Course.from_file(course_path)
        elif course_filetype == '.pkl':
            course = read_pkl_course(course_path)

        self.__course = course
        self.__course_filetype = course_filetype

    #########
    # Slots #
    #########
   
    @Slot()
    def __browse_courses(self):

        dialog = QFileDialog()
        dialog.setFileMode(QFileDialog.ExistingFile)
        dialog.setNameFilter('*.lean *.pkl')

        # TODO: Stop using exec_, not recommended by documentation
        if dialog.exec_():
            course_path = Path(dialog.selectedFiles()[0])
            self.__instanciate_course(course_path)

            title = self.__course.metadata.get('Title', 'no title')
            self.__previous_courses_wgt.add_browsed_course(
                    course_path, title)
            self.__goto_exercise = False
            self.set_preview()

    @Slot(RecentCoursesLWI, bool)
    def __recent_course_clicked(self, course_item: RecentCoursesLWI,
                                goto_exercise: bool):
        course_path = course_item.course_path
        self.__instanciate_course(course_path)
        self.__goto_exercise = goto_exercise
        self.set_preview()



class ExerciseChooser(AbstractCoExChooser):
    """
    The exercise chooser. This widget is activated / shown when a course
    has been chosen by the user.
    - The browser area is made of the course's StatementsTreeWidget
      displaying only the exercises (e.g. no theorems).
    - The preview area is more complex and depends on the course's
      filetype.
      - If the course was chosen from a .lean file, the preview is only
        made of the exercise's title, subtitle and description.
      - If the course was chosend from a .pkl file, exercise's title,
        subtitle and description are available, as well as its goal
        (target, math. objects and math. properties). This cannot be
        done (yet) if the file course is .lean because for displaying
        the goal, we would need to launch the lean server interface and
        we obviously do not want to do that for each exercise. Pickle
        files (see puthon modyle pickle) allow to store class instances
        and thus we can store the course if it has been pre-processed.
        Finally, this preview is either displayed as:
        - two lists for the math objects and properties and a line edit
          for the target;
        - or a single list with all these informations (this is called
          the text mode and it is toggle with a checkbox).
    """
    
    # This signal is emitted when an exercise is previewed. It is
    # received in StartExerciseDialog and the Start exercise button is
    # enabled and set to default.
    exercise_previewed = Signal()

    def __init__(self, course: Course, course_filetype: str):
        """
        See AbstractCoExChooser.__init__ docstring. Here, the browser
        layout is only made of the course's StatementsTreeWidget
        displaying only the exercises (e.g. no theorems). The course
        file type is stored as a class private attribute and will be
        used by set_preview to determine if an exercise is to be
        previewed with its goal or not (see self docstring).

        :param course: The course in which the user chooses an exercise.
        :param course_filetype: The course's file file-type ('.lean' or
            '.pkl'), see self docstring.
        """

        self.__course_filetype = course_filetype  # 'lean' or 'pkl'

        browser_layout = QVBoxLayout()
        exercises_tree = StatementsTreeWidget(course.exercises_list(),
                                              course.outline)
        exercises_tree.resizeColumnToContents(0)
        exercises_tree.itemClicked.connect(self.__emit_exercise_previewed)
        browser_layout.addWidget(exercises_tree)

        exercises_tree.itemClicked.connect(self.__call_set_preview)

        super().__init__(browser_layout)

    def set_preview(self, exercise: Exercise):
        """
        Set exercise preview. See AbstractCoExChooser.set_preview
        docstring. The exercise's title, subtitle and description are
        displayed; if a preview is available (i.e. when course's file
        file-type is '.pkl', see self doctring), it is displayed. This
        method manages these two possibilities with a big if / else
        condition.

        :param exercise: The exercise to be previewed.
        """

        main_widget = QWidget()
        widget_lyt = QVBoxLayout()
        widget_lyt.setContentsMargins(0, 0, 0, 0)
        self.__exercise = exercise

        with_preview = self.__course_filetype == '.pkl'

        if with_preview:

            proofstate = exercise.initial_proof_state
            goal = proofstate.goals[0]  # Only one goal (?)
            target = goal.target
            context = goal.tag_and_split_propositions_objects()
            objects = context[0]
            properties = context[1]

            # ───────────────── Friendly widget ──────────────── #

            propobj_lyt = QHBoxLayout()
            objects_wgt = MathObjectWidget(objects)
            properties_wgt = MathObjectWidget(properties)
            objects_lyt, properties_lyt = QVBoxLayout(), QVBoxLayout()
    
            objects_wgt.adjustSize()
            objects_wgt.setFont(QFont('Menlo'))
            properties_wgt.adjustSize()
            properties_wgt.setFont(QFont('Menlo'))

            objects_lyt.addWidget(QLabel(_('Objects:')))
            properties_lyt.addWidget(QLabel(_('Properties:')))
            objects_lyt.addWidget(objects_wgt)
            properties_lyt.addWidget(properties_wgt)
            propobj_lyt.addLayout(objects_lyt)
            propobj_lyt.addLayout(properties_lyt)

            target_wgt = QLineEdit()
            target_wgt.setText(target.math_type.to_display(format_="utf8",
                                                           is_math_type=True))
            target_wgt.setFont(QFont('Menlo'))

            self.__friendly_wgt = QWidget()
            friendly_wgt_lyt = QVBoxLayout()
            friendly_wgt_lyt.addLayout(propobj_lyt)
            friendly_wgt_lyt.addWidget(QLabel(_('Target:')))
            friendly_wgt_lyt.addWidget(target_wgt)
            self.__friendly_wgt.setLayout(friendly_wgt_lyt)

            # ─────────────────── Code widget ────────────────── #

            self.__code_wgt = QTextEdit()
            self.__code_wgt.setReadOnly(True)
            self.__code_wgt.setFont(QFont('Menlo'))
            if exercise.initial_proof_state:
                text = goal.goal_to_text()
                self.__code_wgt.setText(text)

            # ──────────────────── Checkbox ──────────────────── #

            self.__text_mode_checkbox = QCheckBox(_('Text mode'))
            self.__text_mode_checkbox.clicked.connect(self.toggle_text_mode)
            cb_lyt = QHBoxLayout()
            cb_lyt.addStretch()
            cb_lyt.addWidget(self.__text_mode_checkbox)

            # ──────────────── Contents margins ──────────────── #

            for lyt in [widget_lyt, friendly_wgt_lyt]:
                # Somehow this works…
                lyt.setContentsMargins(0, 0, 0, 0)

            # ──────────────── Organize widgets ──────────────── #

            self.__text_mode_checkbox.setChecked(False)
            self.__friendly_wgt.show()
            self.__code_wgt.hide()

            widget_lyt.addWidget(self.__friendly_wgt)
            widget_lyt.addWidget(self.__code_wgt)
            widget_lyt.addLayout(cb_lyt)
        else:

            widget_lbl = QLabel(_('Goal preview only available when course ' \
                                  'file extension is .pkl.'))
            widget_lbl.setStyleSheet('color: gray;')

            widget_lyt.addWidget(widget_lbl)

        main_widget.setLayout(widget_lyt)

        # ───────────────────── Others ───────────────────── #

        # TODO: Add subtitle, task…
        title = exercise.pretty_name
        description = exercise.description

        super().set_preview(main_widget=main_widget, title=title,
                description=description)

    ##############
    # Properties #
    ##############

    @property
    def course_filetype(self) -> str:
        """
        Return self.__course_filetype.
        """

        return self.__course_filetype
    
    @property
    def exercise(self) -> Optional[Exercise]:
        """
        Return self.__exercise if it exists, None otherwise.
        """

        if self.__exercise:
            return self.__exercise
        else:
            return None

    #########
    # Slots #
    #########

    @Slot(StatementsTreeWidgetItem)
    def __call_set_preview(self, item: StatementsTreeWidgetItem):
        """
        When the user selects an exercise in the course's exercises
        tree, the signal itemClicked is emitted and this slot is called.
        One cannot directly call set_preview because at first we must be
        sure that the clicked item was an exercise item and not a nod
        (e.g. a course section).

        :param item: The clicked item (exercise item or nod item) in the
            course's exercises tree.
        """

        if isinstance(item, StatementsTreeWidgetItem):
            exercise = item.statement
            self.set_preview(exercise)

    @Slot(QTreeWidgetItem)
    def __emit_exercise_previewed(self, item):
        """
        When the user selects an exercise in the course's exercises
        tree, the signal itemClicked is emitted and this slot is called.
        If the clicked item is an exercise item (and not a node, e.g. a
        course section), the signal self.exercise_previewed is emitted.
        The aim of this signal is to tell the class StartExerciseDialog
        when to enable its Start exercise button.

        :param item: The clicked item (exercise item or nod item) in the
            course's exercises tree.
        """

        if isinstance(item, StatementsTreeWidgetItem):
            self.exercise_previewed.emit()

    @Slot()
    def toggle_text_mode(self):
        """
        Toggle the text mode for the previewed goal (see self docstring). 
        """

        if self.__text_mode_checkbox.isChecked():
            self.__friendly_wgt.hide()
            self.__code_wgt.show()
        else:
            self.__friendly_wgt.show()
            self.__code_wgt.hide()


class StartExerciseDialog(QDialog):
    """
    The course and exercise chooser (inherits QDialog). This is the
    first widget when launching d∃∀duction as it is the one which
    allows the user to:
    1. choose a course (from a file or from recent courses);
    2. browse / preview the exercises for the chosen course;
    3. start the chosen exercise (launchs the ExerciseMainWindow).

    StartExerciseDialog is divided in two main sub-widgets (presented in
    a QTabWidget): the course chooser (self.__course_chooser) and the
    exercise chooser (self.__exercise_chooser). At first, only the
    course chooser is enabled. When the user selects a course (either by
    browsing files or clicking on the recent courses list), all its
    exercises.
    """

    exercise_choosen = Signal(Exercise)

    def __init__(self):

        super().__init__()

        self.setWindowTitle(_('Choose course and exercise — d∃∀duction'))
        self.setMinimumWidth(450)
        self.setMinimumHeight(550)

        self.__course_chooser = CourseChooser()
        self.__exercise_chooser = QWidget()

        self.__course_chooser.course_selected.connect(self.__preview_exercises)

        # ───────────────────── Buttons ──────────────────── #

        self.__quit_btn = QPushButton(_('Quit'))
        self.__start_ex_btn = QPushButton(_('Start exercise'))

        self.__quit_btn.setEnabled(False)
        self.__start_ex_btn.setEnabled(False)

        self.__start_ex_btn.clicked.connect(self.__start_exercise)

        # ───────────────────── Layouts ──────────────────── #

        self.__coex_tabwidget = QTabWidget()
        self.__coex_tabwidget.addTab(self.__course_chooser, _('Course'))
        self.__coex_tabwidget.addTab(self.__exercise_chooser, _('Exercise'))

        buttons_lyt = QHBoxLayout()
        buttons_lyt.addStretch()
        buttons_lyt.addWidget(self.__quit_btn)
        buttons_lyt.addWidget(self.__start_ex_btn)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.__coex_tabwidget)
        main_layout.addLayout(buttons_lyt)

        self.setLayout(main_layout)

        # ───────────────────── Others ───────────────────── #

        self.__coex_tabwidget.setTabEnabled(1, False)

    def __preview_exercises(self, course: Course, course_filetype: Path,
                     goto_exercise: bool):

        self.__start_ex_btn.setEnabled(False)

        self.__coex_tabwidget.removeTab(1)
        self.__coex_tabwidget.setTabEnabled(1, True)
        self.__exercise_chooser = ExerciseChooser(course, course_filetype)
        self.__coex_tabwidget.addTab(self.__exercise_chooser, _('Exercise'))
        if goto_exercise:
            self.__coex_tabwidget.setCurrentIndex(1)

        # This can't be done in __init__ because at first,
        # self.__exercise_chooser is an empty QWidget() and therefore it
        # has no signal exercise_previewed. So we must have
        # self.__exercise_chooser to be ExerciseChooser to connect.
        self.__exercise_chooser.exercise_previewed.connect(
                self.__enable_start_ex_btn)

    #########
    # Slots #
    #########

    @Slot()
    def __enable_start_ex_btn(self):
        
        self.__start_ex_btn.setEnabled(True)
        self.__start_ex_btn.setDefault(True)

    @Slot()
    def __start_exercise(self):

        exercise = self.__exercise_chooser.exercise

        # save course_path, title, and exercise number
        # in user_config's previous_courses_list
        course_type     = self.__exercise_chooser.course_filetype
        course          = exercise.course
        course_path     = course.course_path
        title           = course.title
        if exercise in course.statements:
            exercise_number = course.statements.index(exercise)
        else:
            exercise_number = -1
        add_to_recent_courses(course_path,
                              course_type,
                              title,
                              exercise_number)

        self.exercise_choosen.emit(exercise)
        self.accept()  # Fuck you and I'll see you tomorrow!


if __name__ == '__main__':
    app = QApplication()

    start_exercise_dialog = StartExerciseDialog()
    start_exercise_dialog.show()

    sys.exit(app.exec_())
