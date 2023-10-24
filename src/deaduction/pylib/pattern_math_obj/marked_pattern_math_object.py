"""
marked_pattern_math_objects.py : provide the MarkedPatternMathObject class.

The trickiest thing here is an insertion algorithm in an expression tree.
In such a tree, every node has an ordered list of left and right children.
Here this list is induced by the latex_shape, with a choice of a main symbol.

Two cases:
(1) insertion at a non assigned metavar.
(2) insertion after a assigned metavar.
 In any case, after a successful insertion, the marked node should
    - move to the first non assigned metavar of the inserted object,
    if any,
    - otherwise, stay in place. The cursor will indicate the place just after
    the (main symbol of) the inserted object.

Case (1) is easy: just check that types match.

Case (2) splits into the following sub-cases. Let (MO) denotes the assigned
object after which the insertion takes place.

    (2a) The new node (NN) has a metavar left of its main symbol. Let (MVL)
    be the first metavar left of (NN). If (MVL) matches (MO), then (NN) be
    inserted at (MO)'s place, with (MO) becoming (MVL)'s assigned object.
    Precedence rule, involving MO's father, should also be checked here (?).
    If the insertion fails, then it should be tried on the next place in the
    tree path from the mvar to the next node in the infix order (?).

    (2b) If (NN) has no left child, or if (2a) fails, then automatic insertion
    are tried: operators in the automatic list are tried one by one, until one
    matches (MO) as its left child and (NN) as its right child.
    Automatic operators includes
    f, x --> f(x)
    f, A --> f(A)
    f, g --> f circ g ?
    1, 2 --> INT (1, 2)
    ...

    (2c) If (2a) and (2b) fails, then the symmetric right insertion trials
    should be performed.

Then precedence rules must be checked: if the edge between (NN) and its
parent do not bind dy the rule, then a precedence move must be performed.
This operation is repeated until the precedence rules are satisfied.


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

from copy import copy
import logging

if __name__ == '__main__':
    from deaduction.dui.__main__ import language_check
    language_check()

from typing import Optional

from deaduction.pylib.mathobj import MathObject, BoundVar
from deaduction.pylib.pattern_math_obj import PatternMathObject, MetaVar
from deaduction.pylib.math_display import MathDisplay
# from deaduction.pylib.math_display.pattern_init import all_app_patterns
from deaduction.pylib.math_display import PatternMathDisplay
# from .calculator_pattern_strings import automatic_matching_patterns

log = logging.getLogger(__name__)


def merge_nbs(nb1: str, nb2: str) -> Optional[str]:
    nb = nb1 + nb2
    if nb.count('.') < 2:
        return nb


class MarkedTree:
    """
    A tree with zero or one marked node. This is a mixin to build MathObjects
    with a marked node, which may be thought of as some sort of cursor.

    Beware that there are two tree structures, one associated with the
    children attribute, the other one with the ordered_children() method.
    The second one is the important structure with respect to display,
    since it takes into account the descendants appearing in self.latex_shape.
    """

    assigned_math_object = None
    # cursor_pos is the rank of current selected item in self.latex_shape,
    # solely for the marked node. -1 denotes first position.
    cursor_pos = None
    marked_nb = None
    _current_index_in_total_list = None

    @property
    def is_marked(self):
        return self.cursor_pos is not None

    # Most of the following properties should be handled by derived classes #

    @property
    def min_cursor_pos(self):
        return 0

    @property
    def max_cursor_pos(self):
        return 0

    @property
    def children(self):
        return []

    def ordered_children(self):
        return []

    # @property
    # def left_children(self):
    #     return []
    #
    # @property
    # def right_children(self):
    #     return []

    def set_cursor_at_main_symbol(self) -> bool:
        pass

    def is_metavar(self):
        pass

    @property
    def is_assigned(self):
        return bool(self.assigned_math_object)

    #####################
    # Marked descendant #
    #####################

    def marked_descendant(self):
        """
        Return the marked descendant of self, if any.
        """
        if self.is_marked:
            return self

        for child in self.ordered_children():
            if child is self:
                continue
            marked_descendant = child.marked_descendant()
            if marked_descendant:
                return marked_descendant

    @property
    def has_marked_descendant(self) -> bool:
        return bool(self.marked_descendant())

    def child_with_marked_descendant(self):
        for child in self.children:
            if child.marked_descendant():
                return child

    def mark(self):
        # self.is_marked = True
        # self.cursor_pos = 1
        if self.cursor_pos is None:
            self.set_cursor_at_main_symbol()

    def unmark(self):
        """
        Unmark self's marked node.
        """
        if self.is_marked:
            # self.is_marked = False
            self.cursor_pos = None
        else:
            child = self.child_with_marked_descendant()
            if child:
                child.unmark()

    #######################
    # Total list of nodes #
    #######################

    def total_and_cursor_list(self) -> (list, list):
        """
        Return a non-injective list of MathObjects in the tree starting at self,
        where each item
        corresponds to an unbreakable block of string in the display of self.
        Also return the list of cursor numbers, i.e. index of item's
        appearance in the latex_shape where it belongs.
        e.g. if self is generic_parentheses, with one child mv0,
        then total list is (self, mv0, self)
        and cursor_list is (0, 0, 2).

        This makes use of self.ordered_children: essentially, ordered_children
        is expanded by replacing recursively each child by its
        ordered_children list.
        """

        total_list = []
        cursor_list = []
        cursor_counter = 0
        for item in self.ordered_children():
            if item is self:
                total_list.append(self)
                cursor_list.append(cursor_counter)
            else:
                i_t_list, i_c_list = item.total_and_cursor_list()
                total_list.extend(i_t_list)
                cursor_list.extend(i_c_list)

            cursor_counter += 1

        return total_list, cursor_list

    def current_index_in_total_list(self) -> int:
        """
        Return the index of the item corresponding to the current cursor pos
        ( as recorder in self.marked_descendant() and
        self.marked_descendant( ).cursor_pos )
        in self.total_and_cursor_list.
        """

        if self._current_index_in_total_list:
            return self._current_index_in_total_list

        total_list, cursor_list = self.total_and_cursor_list()
        pair = (self.marked_descendant(), self.marked_descendant().cursor_pos)
        l = list(zip(total_list, cursor_list))
        if pair in l:
            idx = l.index(pair)
        else:
            idx = -1

        self._current_index_in_total_list = idx
        return idx

    ######################
    # Moving in the tree #
    ######################

    def first_pos(self):
        total_list, cursor_list = self.total_and_cursor_list()
        first_mvar = total_list[0]
        first_cursor = cursor_list[0]
        return first_mvar, first_cursor

    def is_at_beginning(self):
        return self.marked_descendant().cursor_pos == -1
        # current = self.marked_descendant(), self.marked_descendant().cursor_pos
        # return current == self.first_pos()

    def last_pos(self):
        total_list, cursor_list = self.total_and_cursor_list()
        last_mvar = total_list[-1]
        last_cursor = cursor_list[-1]
        return last_mvar, last_cursor

    def is_at_end(self):
        # total_list, cursor_list = self.total_and_cursor_list()
        # test1 = self.marked_descendant() is total_list[-1]
        # test2 = self.marked_descendant().cursor_pos >= cursor_list[-1]
        # return test1 and test2
        current = self.marked_descendant(), self.marked_descendant().cursor_pos
        return current == self.last_pos()

    def set_cursor_at(self, mvar, pos=None):
        self.marked_descendant().unmark()
        if pos is None:
            mvar.set_cursor_at_main_symbol()
        else:
            mvar.cursor_pos = pos

    def go_to_beginning(self):
        # first_mvar, first_cursor = self.first_pos()
        # self.set_cursor_at(first_mvar, first_cursor)
        self.set_cursor_at(self, -1)

    def go_to_end(self):
        last_mvar, last_cursor = self.last_pos()
        self.set_cursor_at(last_mvar, last_cursor)

    def decrease_cursor_pos(self):
        total_list, cursor_list = self.total_and_cursor_list()
        idx = self.current_index_in_total_list()
        print(f"Cursor idx: {idx}")
        if idx > 0:
            mvar = total_list[idx-1]
            cursor_pos = cursor_list[idx-1]
            self._current_index_in_total_list += -1
            self.set_cursor_at(mvar, cursor_pos)
        else:
            self.go_to_beginning()
            # self.set_cursor_at(self, -1)

    def increase_cursor_pos(self):
        total_list, cursor_list = self.total_and_cursor_list()
        idx = self.current_index_in_total_list()
        if idx < len(total_list) - 1:
            mvar = total_list[idx+1]
            cursor_pos = cursor_list[idx+1]
            self._current_index_in_total_list += 1
            self.set_cursor_at(mvar, cursor_pos)
        else:
            pass

    def next_after_marked(self):
        """
        Return the node which is just after the marked node, i.e. right of
        cursor.
        """
        total_list, cursor_list = self.total_and_cursor_list()
        idx = self.current_index_in_total_list()
        if idx < len(total_list) - 1:
            mvar = total_list[idx+1]
            return mvar

    def parent_of_marked(self):
        mvar = self.marked_descendant()
        if mvar and mvar is not self:
            return self.parent_of(mvar)

    def move_up(self):
        parent = self.parent_of_marked()
        if parent:
            self.set_cursor_at(parent)
            return parent

    def next_unassigned(self):
        total_list, cursor_list = self.total_and_cursor_list()
        idx = self.current_index_in_total_list()
        mvars = [mvar for mvar in total_list[idx+1:] if not mvar.is_assigned]
        if mvars:
            return mvars[0]

    def previous_unassigned(self):
        total_list, cursor_list = self.total_and_cursor_list()
        idx = self.current_index_in_total_list()
        mvars = [mvar for mvar in total_list[:idx] if not mvar.is_assigned]
        if mvars:
            return mvars[-1]

    def move_right_to_next_unassigned(self):
        """
        Move the marked node to the next unassigned mvar, if any.
        """

        mvar = self.next_unassigned()
        if mvar:
            self.set_cursor_at(mvar)
            return mvar

    def move_left_to_previous_unassigned(self):
        """
        Move the marked node to the previous unassigned mvar, if any.
        """

        mvar = self.previous_unassigned()
        if mvar:
            self.set_cursor_at(mvar)
            return mvar

    def move_after_insert(self, assigned_mvar):
        """
        This method is supposed to be called just after an insertion involving
        the marked node. It tries to move the marked node down to the first
        unassigned mvar, or else to the next sister unassigned mvar. It
        returns the new marked mvar.
        """

        # (1) Unassigned children mvar?
        for child in assigned_mvar.ordered_children():
            if child.is_metavar() and not child.is_assigned:
                self.set_cursor_at(child, 0)
                return child

        # (1b) Generic node as a parent?

        # (2) Unassigned sisters?
        parent = self.parent_of(assigned_mvar)
        if parent:
            for child in parent.ordered_children():
                if child.is_metavar() and not child.is_assigned:
                    self.set_cursor_at(child, 0)
                    return child

        # (3) Stay just after assigned_mvar!
        self.set_cursor_at(assigned_mvar)
        return assigned_mvar

    def appears_right_of_cursor(self, other) -> bool:
        """
        True iff other appears right of cursor. Note that other may appear
        both left and right of cursor, but only if it is an ancestor of
        self.marked_element.
        """
        l, _ = self.total_and_cursor_list()
        idx = self.current_index_in_total_list()
        return other in l[idx+1:]

    def appears_left_of_cursor(self, other) -> bool:
        """
        True iff other appears left of cursor.
        """
        l, _ = self.total_and_cursor_list()
        idx = self.current_index_in_total_list()
        return other in l[:idx+1]

    def parent_of(self, descendant):
        """
        If descendant in self's subtree,return its parent.
        """

        if self is descendant:
            return None

        if descendant in self.children:
            return self

        for child in self.children:
            parent = child.parent_of(descendant)
            if parent:
                return parent

    # def father_of_marked_descendant(self):
    #     pass

    # FIXME: OBSOLETE?

    # def left_descendants(self):
    #     """
    #     Return the list of descendants of self.left_children, in infix order.
    #     """
    #     l_list = []
    #     for child in self.left_children:
    #         l_list.extend(child.infix_list())
    #     return l_list
    #
    # def left_unassigned_descendants(self):
    #     left_d = self.left_descendants()
    #     lud = [mvar for mvar in left_d if mvar.is_metavar and
    #            not mvar.is_assigned]
    #     return lud
    #
    # def right_unassigned_descendants(self):
    #     right_d = self.right_descendants()
    #     rud = [mvar for mvar in right_d if mvar.is_metavar and
    #            not mvar.is_assigned]
    #     return rud

    # def right_descendants(self):
    #     """
    #     Return the list of descendants of self.right_children, in infix
    #     order.
    #     """
    #     r_list = []
    #     for child in self.right_children:
    #         r_list.extend(child.infix_list())
    #     return r_list

    # def infix_list(self):
    #     """
    #     Return the list of all nodes in self's tree in the infix order.
    #     """
    #
    #     # if only_unassigned:
    #     #     if self.is_metavar() and not self.is_assigned:
    #     #         maybe_self = [self]
    #     #     else:
    #     #         maybe_self = []
    #     # else:
    #     #     maybe_self = [self]
    #
    #     i_list = (self.left_descendants()
    #               + [self]
    #               + self.right_descendants())
    #
    #     return list(i_list)

    # def marked_infix_idx(self):
    #     if self.marked_descendant():
    #         return self.infix_list().index(self.marked_descendant())

    # def next_from_marked(self):
    #     """
    #     Return the next node from marked descendant in the infix order.
    #     """
    #     i_list = self.infix_list()
    #     # print(i_list)
    #     marked_mvar = self.marked_descendant()
    #     if not marked_mvar:
    #         return None
    #
    #     idx = i_list.index(marked_mvar)
    #     next_mvar = None
    #     # if not unassigned:
    #     if idx < len(i_list) - 1:
    #         next_mvar = i_list[idx + 1]
    #     # else:
    #     #     while idx < len(i_list) - 1 and i_list[idx].is_assigned:
    #     #         idx += 1
    #     #     if not i_list[idx].is_assigned:
    #     #         next_mvar = i_list[idx]
    #
    #     return next_mvar

    # def marked_is_at_end(self):
    #     il = self.infix_list()
    #     return self.marked_descendant() is il[-1]
    #
    # def move_marked_right(self):
    #     """
    #     Move the marked node to the next metavar in self if any. Return the
    #     new marked metavar, or None.
    #     """
    #
    #     next_mvar = self.next_from_marked()
    #     marked_mvar = self.marked_descendant()
    #     if marked_mvar and next_mvar:
    #         marked_mvar.unmark()
    #         next_mvar.mark()
    #         return next_mvar
    #
    # def move_marked_left(self):
    #     """
    #     Move the marked node to the previous metavar.
    #     """
    #
    #     i_list = self.infix_list()
    #     marked_mvar = self.marked_descendant()
    #     idx = i_list.index(marked_mvar)
    #
    #     if idx > 0:
    #         new_mvar = i_list[idx - 1]
    #         marked_mvar.unmark()
    #         new_mvar.mark()
    #         return new_mvar

    # def cursor_is_at_end(self):
    #     """
    #     True iff no cursor pos may not be increased.
    #     In CalculatorController, right arrow should be disabled.
    #     """
    #
    #     # (1) Test child
    #     if not self.is_marked:
    #         child = self.child_with_marked_descendant()
    #         if not child.cursor_is_at_end():
    #             return False
    #
    #     # (2) Test self
    #     return self.cursor_pos and self.cursor_pos == self.max_cursor_pos

    # def cursor_is_at_beginning(self):
    #     """
    #     True iff no cursor pos may not be deacreased.
    #     In CalculatorController, left arrow should be disabled.
    #     """
    #
    #     # (1) Test child
    #     if not self.is_marked:
    #         child = self.child_with_marked_descendant()
    #         if not child.cursor_is_at_beginning():
    #             return False
    #
    #     # (2) Test self
    #     return self.cursor_pos and self.cursor_pos == self.min_cursor_pos

    # def set_cursor_at_beginning(self):
    #     """
    #     Set cursor_pos and marked node at first position in self's subtree.
    #     """
    #     self.cursor_pos = 1
    #     child = self.descendant_at_cursor_pos()
    #     if not child:
    #         self.mark()
    #     else:
    #         assert isinstance(child, MarkedTree)
    #         child.set_cursor_at_beginning()
    #
    # def set_cursor_at_end(self):
    #     """
    #     Set cursor_pos and marked node at last position in self's subtree.
    #     """
    #     self.cursor_pos = self.max_cursor_pos
    #     child = self.descendant_at_cursor_pos()
    #     if not child:
    #         self.mark()
    #     else:
    #         assert isinstance(child, MarkedTree)
    #         child.set_cursor_at_end()

    # def increase_cursor_pos(self):
    #     """
    #     Increase cursor position by 1 if possible,
    #     modify marked node if needed, and return marked node.
    #     Return None if increasing is not possible.
    #     """
    #
    #     # (1) Try to increase marked descendants
    #     if not self.is_marked:
    #         child = self.child_with_marked_descendant()
    #         assert isinstance(child, MarkedTree)
    #         success = child.increase_cursor_pos()
    #         if success:
    #             return success
    #
    #     # (3) Self is marked or child at end: increase self's cursor_pos
    #     # and modify marked node
    #     if self.cursor_pos < self.max_cursor_pos:
    #         self.cursor_pos += 1
    #         child = self.descendant_at_cursor_pos()
    #         if child:
    #             # Cursor at beginning of a new marked node
    #             assert isinstance(child, MarkedTree)
    #             child.set_cursor_at_beginning()
    #             return child.marked_descendant()
    #         else:
    #             # New marked node is self
    #             self.mark()
    #             return self
    #     else:
    #         # End of self reached
    #         self.unmark()
    #         self.cursor_pos = None
    #         return None

    # def decrease_cursor_pos(self):
    #     """
    #     Decrease cursor position by 1 if possible,
    #     modify marked node if needed, and return node to be marked.
    #     Return None if decreasing is not possible.
    #     """
    #
    #     # (1) Try to decrease marked descendants
    #     if not self.is_marked:
    #         child = self.child_with_marked_descendant()
    #         success = child.decrease_cursor_pos()
    #         if success:
    #             # self.marked_descendant().unmark()
    #             # success.mark()
    #             return success
    #
    #     # (3) Self is marked or child at beginning: decrease self's cursor_pos
    #     # and modify marked node
    #     if self.cursor_pos > self.min_cursor_pos:
    #         self.cursor_pos -= 1
    #         child = self.descendant_at_cursor_pos()
    #         if child:
    #             # Cursor at end of a new marked node
    #             assert isinstance(child, MarkedTree)
    #             child.set_cursor_at_end()
    #             return child.marked_descendant()
    #         elif self.is_marked:
    #             return self
    #         else:
    #             # New marked node is self
    #             self.marked_descendant().unmark()
    #             self.mark()
    #             return self
    #     else:
    #         # End of self reached
    #         self.cursor_pos = None
    #         return None

    # def set_cursor_pos_at_child(self, child):
    #     idx = self.cursor_pos_for_child(child)
    #     self.cursor_pos = idx
    #
    # def mark_child(self, child):
    #     self.set_cursor_pos_at_child(child)
    #     child.mark()

    # def set_cursor_at_main_symbol_of(self, mvar) -> bool:
    #     """
    #     Mark mvar, and recursively set cursor at main symbol of mvar (or at
    #     end if no main symbol) and return True in case of success.
    #     """
    #
    #     if self is mvar:
    #         self.mark()
    #         self.set_cursor_at_main_symbol()
    #         return True
    #
    #     for child in self.children:
    #         assert isinstance(child, MarkedTree)
    #         success = child.set_cursor_at_main_symbol_of(mvar)
    #         if success:
    #             self.set_cursor_pos_at_child(child)
    #             return True
    #         else:
    #             self.cursor_pos = None
    #
    #     print(f"Unable to set cursor at ms of {mvar}")

    # def lineage_from(self, descendant) -> []:
    #     if self is descendant:
    #         return [self]
    #     else:
    #         for child in self.children:
    #             child_lineage = child.lineage_from(descendant)
    #             if child_lineage:
    #                 return child_lineage + [self]
    #
    # def marked_lineage_from(self) -> []:
    #     if self.is_marked:
    #         return [self]
    #     else:
    #         for child in self.children:
    #             child_lineage = child.marked_lineage_from()
    #             if child_lineage:
    #                 return child_lineage + [self]
    #
    # def path_from_marked_to_next(self) -> ():
    #     """
    #     Return the two components of the path from the unique marked
    #     descendant to the next node in the infix order, more precisely both
    #     upward paths from node to the common ancestor. The common ancestor is
    #     included in both paths.
    #     """
    #     marked_l = self.marked_lineage_from()
    #     if not marked_l:
    #         return [], []
    #     next_ = self.next_from_marked()
    #     if not next_:
    #         path = marked_l, [marked_l[-1]]
    #     else:
    #         next_l = self.lineage_from(next_)
    #         common_ancestor = self  # Useless
    #         while next_l and marked_l and next_l[-1] is marked_l[-1]:
    #             common_ancestor = marked_l.pop()
    #             next_l.pop()
    #         # next_l.reverse()
    #         path = marked_l + [common_ancestor],  next_l + [common_ancestor]
    #
    #     return path

    # def check_all_cursor_pos(self):
    #     """
    #     Check all cursor pos in self's subtree. Adjust if necessary, picking
    #     the first child that matches when several are possible.
    #     """
    #
    #     m_descendant = self.marked_descendant()
    #     child = None
    #     if self.cursor_pos is not None:
    #         # Check cursor pos
    #         child = self.descendant_at_cursor_pos()
    #         if child and child.marked_descendant() is self.marked_descendant():
    #             # child and cursor_pos are OK
    #             pass
    #         else:
    #             child = None
    #
    #     if not child:
    #         child = self.child_with_marked_descendant()
    #         self.cursor_pos = self.cursor_pos_for_child(child)
    #
    #     # Remove non pertinent cursor_pos:
    #     for other_child in self.children:
    #         if other_child is not child:
    #             child.cursor_pos = None
    #
    #     # Recursively check child:
    #     child.check_cursor_pos()


