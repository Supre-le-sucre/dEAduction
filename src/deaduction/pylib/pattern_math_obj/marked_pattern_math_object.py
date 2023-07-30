"""
marked_pattern_math_objects.py : provide the MarkedPatternMathObject class.

The trickiest thing here is an insertion algorithm in an expression tree.
In such a tree, every node has an ordered list of left and right children.
Here this list is induced by the latex_shape, with a choice of a main symbol.

Two cases:
(1) insertion at a non assigned metavar.
(2) insertion after a matched metavar.
 In any case, after a successful insertion, the marked node should
    - move to the first non assigned metavar of the inserted object,
    if any,
    - otherwise, stay in place. The cursor will indicate the place just after
    the (main symbol of) the inserted object.

Case (1) is easy: just check that types match.

Case (2) splits into the following sub-cases. Let (MO) denotes the matched
object after which the insertion takes place.

    (2a) The new node (NN) has a metavar left of its main symbol. Let (MVL)
    be the first metavar left of (NN). If (MVL) matches (MO), then (NN) be
    inserted at (MO)'s place, with (MO) becoming (MVL)'s matched object.
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

from deaduction.pylib.mathobj import MathObject
from deaduction.pylib.pattern_math_obj import PatternMathObject, MetaVar
from deaduction.pylib.math_display import MathDisplay

log = logging.getLogger(__name__)


class MarkedTree:
    """
    A tree with zero or one marked node. This is a mixin to build MathObjects
    with a marked node, which may be thought of as some sort of cursor.
    mark_first_mvar() should be called on creation of the tree (but not of
    every node, obviously).

    Every node in the tree is assumed to have a list of left and right
    children, which induces an infix order.
    """

    # Fixme: we need children as an attribute, but whose value is set by the
    # main class
    _children = []
    matched_math_object = None
    is_marked = False
    cursor_pos = None
    _has_marked_descendant = False

    def __init__(self, children=None, is_marked=False):
        # Fixme: useless?
        if children:
            self._children = children
        self.is_marked = is_marked

    @property
    def min_cursor_pos(self):
        return 0

    @property
    def max_cursor_pos(self):
        return 0

    @property
    def children(self):
        """
        Fake children, this should be overriden by all subclasses.
        """
        return []

    def cursor_pos_for_child(self, child):
        return None

    @property
    def left_children(self):
        return []

    @property
    def right_children(self):
        return []

    def is_metavar(self):
        pass

    def descendant_at_cursor_pos(self):
        pass

    @property
    def is_matched(self):
        return bool(self.matched_math_object)

    # def parent_of_marked_descendant(self):
    #     """
    #     Return the immediate parent of self.marked_descendant, if any.
    #     """
    #     for child in self.children:
    #         if child.is_marked:
    #             return self
    #         elif child.parent_of_marked_descendant():
    #             return child.parent_of_marked_descendant()

    def marked_descendant(self):
        """
        Return the marked descendant of self, if any.        
        """
        if self.is_marked:
            return self

        for child in self.children:
            marked_descendant = child.marked_descendant()
            if marked_descendant:
                self._has_marked_descendant = True
                return marked_descendant

    def left_descendants(self):
        """
        Return the list of descendants of self.left_children, in infix order.
        """
        l_list = []
        for child in self.left_children:
            l_list.extend(child.infix_list())
        return l_list

    def left_unmatched_descendants(self):
        left_d = self.left_descendants()
        lud = [mvar for mvar in left_d if mvar.is_metavar and
               not mvar.is_matched]
        return lud

    def right_unmatched_descendants(self):
        right_d = self.right_descendants()
        rud = [mvar for mvar in right_d if mvar.is_metavar and
               not mvar.is_matched]
        return rud

    def right_descendants(self):
        """
        Return the list of descendants of self.right_children, in infix
        order.
        """
        r_list = []
        for child in self.right_children:
            r_list.extend(child.infix_list())
        return r_list

    def infix_list(self):
        """
        Return the list of all nodes in self's tree in the infix order.
        """

        # if only_unmatched:
        #     if self.is_metavar() and not self.is_matched:
        #         maybe_self = [self]
        #     else:
        #         maybe_self = []
        # else:
        #     maybe_self = [self]

        i_list = (self.left_descendants()
                  + [self]
                  + self.right_descendants())

        return list(i_list)

    # def marked_infix_idx(self):
    #     if self.marked_descendant():
    #         return self.infix_list().index(self.marked_descendant())

    def right_of_marked_element(self, other) -> bool:
        """
        True iff other is right of marked element in self.infix list.
        """
        l = self.infix_list()
        if self.marked_descendant():
            m_idx = l.index(self.marked_descendant())
            o_idx = l.index(other)
            return m_idx < o_idx

    @property
    def has_marked_descendant(self) -> bool:
        return bool(self.marked_descendant())
        # if not self._has_marked_descendant:
        #     self._has_marked_descendant = bool(self.marked_descendant())
        #
        # return self._has_marked_descendant

    # def index_child_with_marked_descendant(self):
    #     i = 0
    #     for child in self.children:
    #         if child.has_marked_descendant:
    #             return i
    #         i += 1

    def child_with_marked_descendant(self):
        for child in self.children:
            if child.marked_descendant():
                return child

    def mark(self):
        self.is_marked = True
        # self.cursor_pos = 1
        self.set_cursor_at_main_symbol()

    def unmark(self):
        """
        Unmark self's marked node.
        """
        if self.is_marked:
            self.is_marked = False
        else:
            child = self.child_with_marked_descendant()
            if child:
                child.unmark()

    def next_from_marked(self):
        """
        Return the next node from marked descendant in the infix order.
        """
        i_list = self.infix_list()
        # print(i_list)
        marked_mvar = self.marked_descendant()
        if not marked_mvar:
            return None

        idx = i_list.index(marked_mvar)
        next_mvar = None
        # if not unmatched:
        if idx < len(i_list) - 1:
            next_mvar = i_list[idx + 1]
        # else:
        #     while idx < len(i_list) - 1 and i_list[idx].is_matched:
        #         idx += 1
        #     if not i_list[idx].is_matched:
        #         next_mvar = i_list[idx]

        return next_mvar

    def marked_is_at_end(self):
        il = self.infix_list()
        return self.marked_descendant() is il[-1]

    def move_marked_right(self):
        """
        Move the marked node to the next metavar in self if any. Return the 
        new marked metavar, or None.
        """

        next_mvar = self.next_from_marked()
        marked_mvar = self.marked_descendant()
        if marked_mvar and next_mvar:
            marked_mvar.unmark()
            next_mvar.mark()
            return next_mvar

    def move_marked_left(self):
        """
        Move the marked node to the previous metavar.
        """

        i_list = self.infix_list()
        marked_mvar = self.marked_descendant()
        idx = i_list.index(marked_mvar)

        if idx > 0:
            new_mvar = i_list[idx - 1]
            marked_mvar.unmark()
            new_mvar.mark()
            return new_mvar

    def move_up(self):
        # FIXME
        if self.is_marked:
            return None
        elif self.has_marked_descendant:
            marked_child = self.child_with_marked_descendant()
            if marked_child:
                if marked_child.is_marked:
                    marked_child.unmark()
                    self.mark()
                    return self
                else:
                    return marked_child.move_up()

    def move_right_to_next_unmatched(self):
        """
        Move the marked node to the next unmatched mvar, if any.
        """

        i_list = self.infix_list()
        idx = i_list.index(self)
        r_list = i_list[idx:]
        unmatched = [item for item in r_list if not item.is_matched]
        if not unmatched:
            # No unmarked mvar  right of self
            return

        self.move_marked_right()
        while self.marked_descendant().is_matched:
            self.move_marked_right()

    def cursor_is_at_end(self):
        """
        True iff no cursor pos may not be increased.
        In CalculatorController, right arrow should be disabled.
        """

        # (1) Test child
        if not self.is_marked:
            child = self.child_with_marked_descendant()
            if not child.cursor_is_at_end():
                return False

        # (2) Test self
        return self.cursor_pos and self.cursor_pos == self.max_cursor_pos

    def cursor_is_at_beginning(self):
        """
        True iff no cursor pos may not be deacreased.
        In CalculatorController, left arrow should be disabled.
        """

        # (1) Test child
        if not self.is_marked:
            child = self.child_with_marked_descendant()
            if not child.cursor_is_at_beginning():
                return False

        # (2) Test self
        return self.cursor_pos and self.cursor_pos == self.min_cursor_pos

    def set_cursor_at_beginning(self):
        """
        Set cursor_pos and marked node at first position in self's subtree.
        """
        self.cursor_pos = 1
        child = self.descendant_at_cursor_pos()
        if not child:
            self.mark()
        else:
            assert isinstance(child, MarkedTree)
            child.set_cursor_at_beginning()

    def set_cursor_at_end(self):
        """
        Set cursor_pos and marked node at last position in self's subtree.
        """
        self.cursor_pos = self.max_cursor_pos
        child = self.descendant_at_cursor_pos()
        if not child:
            self.mark()
        else:
            assert isinstance(child, MarkedTree)
            child.set_cursor_at_end()

    def increase_cursor_pos(self):
        """
        Increase cursor position by 1 if possible,
        modify marked node if needed, and return marked node.
        Return None if increasing is not possible.
        """

        # (1) Try to increase marked descendants
        if not self.is_marked:
            child = self.child_with_marked_descendant()
            assert isinstance(child, MarkedTree)
            success = child.increase_cursor_pos()
            if success:
                return success

        # (3) Self is marked or child at end: increase self's cursor_pos
        # and modify marked node
        if self.cursor_pos < self.max_cursor_pos:
            self.cursor_pos += 1
            child = self.descendant_at_cursor_pos()
            if child:
                # Cursor at beginning of a new marked node
                assert isinstance(child, MarkedTree)
                child.set_cursor_at_beginning()
                return child.marked_descendant()
            else:
                # New marked node is self
                self.mark()
                return self
        else:
            # End of self reached
            self.unmark()
            self.cursor_pos = None
            return None

    def decrease_cursor_pos(self):
        """
        Increase cursor position by 1 if possible,
        modify marked node if needed, and return marked node.
        Return None if increasing is not possible.
        """

        # (1) Try to decrease marked descendants
        if not self.is_marked:
            child = self.child_with_marked_descendant()
            success = child.decrease_cursor_pos()
            if success:
                return success

        # (3) Self is marked or child at end: increase self's cursor_pos
        # and modify marked node
        if self.cursor_pos > self.min_cursor_pos:
            self.cursor_pos -= 1
            child = self.descendant_at_cursor_pos()
            if child:
                # Cursor at end of a new marked node
                assert isinstance(child, MarkedTree)
                child.set_cursor_at_end()
                return child.marked_descendant()
            else:
                # New marked node is self
                return self
        else:
            # End of self reached
            self.cursor_pos = None
            return None

    def set_cursor_pos_at_child(self, child):
        idx = self.cursor_pos_for_child(child)
        self.cursor_pos = idx

    def mark_child(self, child):
        self.set_cursor_pos_at_child(child)
        child.mark()

    def set_cursor_at_main_symbol(self) -> bool:
        # TODO in derived classes
        pass

    def set_cursor_at_main_symbol_of(self, mvar) -> bool:
        """
        Mark mvar, and recursively set cursor at main symbol of mvar (or at
        end if no main symbol) and return True in case of success.
        """

        if self is mvar:
            self.mark()
            self.set_cursor_at_main_symbol()
            return True

        for child in self.children:
            assert isinstance(child, MarkedTree)
            success = child.set_cursor_at_main_symbol_of(mvar)
            if success:
                self.set_cursor_pos_at_child(child)
                return True
            else:
                self.cursor_pos = None

        print(f"Unable to set cursor at ms of {mvar}")

    def move_after_insert(self, inserted_mvar):
        """
        This method is supposed to be called just after an insertion involving
        the marked node. It tries to move the marked node down to the first
        unmatched mvar, or else to the next unmatched mvar. It returns the
        new marked mvar if any.
        """

        self.marked_descendant().unmark()
        # # (1) Try marked_mvar:
        # marked_mvar = self.marked_descendant()
        # if marked_mvar and not marked_mvar.is_matched:
        #     success = self.set_cursor_at_main_symbol_of(marked_mvar)
        #     # if success:
        #     #     print(f"setting cursor at {marked_mvar}")
        #     # else:
        #     #     print(f"Unable to set cursor at {marked_mvar}")
        #     return marked_mvar

        # (2) Try ALL children of marked mvar:
        for child in inserted_mvar.children:
            if child.is_metavar and not child.is_matched:
                child.mark()
                success = self.set_cursor_at_main_symbol_of(child)
                # self.mark_child(child)
                # if success:
                #     print(f"setting cursor at {child}")
                # else:
                #     print(f"Unable to set cursor at {child}")
                return child

        # # (3) Move right
        # if not self.cursor_is_at_end():
        #     return self.increase_cursor_pos()

        # (3) Set cursor at self main symbol
        inserted_mvar.mark()
        self.set_cursor_at_main_symbol_of(inserted_mvar)

    def lineage_from(self, descendant) -> []:
        if self is descendant:
            return [self]
        else:
            for child in self.children:
                child_lineage = child.lineage_from(descendant)
                if child_lineage:
                    return child_lineage + [self]

    def marked_lineage_from(self) -> []:
        if self.is_marked:
            return [self]
        else:
            for child in self.children:
                child_lineage = child.marked_lineage_from()
                if child_lineage:
                    return child_lineage + [self]

    def path_from_marked_to_next(self) -> ():
        """
        Return the two components of the path from the unique marked
        descendant to the next node in the infix order, more precisely both
        upward paths from node to the common ancestor. The common ancestor is
        included in both paths.
        """
        marked_l = self.marked_lineage_from()
        if not marked_l:
            return [], []
        next_ = self.next_from_marked()
        if not next_:
            path = marked_l, [marked_l[-1]]
        else:
            next_l = self.lineage_from(next_)
            common_ancestor = self  # Useless
            while next_l and marked_l and next_l[-1] is marked_l[-1]:
                common_ancestor = marked_l.pop()
                next_l.pop()
            # next_l.reverse()
            path = marked_l + [common_ancestor],  next_l + [common_ancestor]

        return path


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

    def main_shape_symbol(self) -> (int, str):
        """
        Return main symbol of self, if any, and idx of main symbol in
        latex_shape.
        """
        shape = self.latex_shape()
        return MathDisplay.main_symbol_from_shape(shape)

    @property
    def left_children(self):
        shape = self.latex_shape()
        l_nb, r_nb = MathDisplay.left_right_children(shape)
        l_children = [self.children[i] for i in l_nb]
        # r_children = [self.children[i] for i in r_nb]
        return l_children

    @property
    def right_children(self):
        shape = self.latex_shape()
        l_nb, r_nb = MathDisplay.left_right_children(shape)
        # l_children = [self.children[i] for i in l_nb]
        r_children = [self.children[i] for i in r_nb]
        return r_children

    def set_cursor_at_main_symbol(self):
        idx, ms = self.main_shape_symbol()
        self.cursor_pos = idx + 1
        print(f"Setting cursor_pos at {idx+1} for {self}")

    def clear_all_matchings(self):
        for mvar in self.left_descendants() + self.right_descendants():
            if mvar.is_metavar():
                mvar.clear_matching()

    def insert_if_you_can(self, new_pmo, mvar, parent_mvar):
        """
        Try to insert new_pmo at mvar, as a left child if
        mvar is either a term of left_path or a term of right_path.
        """

        # Beware that match() method do assign the matched object!
        # do_insert=False not implemented

        assert isinstance(new_pmo, MarkedPatternMathObject)
        assert isinstance(mvar, MarkedMetavar)
        if parent_mvar:
            assert isinstance(parent_mvar, MarkedPatternMathObject)

        left = not (self.right_of_marked_element(mvar))

        pmo_display = new_pmo.to_display(format_='utf8')
        log.debug(f"Trying to insert {pmo_display} at {mvar}")
        log.debug(f"left = {left}")
        log.debug(f"Parent mvar = {parent_mvar}")

        # Priority test I (no priority test for common ancestor):
        #  Can new_pmo be a child of parent_mvar?
        if parent_mvar:
            if mvar in parent_mvar.left_children:
                # new_pmo would take the place of mvar, as a left child
                priority_test = (priority(parent_mvar.node, new_pmo.node) != '>')
            else:
                # new_pmo would take the place of mvar, as a right child
                priority_test = (priority(parent_mvar.node, new_pmo.node)
                                 not in ('=', '>'))
            if not priority_test:
                log.debug(f"--> Priority test I failed")
                return False
            else:
                log.debug("--> Priority test I passed")

        # Priority test II: Can mvar be a child of new_pmo?
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

        # Try to insert mvar.matched_math_object as a left/right descendant of
        # new_pmo
        if mvar.is_matched:
            match_child_test = False
            if left:
                log.debug(f"--> Trying to match left mvars of {pmo_display} "
                          f"with"
                          f" {mvar.matched_math_object}")
                for child_new_pmo in new_pmo.left_unmatched_descendants():
                    log.debug(f"----> {child_new_pmo} match?")
                    if child_new_pmo.match(mvar.matched_math_object):
                        # NB: matched_math_object now assigned to child_new_pmo
                        log.debug("yes!")
                        match_child_test = True
                        break
            else:
                log.debug(f"--> Trying to match right mvars of {pmo_display} with"
                          f" {mvar.matched_math_object}")
                for child_new_pmo in new_pmo.right_unmatched_descendants():
                    log.debug(f"----> {child_new_pmo} match?")
                    if child_new_pmo.match(mvar.matched_math_object):
                        log.debug("yes!")
                        match_child_test = True
                        break
            if not match_child_test:
                log.debug("-->Child don't match.")
                return False

        # Additional refactoring for common ancestor only (?):
        # Some of its children may be at the wrong side of new_pmo in the
        # infix order
        if not parent_mvar and mvar.is_matched:  # (mvar is the common ancestor)
            dubious_children = mvar.matched_math_object.children

            if left:
                # mvar.matched_mo has been inserted on the left of new_pmo
                # move bad children of this to the right mvar of new_pmo,
                # trying successively all right descendant of new_pmo
                mvars = new_pmo.right_unmatched_descendants()
                bad_children = [child for child in dubious_children
                                if self.right_of_marked_element(child)]
                if bad_children:
                    display = [child.to_display(format_='utf8')
                               for child in bad_children]
                    log.debug(f"--> Bad children: {display}")
                while bad_children:
                    child = bad_children.pop(0)
                    pmo_mvar = None
                    while mvars:
                        pmo_mvar = mvars.pop(0)
                        math_child = child.matched_math_object
                        if math_child and pmo_mvar.match(math_child):
                            # Success for this child!
                            child.clear_matching()
                            break
                    if pmo_mvar and not pmo_mvar.is_matched:
                        # last mvar did not match
                        return False
            else:
                mvars = new_pmo.left_unmatched_descendants()
                bad_children = [child for child in dubious_children
                                if not self.right_of_marked_element(child)]
                if bad_children:
                    display = [child.to_display(format_='utf8')
                               for child in bad_children]
                    log.debug(f"--> Bad children: {display}")
                while bad_children:
                    child = bad_children.pop(0)
                    pmo_mvar = None
                    while mvars:
                        pmo_mvar = mvars.pop(0)
                        math_child = child.matched_math_object
                        if math_child and pmo_mvar.match(math_child):
                            # Success for this child!
                            child.clear_matching()
                            break
                    if pmo_mvar and not pmo_mvar.is_matched:
                        # last mvar did not match
                        return False

        # Last test: new_pmo match mvar?
        mvar.clear_matching()
        log.debug(f"Last test: try to match {pmo_display} with {mvar}")
        match_mvar_test = mvar.match(new_pmo)
        if not match_mvar_test:
            return False

        return True

    def insert(self, new_pmo: PatternMathObject) -> bool:
        """
        Try to insert pmo in self's tree, so that pmo is just after the
        marked node in the infix order. In case of success, return the mvar
        at which insertion has been done.
        """

        left_path, right_path = self.path_from_marked_to_next()
        # right_path.reverse()

        for (sub_path, path) in [(left_path, left_path),
                                 (right_path[:-1], right_path)]:
            for idx in range(len(sub_path)):
                mvar = path[idx]
                if not mvar.is_metavar():
                    continue
                parent_mvar = path[idx+1] if idx < len(path) - 1 else None
                # Crucial: deepcopy pmo!!
                new_pmo_copy = MarkedPatternMathObject.deep_copy(new_pmo)
                success = self.insert_if_you_can(new_pmo_copy, mvar, parent_mvar)
                if success:
                    return mvar
                else:
                    new_pmo_copy.clear_all_matchings()

        # for idx in range(len(right_path[:-1])):
        #     mvar = right_path[idx]
        #     if not mvar.is_metavar():
        #         continue
        #     parent_mvar = right_path[idx+1]
        #     new_pmo_copy = MarkedPatternMathObject.deep_copy(new_pmo)
        #     success = self.insert_if_you_can(new_pmo_copy, mvar, parent_mvar)
        #     if success:
        #         return True
        #     else:
        #         new_pmo_copy.clear_all_matchings()

        # Try this:
        next_ = self.next_from_marked()
        if next_ and next_.is_metavar() and not next_.is_matched:
            pass
            # TODO: try next!

        # TODO: try automatic patterns

        # TODO: handle multiple patterns

    def insert_at_end(self, new_pmo: PatternMathObject) -> bool:
        i_list = self.infix_list()
        last_node = i_list[-1]
        path = self.lineage_from(last_node)
        for idx in range(len(path)):
            mvar = path[idx]
            if not mvar.is_metavar():
                continue
            parent_mvar = path[idx + 1] if idx < len(path) - 1 else None
            # Crucial: deepcopy pmo!!
            new_pmo_copy = MarkedPatternMathObject.deep_copy(new_pmo)
            success = self.insert_if_you_can(new_pmo_copy, mvar, parent_mvar)
            if success:
                return True
            else:
                new_pmo_copy.clear_all_matchings()

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
        'Delete' current marked metavar, i.e. remove matched_math_object.
        """
        return self.marked_descendant().delete()

    def latex_shape(self, is_type=False, text=False, lean_format=False):
        """
        Modify the latex shape to mark the main symbol, if self.is_marked.
        In particular, insert a tag at the place where a cursor should be 
        displayed.
        """
        shape = super().latex_shape(is_type=False,
                                    text=False,
                                    lean_format=False)
        if not self.is_marked:
            return shape

        marked_shape = MathDisplay.marked_latex_shape(shape)
        return marked_shape

    def descendant_at_cursor_pos(self):
        """
        Return the child or descendant of self at the given cursor pos in the
        latex_shape, if any ; otherwise return None.
        """

        cursor_pos = self.cursor_pos

        if cursor_pos is None:
            return None

        elif cursor_pos == 0:
            # Node should be the previous node in the infix order.
            return None

        latex_shape = self.latex_shape()
        if cursor_pos > self.max_cursor_pos:
            # Bad cursor pos.
            return None

        item = latex_shape[cursor_pos - 1]
        if isinstance(item, tuple) or isinstance(item, int):
            child = self.descendant(item)
            return child
        else:
            return None

    # def move_to_cursor_pos(self, cursor_pos):
    #     """
    #     Move the mark to the descendant at given cursor position.
    #     """
    #
    #     child = self.descendant_at_cursor_pos(cursor_pos)
    #     if child:
    #         self.marked_descendant().unmark()
    #         child.mark()
    #         return child

    @property
    def max_cursor_pos(self):
        return len(self.latex_shape())

    def cursor_pos_for_child(self, child):
        shape = self.latex_shape()
        if child in self.children:
            child_nb = self.children.index(child)
            if child_nb in shape:
                idx = shape.index(child_nb)
                return idx+1

    # def move_right(self):
    #     """
    #     Increase cursor_pos, and change the marked node if needed.
    #     Return the new_marked node in case of success
    #     """
    #
    #     success = None
    #     if not self.is_marked:
    #         success = self.marked_descendant().move_right()
    #         if not success:
    #             success = super().move_right()
    #
    #     elif self.cursor_pos < self.max_cursor():
    #         self.cursor_pos += 1
    #         success = self
    #
    #     else:
    #
    #     return success


