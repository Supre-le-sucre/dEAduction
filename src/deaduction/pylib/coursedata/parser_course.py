"""
# parser_course.py : Parse lean course to extract pertinent data

1) A lean file is parsed according to the grammar described in the "rules"
string below.
2) Parsimonious.grammar computes a tree description of the file
according to this grammar.
3) Then the tree is visited and information is collected at each pertinent
node through the methods below. The information is stored in
course_history, a list that contains all pertinents events:
- end_of_line,
- opening and closing of namespaces (and their metadata),
- statements (definitions, theorems, exercises) and their metadata.
The variable 'data' is a dictionary which is used locally to collect
information that will be stored with each event: an event is a couple
(type_of_event: str, data). For instance for statements, the data is a
dictionary that contains all the metadata associated to the statement.
The course_history is processed by course.py.


Author(s)     : Frédéric Le Roux frederic.le-roux@imj-prg.fr
Maintainer(s) : Frédéric Le Roux frederic.le-roux@imj-prg.fr
Created       : 08 2020 (creation)
Repo          : https://github.com/dEAduction/dEAduction

Copyright (c) 2020 the dEAduction team

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

from pathlib import Path
from typing import List
from parsimonious.grammar import Grammar
from parsimonious.nodes import NodeVisitor
import logging

import deaduction.pylib.logger as logger

log = logging.getLogger(__name__)

############################
# Some aspect of the rules #
############################
# statement = starts with "lemma" + "definition." / "theorem." / "exercise." ;
#           lean_statement includes variables definition,
#           must end with ":=".

# test somewhere else that core_proof does not contain "hypo_analysis"
# it is important that all ends of line are detected by the end_of_line node

# Does not support proof-like 'begin ... end' string in a comment between
# statement and proof
# nor "lemma exercise." in a docstring comment

# metadata = starts with /- dEAduction,
#           must end with a line starting with "-/".
# metadata are optional. The proof of a definition can be before or after
# the metadata but the interlude between statement and metadata cannot
# contain the words "lemma" nor "namespace"
# for exercises, the optional metadata must come immediately after the
# statement, and the begin/end environment must come immediately after
# metadata or statement
# metadata field names are made of anything but spaces
# metadata field contents are indented, and at least one line (maybe empty)
# if the format is not met then the statement will not appear in the list

from typing import List, Tuple
import logging

import deaduction.pylib.logger as logger

log = logging.getLogger(__name__)

course_rules = """course = 
            (something_else metadata)?
            (something_else? 
             space_or_eol*   (namespace_open_or_close / statement))+
            (something_else space_or_eol*)?
"""

something_else_rules = """
something_else = (line_comment / 
((non_coding any_char_but_eol)* end_of_line)  )*
non_coding = !namespace_open_or_close !statement !metadata
"""

namespace_rules = """
namespace_open_or_close = open_namespace / close_namespace

open_namespace = "namespace" space+ namespace_identifier
                (interlude metadata)?

close_namespace = "end" space+ namespace_identifier
"""

statement_rules = """
statement = (exercise / definition_or_theorem)

exercise  = "lemma" space_or_eol+
                    exercise_name space_or_eol+
                    lean_statement
                separator_equal_def
                    (space_or_eol+ metadata)?
                    space_or_eol+ proof

definition_or_theorem = "lemma" space_or_eol+
                    (definition_name / theorem_name) space_or_eol+
                    lean_statement
                separator_equal_def
                    (interlude metadata)?
                    
    definition_name = "definition." identifier 
    theorem_name = "theorem." identifier
    exercise_name = "exercise." identifier
    
    lean_statement = ((!separator_equal_def any_char_but_eol)* end_of_line*)+
    
    separator_equal_def = ":="
"""

proof_rules = """
proof = begin_proof core_proof end_proof
    begin_proof = "begin" space_or_eol 
    core_proof = ((!begin_proof !end_proof any_char_but_eol*) end_of_line)*
    end_proof = "end" space_or_eol