# class RootedMarkedTree(MarkedTree):
#     """
#     A class for the root of a MarkedTree, with methods that keep track of
#     global coherence.
#     """
#
#     def decrease_cursor_pos(self):
#
#         m_descendant = self.marked_descendant()
#
#         if m_descendant.cursor_pos > m_descendant.min_cursor_pos:
#             m_descendant.cursor_pos -= 1
#             return m_descendant
#
#         m_descendant.cursor_pos = None
#         father = self.parent_of(m_descendant)

    # def mark_descendant(self, descendant):
    #     """
    #     Mark descendant and check all cursor_pos.
    #     """
    #
    #     if self.marked_descendant() \
    #             and self.marked_descendant()is not descendant:
    #         self.marked_descendant().unmark()
    #
    #     if not descendant.is_marked():
    #         descendant.mark()
    #
    #     self.check_all_cursor_pos()


# decreasing precedence
priorities = [{'COMPOSITE_NUMBER'},
              {'POINT'},  # FIXME: DECIMAL?
              {'MULT', 'DIV'},
              {'SUM', 'DIFFERENCE'},
              {'PROP_EQUAL', 'PROP_<', 'PROP_>', 'PROP_≤', 'PROP_≥'},
              # {'CLOSE_PARENTHESIS', 'OPEN_PARENTHESIS'}
              ]


