"""
#######################################################
# ServerInterface.py : High level interface to server #
#######################################################

Author(s):      - Frédéric Le Roux <frederic.le-roux@imj-prg.fr>
                - Florian Dupeyron <florian.dupeyron@mugcat.fr>

Maintainers(s): - Frédéric Le Roux <frederic.le-roux@imj-prg.fr>
                - Florian Dupeyron <florian.dupeyron@mugcat.fr>

Date: July 2020

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

import trio
import logging
from typing import Optional, Dict

# from deaduction.pylib.utils.nice_display_tree import nice_display_tree
from deaduction.pylib.coursedata.exercise_classes import Exercise, Statement
from deaduction.pylib.proof_state.proof_state import ProofState
from deaduction.pylib.lean.response import Message
from deaduction.pylib.editing import LeanFile
from deaduction.pylib.lean.request import SyncRequest
from deaduction.pylib.lean.server import LeanServer
from deaduction.pylib.lean.installation import LeanEnvironment
from deaduction.pylib.actions import CodeForLean, get_effective_code_numbers
from deaduction.pylib.coursedata import Course
from deaduction.pylib.proof_tree import LeanResponse


import deaduction.pylib.config.vars as cvars
import deaduction.pylib.config.site_installation as inst
import deaduction.pylib.server.exceptions as exceptions
from deaduction.pylib.server.high_level_request import (HighLevelServerRequest,
                                                        InitialProofStateRequest,
                                                        ProofStepRequest,
                                                        ExerciseRequest)

from PySide2.QtCore import Signal, QObject

############################################
# Lean magic messages
############################################
LEAN_UNRESOLVED_TEXT = "tactic failed, there are unsolved goals"
LEAN_NOGOALS_TEXT    = "tactic failed, there are no goals to be solved"
LEAN_USES_SORRY      = " uses sorry"

global _


#####################
# ServerQueue class #
#####################
class ServerQueue(list):
    """
    This class stores a list of pending task for Lean server, and launches the
    first task in the list when the previous task is done.
    The "next_task" method is also responsible for the timeout: if the task
    is not done within TIMEOUT, then the request is sent another time with
    doubled timeout, and again until NB_TRIALS is reached.
    A cancellation method can be applied when a task is cancelled.
    """

    TIMEOUT = 10  # 20 FIXME
    STARTING_TIMEOUT = 20  # 40
    NB_TRIALS = 2  # 3 FIXME

    def __init__(self, nursery, timeout_signal):
        super().__init__()
        self.log = logging.getLogger("ServerQueue")

        # Initial parameters
        self.nursery                               = nursery
        self.timeout_signal                        = timeout_signal

        # Tags
        self.started = False
        self.is_busy = False

        # Cancel scope
        self.cancel_scope: Optional[trio.CancelScope] = None
        self.actual_timeout = self.TIMEOUT

        # Trio Event, initialized when a new queue starts,
        # and set when it ends.
        self.queue_ended            = None

    def add_task(self, fct, *args, cancel_fct=None, on_top=False):
        """
        Add a task to the queue. The task may be added at the end of the
        queue (default), or on top. If queue is not busy, that is, no task
        is currently running, then call next_task so that the added task
        starts immediately.
        """
        if on_top:
            self.append((fct, cancel_fct, args))
            self.log.debug(f"Adding task on top")
        else:
            self.log.debug(f"Adding task")
            self.insert(0, (fct, cancel_fct, args))
        if not self.is_busy:  # Execute task immediately
            self.is_busy = True
            self.queue_ended = trio.Event()
            self.next_task()

    def next_task(self):
        """
        Start first task of the queue, if any.
        """
        if len(self) > 0:
            # Launch first task
            fct, cancel_fct, args = self.pop()
            self.log.debug(f"Launching task")  # : {args}")
            # continue_ = input("Launching task?")  # FIXME: debugging
            self.nursery.start_soon(self.task_with_timeout, fct, cancel_fct,
                                    args)
        else:
            self.is_busy = False
            self.queue_ended.set()
            self.log.debug(f"No more tasks")

    async def process_task(self, fct: callable, *args, timeout=True):
        """
        Wait for the queue to end, and then process fct.
        This allows to await for the end of the task, which is not possible
        if the task is put into the queue.
        This method is deprecated, all tasks should go through add_task().
        """

        if self.queue_ended is not None:
            await self.queue_ended.wait()
        if timeout:
            await self.task_with_timeout(fct, args)
        else:
            await fct(*args)

    async def task_with_timeout(self, fct: callable, cancel_fct, args: tuple):
        """
        Execute function fct with timeout TIMEOUT, and number of trials
        NB_TRIALS.

        The tuple args will be unpacked and used as arguments for fct.

        When execution is complete, the next task in ServerQueue is launched.

        If task is canceled, cancel_fct is called.
        """
        nb = 0
        if not self.started:
            # Set timeout at the very first task
            self.actual_timeout = self.STARTING_TIMEOUT
            self.started = True
        else:
            self.actual_timeout = self.TIMEOUT
        while nb < self.NB_TRIALS:
            nb += 1
            try:
                with trio.move_on_after(self.actual_timeout) \
                        as self.cancel_scope:
                    ################
                    # Process task #
                    await fct(*args)
                    ################
                if self.cancel_scope.cancelled_caught:
                    self.log.warning(f"No answer within "
                                     f"{self.actual_timeout}s (trial {nb})")
                    self.actual_timeout = 2 * self.actual_timeout
                    if nb == self.NB_TRIALS:  # Task definitively  cancelled!
                        # Emit lean_response signal with timeout error
                        lean_response = LeanResponse(error_type=3)
                        self.timeout_signal.emit(lean_response)
                    else:  # Task will be tried again
                        if cancel_fct:
                            cancel_fct()
                else:
                    break
            except TypeError as e:
                self.log.debug("TypeError while cancelling trio")
                self.log.debug(e)
                self.actual_timeout = 2 * self.actual_timeout
                if nb == self.NB_TRIALS:  # Task definitively  cancelled!
                    # Emit lean_response signal with timeout error
                    # FIXME:
                    lean_response = LeanResponse(error_type=3)
                    self.timeout_signal.emit(lean_response)
                else:  # Task will be tried again
                    if cancel_fct:
                        cancel_fct()

        # Launch next task when done!
        self.next_task()

    def cancel_current_task(self):
        if self.cancel_scope:
            self.cancel_scope.cancel()


#########################
# ServerInterface class #
#########################

class ServerInterface(QObject):
    """
    High level interface to lean server, as handled by the low level
    module lean. Two kind of requests are considered:

        - processing one exercise: the content of self.lean_file is sent to
        Lean, and the data for computing the new proof state is received.

        - processing the initial proof states of a list of statements,
        as stored in self.__course_data.

    In the first case, self.__course_data is assumed to be None.

    The ServerInterface may process only one task at a time.
    The queue is handled by a ServerQueue instance.
    """
    ############################################
    # Qt Signals
    ############################################
    proof_state_change = Signal(ProofState)  # FIXME: suppress
    update_started              = Signal()  # Unused
    update_ended                = Signal()  # Unused

    proof_no_goals              = Signal()  # FIXME: suppress
    failed_request_errors       = Signal()  # FIXME: suppress?

    # Signal sending info from Lean
    lean_response = Signal(LeanResponse)

    # For functionality using ipf (tooltips, implicit definitions):
    initial_proof_state_set     = Signal()
    # To store effective code, so that history_replace is called:
    effective_code_received     = Signal(CodeForLean)
    # To update the Lean editor console:
    lean_file_changed           = Signal(str)
    # To launch the Coordinator.server_task:
    exercise_set                = Signal()  # Fixme: not used!

    MAX_CAPACITY = 10  # Max number of statements sent in one request

    ############################################
    # Init, and state control
    ############################################

    def __init__(self, nursery):
        super().__init__()
        self.log = logging.getLogger("ServerInterface")

        # Lean environment
        self.lean_env: LeanEnvironment = LeanEnvironment(inst)

        # Lean attributes
        self.lean_server: LeanServer   = LeanServer(nursery, self.lean_env)
        self.nursery: trio.Nursery     = nursery
        self.request_seq_num           = -1
        self.pending_requests: Dict[int, HighLevelServerRequest] = {}

        # Set server callbacks
        self.lean_server.on_message_callback = self.__on_lean_message
        self.lean_server.running_monitor.on_state_change_callback = \
            self.__on_lean_state_change

        # Current exercise (when processing one exercise)
        self.lean_file: Optional[LeanFile] = None
        self.__exercise_current            = None
        self.__use_fast_method_for_lean_server = False
        self.__previous_proof_state = None

        # Current course (when processing a bunch of statements for initial
        # proof state)
        # self.__course_data             = None  # FIXME: obsolete

        # Events
        self.lean_server_running       = trio.Event()
        self.file_invalidated          = trio.Event()
        # self.__proof_state_valid       = trio.Event()  # FIXME: useless

        # proof_receive_done is set when enough information have been
        # received, i.e. (for exercise processing) either we have context and
        # target and all effective codes, OR an error message
        # self.proof_receive_done      = trio.Event()

        # FIXME: obsolete (cf HighLevelServerRequest)
        # self.__tmp_hypo_analysis       = []
        # self.__tmp_targets_analysis    = ""

        # When some CodeForLean is sent to the __update method, it will be
        # duplicated and stored in __tmp_effective_code. This attribute will
        # be progressively modified into an effective code which is devoid
        # of or_else combinator, according to the "EFFECTIVE CODE" messages
        # sent by Lean.
        # self.__tmp_effective_code      = CodeForLean.empty_code()
        self.is_running                = False
        # self.last_content              = ""  # Content of last LeanFile sent.
        # self.__file_content_from_state_and_tactic = None
        # Errors memory channels
        # FIXME: obsolete?
        self.error_send, self.error_recv = \
            trio.open_memory_channel(max_buffer_size=1024)

        # ServerQueue
        self.server_queue = ServerQueue(nursery=nursery,
                                        timeout_signal=self.lean_response)

    def test(self, b: bool) -> bool:
        """
        Method to bypass tests when the fast method is used.
        """
        return b or self.use_fast_method_for_lean_server

    # def __analysis_code(self) -> str:
    #     nb = self.request_seq_num + 1
    #     code = f"targets_analysis {nb},\n" \
    #            f"all_goals {{hypo_analysis {nb}}},\n"
    #     return  code

    # def __begin_end_code(self, code_string: str) -> str:
    #     code_string = code_string.strip()
    #     if not code_string.endswith(","):
    #         code_string += ","
    #
    #     if not code_string.endswith("\n"):
    #         code_string += "\n"
    #
    #     code = "begin\n" \
    #            + code_string \
    #            + self.__analysis_code()\
    #            + "end\n"
    #     return code

    def __expected_nb_goals(self):
        """
        Return the number of goals, estimated by the number of ocurence of
        '¿¿¿' in self.__tmp_targets_analysis.
        NB: -1 indicates no information, whereas 0 indicates no more goals.
        FIXME: obsolete
        """
        if not self.__tmp_targets_analysis:
            return -1
        else:
            return self.__tmp_targets_analysis.count('¿¿¿')

    @property
    def use_fast_method_for_lean_server(self):
        return self.__use_fast_method_for_lean_server

    # @property
    # def lean_file_contents(self):
    #     if self.use_fast_method_for_lean_server:
    #         return self.__file_content_from_state_and_tactic
    #     elif self.__course_data:
    #         return self.__course_data.file_contents
    #     elif self.lean_file:
    #         return self.lean_file.contents

    async def start(self):
        """
        Asynchronously start the Lean server.
        """
        await self.lean_server.start()
        self.file_invalidated.set()  # No file at starting
        self.lean_server_running.set()

    def stop(self):
        """
        Stop the Lean server.
        """
        # global SERVER_QUEUE
        # SERVER_QUEUE.started = False
        self.server_queue.started = False
        self.lean_server_running = trio.Event()
        self.lean_server.stop()

    def __add_time_to_cancel_scope(self):
        """
        Reset the deadline of the cancel_scope.
        """
        if self.server_queue.cancel_scope:
            time = self.server_queue.actual_timeout
            self.server_queue.cancel_scope.deadline = (trio.current_time()
                                                       + time)
            # deadline = (self.server_queue.cancel_scope.deadline
            #             - trio.current_time())
            # self.log.debug(f"Cancel scope deadline: {deadline}")

    ############################################
    # Callbacks from lean server
    ############################################
    # def __check_receive_state(self):
    #     """
    #     Check if every awaited piece of information has been received:
    #     i.e. target and hypo analysis, and all effective codes to replace
    #     the or_else instructions. After the signal proof_receive_done is
    #     set, the __update method will stop listening to Lean, and start
    #     updating Proofstate.
    #         (for processing exercise only)
    #     """
    #     # FIXME: obsolete
    #     self.log.debug("Checking receive state: ")
    #     self.log.debug(f"{len(self.__tmp_hypo_analysis)}/{self.__expected_nb_goals()}")
    #     if self.__expected_nb_goals() == 0:  # No More Goals!
    #         # self.no_more_goals = True
    #         self.proof_receive_done.set()  # Done receiving
    #     elif (self.__tmp_targets_analysis
    #             and self.__tmp_hypo_analysis
    #             # Check every goal hypo_analysis have been received:
    #             and len(self.__tmp_hypo_analysis) ==
    #           self.__expected_nb_goals()):
    #         if not self.__tmp_effective_code.has_or_else():
    #             self.proof_receive_done.set()
    #         else:  # debug
    #             print("Code has or else:")
    #             print(self.__tmp_effective_code.to_code())

    def __check_request_complete(self, request_seq_num):
        request = self.pending_requests.get(request_seq_num)
        if request and request.is_complete():
            request.set_proof_received()
            self.pending_requests.pop(request_seq_num)

    def __on_lean_message(self, msg: Message):
        """
        Treatment of relevant Lean messages. Note that the text may contain
        several lines. Error messages are treated via the __filter_error
        method. Other relevant messages are
        - message providing the new context,
        - message providing the new target,
        - messages providing the successful effective codes that will be
        used to replace the "or else" sequences of instructions.
        After relevant messages, the __check_receive_state method is called
        to check if all awaited messages have been received.
            (for processing exercise only ; for initial proof states
            processing, this method just call the
            __on_lean_message_for_course method).
        """

        # TODO:
        #  treat effective code in Request class
        #  Check info is complete, send signals if this is so

        txt = msg.text
        # self.log.debug("Lean message: " + txt)

        self.__add_time_to_cancel_scope()

        if msg.seq_num in self.pending_requests:
            request = self.pending_requests[msg.seq_num]
        else:
            self.log.warning(f"Pending requests seq_num are {self.pending_requests.key()}: "
                             f"ignoring msg form seq_num {msg.seq_num}")
            return
        # TODO: adapt with request
        # TODO: handle error msgs

        # # Filter seq_num
        # if msg.seq_num is not None:
        #     req_seq_num = self.request_seq_num
        #     # self.log.debug(f"Received msg with seq_num {msg.seq_num}")
        #     if msg.seq_num != req_seq_num :
        #         self.log.warning(f"Request seq_num is {req_seq_num}: "
        #                          f"ignoring msg form seq_num {msg.seq_num}")
        #         return

        # if self.__course_data:
        #     self.__on_lean_message_for_course(msg)
        #     return

        line = msg.pos_line
        severity = msg.severity
        last_line_of_inner_content = self.lean_file.last_line_of_inner_content

        if severity == Message.Severity.error:
            self.log.error(f"Lean error at line {line}: {txt}")
            # FIXME: treat errors according to request
            self.__filter_error(msg, request)  # Record error ?

        elif severity == Message.Severity.warning:
            if not txt.endswith(LEAN_USES_SORRY):
                self.log.warning(f"Lean warning at line {line}: {txt}")

        elif txt.startswith("context #:"):
            request.store_hypo_analysis(txt, line)

        elif txt.startswith("targets #:"):
            request.store_targets_analysis(txt, line)

        # elif txt.startswith("context #:") \
        #         and self.test(line == last_line_of_inner_content + 2):
        #     self.log.info("Got new context")
        #     self.__tmp_hypo_analysis.append(txt)
        #     self.__check_receive_state()
        #
        # elif txt.startswith("targets #:") \
        #         and self.test(line == last_line_of_inner_content + 1)\
        #         and not self.__tmp_targets_analysis:
        #     self.log.info("Got new targets")
        #     self.__tmp_targets_analysis = txt
        #     self.__check_receive_state()

        # FIXME:
        elif txt.startswith("EFFECTIVE CODE"):
            if isinstance(request, ProofStepRequest):
                request.process_effective_code(msg)
            # and self.test(line == last_line_of_inner_content) \
            #     and self.__tmp_effective_code.has_or_else():
            # # txt may contain several lines
            # for txt_line in txt.splitlines():
            #     if not txt_line.startswith("EFFECTIVE CODE"):
            #         # Message could be "EFFECTIVE LEAN CODE"
            #         # TODO: treat these messages
            #         continue
            #     self.log.info(f"Got {txt_line}")
            #     node_nb, code_nb = get_effective_code_numbers(txt_line)
            #     # Modify __tmp_effective_code by selecting the effective
            #     #  or_else alternative according to codes
            #     self.__tmp_effective_code, found = \
            #         self.__tmp_effective_code.select_or_else(node_nb, code_nb)
            #     if found:
            #         self.log.debug("(selecting effective code)")
            #
            # # Test if there remain some or_else combinators
            # if not self.__tmp_effective_code.has_or_else():
            #     # Done with effective codes, history_replace will be called
            #     self.log.debug("No more effective code to receive")
            #     if hasattr(self.effective_code_received, 'emit'):
            #         self.effective_code_received.emit(self.__tmp_effective_code)
            #     self.__check_receive_state()

        self.__check_request_complete(msg.seq_num)

    def __on_lean_state_change(self, is_running: bool):
        self.__add_time_to_cancel_scope()

        if is_running != self.is_running:
            self.log.info(f"New lean state: {is_running}")
            self.is_running = is_running

    # def __check_receive_course_data(self, index):
    #     """
    #     Check if context and target has been received
    #     for the statement corresponding to index.
    #     If so,
    #         - set initial proof state for statement,
    #         - emi signal initial_proof_state_set,
    #         - check if all statements have been processed, and if so,
    #         emit signal proof_receive_done
    #     """
    #     hypo = self.__course_data.hypo_analysis[index]
    #     target = self.__course_data.targets_analysis[index]
    #     if hypo and target:
    #         statements = self.__course_data.statements
    #         st = statements[index]
    #         if not st.initial_proof_state:
    #             ps = ProofState.from_lean_data(hypo, target, to_prove=False)
    #             st.initial_proof_state = ps
    #             # Emit signal in case an exercise is waiting for its ips
    #             self.initial_proof_state_set.emit()
    #
    #         if None not in [st.initial_proof_state for st in
    #                         self.__course_data.statements]:
    #             self.log.debug("All proof states received")
    #             self.proof_receive_done.set()

    # def __on_lean_message_for_course(self, msg: Message):
    #     """
    #     Treatment of relevant Lean messages.
    #     """
    #
    #     txt = msg.text
    #     # self.log.debug("Lean message: " + txt)
    #     line = msg.pos_line
    #     severity = msg.severity
    #
    #     if severity == Message.Severity.error:
    #         self.log.error(f"Lean error at line {msg.pos_line}: {txt}")
    #         self.__filter_error(msg)  # Record error ?
    #
    #     elif severity == Message.Severity.warning:
    #         if not txt.endswith(LEAN_USES_SORRY):
    #             self.log.warning(f"Lean warning at line {msg.pos_line}: {txt}")
    #
    #     elif txt.startswith("context #"):
    #         if line in self.__course_data.statement_from_hypo_line:
    #             st = self.__course_data.statement_from_hypo_line[line]
    #             index = self.__course_data.statements.index(st)
    #             self.log.info(f"Got new context for statement {st.lean_name}, "
    #                           f"index = {index}")
    #             self.__course_data.hypo_analysis[index] = [txt]
    #             self.__check_receive_course_data(index)
    #         else:
    #             self.log.debug(f"(Context for statement line {line} "
    #                            f"received but not expected)")
    #     elif txt.startswith("targets #:"):
    #         if line in self.__course_data.statement_from_targets_line:
    #             st = self.__course_data.statement_from_targets_line[line]
    #             index = self.__course_data.statements.index(st)
    #             self.log.info(f"Got new targets for statement {st.lean_name}, "
    #                           f"index = {index}")
    #             self.__course_data.targets_analysis[index] = txt
    #             self.__check_receive_course_data(index)
    #
    #         else:
    #             self.log.debug(f"(Target for statement line {line} received "
    #                            f"but not expected)")

    ############################################
    # Message filtering
    ############################################

    def __filter_error(self, msg: Message, request):
        """
        Filter error messages from Lean,
        - according to position (i.e. ignore messages that do not correspond
         to the new part of the virtual file),
        - ignore "proof uses sorry" messages.
        """
        # FIXME: supprimer le canal d'erreur ??

        if request.request_type == 'ProofStep':
            if msg.text.startswith(LEAN_NOGOALS_TEXT):
                # todo: request complete
                pass
            elif msg.text.startswith(LEAN_UNRESOLVED_TEXT):
                pass
            else:
                # TODO: request complete, handle error
                self.error_send.send_nowait(msg)
                self.proof_receive_done.set()  # Done receiving

        # # Filter message text, record if not ignored message
        #
        # first_line = self.lean_file.first_line_of_last_change
        # last_line = self.lean_file.last_line_of_inner_content
        # # FIXME: this is obsolete:
        # if msg.text.startswith(LEAN_NOGOALS_TEXT) \
        #         and self.test(msg.pos_line == last_line + 2):
        #     # self.no_more_goals = True
        #     self.proof_receive_done.set()  # Done receiving
        #     # if hasattr(self.proof_no_goals, "emit"):
        #     #     self.proof_receive_done.set()  # Done receiving
        #     #     self.proof_no_goals.emit()
        # elif msg.text.startswith(LEAN_UNRESOLVED_TEXT):
        #     pass
        # # Ignore messages that do not concern current proof
        # elif self.lean_file and \
        #         not self.test(first_line <= msg.pos_line <= last_line):
        #     pass
        # else:
        #     self.error_send.send_nowait(msg)
        #     self.proof_receive_done.set()  # Done receiving

    ##########################################
    # Update proof state of current exercise #
    ##########################################
    def __add_pending_request(self, request: HighLevelServerRequest):
        self.request_seq_num += 1
        request.set_seq_num(self.request_seq_num)
        request.init_proof_received_event(trio.Event())
        self.pending_requests[self.request_seq_num] = request
        self.log.debug(f"Add request")
        nb = len(self.pending_requests)
        if nb > 1:
            self.log.warning(f"{nb} requests pending")

    async def __get_response_from_request(self, request=None):
        """
        Call Lean server to update the proof_state.
            (for processing exercise only)
        """

        # lean_code = request.lean_code

        # first_line_of_change = self.lean_file.first_line_of_last_change
        # self.log.debug(f"Updating, "
        #                f"checking errors from line "
        #                f"{first_line_of_change}, and context at "
        #                f"line {self.lean_file.last_line_of_inner_content + 1}")

        # if lean_code:
        #     self.__tmp_effective_code = deepcopy(lean_code)
        # else:
        #     self.__tmp_effective_code = CodeForLean.empty_code()
        # Update the lean text editor:
        # TODO: move to request definition?
        self.lean_file_changed.emit(self.lean_file.inner_contents)

        if hasattr(self.update_started, "emit"):
            self.update_started.emit()

        # Invalidate events
        self.file_invalidated = trio.Event()
        # self.proof_receive_done = trio.Event()  # FIXME: one by request
        # self.__course_data = None
        # self.no_more_goals = False
        # FIXME: obsolete:
        # self.__tmp_hypo_analysis = []
        # self.__tmp_targets_analysis = ""

        resp = None

        ###################
        # Sending request #
        ###################
        # Loop in case Lean's answer is None, which happens...
        while not resp:
            # self.request_seq_num += 1
            request.set_seq_num(self.request_seq_num)
            self.log.debug(f"Request seq_num: {self.request_seq_num}")
            print(request.file_contents())
            req = SyncRequest(file_name="deaduction_lean",
                              content=request.file_contents())
            self.log.debug(f"req seq_num: {req.seq_num}")
            resp = await self.lean_server.send(req)

        if resp.message == "file_unchanged":
            self.log.warning("File unchanged!")

        if resp.message in ("file invalidated", "file_unchanged"):
            # TODO: handle file_unchanged?? Should never happen!
            self.log.debug("Response seq_num: "+str(resp.seq_num))
            self.file_invalidated.set()

            #########################################
            # Waiting for all pieces of information #
            #########################################
            await request.proof_received_event.wait()
            # ------ Up to here task may be cancelled by timeout ------ #
            self.server_queue.cancel_scope.shield = True

            self.log.debug(_("Proof State received"))

            # Timeout TODO: move this at the end
            # FIXME: useful??
            with trio.move_on_after(1):
                await self.lean_server.running_monitor.wait_ready()

            self.log.debug(_("After request"))

            if hasattr(self.update_ended, "emit"):
                self.update_ended.emit()

        else:
            self.log.warning(f"Unexpected Lean response: {resp.message}")

        # Emit exceptions ?
        error_list = []
        try:
            while True:
                error_list.append(self.error_recv.receive_nowait())
        except trio.WouldBlock:
            pass

        error_type = 1 if error_list else 0
        # effective_code = (None if self.__tmp_effective_code.is_empty()
        #                   else self.__tmp_effective_code)
        # analysis = (self.__tmp_hypo_analysis, self.__tmp_targets_analysis)
        analyses = (request.hypo_analyses, request.targets_analyses)

        if isinstance(request, ProofStepRequest):
            if request.effective_code_received:
                self.effective_code_received.emit(request.effective_code)
            lean_response = LeanResponse(proof_step=request.proof_step,
                                         analyses=analyses,
                                         error_type=error_type,
                                         error_list=error_list)
            self.lean_response.emit(lean_response)

        # self.__previous_proof_state = None

    ###########################
    # Exercise initialisation #
    ###########################
    # def __file_from_exercise(self, statement):
    #     """
    #     Create a virtual file from exercise. Concretely, this consists in
    #     - separating the part of the file before the proof into a preamble,
    #     - add the tactics "hypo_analysis, targets_analysis"
    #     - remove all statements after the proof.
    #
    #     If exercise.negate_statement, then the statement is replaced by its
    #     negation.
    #
    #     Then a virtual file is instantiated.
    #
    #     :param statement: Statement (most of the time an Exercise)
    #     """
    #     file_content = statement.course.file_content
    #     lines        = file_content.splitlines()
    #     begin_line   = statement.lean_begin_line_number
    #
    #     # Construct short end of file by closing all open namespaces
    #     end_of_file = "end\n"
    #     end_of_file += statement.close_namespace_str()
    #     # namespaces = statement.ugly_hierarchy()
    #     # while namespaces:
    #     #     namespace = namespaces.pop()
    #     #     end_of_file += "end " + namespace + "\n"
    #     end_of_file += "end course"
    #
    #     # Replace statement by negation if required
    #     if (hasattr(statement, 'negate_statement')
    #             and statement.negate_statement):
    #         # lean_core_statement = statement.lean_core_statement
    #         # negation = " not( " + lean_core_statement + " )"
    #         lemma_line = statement.lean_line - 1
    #         # rough_core_content = "\n".join(lines[lemma_line:begin_line]) + "\n"
    #         # new_core_content = rough_core_content.replace(
    #         #                         lean_core_statement, negation)
    #         negated_goal = statement.negated_goal()
    #         new_core_content = negated_goal.to_lean_example()
    #         virtual_file_preamble = "\n".join(lines[:lemma_line]) \
    #                                 + "\n" + new_core_content \
    #                                 + "begin\n"
    #         # Debug
    #         # core = lines[lemma_line] + "\n" + new_core_content + "begin\n"
    #         # print(core)
    #
    #     else:
    #         # Construct virtual file
    #         virtual_file_preamble = "\n".join(lines[:begin_line]) + "\n"
    #
    #     # virtual_file_afterword = "hypo_analysis,\n" \
    #     #                          "targets_analysis,\n" \
    #     #                          + end_of_file
    #
    #     virtual_file_afterword = self.__analysis_code() + end_of_file
    #
    #     virtual_file = LeanFile(file_name=statement.lean_name,
    #                             preamble=virtual_file_preamble,
    #                             afterword=virtual_file_afterword)
    #     # Ensure file is different at each new request:
    #     # (avoid "file unchanged" response)
    #     virtual_file.add_seq_num(self.request_seq_num)
    #
    #     virtual_file.cursor_move_to(0)
    #     virtual_file.cursor_save()
    #     return virtual_file

    async def set_exercise(self, proof_step, exercise: Exercise):
        """
        Initialise the virtual_file from exercise.

        :param exercise:        The exercise to be set
        :return:                virtual_file
        """

        self.log.info(f"Set exercise to: "
                      f"{exercise.lean_name} -> {exercise.pretty_name}")
        self.__exercise_current = exercise

        # self.lean_file = self.__file_from_exercise(exercise)
        # self.__use_fast_method_for_lean_server = False
        # # FIXME: obsolete:
        # self.__previous_proof_state = None

        request = ExerciseRequest(proof_step=proof_step,
                                  exercise=exercise)
        self.__add_pending_request(request)
        self.lean_file = request.virtual_file

        await self.__get_response_from_request(request=request)
        # if hasattr(self, "exercise_set"):
        self.exercise_set.emit()

    ###########
    # History #
    ###########
    # FIXME: obsolete?
    # async def history_undo(self):
    #     """
    #     Go one step forward in history in the lean_file.
    #     """
    #     self.lean_file.undo()
    #     await self.__update()
    #
    # async def history_redo(self):
    #     """
    #     Go one step backward in history in the lean_file.
    #     """
    #     self.lean_file.redo()
    #     await self.__update()
    #
    # async def history_rewind(self):
    #     """
    #     Go to beginning of history in the lean_file.
    #     """
    #     self.lean_file.rewind()
    #     await self.__update()
    #
    # async def history_goto(self, history_nb):
    #     """
    #     Move to a psecific place in the history of the Lean file.
    #     """
    #     self.lean_file.goto(history_nb)
    #     await self.__update()
    #
    # async def history_delete(self):
    #     """
    #     Delete last step of history in the lean_file. Called when FailedRequest
    #     Error.
    #     """
    #     self.lean_file.delete()
    #     await self.__update()

    def history_replace(self, code: CodeForLean):
        """
        Replace last entry in the lean_file by code without calling Lean.
        WARNING: code should be an effective code which is equivalent,
        from the Lean viewpoint, to last code entry.
        NB: this method does NOT call self.__update().

        :param code: CodeForLean
        """
        if code:
            # Formatting. We do NOT want the "no_meta_vars" tactic!
            code_string = code.to_code(exclude_no_meta_vars=True)
            code_string = code_string.strip()
            if not code_string.endswith(","):
                code_string += ","
            if not code_string.endswith("\n"):
                code_string += "\n"

            lean_file = self.lean_file
            label = lean_file.history[lean_file.target_idx].label
            self.lean_file.undo()
            self.lean_file.insert(label=label, add_txt=code_string)
            # Update the lean text editor:
            self.lean_file_changed.emit(self.lean_file.inner_contents)

    ###################
    # Code management #
    ###################

    # def __lean_import_course_preamble(self) -> str:
    #     file_name = self.__exercise_current.course.course_file_name
    #     return f"import {file_name}\n"

    # def set_file_content_from_state_and_tactic(self, goal, code_string):
    #     """
    #     Set the file content from goal and code. e.g.
    #     import ...
    #     namespace ...
    #     open ...
    #     example (X: Type) : true :=
    #     begin
    #         <some code>
    #     end
    #     """
    #     exercise = self.__exercise_current
    #     # Rqst seq_num prevents from unchanged file
    #     file_content = f"-- Seq num {self.request_seq_num}\n" \
    #         + self.__lean_import_course_preamble() \
    #         + "section course\n" \
    #         + exercise.open_namespace_str() \
    #         + exercise.open_read_only_namespace_str() \
    #         + goal.to_lean_example() \
    #         + self.__begin_end_code(code_string) \
    #         + exercise.close_namespace_str() \
    #         + "end course\n"
    #     self.__file_content_from_state_and_tactic = file_content

    async def code_insert(self, label: str,
                          proof_step,
                          # lean_code: CodeForLean,
                          # previous_proof_state: ProofState,
                          use_fast_method: bool = True):
        """
        Inserts code in the Lean virtual file.
        """

        # lean_code = proof_step.lean_code
        # previous_proof_state = proof_step.proof_state
        request = ProofStepRequest(proof_step=proof_step,
                                   exercise=self.__exercise_current)
        self.__add_pending_request(request)

        # self.__use_fast_method_for_lean_server = use_fast_method
        # self.__previous_proof_state = (previous_proof_state if use_fast_method
        #                                else None)

        # (1) Lean code processing
        # Add "no meta vars" + "effective code nb"
        # and keep track of node_counters
        # lean_code, code_string = lean_code.to_decorated_code()
        # NB: lean_code now contains node_counters (and no_meta_vars)
        # code_string = code_string.strip()
        # if not code_string.endswith(","):
        #     code_string += ","
        #
        # if not code_string.endswith("\n"):
        #     code_string += "\n"
        #
        # self.log.info("CodeForLean: " + lean_code.to_code())
        # self.log.info(lean_code)
        # self.log.info("Code sent to Lean: " + code_string)
        # print("Code sent to Lean:")
        # nice_display_tree(code_string)

        # self.log.debug("Code sent:" + code_string)

        # (2) Set file content for fast method
        # if use_fast_method:
        #     goal = previous_proof_state.goals[0]
        #     self.set_file_content_from_state_and_tactic(goal, code_string)
        #     # self.log.info('Using fast method for Lean server')
        #     print(self.lean_file_contents)

        # (3) Update LeanFile
        self.lean_file.insert(label=label, add_txt=request.code_string)
        # Ensure content is not identical to last sent (void "no change")
        # content = self.lean_file.inner_contents  # Without preamble
        # FIXME: obsolete (now seq_num is always somewhere in the file)
        # if content == self.last_content:
        #     self.lean_file.add_seq_num(self.request_seq_num)
        # self.last_content = self.lean_file.inner_contents

        # (4) Send Lean request
        await self.__get_response_from_request(request=request)

    async def code_set(self, label: str, code: str):
        """
        Sets the code for the current exercise. This is supposed to be called
        when user sets code using the Lean console, but this functionality
        is not activated right now because it f... up the history.
        """
        # FIXME: adapt HighLevelLeanRequest to this case

        self.__use_fast_method_for_lean_server = False
        self.__previous_proof_state = None

        self.log.info("Code sent to Lean: " + code)
        if not code.endswith(","):
            code += ","

        if not code.endswith("\n"):
            code += "\n"

        self.lean_file.state_add(label, code)

        # request = ...
        await self.__get_response_from_request()

    #####################################################################
    # Methods for getting initial proof states of a bunch of statements #
    #####################################################################

    async def __get_initial_proof_states(self, course, statements):
        """
        Call Lean server to get the initial proof states of statements
        as stored in course_data.
        """

        # FIXME: use self.get_response...
        self.log.info('Getting initial proof states')
        # file_name = str(self.__course_data.course.relative_course_path)
        # self.__course_data = course_data  # FIXME
        # self.__use_fast_method_for_lean_server = False
        # self.__previous_proof_state = None

        # Add request
        # self.request_seq_num += 1
        request = InitialProofStateRequest(course=course,
                                           statements=statements)
        self.__add_pending_request(request)

        # TODO: try to merge this with __get_response_from_request()
        # Invalidate events
        self.file_invalidated           = trio.Event()
        # self.proof_receive_done       = trio.Event()

        # Ask Lean server and wait for answer
        self.log.debug(f"Request seq_num: {self.request_seq_num}")
        self.request_seq_num += 1
        request.set_seq_num(self.request_seq_num)
        req = SyncRequest(file_name="deaduction_lean",
                          content=request.file_contents())
        resp = await self.lean_server.send(req)
        print(f"--> {resp.message}")
        if resp.message == "file invalidated":
            print("file invalidated)")
            self.file_invalidated.set()

            # ───────── Waiting for all pieces of information ──────── #
            await request.proof_received_event.wait()
            print("(proof received)")
            # self.log.debug(_("All proof states received"))
            self.initial_proof_state_set.emit()
            if hasattr(self.update_ended, "emit"):
                self.update_ended.emit()

    def set_statements(self, course: Course, statements: [] = None,
                       on_top=False):
        """
        This method takes a list of statements and split it into lists of
        length ≤ self.MAX_CAPACITY before calling
        self.get_initial_proof_states. This is a recursive method.
        """

        statements = list(statements)  # Just in case statements is an iterator
        if statements is None:
            statements = course.statements

        if len(statements) <= self.MAX_CAPACITY:
            self.log.debug(f"Set {len(statements)} statement(s)")
            self.server_queue.add_task(self.__get_initial_proof_states,
                                       course, statements,
                                       on_top=on_top)
        else:
            self.log.debug(f"{len(statements)} statements to process...")
            # Split statements
            self.set_statements(course, statements[:self.MAX_CAPACITY],
                                on_top=on_top)
            self.set_statements(course, statements[self.MAX_CAPACITY:],
                                on_top=on_top)