"""

metadata_rules = """
metadata =  open_metadata
            metadata_field+
            close_metadata
            
    metadata_field = metadata_field_name  end_of_line
                    ((space+ metadata_field_content end_of_line) /end_of_line)+
        
        metadata_field_name = (!space !close_metadata any_char_but_eol)+ space*
        metadata_field_content = !close_metadata any_char_but_eol*
    open_metadata = "/-" space+ "dEAduction" space_or_eol+
    close_metadata = "-/"
"""

interlude_rules = """
interlude = ((!metadata !"lemma" !"namespace" any_char_but_eol)* 
                    space_or_eol*)*
"""
# may be empty

line_comment_rules = """
line_comment = "--" any_char_but_eol* end_of_line
"""

identifier_rules = """
identifier           = identifier_start (identifier_rest)*
namespace_identifier = identifier_start (identifier_rest)*
    identifier_start = letter / "_"
    identifier_rest = identifier_start / digits
"""

basic_rules = """
any_char_but_eol = ~r"."
letter = ~r"[a-zA-Z]"
digits = ~r"[0-9']"
space_or_eol = end_of_line / ~r"\s"
space = !end_of_line ~r"\s"
end_of_line = "\\n"
"""

rules = course_rules + something_else_rules \
        + namespace_rules \
        + statement_rules + proof_rules + interlude_rules \
        + metadata_rules \
        + line_comment_rules \
        + identifier_rules + basic_rules

lean_course_grammar = Grammar(rules)

#############################################
# visiting methods for each pertinent nodes #
#############################################
class LeanCourseVisitor(NodeVisitor):
    def visit_course(self, node, visited_children) -> Tuple[List[str], dict]:
        course_history, data = get_info(visited_children)
        data.setdefault("metadata", {})
        metadata = data.pop("metadata")
        return course_history, metadata

    #############
    # statements #
    #############
    def visit_statement(self, node, visited_children):
        """
        - collect the metadata from children in data['metadata'],
        the lean_name and type of statement from data['exercise_name'] etc.
        - create an event in the  course_history list with
            name    = 'exercise', 'definition' or 'theorem'
            content = metadata dictionary
        """
        course_history, data = get_info(visited_children)
        data.setdefault("metadata", {})
        metadata = data.pop("metadata")
        if "exercise_name" in data.keys():
            event_name = "exercise"
            lean_name = data.pop("exercise_name")
        elif "definition_name" in data.keys():
            event_name = "definition"
            lean_name = data.pop("definition_name")
        elif "theorem_name" in data.keys():
            event_name = "theorem"
            lean_name = data.pop("theorem_name")
        else:
            log.warning(f"no name found for statement with data "
                        f"{data} and metadata {metadata}")
        metadata["lean_name"] = lean_name
        metadata["lean_statement"] = data.pop("lean_statement")
        # compute automatic PrettyName if not found by parser
        short_name = lean_name.split(".")[1]
        automatic_pretty_name = short_name.replace("_", " ").capitalize()
        metadata.setdefault("PrettyName", automatic_pretty_name)

        event = event_name, metadata
        course_history.insert(0, event)
        return course_history, data

    def visit_begin_proof(self, node, visited_children):
        """begin and end of proofs for exercises are collected and sotred in
        the course_history in order to get the line number where dEAduction
        should start the proof"""
        course_history, data = get_info(visited_children)
        event = "begin_proof", None
        course_history.insert(0, event)  # to get the good line number
        return course_history, data

    def visit_end_proof(self, node, visited_children):
        course_history, data = get_info(visited_children)
        event = "end_proof", None
        course_history.insert(0, event)
        return course_history, data

    ############
    # metadata #
    ############
    def visit_metadata(self, node, visited_children):
        # return the joined data of all children
        course_history, metadata = get_info(visited_children)
        data = {"metadata": metadata}
        log.debug(f"got metadata {data}")
        return course_history, data

    def visit_metadata_field(self, node, visited_children):
        # return the joined data of all children
        course_history, data = get_info(visited_children)
        # the following collect the metadata in the corresponding field
        # this is the only info from children,
        # so it is passed as data
        metadata = {}
        if "metadata_field_content" in data.keys():
            metadata[data["metadata_field_name"]] = \
                                                data["metadata_field_content"]
        return course_history, metadata

    def visit_metadata_field_name(self, node, visited_children):
        course_history, data = get_info(visited_children)
        data["metadata_field_name"] = node.text
        return course_history, data

    def visit_metadata_field_content(self, node, visited_children):
        course_history, data = get_info(visited_children)
        data.setdefault("metadata_field_content", "")
        data["metadata_field_content"] += " " + node.text.strip()
        # field content may spread on several lines
        return course_history, data


    ##############
    # namespaces #
    ##############
    def visit_open_namespace(self, node, visited_children):
        course_history, data = get_info(visited_children)
        name = data.pop("namespace_identifier")
        try:
            metadata = data.pop("metadata")
            pretty_name = metadata["PrettyName"]
        except KeyError:
            pretty_name = name.replace("_", " ").capitalize()
        event = "open_namespace", {"name": name, "pretty_name": pretty_name}
        course_history.insert(0, event)
        return course_history, data

    def visit_close_namespace(self, node, visited_children):
        course_history, data = get_info(visited_children)
        event = "close_namespace", None
        course_history.append(event)
        return course_history, data

    ###############
    # end of line #
    ###############
    def visit_end_of_line(self, node, visited_children):
        event = "end_of_line", None
        return [event], {}

    ###################
    # collecting data #
    ###################

    def visit_definition_name(self, node, visited_children):
        course_history, data = get_info(visited_children)
        data["definition_name"] = node.text
        return course_history, data

    def visit_theorem_name(self, node, visited_children):
        course_history, data = get_info(visited_children)
        data["theorem_name"] = node.text
        return course_history, data

    def visit_exercise_name(self, node, visited_children):
        course_history, data = get_info(visited_children)
        data["exercise_name"] = node.text
        return course_history, data

    def visit_lean_statement(self, node, visited_children):
        course_history, data = get_info(visited_children)
        data["lean_statement"] = node.text
        return course_history, data

    def visit_namespace_identifier(self, node, visited_children):
        course_history, data = get_info(visited_children)
        data["namespace_identifier"] = node.text
        return course_history, data

    #################
    # generic visit #
    #################
    def generic_visit(self, node, visited_children):
        # return the joined data of all children
        course_history, data = get_info(visited_children)
        return course_history, data


def get_info(children: List[dict]):
    course_history = []
    data = {}
    for child_history, child_data in children:
        course_history.extend(child_history)
        if child_data:
            data.update(child_data)
    return course_history, data


if __name__ == "__main__":
    logger.configure()
    course_file1 = Path('../../../../tests/lean_files/short_course/exercises'
                        '.lean')
    course_file2 = Path(
        '../../../../tests/lean_files/courses'
        '/exercises_theorie_des_ensembles.lean')
    file_content1 = course_file1.read_text()
    file_content2 = """