def priority(self: str, other: str) -> str:
    """
    Return '=' if self and other have the same priority level,
    '>' or '<' if they have distinct comparable priority levels,
    None otherwise.
    """

    if not self or not other:
        return None
    self_found = False
    other_found = False
    for nodes in priorities:
        if self in nodes:
            if other_found:
                return '<'
            if other in nodes:
                return '='
            else:
                self_found = True
        elif other in nodes:
            if self_found:
                return '>'
            else:
                other_found = True


def in_this_order(self, other, list_):
    """
    Return True if self and other are in this order in list_, False if they
    are in the reverse order.
    """
    yes = None
    both_in = False
    for item in list_:
        if item is self:
            if yes is None:  # self is first
                yes = True
            elif yes is False:  # self is second
                both_in = True
        elif item is other:
            if yes:  # other is second
                both_in = True
            else:  # other is first
                yes = False

    if both_in:
        return yes


class MarkedPatternMathObject(PatternMathObject, MarkedTree):
    """
    A PatternMathObject with a marked node.
    """

    cursor_pos = None
    automatic_patterns = []  # Populated in calculator_pattern_strings.py
    app_patterns = []
    applications_from_ctxt = []

    #
    # @classmethod
    # def populate_automatic_patterns(cls):
    #     for pattern_string in automatic_matching_patterns:
    #         mpmo = cls.from_string(pattern_string)
    #         cls.automatic_patterns.append(mpmo)

    @classmethod
    def from_pattern_math_object(cls, pmo: PatternMathObject):
        """
        Create a MarkedPatternMathObject from a PatternMathObject,
        or a MarkedMetavar if pmo is a metavar.
        """

        if isinstance(pmo, MetaVar):
            return MarkedMetavar.from_mvar(pmo)

        children = [MarkedMetavar.from_mvar(child, parent=pmo)
                    if isinstance(child, MetaVar)
                    else cls.from_pattern_math_object(child)
                    for child in pmo.children]
        # NO_MATH_TYPE should be kept identical
        marked_type = (pmo.math_type if pmo.math_type.is_no_math_type()
                       else copy(pmo.math_type))
        if pmo.is_bound_var:
            marked_pmo = MarkedBoundVar(node=pmo.node, info=pmo.info,
                                        children=children,
                                        math_type=marked_type)
        else:
            marked_pmo = cls(pmo.node, pmo.info, children,
                             marked_type, pmo.imperative_matching)
        return marked_pmo

    @classmethod
    def from_math_object(cls, math_object: MathObject,
                         turn_lc_into_mvar=False):
        """
        Construct an instance of cls by first constructing an instance of
        PatternMathObject, but not turning local constants into metavars.
        """
        pmo = super().from_math_object(math_object,
                                       turn_lc_into_mvar=turn_lc_into_mvar)
        marked_pmo = cls.from_pattern_math_object(pmo)
        return marked_pmo

    @classmethod
    def from_string(cls, s: str, metavars=None):
        pmo = super().from_string(s, metavars)
        mpmo = cls.from_pattern_math_object(pmo)
        return mpmo

    @classmethod
    def application_from_function(cls, fct):
        """
        Given a function fct, construct the MPMO corresponding to
        APP(fct, mvar) where mvar is a fresh mvar.
        """

        if not isinstance(fct, cls):
            fct = cls.from_math_object(fct)

        children = fct.math_type.children
        if children:
            arg_type = children[0]
        else:
            arg_type = cls.NO_MATH_TYPE

        mvar = MarkedMetavar(math_type=arg_type)
        mpmo = cls.application(fct, mvar)
        return mpmo

    @classmethod
    def populate_applications_from_context(cls, context):
        """
        For each MathObject fct from context, if suitable, compute
        app(fct, mvar), and return the list.
        """
        apps = [cls.application_from_function(fct)
                for fct in context
                if fct.is_suitable_for_app()]
        cls.applications_from_ctxt = apps

    @classmethod
    def populate_app_marked_patterns(cls):
        patterns = PatternMathDisplay.fake_app_constant_patterns
        cls.app_patterns = [cls.from_string(pat) for pat in patterns]

    @classmethod
    def generic_node(cls, left_child=None, right_child=None, node=None):
        """
        Create a MarkedPatternMathObject with node GENERIC_NODE and
        given children. This is used to force insertion when math_type is
        unknown.
        """
        if node is None:
            node = "GENERIC_NODE"
        pattern = node + "(?0, ?1)"
        generic_node = cls.from_string(pattern)
        mvar1 = generic_node.children[0]
        mvar2 = generic_node.children[1]
        mvar1.assigned_math_object = left_child
        mvar2.assigned_math_object = right_child
        return generic_node

    @classmethod
    def generic_parentheses(cls, child=None):
        """
        Create a MarkedPatternMathObject with node GENERIC_PARENTHESES and
        """
        pattern = "GENERIC_PARENTHESES(?0)"
        generic_node = cls.from_string(pattern)
        mvar = generic_node.children[0]
        mvar.assigned_math_object = child
        return generic_node

    # @classmethod
    # def composite_number(cls, left_child, right_child):
    #     return cls.generic_node(left_child, right_child,
    #                             node="COMPOSITE_NUMBER")

    def latex_shape(self, is_type=False, text=False, lean_format=False):
        """
        Modify the latex shape to mark the main symbol, if self.is_marked.
        In particular, insert a tag at the place where a cursor should be
        displayed.
        """
        shape = super().latex_shape(is_type=is_type,
                                    text=text,
                                    lean_format=lean_format)
        if not self.is_marked:
            return shape

        marked_shape = MathDisplay.marked_latex_shape(shape, self.cursor_pos)
        return marked_shape

    @property
    def max_cursor_pos(self):
        return len(self.latex_shape())

    def main_shape_symbol(self) -> (int, str):
        """
        Return main symbol of self, if any, and idx of main symbol in
        latex_shape.
        """
        shape = self.latex_shape()
        return MathDisplay.main_symbol_from_shape(shape)

    def ordered_children(self):
        """
        List of ordered children or descendant appearing in latex_shape,
        with str entries replaced by self.
            e.g. if <shape is
        (r"\forall", (1,), r" \subset ", (0, 0), ", ", (2,)),

            then this methid will return
        (self, self.children[1], self, self.descendant(0,0), self,
        self.children[2] )

        """
        # FIXME: put this and following methods in PatternMathObj?
        # Unmarked latex_shape
        shape = super().latex_shape(is_type=False,
                                    text=False,
                                    lean_format=False)

        children_nbs = MathDisplay.ordered_children(shape)

        children = []
        for nb in children_nbs:
            if nb is None:
                children.append(self)
            else:
                children.append(self.descendant(nb))
        return children

    def partionned_children(self):
        """
        Partition proper children (items of self.ordered_children that are
        not self) into three lists:
        left, central, right.
        Left children are the ones are before the first of self in
        self.ordered_children.
        """
        left = []
        central = []

        children = self.ordered_children()

        left_or_central = left
        idx = -1
        for child in children:
            if child is self:
                if left_or_central is left:
                    # Move from left to central at first appearance of self:
                    left_or_central = central
                else:
                    # Remember last appearance of self
                    idx = len(central)
            else:
                left_or_central.append(child)

        if left_or_central is left:
            # self does not appear
            return [], left_or_central, []
        elif idx != -1:
            # Generic case
            central, right = central[:idx], central[idx:]
            return left, central, right
        else:
            # self appear only once: no central children
            return left, [], left_or_central

    def partionned_mvars(self, unassigned=False) -> [[PatternMathObject]]:
        lists = self.partionned_children()
        descendant_lists = ([], [], [])
        for l, new_l in zip(lists, descendant_lists):
            for child in l:
                new_l.extend(child.all_mvars(unassigned=unassigned))

        return descendant_lists

    def set_cursor_at_main_symbol(self):
        idx, ms = self.main_shape_symbol()
        self.cursor_pos = idx
        print(f"Setting cursor_pos at {idx} for {self}")

    # def clear_all_matchings(self):
    #     for mvar in self.left_descendants() + self.right_descendants():
    #         if mvar.is_metavar():
    #             mvar.clear_matching()

    def bound_var_affected_by(self, mvar) -> Optional[BoundVar]:
        """
        If mvar is the type of a bound_var, return the bound_var.
        Also if mvar affects the type of a bound_var.
        """

        parent = self.parent_of(mvar)
        if not parent:
            return
        if parent.has_bound_var() and mvar == parent.children[0]:
            return parent.bound_var
        else:
            return self.bound_var_affected_by(parent)

    def priority_test(self, parent, left_children):
        """
        return True is self can be a left/right child of parent
        (left iff left_children=True).        
        """

        # FIXME: use MathDisplay.priority_test
        if left_children:
            # self can be a left child of parent?
            test = (priority(parent.node, self.node) != '>')
        else:
            # self can be a right child of parent?
            test = (priority(parent.node, self.node) not in ('=', '>'))
        return test

    # def automatic_insert(self, new_pmo, mvar):
    #     """
    #     Try to insert new_pmo at mvar by first inserting an automatic
    #     pattern, and then inserting mvar.math_object (if any) and new_pmo as a
    #     child.
    #     """
    #     # TODO
    #     pass

    @staticmethod
    def assign(mvars, math_object, assignments, check_types=False) -> bool:
        """
        Try to assign math_object to one of the mvar in mvars.
        If check_types is True then assignment is included in the match
        method (and done only if this match is a success).
        In the opposite case, and if the match fails, the assignment will be
        done anyway, and for this it is recorded in the assignments list.
        """
        for child_new_pmo in mvars:
            log.debug(f"----> {child_new_pmo} match?")
            if child_new_pmo.match(math_object, use_cls_metavars=True):
                log.debug("yes!")
                return True
            elif not check_types:
                assignments.append((child_new_pmo,
                                    math_object))
                log.debug("Check type failed, assign anyway")
                return True

    def priority_tests(self, new_pmo, mvar, parent_mvar) -> bool:
        """
        Check if the priority rules are compatible with
        (1) new_pmo being a child of parent_mvar in place of mvar
        (mvar is a left or right child of parent_mvar)
        (2) mvar being a left or right child of new_pmo
        (left/right according to position of mvar relative to the current
        cursor)
        """
        # Priority test I (no priority test for common ancestor):
        #  Can new_pmo be a child of parent_mvar?
        if parent_mvar:
            left_children, central_children, right_children = \
                parent_mvar.partionned_children()
            if mvar in left_children:
                # new_pmo would take the place of mvar, as a left child
                priority_test = (priority(parent_mvar.node, new_pmo.node) != '>')
            elif mvar in right_children:
                # new_pmo would take the place of mvar, as a right child
                priority_test = (priority(parent_mvar.node, new_pmo.node)
                                 not in ('=', '>'))
            else:
                priority_test = True
            if not priority_test:
                log.debug(f"--> Priority test I failed")
                return False
            else:
                log.debug("--> Priority test I passed")

        # Priority test II: Can mvar be a child of new_pmo?
        left = self.appears_left_of_cursor(mvar)
        if left:  # mvar would be inserted as a left child
            priority_test = (priority(new_pmo.node, mvar.node) != '>')
        else:
            priority_test = (priority(new_pmo.node, mvar.node)
                             not in ('=', '>'))
        if not priority_test:
            log.debug(f"--> Priority test II failed")
            return False
        else:
            log.debug("--> Priority test II passed")
            return True

    @staticmethod
    def do_assign(assignments):
        for metavar, math_object in assignments:
            metavar.assigned_math_object = math_object

    def first_right_descendants(self, mvar) -> list:
        """
        Return the list of descendants of mvar which are the first to be at
        the right of the cursor pos in their lineage, from top to bottom.
        These are the nodes which must be re-assigned if mvar is re-assigned
        to the left of the cursor.
        They are either right descendants of the last left child,
        or right children.
        """

        math_object = mvar.assigned_math_object
        if not math_object:
            return []
        children = math_object.children

        left_children = [child for child in children
                         if not self.appears_right_of_cursor(child)]

        right_children = [child for child in children
                          if not self.appears_left_of_cursor(child)]

        if left_children:
            limit_child = left_children[-1]
            more_right_descendants = self.first_right_descendants(limit_child)
        else:
            more_right_descendants = []

        return more_right_descendants + right_children

    def first_left_descendants(self, mvar) -> list:
        """
        Return the list of descendants of mvar which are the first to be at
        the right of the cursor pos in their lineage, from top to bottom.
        These are the nodes which must be re-assigned if mvar is re-assigned
        to the left of the cursor.
        They are either right descendants of the last left child,
        or right children.
        """

        math_object = mvar.assigned_math_object
        if not math_object:
            return []
        children = math_object.children

        left_children = [child for child in children
                         if not self.appears_right_of_cursor(child)]

        right_children = [child for child in children
                          if not self.appears_left_of_cursor(child)]

        if right_children:
            limit_child = right_children[0]
            more_left_descendants = self.first_left_descendants(limit_child)
        else:
            more_left_descendants = []

        return left_children + more_left_descendants

    def re_assign(self, mvar, new_pmo, assignments, check_types) -> bool:
        """
        Try to re-assign the assigned_math_object of mvar, which is a node of
        self, to new_pmo, to be inserted at cursor pos.
        Some of the children of mvar may have been displaced by the
        re-assignment to the wrong side of new_pmo, and those have to be
        also re-assigned to mvar children of new_pmo.
        """

        # FIXME:
        #  (2) some previous assignment are cleared even in case of failure??

        assert mvar.is_assigned
        # Determine if mvar should be assigned to a left or right child of
        # new_pmo, i.e. if it appears left or right of cursor.
        left = self.appears_left_of_cursor(mvar)
        right = self.appears_right_of_cursor(mvar)

        left_mvars, central_mvars, right_mvars = \
            new_pmo.partionned_mvars(unassigned=True)
        pmo_display = new_pmo.to_display(format_='utf8')

        left_insertion = False
        central_insertion = False
        right_insertion = False
        math_object = mvar.assigned_math_object
        if left:
            log.debug(f"--> Trying to match left mvars of {pmo_display} "
                      f"with {math_object}")
            left_insertion = self.assign(left_mvars, math_object,
                                         assignments, check_types)

        if not left_insertion and right:
            log.debug(f"--> Trying to match right mvars of {pmo_display} with"
                      f" {math_object}")
            right_insertion = self.assign(right_mvars, math_object,
                                          assignments, check_types)

        if not (left_insertion or right_insertion):
            log.debug(f"--> Trying to match central mvars of {pmo_display} "
                      f"with {math_object}")
            central_insertion = self.assign(central_mvars, math_object,
                                            assignments, check_types)

        insertion = (left_insertion or right_insertion or central_insertion)
        if not insertion:
            log.debug("-->Child don't match.")
            return False
        elif central_insertion:
            return True
        # Now left_insertion or right_insertion

        ##############################
        # (C) Additional refactoring #
        ##############################
        # Some of mvar.assigned_math_object's children may be at the wrong
        # side of new_pmo

        # (C-1) Find bad children
        mvars, bad_children = ((right_mvars, self.first_right_descendants(mvar))
                               if left_insertion else
                               (left_mvars, self.first_left_descendants(mvar))
                               )
        display = [child.to_display(format_='utf8')
                   for child in bad_children]
        log.debug(f"--> Bad children: {display}")

        # (C-2) move bad children
        # FIXME: algo should be symmetric but is not,
        #  this can be a problem in case of multiple mvars.
        mvar_to_be_cleared = []
        while bad_children:
            child = bad_children.pop(0)
            math_child = child.assigned_math_object
            if not math_child:
                continue

            success = False
            while mvars:
                pmo_mvar = mvars.pop(0)
                # if math_child:
                if pmo_mvar.match(math_child,
                                  use_cls_metavars=True):
                    # Success for this child!
                    # FIXME: only in case of global success?! :
                    # child.clear_assignment()
                    mvar_to_be_cleared.append(child)
                    success = True
                    break
                elif not check_types:
                    mvar_to_be_cleared.append(child)
                    # child.clear_assignment()
                    assignments.append((pmo_mvar,
                                        math_child))
                    success = True
                    log.debug("Failed, assigned anyway")
                    break
            if not success:
                # last mvar did not match
                log.debug(f"unable to assign child {child}")
                return False
            else:
                [child.clear_assignment() for child in mvar_to_be_cleared]
                log.debug(f"Child {child} assigned to {pmo_mvar}")

        return True

    def insert_if_you_can(self, new_pmo, mvar, parent_mvar=None,
                          check_types=False):
        """
        Try to insert new_pmo at mvar, as a left child if
        mvar is either a term of left_path or a term of right_path.
        """

        PatternMathObject.clear_cls_metavars()
        assignments = []

        assert isinstance(new_pmo, MarkedPatternMathObject)
        assert isinstance(mvar, MarkedMetavar)
        if parent_mvar:
            assert isinstance(parent_mvar, MarkedPatternMathObject)

        left = self.appears_left_of_cursor(mvar)
        right = self.appears_right_of_cursor(mvar)

        pmo_display = new_pmo.to_display(format_='utf8')
        log.debug(f"Trying to insert {pmo_display} at {mvar}")
        log.debug(f"left/right = {left, right}")
        log.debug(f"Parent mvar = {parent_mvar}")

        ######################
        # (A) Priority tests #
        ######################
        if not self.priority_tests(new_pmo, mvar, parent_mvar):
            return False

        ########################
        # (B) First match test #
        ########################
        # Try to insert mvar.assigned_math_object as a left/right/central
        # mvars of new_pmo
        if (mvar.is_assigned and
                not self.re_assign(mvar, new_pmo, assignments, check_types)):
            return False

        ##################
        # (D) Last match #
        ##################
        # Last test: new_pmo match mvar?
        mvar.clear_assignment()
        log.debug(f"Last test: try to match {pmo_display} with {mvar}")
        match_mvar_test = mvar.match(new_pmo,
                                     # debug=True,
                                     use_cls_metavars=True)
        if not match_mvar_test:
            if not check_types:
                assignments.append((mvar, new_pmo))
                log.debug("--> failed, assign anyway")
            else:
                return False
        else:
            log.debug("-->match!")

        # Insertion succeeded:
        # Assign all mvars that have been matched in this method:
        # if check_types:
        mvar.assign_matched_metavars()
        self.do_assign(assignments)
        return True

    # def insert_if_you_can_on_next_mvar(self):
    #     pass

    def insert(self, new_pmo: PatternMathObject):
        """
        Try to insert pmo in self's tree, so that pmo is just after the
        marked node in the infix order. In case of success, return the mvar
        at which insertion has been done.

        We first try insertion at the marked mvar, which is supposed to be
        just before cursor pos, and all the way up from
        there. If none works, then we try again starting from the mvar just
        after cursor pos.
        """

        # mvar = self.marked_descendant()
        # new_pmo_copy = new_pmo.deep_copy(new_pmo)
        new_pmo_copy = MarkedPatternMathObject.deep_copy(new_pmo)

        for mvar in (self.marked_descendant(), self.next_after_marked()):
            if not mvar:
                continue
            if mvar.node == "GENERIC_NODE":
                success = self.substitute_generic_node(mvar, new_pmo_copy)
                if success:
                    return mvar

            parent_mvar = self.parent_of(mvar)

            while mvar:
                success = self.insert_if_you_can(new_pmo_copy, mvar, parent_mvar)
                if success:
                    return mvar
                mvar = parent_mvar
                parent_mvar = self.parent_of(parent_mvar)
                if mvar and not mvar.is_metavar():
                    continue

        # return self.generic_insert(new_pmo)

        # TODO: try automatic patterns

        # TODO: handle multiple patterns

    # FIXME: obsolete?

    def insert_app_parentheses(self):
        mvar = self.marked_descendant()
        math_object = mvar.assigned_math_object
        if not math_object:
            return
        for app_pattern in self.app_patterns + self.applications_from_ctxt:
            child = app_pattern.children[0]
            if child.match(math_object):
                new_pmo = app_pattern.deep_copy(app_pattern)
                new_pmo.children[0].match(math_object)
                new_pmo.assign_matched_metavars()
                if mvar.match(new_pmo):
                    mvar.assign_matched_metavars()
                else:
                    mvar.assigned_math_object = new_pmo
                return mvar

    def substitute_generic_node(self, mvar, new_pmo, check_types=False):
        """
        Given an mvar whose assigned_math_object is a generic_node,
        substitute this generic node by new_pmo.
        """

        # nb_children = len([child for child in mvar.children
        #                    if child.assigned_math_object])
        #
        # if nb_children > len(new_pmo.children):
        #     # Fail
        #     return

        assignments = []
        [child1, child2] = mvar.children
        mo1, mo2 = child1.assigned_math_object, child2.assigned_math_object
        left_mvars, central_mvars, right_mvars = \
            new_pmo.partionned_mvars(unassigned=True)
        if mo1:
            if left_mvars:
                child1_mvar = left_mvars[0]
                if not check_types:
                    assignments.append((child1_mvar, mo1))
                else:
                    pass  # TODO!!
            elif central_mvars:
                child1_mvar = central_mvars.pop(0)
                assignments.append((child1_mvar, mo1))
            else:
                return False
        if mo2:
            if right_mvars:
                child2_mvar = right_mvars[0]
                assignments.append((child2_mvar, mo2))
            elif central_mvars:
                child2_mvar = central_mvars.pop(0)
                assignments.append((child2_mvar, mo2))
            else:
                return False

        self.do_assign(assignments)
        mvar.assigned_math_object = new_pmo
        return True

    def insert_number(self, new_pmo):
        """
        Try to merge numbers to create a new value.
        """
        if new_pmo.node not in ('NUMBER', 'POINT'):
            return

        new_pmo_value = new_pmo.value if new_pmo.node == 'NUMBER' else '.'

        mvar = self.marked_descendant()
        left_child = mvar.assigned_math_object
        if left_child and left_child.node == 'NUMBER':
            left = left_child.value
            new_value = merge_nbs(left, new_pmo_value)
            if new_value:
                left_child.value = new_value
                return mvar
        else:
            mvar = self.next_after_marked()
            right_child = mvar.assigned_math_object
            if right_child and right_child.node == 'NUMBER':
                right = right_child.value
                new_value = merge_nbs(new_pmo_value, right)
                if new_value:
                    right_child.value = new_value
                    return mvar

    def generic_insert(self, new_pmo: PatternMathObject):
        """
        Force insertion of new_pmo at self.marked_descendant() by inserting
        a generic node.
        """

        new_pmo_copy = MarkedPatternMathObject.deep_copy(new_pmo)

        new_nb = self.insert_number(new_pmo)
        if new_nb:
            self.set_cursor_at(new_nb)
            return self.marked_descendant()

        # GENERIC INSERT DESACTIVATED:
        else:
            return

        mvar = self.marked_descendant()
        left_child = mvar.assigned_math_object
        if left_child:
            mvar.clear_assignment()
            # if (left_child.node == 'NUMBER'
            #         and new_pmo_copy.node in ('NUMBER', 'POINT')):
            #     generic_node = MarkedPatternMathObject.composite_number(
            #                 left_child=left_child, right_child=new_pmo_copy)
            # else:
            generic_node = MarkedPatternMathObject.generic_node(
                        left_child=left_child, right_child=new_pmo_copy)
        else:
            generic_node = MarkedPatternMathObject.generic_node(
                left_child=new_pmo_copy)

        mvar.assigned_math_object = generic_node
        self.set_cursor_at(generic_node.children[1], 1)

        return self.marked_descendant()

    # def automatic_patterns(self):
    #     """
    #     Try to replace generic nodes in self sub-tree by patterns in the
    #     automatic_patterns list.
    #     """

    # def post_process(self):
        # new_children = [child.post_process() for child in self.children]
        #
        # if self.node == "COMPOSITE_NUMBER":
        #     child0 = new_children[0]
        #     child1 = new_children[1]
        #     if child0.node == 'NUMBER' and child1.node == 'NUMBER':
        #         # Concatenate
        #         new_child = child0.value() + child1.value()
        #         return new_child
        # elif self.node == "POINT":
        #     child0 = new_children[0]
        #     child1 = new_children[1]
        #     if child0.node == 'NUMBER' and child1.node == 'NUMBER':
        #         # Concatenate
        #         new_child = child0.value() + '.' + child1.value()
        #         return new_child
        #
        # return self


    @classmethod
    def tree_from_list(cls, i_list: []):
        """
        Construct a MarkedPatternMathObject from a list of such, whose infix
        list is the given list.
        """
        if len(i_list) == 1:
            return MarkedPatternMathObject.deep_copy(i_list[0])
        else:
            new_pmo = i_list.pop(-1)
            new_tree = cls.tree_from_list(i_list)
            if new_tree:
                success = new_tree.insert_at_end(new_pmo)
                if success:
                    return new_tree

    def insert_after_marked(self, new_pmo: PatternMathObject):
        """
        Alternative to the insert() method: reconstruct all the tree.
        """

        # Non recursive version:
        # i_list = self.infix_list()
        # new_tree = MarkedPatternMathObject.deep_copy(i_list[0])
        # for node in i_list[1:]:
        #     success = new_tree.insert_at_end(node)
        #     if not success:
        #         return False
        #     if node is self.marked_descendant():
        #         success = new_tree.insert_at_end(new_pmo)
        #         if not success:
        #             return False
        #
        # return True

        # Recursive version
        if self.marked_is_at_end():
            return self.insert_at_end(new_pmo)

        i_list = self.infix_list()
        return self.tree_from_list(i_list)

    def clear_marked_mvar(self):
        """
        'Delete' current marked metavar, i.e. remove assigned_math_object.
        """

        if self.marked_descendant():
            success = self.marked_descendant().delete()
            if success:
                self.set_cursor_at(self.marked_descendant(), 0)
                self.decrease_cursor_pos()
                return True