class MarkedMetavar(MetaVar, MarkedPatternMathObject):
    """
    A Metavar which can be marked.
    """

    def __repr__(self):
        rep = super().__repr__()
        if self.is_marked:
            rep = '--> ' + rep
        return rep

    @property
    def matched_math_object(self):
        return self._matched_math_object

    @matched_math_object.setter
    def matched_math_object(self, math_object):
        self._matched_math_object = math_object

    @classmethod
    def deep_copy(cls, self):
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
        node = (self.matched_math_object._node
                if self.matched_math_object else self._node)
        return node

    @property
    def info(self):
        """
        Override super().children in case self has a matched_math_object.
        """
        info = (self.matched_math_object._info
                if self.matched_math_object else self._info)
        return info

    @property
    def children(self):
        """
        Override super().children in case self has a matched_math_object.
        """
        children = (self.matched_math_object._children
                    if self.matched_math_object else self._children)
        return children

    @classmethod
    def from_mvar(cls, mvar: MetaVar, parent=None):
        marked_mvar = cls(math_type=mvar.math_type)
        marked_mvar.parent = parent
        marked_mvar.matched_math_object = mvar.matched_math_object
        return marked_mvar

    # def insert_over_matched_math_object(self, pmo: PatternMathObject,
    #                                     lineage=None) -> bool:
    #     """
    #     See next method's doc.
    #     """
    #
    #     # (1) Special cases
    #     self_object = self.matched_math_object
    #     if self_object.math_type.is_number() or self_object.node == 'NUMBER':
    #         value = str(self_object.value)
    #         if pmo.math_type.is_number() or pmo.node == 'NUMBER':
    #             units = str(pmo.value)
    #             self_object.value = value + units
    #             return True
    #         elif pmo.node == 'POINT':
    #             if '.' not in value:
    #                 self_object.value = value + '.'
    #                 return True
    #             else:
    #                 return False

        # (2) If self_object and pmo both have children and have the same
        #  nb of children, try to replace.
        # if self_object.children and \
        #         len(self_object.children) == len(pmo.children):
        #     tests = [self.match(pmo)]
        #     for child, child_mvar in zip(self_object.children, pmo.children):
        #         if isinstance(child_mvar, MetaVar):
        #             tests.append(child_mvar.match(child))
        #     if all(tests):
        #         self.matched_math_object = pmo
        #         for child, child_mvar in zip(self_object.children,
        #                                      pmo.children):
        #             child_mvar.matched_math_object = child
        #         return True

        # # (3) Try to insert
        # mvar = pmo.first_mvar()
        # if not mvar:
        #     return False
        #
        # # (3a) Check parent priority, and maybe insert at parent
        # else:
        #     # FIXME: left or right children????
        #     if lineage:
        #         parent = lineage.pop()
        #         if hasattr(parent, "insert_over_matched_math_object"):
        #             # TODO: if not, try parent's parent
        #             # Compare priority of pmo and parent
        #             self_node = parent.node
        #             other_node = pmo.node
        #             prior = priority(self_node, other_node)
        #             if prior in ('=', '>'):
        #                 success = parent.insert_over_matched_math_object(pmo,
        #                                                                  lineage)
        #                 if success:
        #                     return True
        #
        # # (3b) Insert at self
        # match = mvar.match(self.matched_math_object)
        # if match:
        #     mvar.matched_math_object = self.matched_math_object
        #     self.matched_math_object = pmo
        #     return True
        # else:
        #     return False

    # def insert(self, math_object: PatternMathObject, lineage=None) -> bool:
    #     """
    #     Try to insert math_object in self. Return True in case of success,
    #     False otherwise.
    #     - If self does not have matched_math_object, just check that
    #     math_types match (to be improved: try automatic matching, e.g.
    #         f --> f(.) );
    #     - Otherwise, try to substitute matched_math_object with math_object
    #     by matching the matched_math_obj with the first mvar of math_object
    #     (to be improved: try automatic matching?)
    #     """
    #
    #     # Crucial: deepcopy math_object!!
    #     math_object = math_object.deep_copy(math_object)
    #
    #     if not self.matched_math_object:
    #         match = self.match(math_object)
    #         if match:
    #             self.matched_math_object = math_object
    #             return True
    #         else:
    #             # FIXME: insert an MVAR with math_object as first child?
    #             return False
    #
    #     else:
    #         return self.insert_over_matched_math_object(math_object, lineage)

    def delete(self):
        """
        FIXME: what is the desired behavior?
        """
        if self.matched_math_object:
            self.matched_math_object = None
            if isinstance(self.math_type, MetaVar):
                self.math_type.matched_math_object = None
            return True

    # def to_display(self, format_="html", text=False,
    #                use_color=True, bf=False, is_type=False,
    #                used_in_proof=False):
    #     # mmo = self.matched_math_object
    #     unmark = False
    #     mmo = None
    #     if mmo:
    #         assert isinstance(mmo, MarkedPatternMathObject)
    #         if self.is_marked and not mmo.is_marked:
    #             mmo.mark()
    #             unmark = True
    #         display = mmo.to_display(format_=format_, text=text,
    #                                  use_color=use_color, bf=bf,
    #                                  is_type=is_type)
    #         if unmark:
    #             mmo.unmark()
    #     else:
    #         display = MathObject.to_display(self, format_=format_, text=text,
    #                                         use_color=use_color, bf=bf,
    #                                         is_type=is_type)
    #
    #     return display

    # @classmethod
    # def mark_cursor(cls, yes=True):
    #     MathDisplay.mark_cursor = yes

    # def latex_shape(self, is_type=False, text=False, lean_format=False):
    #     """
    #     Modify the latex shape to mark the main symbol, if self.is_marked.
    #     """
    #     shape = super().latex_shape(is_type=False,
    #                                 text=False,
    #                                 lean_format=False)
    #     if not self.is_marked:
    #         return shape
    #
    #     marked_shape = MathDisplay.marked_latex_shape(self.node, shape)
    #     return marked_shape
    #

# def marked(item):
#     """
#     This method add a tag to the main symbol of a tuple representing a latex
#     shape.
#     FIXME: criterium and marking to be modified.
#     """
#     marked_item = ('*' + item if isinstance(item, str)
#                    else item)
#     return marked_item


if __name__ == "__main__":
    s1 = "SUM(?1 , NUMBER/value=1)"
    # pmo = PatternMathObject.from_string(s1)
    # mpmo1 = MarkedPatternMathObject.from_pattern_math_object(pmo)
    mpmo = MarkedPatternMathObject.from_string(s1)
    mpmo.mark_first_mvar()
    child_ = mpmo.children[1]
    print(mpmo.to_display(format_='utf8'))
