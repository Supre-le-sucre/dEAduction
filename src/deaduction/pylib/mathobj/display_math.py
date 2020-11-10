"""
##############################################
# display_math: display mathematical objects #
##############################################

Author(s)     : Frédéric Le Roux frederic.le-roux@imj-prg.fr
Maintainer(s) : Frédéric Le Roux frederic.le-roux@imj-prg.fr
Created       : 06 2020 (creation)
Repo          : https://github.com/dEAduction/dEAduction

Copyright (c) 2020 the dEAduction team

Contain the data for processing PropObj into a latex representation

The basic data for representing math objects is the latex_from_node dictionary.
It associates, to each MathObject.node attribute, the shape to display, e.g.
    "PROP_INCLUDED": [0, " \subset ", 1],
where the numbers refer to the MathObject's children.
The from_math_object method picks the right shape from this dictionary,
and then call the Shape.from_shape method.

TODO: explain utf8 and Lean

To implement a new node for display:
- for standards nodes, it suffices to add an entry in the latex_from_node
dictionary (and in the latex_to_ut8, utf8_to_lean, node_to_lean if
necessary). Those dictionaries are in display_data.py.

- for some specific constant, use the latex_from_constant_name dictionary
These constant are displayed through display_application,
e.g. APP(injective, f).

- for more specific nodes, one can define a new display function and call it
via the from_specific_node function.


 Note that the shape can include calls to some specific formatting functions,
 e.g.
    - display_application,
    - display_local_constant,
    - display_constant,
    - display_lambda


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
import types
from dataclasses import dataclass

import deaduction.pylib.logger              as logger
from deaduction.config                      import _

from .MathObject import MathObject
from deaduction.pylib.mathobj.give_name     import give_local_name
from .display_data import ( latex_from_constant_name,
                            text_from_node,
                            lean_from_node,
                            latex_from_node,
                            latex_to_utf8_dic,
                            latex_to_lean_dic,
                            have_bound_vars,
                            needs_paren
                            )

log = logging.getLogger(__name__)


@dataclass
class Shape:
    """class used to compute the display of some MathObject
    Example: if node = 'PROP_EQUAL',
    - as a first step the shape will have display [0, " = ", 1]
    (as a result of the from_math_object() class method)
    - as a second step, this display will be expanded with '0' and '1' replaced
    by the shapes of the children (by the from_shape() method)

    To distinguish expanded vs non expanded forms, the latter is usually named
    "shape" instead of "shape"
    """
    display:                    list
    math_object:                MathObject
    format_:                    str         = 'latex'
    text_depth:                 int         = 0
    supplementary_children:     list        = None

    @classmethod
    def from_math_object(cls,
                         math_object: MathObject,
                         format_="utf8",
                         text_depth=0
                         ):
        """
        This function essentially looks in the format_from_node
        dictionary, and then pass the result to the from_shape method
        which recursively compute the display.

        :param math_object: the MathObject instance to be displayed
        :param format_:     "utf8", "latex", "lean"
        :param text_depth:  when format_="latex" or "utf8", only the symbols at
                            level less than text_depth in the tree are replaced
                            by text. So for instance   "text_depth=0"
                            uses only symbols ; this is used to display context

        :return:            an (expanded) shape, whose display attribute is a
                            structured string, to be transform into a string by
                            the structured_display_to_string function
        """
        # log.debug(f"Computing math display of {math_object}")
        if format_ not in ["latex", 'utf8', "lean"]:
            return shape_error(f"unknown format = {format_}")

        node = math_object.node
        if format_ == "lean" and node in lean_from_node:
            raw_shape = Shape(display=lean_from_node[node],
                              math_object=math_object,
                              format_=format_)

        elif node in text_from_node and text_depth > 0:
            raw_shape = Shape(display=text_from_node[node],
                              math_object=math_object,
                              format_=format_)

        elif node in latex_from_node:
            raw_shape = Shape(display=latex_from_node[node],
                              math_object=math_object,
                              format_=format_)

        else:  # node not found in dictionaries: try specific methods
            raw_shape = Shape.from_specific_nodes(math_object,
                                                  format_,
                                                  text_depth
                                                  )

        # From now on shape is an instance of Shape
        if format_ == "lean" and node not in lean_from_node:
            raw_shape.latex_to_lean()
        elif format_ == "utf8":
            raw_shape.latex_to_utf8()
        elif format == "latex" and text_depth <= 0:
            raw_shape.text_to_latex()

        # TODO: manage subscript, exponents, and \text
        # for elements of raw_shape that are strings (not list)
        # finally expand raw_shape
        return raw_shape.expand_from_shape()

    @classmethod
    def from_specific_nodes(cls, math_object, format_, text_depth):
        """
        case of node in specific_node_dic,
        or  "SET_UNIVERSE" ->
            "SET_COMPLEMENT": ""

            :param math_object:
            :param format_:
            :param text_depth:

            :return: a raw shape
        """
        node = math_object.node
        display = []
        shape = None
        if node == "APPLICATION":
            # this one returns a shape, to handle supplementary children
            shape = shape_from_application(math_object, format_)
        elif node in ["LOCAL_CONSTANT", "CONSTANT"]:
            # return display, not shape
            display = display_constant(math_object, format_)
            # TODO: display or shape ?
        elif node == "LAMBDA":
            display = display_lambda(math_object, format_)
        elif node == "SET_UNIVERSE":
            display = [math_object.math_type_child_name()]
        elif node == "SET_COMPLEMENT":
            universe = math_object.math_type_child_name()
            display = [universe, r" \backslash ", 0]
        if display:
            shape = Shape(display,
                          math_object,
                          format_,
                          text_depth)
        if shape:
            return shape
        else:
            return shape_error("unknown object")

    def expand_from_shape(self):
        # TODO: take care of supplementary children
        """
        Replace each element of shape with its display.
        Ex of shape: [0, " = ", 1]
        For more examples, see values of the latex_from_node dictionary.
            - numbers refer to children, and will be replaced by the
                corresponding display,
            - strings are displayed as such for utf8, (see exceptions below)
            - functions are called
        Exceptions for strings:
            - "_child#" code for subscript version of child number #
            - some items may already be in displayable form

        :return: a modified instance of Shape
        """
        # log.debug(f"Trying to display from shape {shape}")
        # todo: supplementary children, negative indices
        display =       self.display
        math_object =   self.math_object
        format_ =       self.format_
        text_depth =    self.text_depth

        # add supplementary children (in case node = "APPLICATION")
        children = math_object.children
        if self.supplementary_children:
            children += self.supplementary_children

        expanded_display = []
        counter = -1
        for item in display:
            counter += 1
            display_item = "¿**"
            # specific display
            if isinstance(item, types.FunctionType):
                # e.g. item = display_constant, display_application, ...
                display_item = item(math_object, format_)
            # integers code for children
            elif isinstance(item, int):
                if -len(math_object.children) <= item < len(
                                                    math_object.children):
                    child = math_object.children[item]
                    display_item = Shape.from_math_object(
                                        math_object=child,
                                        format_=format_,
                                        text_depth=text_depth - 1
                                                          )
                    # with brackets?
                    if text_depth < 1:
                        if needs_paren(math_object, item):
                            display_item = ['('] + display_item + [')']
                else:
                    display_item = '*child out of range*'
            # strings
            elif isinstance(item, str):
                if item.startswith("_child"):
                    number = int(item[len("_child"):])
                    child = math_object.children[number]
                    pre_display_item = Shape.from_math_object(
                                            math_object=child,
                                            format_=format_,
                                            text_depth=text_depth - 1
                                                              )
                    display_item = global_subscript(pre_display_item)  # TODO
                elif item.find("∈") != -1 and isinstance(display[counter + 1], int):
                    # replace "∈" with ":" in some cases
                    type_ = math_object.children[display[counter + 1]]
                    symbol = display_belongs_to(type_, format_, text_depth)
                    display_item = item.replace('∈', symbol)
                else:
                    pass  # todo: remove if useless
                    #display_item = string_to_latex(item)

            elif isinstance(item, list):
                display_item = item
            expanded_display.append(display_item)

        if len(expanded_display) == 1:
            expanded_display = expanded_display[0]

        self.display = expanded_display

    def latex_to_utf8(self):
        """call latex_to_utf8_dic to replace each item in self by utf8
        version"""
        display = self.display
        for string, n in zip(display, range(len(display))):
            if isinstance(string, str):
                striped_string = string.strip()  # remove spaces
                if striped_string in latex_to_utf8_dic:
                    utf8_string = latex_to_utf8_dic[striped_string]
                    string.replace(striped_string, utf8_string)
                    display[n] = string

    def latex_to_lean(self):
        """call latex_to_lean_dic"""
        display = self.display
        for string, n in zip(display, range(len(display))):
            if isinstance(string, str):
                striped_string = string.strip()  # remove spaces
                if striped_string in latex_to_lean_dic:
                    lean_string = latex_to_lean_dic[striped_string]
                    string.replace(striped_string, lean_string)
                    display[n] = string

    def text_to_latex(self):
        """for each string item in self which is pure text,
        add "\text{}" around item"""
        display = self.display
        for item, n in zip(display, range(len(display))):
            if isinstance(item, str):
                latex_item = string_to_latex(item)
                display[n] = latex_item


#########################################################################
#########################################################################
# Specific display functions, called by from_specific_node               #
#########################################################################
#########################################################################
# display_constant for "CONSTANT" and "LOCAL_CONSTANT"
# shape_from_application for "APPLICATION"
# display_set_family (called by display_constant when needed)
# display_lambda
def shape_from_application(math_object,
                           format_,
                           supplementary_children=None
                           ) -> Shape:
    """
    display for node 'APPLICATION'
    This is a very special case, includes e.g.
    - APP(injective, f)             -> f is injective
    - APP(APP(composition, f),g)    -> f \circ g
    - APP(f, x)                     -> f(x)

    :param format_:
    :param math_object:
    :param supplementary_children: use to transform
                                            APP(APP(...APP(x0,x1),...,xn)
                                    into
                                            APP(x0, x1, ..., xn)
    """
    if supplementary_children is None:
        supplementary_children = []
    application = math_object.children[0]
    second_child = math_object.children[1]
    supplementary_children.insert(0, second_child)

    # (1) call the function recursively until all args are in
    # supplementary_children
    if application.node == "APPLICATION":
        return shape_from_application(application,
                                      format_,
                                      supplementary_children)

    display = []

    # (2) case of index notation: sequences, set families
    if application.math_type.node in ["SET_FAMILY", "SEQUENCE"]:
        # we DO NOT call display for application because we just want
        #  "E_i",       but NOT       "{E_i, i ∈ I}_i"      !!!
        # We just take care of two cases of APP(E,i) with either
        # (1) E a local constant, or
        # (2) E a LAMBDA with body APP(F, j) with F local constant
        name = 0  # default case
        if application.node == "LOCAL_CONSTANT":
            name = application.display_name()
        if application.node == "LAMBDA":
            body = application.children[2]
            if body.node == "APPLICATION" and body.children[0].node == \
                    "LOCAL_CONSTANT":
                name = body.children[0].display_name()
        display = [name, "_child1"],

    # (3) case of constants, e.g. APP( injective, f)
    elif application.node == "CONSTANT":
        name = application.display_name()
        if name in latex_from_constant_name:
            display = latex_from_constant_name[name]
        else:  # standard format
            display = latex_from_constant_name['STANDARD']

    # (4) finally: functional notation
    if not display:
        display = [0, "(", 1, ")"]

    raw_shape = Shape(display=display,
                  math_object=math_object,
                  format_=format_,
                  supplementary_children=supplementary_children
                  )
    return raw_shape


def display_constant(math_object, format_) -> list:
    """
    Display for nodes 'CONSTANT' and 'LOCAL_CONSTANT'
    NB: expressions APP(constant, ...) are treated directly in
    display_application

    :param math_object:
    :param format_:
    :return:            'display' list
    """
    display = "*CST*"
    if hasattr(math_object.math_type,"node"):
        if math_object.math_type.node == "SET_FAMILY":
            return display_set_family(math_object, format_)
        elif math_object.math_type.node == "SEQUENCE":
            return "*SEQ*"  # todo
    display = [math_object.display_name()]
    return display


# the following is not called directly, but via display_constant
def display_sequence(math_object, format_="latex") -> list:
    # TODO: on the model of display_set_family
    pass


def display_set_family(math_object, format_="latex") -> list:
    """
    e.g. if E: I -> set X,
    then compute a good name for an index in I (e.g. 'i'),
    and display "{E_i, i in I}"

    WARNING: this bound variable is not referenced anywhere, in particular
    it will not appear in extract_local_vars.
    """
    # first find a name for the bound var
    name = math_object.display_name()
    math_type_name = math_object.math_type_child_name()
    bound_var_type = math_object.math_type.children[0]
    index_name = give_local_name(math_type=bound_var_type,
                                 body=math_object)
    display = [r"\{", name, "_", index_name, ', ',
               index_name, r" \in ", math_type_name, r"\}"]
    return display


def display_lambda(math_object, format_="latex") -> list:
    """
    format for lambda expression, e.g.
    - set families with explicit bound variable
        lambda (i:I), E i)
        encoded by LAMBDA(I, i, APP(E, i)) --> "{E_i, i ∈ I}"
    - sequences,
    - mere functions
        encoded by LAMBDA(X, x, APP(f, x))  --> "f"
    - anything else is displayed as "x ↦ f(x)"
    """
    display = []
    math_type = math_object.math_type
    _, var, body = math_object.children
    if math_type.node == "SET_FAMILY":
        display = [r'\{', 2, ', ', 1, r' \in ', 0, r'\}']
    elif math_type.node == "SEQUENCE":
        shape = ['(', 2, ')', '_{', 1, r' \in ', 0, '}']
        # todo: manage subscript
    elif body.node == "APPLICATION" and body.children[1] == var:
        # object is of the form x -> f(x)
        mere_function = body.children[0]  # this is 'f'
        # we call the whole process in case 'f' is not a LOCAL_CONSTANT
        display = Shape.from_math_object(mere_function, format_).display
    else:  # generic display
        display = [1, '↦', 2]
    if not display:
        display = ['*unknown lambda*']
    return display


##################
# other displays #
##################
# This function is called directly by MathObject.to_display
# Thus it has to return an EXPANDED shape
def display_math_type_of_local_constant(math_type, format_, text_depth=0) \
        -> Shape:
    """
    process special cases, e.g.
    1) x : an element of X"
    (in this case   math_object represents x,
                    math_object.math_type represents X,
                    and the analysis is based on the math_type of X.
    2) A : a subset of X
    """
    #######################################################
    # special math_types for which display is not the same #
    #######################################################
    display = []
    if hasattr(math_type, 'math_type') \
            and hasattr(math_type.math_type, 'node') \
            and math_type.math_type.node == "TYPE":
        name = math_type.info["name"]
        display = [_("an element of") + " ", name]
    elif hasattr(math_type, 'node') and math_type.node == "SET":
        display = [_("a subset of") + " ", 0]
    if display:
        raw_shape = Shape(display=display,
                      math_object=math_type,
                      format_=format_,
                      text_depth=text_depth
                      )
        return raw_shape.expand_from_shape()

    #################
    # usual method  #
    #################
    else:  # return usual expanded shape
        return Shape.from_math_object(math_object=math_type,
                                      format_=format_,
                                      text_depth=text_depth)


######################
######################
# auxiliary displays #
######################
######################
def display_belongs_to(math_type, format_, text_depth, belonging=True) -> str:
    """
    compute the adequate shape for display of "x belongs to X", e.g.
    - generically, "x∈X"
    - specifically,
        - "f : X -> Y" (and not f ∈ X-> Y),
        or "f is a function from X to Y"
        - "P: a proposition" (and not P ∈ a proposition),
        FIXME
    """
    #log.debug(f"display ∈ with {math_type}, {format_}, {text_depth}")
    if format_ == "text+utf8" and text_depth > 0:
        if math_type.node == "PROP" \
                or (math_type.node == "FUNCTION" and text_depth > 1):
            symbol = _("is")
        elif math_type.node == "FUNCTION" and text_depth == 1:
            symbol = ":"
        else:
            symbol = _("belongs to")
    else:
        if math_type.node in ["FUNCTION", "PROP"]:
            symbol = ":"
        else:
            symbol = "∈"
    return symbol


def string_to_latex(string: str):
    """Put the "\text" command around pure text for Latex format"""
    if string.isalpha():
        string = r"\text{" + string + r"}"
    return string


#######################################
#######################################
# some tools for manipulating strings #
#######################################
#######################################
def subscript(index, format_):
    # TODO !!
    return "_" + index


def text_to_subscript(structured_string):
    """
    recursive version, for strings to be displayed use global_subscript instead
    :param structured_string: list of sturctured string
    :return: the structured string in a subscript version if available,
    or the structured string unchanged if not,
    and a boolean is_subscriptable
    """
    normal_list = "0123456789" + "aeioruv"
    subscript_list = "₀₁₂₃₄₅₆₇₈₉" + "ₐₑᵢₒᵣᵤᵥ"
    # subscript_list = "₀₁₂₃₄₅₆₇₈₉" + "ₐₑᵢⱼₒᵣᵤᵥₓ"
    is_subscriptable = True
    if isinstance(structured_string, list):
        sub_list = []
        for item in structured_string:
            sub, bool = text_to_subscript(item)
            if not bool:  # not subscriptable
                return structured_string, False
            else:
                sub_list.append(sub)
        return sub_list, True

    # from now on structured_string is assumed to be a string
    for letter in structured_string:
        if letter not in normal_list:
            is_subscriptable = False
    if is_subscriptable:
        subscript_string = ""
        for l in structured_string:
            subscript_string += subscript_list[normal_list.index(l)]
    else:
        subscript_string = structured_string
    return subscript_string, is_subscriptable


def global_subscript(structured_string):
    sub, is_subscriptable = text_to_subscript(structured_string)
    if is_subscriptable:
        return sub
    else:
        return ['_'] + [sub]
        # [sub] necessary in case sub is an (unstructured) string


def display_text_quant(math_object, format_, text_depth):
    """
    Compute a smart text version of a quantified sentence.

    :param math_object: a math object with node "QUANT_∀", "QUANT_∃", or
                        "QUANT_∃!".
    :param format_:     "text+utf8"
    :param text_depth:  see display_math_object
    """
    #TODO
    pass


def display_text_belongs_to(math_object, format_, text_depth):
    """Compute a smart version of

    :param math_object: a math object whose node is "PROP_BELONGS"
    :param format_:     "text+utf8"
    :param text_depth:  see display_math_object
    """
    #TODO
    pass


def shape_error(message: str, math_object= None, format_ = "", text_depth=0):
    shape = Shape(['*' + message + '*'],
                  math_object,
                  format_,
                  text_depth)
    return shape


##########
# essais #
##########
if __name__ == '__main__':
    logger.configure()