class MarkedMetavar(MetaVar, MarkedPatternMathObject):
    """
    A Metavar which can be marked.
    """

    def __repr__(self):
        rep = super().__repr__()
        if self.is_marked:
            rep = '--> ' + rep
        return rep

    # @property
    # def assigned_math_object(self):
    #     return self._assigned_math_object
    #
    # @assigned_math_object.setter
    # def assigned_math_object(self, math_object):
    #     self._assigned_math_object = math_object

    @classmethod
    def deep_copy(cls, self, original_bound_vars=None, copied_bound_vars=None):
        new_mvar: MarkedMetavar = super().deep_copy(self)
        new_mvar.cursor_pos = self.cursor_pos
        if self.is_marked:
            new_mvar.mark()
        return new_mvar

    @property
    def node(self):
        """
        Override super().node.
        """
        node = (self.assigned_math_object.node
                if self.assigned_math_object else self._node)
        return node

    @property
    def info(self):
        """
        Override super().children in case self has a assigned_math_object.
        """
        info = (self.assigned_math_object.info
                if self.assigned_math_object else self._info)
        return info

    @property
    def children(self):
        """
        Override super().children in case self has a assigned_math_object.
        """
        children = (self.assigned_math_object.children
                    if self.assigned_math_object else self._children)
        return children

    @classmethod
    def from_mvar(cls, mvar: MetaVar, parent=None):
        marked_mvar = cls(math_type=mvar.math_type)
        marked_mvar.parent = parent
        marked_mvar.assigned_math_object = mvar.assigned_math_object
        return marked_mvar

    def delete(self):
        """
        FIXME: what is the desired behavior?
        """
        if self.assigned_math_object:
            self.assigned_math_object = None
            if isinstance(self.math_type, MetaVar):
                self.math_type.assigned_math_object = None
            return True


class MarkedBoundVar(BoundVar, MarkedPatternMathObject):
    """
    A BoundVar that can be marked.
    """

    def __init__(self, node, info, children, math_type,
                 parent=None, deep_copy=False):
        name = info.get('name')
        lean_name = info.get('lean_name')
        if (not name or name == 'NO NAME') \
                and (lean_name and lean_name != 'NO NAME'):
            info['name'] = lean_name

        super().__init__(node, info, children, math_type, parent, deep_copy)

    @property
    def name(self):
        name = self.info.get('name')
        if name == 'NO NAME':
            lean_name = self.info.get('lean_name')
            name = '[' + lean_name + ']' if lean_name else '[?]'
        return name


MarkedPatternMathObject.populate_app_marked_patterns()


if __name__ == "__main__":
    s1 = "SUM(?1 , NUMBER/value=1)"
    # pmo = PatternMathObject.from_string(s1)
    # mpmo1 = MarkedPatternMathObject.from_pattern_math_object(pmo)
    mpmo = MarkedPatternMathObject.from_string(s1)
    mpmo.mark_first_mvar()
    child_ = mpmo.children[1]
    print(mpmo.to_display(format_='utf8'))
