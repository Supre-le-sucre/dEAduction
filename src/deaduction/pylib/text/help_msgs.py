"""
#######################################################
# help_msgs.py : set msgs for help on context objects #
#######################################################

Note that msgs are not translated here, to handle the case when usr changes
language. They must be translated when used.

Author(s)     : Frédéric Le Roux frederic.le-roux@imj-prg.fr
Maintainer(s) : Frédéric Le Roux frederic.le-roux@imj-prg.fr
Created       : 08 2022 (creation)
Repo          : https://github.com/dEAduction/dEAduction

Copyright (c) 2022 the d∃∀duction team

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

# import deaduction.pylib.config.vars as cvars
# from deaduction.pylib.math_display.utils import replace_dubious_characters


# We do not want translation at init but on the spot
# But we want poedit to mark those str for translation
def _(msg):
    return msg


use = dict()
prove = dict()

prop_types = {"forall": _("universal property"),
              "exists": _("existential property"),
              "implies": _("implication"),
              "and": _("conjunction"),
              "or": _("disjunction"),
              "not": _("negation"),
              "iff": _("logical equivalence"),
              "equal": _("equality"),
              "function": "function"}

phrase = {"to_use": _("To use this property"),
          "to_start_proof": _("To start a proof of this property")
          }

use["forall"] = (_("This is a universal property, which tells something about "
                 "every element of {type_}."),
                 _("To use this property, press the ∀ button after selecting "
                   "an element of {type_}."),
                 _("To use this property, you need some element of {type_}. Is "
                   "there any in the context? If not, can you create some?"))


prove["forall"] = (use["forall"][0],
                   _("To start a proof of this property, press the ∀ "
                     "button."),
                   # _("Pressing the ∀ button will introduce an element of {"
                   #   "type_} in the context, and simplify the target.<br>"
                   _(" It is generally a good idea to simplify the target as "
                     "much as possible by introducing all variables and "
                     "hypotheses in the context."))

use["implies"] = (_("This is an implication, which asserts that some property "
                    "P: {ch0}, the <em> premise </em>, implies some other "
                    "property Q: {ch1}, the <em> conclusion </em>."),
                  _("To use this property, press the ⇒ button after selecting "
                    "another property which match the premise."),
                  _("To use this property, you need property {ch0}. Do you "
                    "have it in the context?"))

prove["implies"] = (use["implies"][0],
                    _("To start a proof of this property, press the ⇒ button."),
                    _('It is generally a good idea to simplify the target as '
                      'much as possible by introducing all variables and '
                      'hypotheses in the context.') + " " +
                    _('Note that an implication may also be proved by '
                      'contraposition (see the "Proof methods" button).'))
# "Pressing the ⇒ button will introduce the premise in "
#                       "the context, and the target will become the "
#                       "conclusion.<br>"

use["exists"] = (_("This is an existential property, which asserts the "
                   "existence of an element of {type_} satisfying a precise "
                   "property."),
                 _("To use this property, just press the ∃ button."),
                 "")

prove["exists"] = (_("This is an existential property, which asserts the "
                     "existence of an element of {type_} satisfying a precise "
                     "property."),
                _("To start a proof of this property, press the ∃ button after "
                  "selecting"
                  "the element of {type_} that satisfies the wanted property."),
                _("Is there some element of {type_} in the context? If this is "
                  "so, does it suits your needs? If not, how can you create "
                  "some?"))

use["or"] = (_("This property is a disjunction."),
             _("Press the ∨ (OR) button to engage in a proof by cases; you "
               "will successively examine the case when {ch0} holds and the "
               "case when {ch1} holds."),
             _("Would it help you to know which one of the two properties hold?"
               "If so, then you could consider engaging in a proof by cases."))


prove["or"] = (use["or"][0],
               _("Press the ∨ (OR) button to simplify the goal by deciding "
                 "which one of the two properties you will prove. You may "
                 "forget about the other one!"),
               _("Do you have enough information in the context to prove one "
                 "of these two properties? <br> --> If this is so, then choose "
                 "this "
                 "property with the ∨ (OR) button. <br> --> If not, you should "
                 "first get more information "
                 "(maybe by engaging in a proof by cases)."))

use["and"] = (_("This property is a conjunction."),
              _("Press the ∧ (AND) button to separate both properties."),
              "")


prove["and"] = (use["and"][0],
                _("Press the ∧ (AND) button to prove separately and "
                  "successively each property."),
                _("Note that you will have to prove <em> both </em> "
                  "properties, as opposed to disjunction for which you may "
                  "choose which property you prove."))

use["not"] = (_("This property is a negation."),
              _("Press the ¬ (NOT) button to try to simplify the property."),
              "")

prove["not"] = use["not"]

use[_("iff")] = (_("This property is a logical equivalence."),
                 'You can use the ⇔ ("IF AND ONLY IF") button <ul>'
                 '<li>to split it into two implications,</li>'
                 '<li>or to substitute {ch0} for {ch1}, or vice-versa, '
                 'in the target or in some other property of the context.</li>'
                 '</ul>',
                 "")

prove[_("iff")] = (_("This property is a logical equivalence."),
                   _('Press the ⇔ ("IF AND ONLY IF") button, to split the '
                     'proof into the proofs of the direct and reverse '
                     'implications. You may also use the ∧ (AND) button.'),
                   "")

use['equal'] = (_("This is an equality between two elements of {"
                  "ch0_type}."),
                _('You may use this equality to substitute {ch0} for '
                  '{ch1}, or vice-versa, in the target or in some other '
                  'property of the context. To do this, press the "=" (EQUAL) '
                  'button after selecting the other property.'),
                "")

prove['equal'] = (use['equal'][0], "", "")

use["function"] = (_("This is a function from {ch0} to {ch1}."),
                   _("You may apply this function to some element of {ch0}, "
                     "or to an equality between two elements of {ch0}. For "
                     "this, press the ↦ (MAP) button after selecting an element"
                     " or an equality."),
                   "")

use["definition"] = (_('This matches the definition {def_name}.'),
                     _("You may unroll a definition by clicking on it in "
                       "the Statements area."),
                     "")

prove["definition"] = use["definition"]

use["definitions"] = (_('This matches definitions {def_names}.'),
                      _("You may unroll a definition by clicking on it in "
                        "the Statements area."),
                      "")

prove["definitions"] = use["definitions"]

use["unroll_implicit_def"] = _("To see this property explicitly as a {"
                               "prop_type}, you may unfold definition {"
                               "def_name} by clicking on it in the Statement "
                               "area.")

# TODO:
#  - bounded quantification
#  - Defs implicites qui sont des forall : suggérer aussi d'aller voir la déf
#  - formule atomique à montrer (appartenance, inégalité, négation d'un truc
#    élémentaire, etc)
#  - elements (comment les utiliser ?)
#  - This can also be used for substitution with the = / <=> button
#    (or for implication with the => button).
#  Et surtout, erreurs --> bouton aide

#
# use = (_(""),
#        _(""),
#        _(""))
#
#
# use = (_(""),
#        _(""),
#        _(""))
#
#
# use = (_(""),
#        _(""),
#        _(""))
#
#
# use = (_(""),
#        _(""),
#        _(""))
#
#
# use = (_(""),
#        _(""),
#        _(""))
#
#
# use = (_(""),
#        _(""),
#        _(""))
#
#
# use = (_(""),
#        _(""),
#        _(""))