lemma exercise.image_reciproque_inter_quelconque  (H : ∀ i:I,  (E i = f ⁻¹' (F
i))) :  (f ⁻¹'  (set.Inter F)) = set.Inter E :=
/- dEAduction
Description

-/
begin
end

"""
    file_content3 = """
lemma exercise.union_distributive_inter : A ∩ (B ∪ C)  = (A ∩ B) ∪ (A ∩ C) := 
/- dEAduction
PrettyName
    Intersection d'une union
-/
begin
    sorry
end
"""
    file_content4 = """
lemma exercise.union toto := 

/- dEAduction
PrettyName
    Intersection d'une union
-/

begin
    sorry
end
"""
    file_content5 = """
lemma exercise.union_distributive_inter : A ∩ (B ∪ C)  = (A ∩ B) ∪ (A ∩ C) := 


begin
    
end
"""
    course_tree1 = lean_course_grammar.parse(file_content1)
#    course_tree2 = lean_course_grammar.parse(file_content2)
#    course_tree3 = lean_course_grammar.parse(file_content3)
    course_tree4 = lean_course_grammar.parse(file_content4)
#    course_tree5 = lean_course_grammar.parse(file_content5)
    #print(course_tree)
    visitor = LeanCourseVisitor()
    course_history, _ = visitor.visit(course_tree4)
    print(f"course history: {course_history}")
